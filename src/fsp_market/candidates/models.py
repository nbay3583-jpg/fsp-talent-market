from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import Grade, SalaryType, Sublevel, VerificationStatus
from fsp_market.db import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    specialization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("specializations.id"),
        nullable=True,
    )
    claimed_grade: Mapped[Grade | None] = mapped_column(
        String(32),
        nullable=True,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        String(32),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
    )
    verified_grade: Mapped[Grade | None] = mapped_column(
        String(32),
        nullable=True,
    )
    verified_sublevel: Mapped[Sublevel | None] = mapped_column(
        String(32),
        nullable=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    # Matching preferences (hard constraints on the candidate side). Contacts are never exposed.
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_type: Mapped[SalaryType | None] = mapped_column(String(8), nullable=True)
    work_formats: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    available_in_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    open_to_invitations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)  # private contact
    # Email verification: only a SHA-256 of the one-time token is stored.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_token_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
