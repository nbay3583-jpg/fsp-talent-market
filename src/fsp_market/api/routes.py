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
    select_variants,
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
    answers: dict[int, str]  # variant_id -> chosen option key


class FSPLinkIn(BaseModel):
    fsp_id: str = Field(min_length=1, max_length=64)


def _tasks(session: Session, attempt: AssessmentAttempt) -> list[dict[str, Any]]:
    out = []
    for variant in select_variants(session, attempt.target_grade, attempt.id):
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
                "options": variant.input_data["options"],
            }
        )
    return out


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
    try:
        if attempt is None:
            attempt = start_attempt(session, candidate_id, body.target_grade)
    except CooldownError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AssessmentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return {
        "attempt_id": attempt.id,
        "target_grade": attempt.target_grade,
        "tasks": _tasks(session, attempt),
    }


@router.get("/assessments/{attempt_id}")
def get_assessment(
    attempt_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    attempt = _own_attempt(session, attempt_id, candidate_id)
    return {
        "attempt_id": attempt.id,
        "target_grade": attempt.target_grade,
        "status": attempt.status,
        "tasks": _tasks(session, attempt),
    }


@router.post("/assessments/{attempt_id}/submit")
def submit(
    attempt_id: int, body: SubmitIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    attempt = _own_attempt(session, attempt_id, candidate_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="assessment already submitted")
    variants = {v.id: v for v in select_variants(session, attempt.target_grade, attempt.id)}
    if set(body.answers) != set(variants):
        raise HTTPException(status_code=422, detail="answers must cover exactly the assigned tasks")
    for variant_id, choice in body.answers.items():
        if choice not in variants[variant_id].input_data["options"]:
            raise HTTPException(status_code=422, detail=f"invalid option for task {variant_id}")
    submit_answers(session, attempt.id, dict(body.answers))
    result = score_attempt(session, attempt.id)
    session.commit()
    return {
        "attempt_id": attempt.id,
        "target_grade": result.target_grade,
        "verification_status": result.verification_status,
        "passed": result.passed,
        "score": result.total_score,
        "competency_scores": result.subscores,
        "achieved_sublevel": result.achieved_sublevel,
        "claimed_grade": session.get(Candidate, candidate_id).claimed_grade,
    }


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
        "grades": {"JUNIOR": ["J1", "J2"], "MIDDLE": ["M1", "M2"], "SENIOR": ["S1", "S2"]},
        "skills": [
            {"code": s.code, "name": s.name, "verifiable": s.competency_id is not None}
            for s in session.scalars(select(Skill).order_by(Skill.code))
        ],
    }
