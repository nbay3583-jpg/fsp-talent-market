from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.common.enums import (
    AttemptStatus,
    Grade,
    Sublevel,
    TaskFormat,
    VerificationStatus,
)
from fsp_market.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_values(e):
    return [m.value for m in e]


class TaskFamily(Base):
    __tablename__ = "task_families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id"), nullable=False)
    target_grade: Mapped[Grade] = mapped_column(
        Enum(Grade, native_enum=False, length=32, values_callable=_enum_values),
        nullable=False,
    )
    target_sublevel: Mapped[Sublevel | None] = mapped_column(
        Enum(Sublevel, native_enum=False, length=32, values_callable=_enum_values),
        nullable=True,
    )
    difficulty_band: Mapped[int] = mapped_column(Integer, nullable=False)
    rubric: Mapped[Any] = mapped_column(JSON, nullable=False)
    edge_case_classes: Mapped[Any] = mapped_column(JSON, nullable=False)
    allowed_formats: Mapped[Any] = mapped_column(JSON, nullable=False)
    # Families dropped from the current content are deactivated, never deleted (old attempts
    # keep their variants and results).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rubric_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("task_families.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    task_format: Mapped[TaskFormat] = mapped_column(
        Enum(TaskFormat, native_enum=False, length=32, values_callable=_enum_values),
        nullable=False,
    )
    structure: Mapped[str] = mapped_column(Text, nullable=False)
    parameter_schema: Mapped[Any] = mapped_column(JSON, nullable=False)
    scoring_rule: Mapped[Any] = mapped_column(JSON, nullable=False)


class TaskPreset(Base):
    __tablename__ = "task_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("task_templates.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    parameters: Mapped[Any] = mapped_column(JSON, nullable=False)


class TaskVariant(Base):
    __tablename__ = "task_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("task_templates.id"), nullable=False)
    preset_id: Mapped[int | None] = mapped_column(ForeignKey("task_presets.id"), nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    input_data: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    expected_behavior: Mapped[Any] = mapped_column(JSON, nullable=False)
    scoring_contract: Mapped[Any] = mapped_column(JSON, nullable=False)
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    target_grade: Mapped[Grade] = mapped_column(
        Enum(Grade, native_enum=False, length=32, values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(
            AttemptStatus,
            native_enum=False,
            length=32,
            values_callable=_enum_values,
        ),
        default=AttemptStatus.IN_PROGRESS,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Server-side timing: deadline_at (UTC) is the single source of truth for the countdown.
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_ids: Mapped[Any | None] = mapped_column(JSON, nullable=True)  # frozen at start
    # {variant_id: {"answer": ..., "saved_at": iso}} autosaved answers (survive reload / expiry)
    draft_answers: Mapped[Any | None] = mapped_column(JSON, nullable=True)


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "variant_id", name="uq_assessment_answers_attempt_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("assessment_attempts.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("task_variants.id"), nullable=False)
    answer: Mapped[Any] = mapped_column(JSON, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    subscores: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_attempts.id"), unique=True, nullable=False
    )
    target_grade: Mapped[Grade] = mapped_column(
        Enum(Grade, native_enum=False, length=32, values_callable=_enum_values),
        nullable=False,
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    subscores: Mapped[Any] = mapped_column(JSON, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            native_enum=False,
            length=32,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    achieved_sublevel: Mapped[Sublevel | None] = mapped_column(
        Enum(Sublevel, native_enum=False, length=32, values_callable=_enum_values),
        nullable=True,
    )
    rubric_result: Mapped[Any] = mapped_column(JSON, nullable=False)
    # Per-task audit trail: template/variant/seed/difficulty band/rubric version/answer/time.
    trace: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
