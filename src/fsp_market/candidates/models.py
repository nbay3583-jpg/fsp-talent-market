from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import Grade, Sublevel, VerificationStatus
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
