"""Candidate-facing vertical slice: register -> start assessment -> submit -> Evidence Profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, ProviderDep, SessionDep
from fsp_market.assessments import tech_exams
from fsp_market.assessments.breakdown import competency_breakdown
from fsp_market.assessments.models import (
    AssessmentAttempt,
    TaskFamily,
    TaskTemplate,
)
from fsp_market.assessments.service import (
    AssessmentError,
    CooldownError,
    DeadlinePassed,
    attempt_variants,
    ensure_deadline,
    finalize_expired,
    is_expired,
    remaining_seconds,
    save_draft,
    score_attempt,
    start_attempt,
    submit_answers,
    utcnow,
)
from fsp_market.auth.credentials import hash_password
from fsp_market.auth.email_verification import confirm, cooldown_left, issue_verification
from fsp_market.auth.tokens import create_token
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import AttemptStatus, Grade
from fsp_market.config import get_settings
from fsp_market.evidence.fsp_link import FSPVerificationError, attach_fsp_evidence
from fsp_market.evidence.profile import build_evidence_profile
from fsp_market.fsp.provider import FSPProvider
from fsp_market.skills.models import Skill
from fsp_market.taxonomy.grades import GRADE_SUBLEVELS, sublevel_label_ru
from fsp_market.taxonomy.models import Competency, Specialization

router = APIRouter(prefix="/api", tags=["candidate"])


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    specialization: str = "backend_python"
    claimed_grade: Grade
    password: str | None = Field(default=None, min_length=8, max_length=200)  # enables password sign-in


class StartIn(BaseModel):
    exam: str | None = None  # None = Core Assessment; "fastapi" | "postgresql" = independent exam
    target_grade: Grade


class SubmitIn(BaseModel):
    answers: dict[int, Any]  # variant_id -> option key | list of keys | number


class FSPLinkIn(BaseModel):
    fsp_id: str = Field(min_length=1, max_length=64)


def _tasks(session: Session, attempt: AssessmentAttempt) -> list[dict[str, Any]]:
    out = []
    for variant in attempt_variants(session, attempt):
        competency = session.scalar(
            select(Competency.code)
            .join(TaskFamily, TaskFamily.competency_id == Competency.id)
            .join(TaskTemplate, TaskTemplate.family_id == TaskFamily.id)
            .where(TaskTemplate.id == variant.template_id)
        )
        if attempt.exam_code in tech_exams.EXAMS:
            competency = tech_exams.EXAMS[attempt.exam_code]["skill"]
        out.append(  # never expose the scoring contract / correct answer
            {
                "variant_id": variant.id,
                "competency": competency,
                "prompt": variant.prompt,
                "answer_type": variant.input_data.get("answer_type", "single"),
                "options": variant.input_data.get("options"),
            }
        )
    return out


def _attempt_payload(session: Session, attempt: AssessmentAttempt) -> dict[str, Any]:
    now = utcnow()
    return {
        "attempt_id": attempt.id,
        "target_grade": attempt.target_grade,
        "status": attempt.status,
        "exam": attempt.exam_code,
        "tasks": _tasks(session, attempt),
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "deadline_at": attempt.deadline_at.isoformat() if attempt.deadline_at else None,
        "time_limit_seconds": attempt.time_limit_seconds,
        "server_time": now.isoformat(),
        "remaining_seconds": remaining_seconds(attempt, now),
        "saved_answers": {k: v["answer"] for k, v in (attempt.draft_answers or {}).items()},
    }


def _result_payload(session: Session, candidate_id: int, attempt, result, expired=False):
    return {
        "attempt_id": attempt.id,
        "target_grade": result.target_grade,
        "verification_status": result.verification_status,
        "passed": result.passed,
        "score": result.total_score,
        "competency_scores": result.subscores,
        "achieved_sublevel": result.achieved_sublevel,
        "exam": attempt.exam_code,
        "competency_breakdown": [] if attempt.exam_code else competency_breakdown(session, result),
        "claimed_grade": session.get(Candidate, candidate_id).claimed_grade,
        "expired": expired or attempt.expired,
    }


def _check_answer(variant, value) -> None:
    kind = variant.input_data.get("answer_type", "single")
    opts = variant.input_data.get("options") or {}
    if kind == "single" and value not in opts:
        raise HTTPException(status_code=422, detail=f"invalid option for task {variant.id}")
    if kind == "multi" and not (
        isinstance(value, list) and value and all(v in opts for v in value)
    ):
        raise HTTPException(status_code=422, detail=f"invalid options for task {variant.id}")
    if kind == "number":
        try:
            float(str(value).replace(",", "."))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"number expected for task {variant.id}") from exc


def _own_attempt(session: Session, attempt_id: int, candidate_id: int) -> AssessmentAttempt:
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="assessment not found")
    return attempt


@router.post("/candidates", status_code=201)
def register(body: RegisterIn, session: Session = SessionDep) -> dict[str, Any]:
    spec = session.scalar(select(Specialization).where(Specialization.code == body.specialization))
    if spec is None:
        raise HTTPException(status_code=422, detail="unknown specialization")
    candidate = Candidate(
        email=body.email,
        full_name=body.full_name,
        specialization_id=spec.id,
        claimed_grade=body.claimed_grade,
        profile_visible=True,  # intent; effective only after the email is verified
        password_hash=hash_password(body.password) if body.password else None,
    )
    session.add(candidate)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="email already registered") from exc
    sent, link = issue_verification(session, candidate)
    session.commit()
    token = create_token(candidate.id, get_settings().jwt_secret)
    out: dict[str, Any] = {"candidate_id": candidate.id, "access_token": token, "email_verification_sent": sent}
    if not sent and get_settings().demo_mode:  # demo only: no SMTP, so the link is shown in the UI
        out["demo_verification_link"] = link
    return out


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/auth/verify-email")
def verify_email(body: VerifyEmailIn, session: Session = SessionDep) -> dict[str, Any]:
    cand = confirm(session, body.token)
    if cand is None:
        session.rollback()
        raise HTTPException(status_code=400, detail="invalid or expired token")
    session.commit()
    return {"email_verified": True}


@router.post("/candidates/me/email/resend")
def resend_verification(
    candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    cand = session.get(Candidate, candidate_id)
    if cand.email_verified:
        return {"email_verified": True, "sent": False}
    wait = cooldown_left(cand)
    if wait:
        raise HTTPException(status_code=429, detail=f"retry in {wait}s")
    sent, link = issue_verification(session, cand)
    session.commit()
    out: dict[str, Any] = {"email_verified": False, "sent": sent}
    if not sent and get_settings().demo_mode:
        out["demo_verification_link"] = link
    return out


def _expire_if_needed(session: Session, attempt: AssessmentAttempt) -> bool:
    now = utcnow()
    ensure_deadline(attempt, now)
    if is_expired(attempt, now):
        finalize_expired(session, attempt, now)
        session.commit()
        return True
    return False


@router.post("/assessments", status_code=201)
def start_assessment(
    body: StartIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    if body.exam is not None and body.exam not in tech_exams.EXAMS:
        raise HTTPException(status_code=422, detail="unknown exam")
    cand = session.get(Candidate, candidate_id)
    if cand.specialization_id is not None and session.scalar(
        select(Competency.id).where(Competency.specialization_id == cand.specialization_id).limit(1)
    ) is None:
        raise HTTPException(status_code=409, detail="assessment for this specialization is not available yet")
    attempt = session.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.candidate_id == candidate_id,
            AssessmentAttempt.target_grade == body.target_grade,
            AssessmentAttempt.exam_code.is_(None) if body.exam is None else AssessmentAttempt.exam_code == body.exam,
            AssessmentAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )
    if attempt is not None and _expire_if_needed(session, attempt):
        attempt = None
    try:
        if attempt is None:
            attempt = start_attempt(session, candidate_id, body.target_grade, exam=body.exam)
    except CooldownError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AssessmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return _attempt_payload(session, attempt)


@router.get("/assessments/{attempt_id}")
def get_assessment(
    attempt_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    attempt = _own_attempt(session, attempt_id, candidate_id)
    _expire_if_needed(session, attempt)
    session.commit()
    return _attempt_payload(session, attempt)


@router.put("/assessments/{attempt_id}/answers")
def autosave(
    attempt_id: int, body: SubmitIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    attempt = _own_attempt(session, attempt_id, candidate_id)
    variants = {v.id: v for v in attempt_variants(session, attempt)}
    for vid, value in body.answers.items():
        if vid in variants:
            _check_answer(variants[vid], value)
    try:
        save_draft(session, attempt, dict(body.answers))
    except DeadlinePassed as exc:
        session.commit()
        raise HTTPException(status_code=409, detail="deadline_passed") from exc
    except AssessmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"saved": len(body.answers), "remaining_seconds": remaining_seconds(attempt)}


@router.post("/assessments/{attempt_id}/submit")
def submit(
    attempt_id: int, body: SubmitIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    attempt = _own_attempt(session, attempt_id, candidate_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="assessment already submitted")
    now = utcnow()
    if is_expired(attempt, now):  # late answers are ignored; saved ones are scored
        result = finalize_expired(session, attempt, now)
        session.commit()
        return _result_payload(session, candidate_id, attempt, result, expired=True)
    variants = {v.id: v for v in attempt_variants(session, attempt)}
    if set(body.answers) != set(variants):
        raise HTTPException(status_code=422, detail="answers must cover exactly the assigned tasks")
    for vid, value in body.answers.items():
        _check_answer(variants[vid], value)
    submit_answers(session, attempt.id, dict(body.answers))
    result = score_attempt(session, attempt.id)
    session.commit()
    return _result_payload(session, candidate_id, attempt, result)


@router.get("/candidates/me/profile")
def my_profile(candidate_id: int = CandidateDep, session: Session = SessionDep) -> dict[str, Any]:
    return build_evidence_profile(session, candidate_id)


@router.post("/candidates/me/fsp")
def link_fsp(
    body: FSPLinkIn,
    candidate_id: int = CandidateDep,
    session: Session = SessionDep,
    provider: FSPProvider = ProviderDep,
) -> dict[str, Any]:
    try:
        created = attach_fsp_evidence(session, candidate_id, provider, body.fsp_id)
    except FSPVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    # idempotent relink adds nothing new, but the history is still there
    has_history = created > 0 or bool(provider.get_achievements(body.fsp_id))
    return {"evidence_added": created, "has_history": has_history}


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    specialization: str | None = None
    claimed_grade: Grade | None = None


def _candidate_me(session: Session, cand: Candidate) -> dict[str, Any]:
    spec = session.get(Specialization, cand.specialization_id) if cand.specialization_id else None
    return {
        "id": cand.id,
        "full_name": cand.full_name,
        "email": cand.email,  # own data: the candidate may see it
        "email_verified": cand.email_verified,
        "phone": cand.phone,
        "specialization": spec.code if spec else None,
        "claimed_grade": cand.claimed_grade,
        "verification_status": cand.verification_status,
        "verified_grade": cand.verified_grade,
        "verified_sublevel": cand.verified_sublevel,
        "preferences": {
            "salary_min": cand.salary_min,
            "salary_type": cand.salary_type,
            "work_formats": cand.work_formats or [],
            "location": cand.location,
            "available_in_days": cand.available_in_days,
            "profile_visible": cand.profile_visible,
            "published": bool(cand.profile_visible and cand.email_verified),
            "publish_blockers": [
                b for b, bad in (
                    ("email_not_verified", not cand.email_verified),
                    ("profile_hidden", not cand.profile_visible),
                    ("not_open_to_invitations", not cand.open_to_invitations),
                    ("no_specialization", cand.specialization_id is None),
                ) if bad
            ],
            "open_to_invitations": cand.open_to_invitations,
        },
    }


@router.get("/candidates/me")
def me(candidate_id: int = CandidateDep, session: Session = SessionDep) -> dict[str, Any]:
    return _candidate_me(session, session.get(Candidate, candidate_id))


@router.patch("/candidates/me/profile")
def update_profile(
    body: ProfileIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    cand = session.get(Candidate, candidate_id)
    data = body.model_dump(exclude_unset=True)
    if "specialization" in data:
        spec = session.scalar(
            select(Specialization).where(Specialization.code == data["specialization"])
        )
        if spec is None:
            raise HTTPException(status_code=422, detail="unknown specialization")
        cand.specialization_id = spec.id
    if data.get("full_name"):
        cand.full_name = data["full_name"]
    if data.get(
        "claimed_grade"
    ):  # the candidate chooses the grade they claim; assessment verifies it
        cand.claimed_grade = data["claimed_grade"]
    session.commit()
    return _candidate_me(session, cand)


@router.get("/catalog")
def catalog(session: Session = SessionDep) -> dict[str, Any]:
    """Public reference data for forms: specialisations, grades with sublevels, skills."""
    # a specialisation can be assessed only when it has competencies (and therefore task templates)
    assessable = set(session.scalars(select(Competency.specialization_id).distinct()))
    return {
        "specializations": [
            {"code": s.code, "name": s.name, "assessment_available": s.id in assessable}
            for s in session.scalars(select(Specialization).order_by(Specialization.id))
        ],
        "grades": {g.value: [s.value for s in subs] for g, subs in GRADE_SUBLEVELS.items()},
        "sublevel_labels": {
            s.value: sublevel_label_ru(s) for subs in GRADE_SUBLEVELS.values() for s in subs
        },
        "skills": [
            {"code": s.code, "name": s.name, "verifiable": s.competency_id is not None}
            for s in session.scalars(select(Skill).order_by(Skill.code))
        ],
    }


@router.get("/exams")
def exam_catalog(
    candidate_id: int = CandidateDep, session: Session = SessionDep
) -> list[dict[str, Any]]:
    """Independent technology exams: each confirms ONE skill and never changes the overall grade."""
    out = []
    for code, info in tech_exams.EXAMS.items():
        tasks = {
            str(grade): session.scalar(
                select(func.count(TaskFamily.id)).where(
                    TaskFamily.is_active.is_(True),
                    TaskFamily.target_grade == grade,
                    TaskFamily.code.like(tech_exams.family_prefix(code) + "%"),
                )
            )
            for grade in Grade
        }
        out.append(
            {
                "exam": code,
                "skill": info["skill"],
                "name": info["name"],
                "tasks": tasks,
                "time_limit_seconds": tech_exams.TIME_LIMIT_SECONDS,
            }
        )
    return out
