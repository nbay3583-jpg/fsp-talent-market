"""Candidate-facing vertical slice: register -> start assessment -> submit -> Evidence Profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, ProviderDep, SessionDep
from fsp_market.assessments.models import (
    AssessmentAttempt,
    TaskFamily,
    TaskTemplate,
)
from fsp_market.assessments.service import (
    AssessmentError,
    CooldownError,
    score_attempt,
    attempt_variants,
    DeadlinePassed,
    ensure_deadline,
    finalize_expired,
    is_expired,
    remaining_seconds,
    save_draft,
    utcnow,
    start_attempt,
    submit_answers,
)
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


class StartIn(BaseModel):
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
    )
    session.add(candidate)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="email already registered") from exc
    token = create_token(candidate.id, get_settings().jwt_secret)
    return {"candidate_id": candidate.id, "access_token": token}


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
    attempt = session.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.candidate_id == candidate_id,
            AssessmentAttempt.target_grade == body.target_grade,
            AssessmentAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )
    if attempt is not None and _expire_if_needed(session, attempt):
        attempt = None
    try:
        if attempt is None:
            attempt = start_attempt(session, candidate_id, body.target_grade)
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
    return {"evidence_added": created, "has_history": created > 0}


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
    return {
        "specializations": [
            {"code": s.code, "name": s.name}
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
