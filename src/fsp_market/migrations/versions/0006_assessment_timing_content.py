"""assessment timing (server deadline), frozen variant selection, audit trace, family activation"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_families",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("task_families", sa.Column("rubric_version", sa.String(64), nullable=True))
    op.add_column(
        "assessment_attempts", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("assessment_attempts", sa.Column("time_limit_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "assessment_attempts",
        sa.Column("expired", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("assessment_attempts", sa.Column("seed", sa.Integer(), nullable=True))
    op.add_column("assessment_attempts", sa.Column("rubric_version", sa.String(64), nullable=True))
    op.add_column("assessment_attempts", sa.Column("variant_ids", sa.JSON(), nullable=True))
    op.add_column("assessment_attempts", sa.Column("draft_answers", sa.JSON(), nullable=True))
    op.add_column("assessment_results", sa.Column("trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("assessment_results", "trace")
    for col in (
        "draft_answers",
        "variant_ids",
        "rubric_version",
        "seed",
        "expired",
        "time_limit_seconds",
        "deadline_at",
    ):
        op.drop_column("assessment_attempts", col)
    op.drop_column("task_families", "rubric_version")
    op.drop_column("task_families", "is_active")
