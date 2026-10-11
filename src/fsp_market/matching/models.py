from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import Grade, SalaryType, SkillImportance, Sublevel
from fsp_market.common.ids import utcnow
from fsp_market.db import Base


class EmployerNeed(Base):
    __tablename__ = "employer_needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(Integer, ForeignKey("employers.id"))
    title: Mapped[str] = mapped_column(String(255))
    specialization_id: Mapped[int] = mapped_column(Integer, ForeignKey("specializations.id"))
    target_grade: Mapped[Grade] = mapped_column(String(32))
    target_sublevel: Mapped[Sublevel | None] = mapped_column(String(8), nullable=True)
    # Pre-0005 two-sublevel target, kept for review after the move to three sublevels.
    legacy_target_sublevel: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    salary_type: Mapped[SalaryType] = mapped_column(String(8))
    work_formats: Mapped[list] = mapped_column(JSON)  # acceptable WorkFormat values
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    max_start_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # OPEN needs take part in matching and new invitations; CLOSED keeps history intact.
    status: Mapped[str] = mapped_column(String(8), default="OPEN", server_default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Candidates see a need in their recommendations only when the employer published it.
    public_to_candidates: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false()
    )
    # Team profile inputs: the manager's work-style answers and the hash of the anonymous survey link.
    work_style: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    team_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NeedSkill(Base):
    __tablename__ = "need_skills"
    __table_args__ = (UniqueConstraint("need_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(Integer, ForeignKey("employer_needs.id"))
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"))
    importance: Mapped[SkillImportance] = mapped_column(String(16))
    weight: Mapped[float] = mapped_column(Float)  # snapshot of the policy weight used


class MatchRun(Base):
    """One immutable matching run; refinement filters read it, never rewrite it."""

    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(Integer, ForeignKey("employer_needs.id"))
    policy: Mapped[Any] = mapped_column(JSON)  # snapshot of weights/tolerances used
    candidates_considered: Mapped[int] = mapped_column(Integer)
    excluded_summary: Mapped[Any] = mapped_column(JSON)  # exclusion code -> count
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (UniqueConstraint("run_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("match_runs.id"))
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"))
    rank: Mapped[int] = mapped_column(Integer)
    requirement_fit: Mapped[float] = mapped_column(Float)  # fit to THIS need only
    components: Mapped[Any] = mapped_column(JSON)
    why: Mapped[Any] = mapped_column(JSON)
    gaps: Mapped[Any] = mapped_column(JSON)
    verification_status: Mapped[str] = mapped_column(String(16))
