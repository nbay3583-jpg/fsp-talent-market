from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import (
    EvidenceStrength,
    EvidenceType,
    Grade,
    Sublevel,
)
from fsp_market.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    competency_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("competencies.id"),
        nullable=True,
    )


class SkillClaim(Base):
    __tablename__ = "skill_claims"
    __table_args__ = (UniqueConstraint("candidate_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidates.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"), nullable=False)
    claimed_level: Mapped[Grade | None] = mapped_column(
        String(32),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        default="self_reported",
    )
    context: Mapped[str | None] = mapped_column(Text, nullable=True)


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(Integer, ForeignKey("skill_claims.id"), nullable=False)
    evidence_type: Mapped[EvidenceType] = mapped_column(
        String(32),
        nullable=False,
    )
    strength: Mapped[EvidenceStrength] = mapped_column(
        String(32),
        nullable=False,
    )
    level: Mapped[Grade | None] = mapped_column(
        String(32),
        nullable=True,
    )
    sublevel: Mapped[Sublevel | None] = mapped_column(
        String(32),
        nullable=True,
    )
    attempt_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("assessment_attempts.id"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )


class VerifiedSkillLevel(Base):
    __tablename__ = "verified_skill_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skill_claims.id"), unique=True, nullable=False
    )
    level: Mapped[Grade] = mapped_column(String(32), nullable=False)
    sublevel: Mapped[Sublevel | None] = mapped_column(
        String(32),
        nullable=True,
    )
    basis_evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skill_evidence.id"), nullable=False
    )
