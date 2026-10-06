"""Invitation API. Contact data leaves the server only via invitations.service.contacts_for."""

from __future__ import annotations

from typing import Any, Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, EmployerDep, SessionDep
from fsp_market.common.enums import SalaryType, WorkFormat
from fsp_market.invitations import service
from fsp_market.invitations.models import Invitation

router = APIRouter(prefix="/api", tags=["invitations"])


class InvitationIn(BaseModel):
    candidate_id: int
    need_id: int | None = None
    match_run_id: int | None = None
    company: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1)
    salary_from: int = Field(gt=0)
    salary_to: int = Field(gt=0)
    salary_type: SalaryType  # GROSS / NET must be stated explicitly
    work_format: WorkFormat
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.salary_to < self.salary_from:
            raise ValueError("salary_to must be >= salary_from")
        return self


def _employer_invitation(session: Session, inv_id: int, employer_id: int) -> Invitation:
    inv = session.get(Invitation, inv_id)
    if inv is None or inv.employer_id != employer_id:
        raise HTTPException(status_code=404, detail="invitation not found")
    return inv


def _candidate_invitation(session: Session, inv_id: int, candidate_id: int) -> Invitation:
    inv = session.get(Invitation, inv_id)
    if inv is None or inv.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="invitation not found")
    return inv


@router.post("/employer/invitations", status_code=201)
def send(
    body: InvitationIn, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    try:
        inv = service.send_invitation(session, employer_id, **body.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.InvitationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return service.employer_view(session, inv)


@router.get("/employer/invitations")
def employer_list(
    employer_id: int = EmployerDep, session: Session = SessionDep
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Invitation).where(Invitation.employer_id == employer_id).order_by(Invitation.id)
    )
    return [service.employer_view(session, i) for i in rows]


@router.get("/employer/invitations/{inv_id}")
def employer_get(
    inv_id: int, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    return service.employer_view(session, _employer_invitation(session, inv_id, employer_id))


@router.get("/candidates/me/invitations")
def candidate_list(
    candidate_id: int = CandidateDep, session: Session = SessionDep
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Invitation).where(Invitation.candidate_id == candidate_id).order_by(Invitation.id)
    )
    return [service.candidate_view(i) for i in rows]


@router.get("/candidates/me/invitations/{inv_id}")
def candidate_open(
    inv_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    """Opening an invitation marks it VIEWED (SENT -> VIEWED) and shows the full terms."""
    inv = _candidate_invitation(session, inv_id, candidate_id)
    service.mark_viewed(inv)
    session.commit()
    return service.candidate_view(inv)


def _respond(action, inv_id: int, candidate_id: int, session: Session) -> dict[str, Any]:
    inv = _candidate_invitation(session, inv_id, candidate_id)
    try:
        action(inv)
    except service.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return service.candidate_view(inv)


@router.post("/candidates/me/invitations/{inv_id}/accept")
def accept(
    inv_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    return _respond(service.accept, inv_id, candidate_id, session)


@router.post("/candidates/me/invitations/{inv_id}/decline")
def decline(
    inv_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    return _respond(service.decline, inv_id, candidate_id, session)
