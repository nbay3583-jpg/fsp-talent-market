from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.ids import utcnow
from fsp_market.db import Base


class TeamResponse(Base):
    """One anonymous, voluntary team-member questionnaire. No identity is stored on purpose."""

    __tablename__ = "team_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(Integer, ForeignKey("employer_needs.id"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Favorite(Base):
    """Employer's saved interest in a candidate; nothing is sent to the candidate."""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("employer_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(Integer, ForeignKey("employers.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"))
    need_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("employer_needs.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
