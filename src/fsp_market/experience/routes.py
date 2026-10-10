"""Work-experience CRUD for the signed-in candidate (declared data, not verification)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, SessionDep
from fsp_market.experience.models import WorkExperience
from fsp_market.skills.models import Skill

router = APIRouter(prefix="/api/candidates/me/experience", tags=["experience"])


class ExperienceIn(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    position: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date | None = None
    stack: list[str] = Field(default_factory=list, max_length=30)
    tasks: str = Field(default="", max_length=4000)
    projects: str = Field(default="", max_length=4000)
    achievements: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def _dates(self) -> ExperienceIn:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class ExperiencePatch(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    position: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    stack: list[str] | None = Field(default=None, max_length=30)
    tasks: str | None = Field(default=None, max_length=4000)
    projects: str | None = Field(default=None, max_length=4000)
    achievements: str | None = Field(default=None, max_length=4000)


def view(e: WorkExperience) -> dict[str, Any]:
    return {
        "id": e.id,
        "company": e.company,
        "position": e.position,
        "start_date": e.start_date.isoformat(),
        "end_date": e.end_date.isoformat() if e.end_date else None,
        "stack": list(e.stack or []),
        "tasks": e.tasks,
        "projects": e.projects,
        "achievements": e.achievements,
        "confirmed": False,  # declared by the candidate; never verified by the platform
    }


def _check_stack(session: Session, stack: list[str]) -> list[str]:
    known = set(session.scalars(select(Skill.code).where(Skill.code.in_(stack or ["-"]))))
    unknown = sorted(set(stack) - known)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown skills: {', '.join(unknown)}")
    return list(dict.fromkeys(stack))


def _own(session: Session, exp_id: int, candidate_id: int) -> WorkExperience:
    row = session.get(WorkExperience, exp_id)
    if row is None or row.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="experience not found")
    return row


@router.get("")
def list_experience(candidate_id: int = CandidateDep, session: Session = SessionDep):
    rows = session.scalars(
        select(WorkExperience)
        .where(WorkExperience.candidate_id == candidate_id)
        .order_by(WorkExperience.start_date.desc(), WorkExperience.id.desc())
    )
    return {"items": [view(r) for r in rows]}


@router.post("", status_code=201)
def create_experience(
    body: ExperienceIn, candidate_id: int = CandidateDep, session: Session = SessionDep
):
    data = body.model_dump()
    data["stack"] = _check_stack(session, data["stack"])
    row = WorkExperience(candidate_id=candidate_id, **data)
    session.add(row)
    session.commit()
    return view(row)


@router.patch("/{exp_id}")
def update_experience(
    exp_id: int,
    body: ExperiencePatch,
    candidate_id: int = CandidateDep,
    session: Session = SessionDep,
):
    row = _own(session, exp_id, candidate_id)
    data = body.model_dump(exclude_unset=True)
    if "stack" in data and data["stack"] is not None:
        data["stack"] = _check_stack(session, data["stack"])
    for key, value in data.items():
        if value is None and key != "end_date":
            continue
        setattr(row, key, value)
    if row.end_date and row.end_date < row.start_date:
        session.rollback()
        raise HTTPException(status_code=422, detail="end_date must not precede start_date")
    session.commit()
    return view(row)


@router.delete("/{exp_id}", status_code=204)
def delete_experience(
    exp_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> None:
    session.delete(_own(session, exp_id, candidate_id))
    session.commit()
