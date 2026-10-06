"""Employer-side API: needs, Requirement Match runs, Full Pool, candidate detail.

Employers never receive candidate contacts (email/phone/full name); see
matching.service.public_candidate. Contact unlock belongs to a later phase.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, EmployerDep, SessionDep
from fsp_market.auth.tokens import create_token
from fsp_market.common.enums import Grade, SalaryType, Sublevel, WorkFormat
from fsp_market.config import get_settings
from fsp_market.employers.models import Employer
from fsp_market.invitations import service as invitation_service
from fsp_market.matching import service
from fsp_market.matching.models import EmployerNeed, MatchRun

router = APIRouter(prefix="/api", tags=["employer"])


class EmployerRegisterIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=3, max_length=255)


class NeedIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    specialization: str = "backend_python"
    target_grade: Grade
    target_sublevel: Sublevel | None = None
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    salary_from: int = Field(gt=0)
    salary_to: int = Field(gt=0)
    salary_type: SalaryType
    work_formats: list[WorkFormat] = Field(min_length=1)
    location: str | None = None
    max_start_days: int | None = Field(default=None, ge=0)
    description: str = ""


class PreferencesIn(BaseModel):
    salary_min: int | None = Field(default=None, gt=0)
    salary_type: SalaryType | None = None
    work_formats: list[WorkFormat] | None = None
    location: str | None = None
    available_in_days: int | None = Field(default=None, ge=0)
    profile_visible: bool | None = None
    open_to_invitations: bool | None = None
    phone: str | None = Field(default=None, max_length=32)


def _own_need(session: Session, need_id: int, employer_id: int) -> EmployerNeed:
    need = session.get(EmployerNeed, need_id)
    if need is None or need.employer_id != employer_id:
        raise HTTPException(status_code=404, detail="need not found")
    return need


@router.post("/employers", status_code=201)
def register_employer(body: EmployerRegisterIn, session: Session = SessionDep) -> dict[str, Any]:
    employer = Employer(company_name=body.company_name, contact_email=body.contact_email)
    session.add(employer)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="email already registered") from exc
    token = create_token(employer.id, get_settings().jwt_secret, role="employer")
    return {"employer_id": employer.id, "access_token": token}


@router.get("/employers/me")
def employer_me(employer_id: int = EmployerDep, session: Session = SessionDep) -> dict[str, Any]:
    employer = session.get(Employer, employer_id)
    return {"id": employer.id, "company_name": employer.company_name}


@router.patch("/candidates/me/preferences")
def update_preferences(
    body: PreferencesIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    from fsp_market.candidates.models import Candidate

    cand = session.get(Candidate, candidate_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(
            cand, field, [str(v) for v in value] if field == "work_formats" and value else value
        )
    session.commit()
    return {"updated": sorted(body.model_dump(exclude_unset=True))}


@router.post("/employer/needs", status_code=201)
def create_need(
    body: NeedIn, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    try:
        need = service.create_need(
            session,
            employer_id,
            title=body.title,
            specialization=body.specialization,
            target_grade=body.target_grade,
            target_sublevel=body.target_sublevel,
            required_skills=body.required_skills,
            optional_skills=body.optional_skills,
            salary_from=body.salary_from,
            salary_to=body.salary_to,
            salary_type=body.salary_type,
            work_formats=[str(w) for w in body.work_formats],
            location=body.location,
            max_start_days=body.max_start_days,
            description=body.description,
        )
    except service.NeedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return service.need_to_dict(session, need)


@router.get("/employer/needs")
def list_needs(
    employer_id: int = EmployerDep, session: Session = SessionDep
) -> list[dict[str, Any]]:
    needs = session.scalars(
        select(EmployerNeed)
        .where(EmployerNeed.employer_id == employer_id)
        .order_by(EmployerNeed.id)
    )
    return [service.need_to_dict(session, n) for n in needs]


@router.get("/employer/needs/{need_id}")
def get_need(need_id: int, employer_id: int = EmployerDep, session: Session = SessionDep):
    return service.need_to_dict(session, _own_need(session, need_id, employer_id))


@router.post("/employer/needs/{need_id}/match", status_code=201)
def run_match(
    need_id: int,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    employer_id: int = EmployerDep,
    session: Session = SessionDep,
) -> dict[str, Any]:
    need = _own_need(session, need_id, employer_id)
    run = service.run_match(session, need)
    session.commit()
    return service.run_results(session, run, limit=limit)


@router.get("/employer/match-runs/{run_id}")
def get_match_run(
    run_id: int,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    min_fit: Annotated[float | None, Query(ge=0, le=1)] = None,
    verified_only: bool = False,
    skill: str | None = None,
    employer_id: int = EmployerDep,
    session: Session = SessionDep,
) -> dict[str, Any]:
    run = session.get(MatchRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="match run not found")
    _own_need(session, run.need_id, employer_id)
    return service.run_results(
        session,
        run,
        limit=limit,
        offset=offset,
        min_fit=min_fit,
        verified_only=verified_only,
        skill=skill,
    )


@router.get("/employer/pool")
def pool(
    specialization: str | None = None,
    grade: Grade | None = None,
    sublevel: Sublevel | None = None,
    verification: str | None = None,
    skill: Annotated[list[str] | None, Query()] = None,
    has_fsp: bool | None = None,
    work_format: WorkFormat | None = None,
    location: str | None = None,
    salary_max: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    employer_id: int = EmployerDep,
    session: Session = SessionDep,
) -> dict[str, Any]:
    return service.full_pool(
        session,
        specialization=specialization,
        grade=grade,
        sublevel=sublevel,
        verification=verification,
        skills=skill,
        has_fsp=has_fsp,
        work_format=work_format,
        location=location,
        salary_max=salary_max,
        limit=limit,
        offset=offset,
    )


@router.get("/employer/candidates/{candidate_id}")
def candidate_detail(
    candidate_id: int,
    need_id: int | None = None,
    employer_id: int = EmployerDep,
    session: Session = SessionDep,
) -> dict[str, Any]:
    need = _own_need(session, need_id, employer_id) if need_id is not None else None
    detail = service.candidate_detail(session, candidate_id, need)
    if detail is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    contacts = invitation_service.unlocked_contacts(session, employer_id, candidate_id)
    detail["contact_status"] = "UNLOCKED" if contacts else "LOCKED"
    if contacts:  # only after the candidate accepted this employer's invitation
        detail["contacts"] = contacts
    return detail
