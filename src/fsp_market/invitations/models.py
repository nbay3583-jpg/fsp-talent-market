from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import InvitationStatus, SalaryType, WorkFormat
from fsp_market.common.ids import utcnow
from fsp_market.db import Base


class Invitation(Base):
    """Salary-backed, addressed offer. Salary is mandatory and visible to the candidate up front."""

    __tablename__ = "invitations"
    __table_args__ = (
        # backend-level duplicate guard: one live invitation per employer+candidate pair
        Index(
            "uq_invitations_one_open_per_pair",
            "employer_id",
            "candidate_id",
            unique=True,
            postgresql_where=text("status IN ('SENT','VIEWED','ACCEPTED','CONTACTS_UNLOCKED')"),
            sqlite_where=text("status IN ('SENT','VIEWED','ACCEPTED','CONTACTS_UNLOCKED')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(Integer, ForeignKey("employers.id"))
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"))
    need_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("employer_needs.id"), nullable=True
    )
    match_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("match_runs.id"), nullable=True
    )
    company: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_to: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_type: Mapped[SalaryType] = mapped_column(String(8), nullable=False)
    work_format: Mapped[WorkFormat] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[InvitationStatus] = mapped_column(String(24), default=InvitationStatus.SENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contacts_unlocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
