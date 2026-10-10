"""email verification columns and candidate work experience"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("candidates", sa.Column("email_token_hash", sa.String(64), nullable=True))
    op.add_column(
        "candidates", sa.Column("email_token_expires", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "candidates", sa.Column("email_token_sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "work_experiences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("position", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("stack", sa.JSON(), nullable=False),
        sa.Column("tasks", sa.Text(), nullable=False),
        sa.Column("projects", sa.Text(), nullable=False),
        sa.Column("achievements", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_work_experiences_candidate_id", "work_experiences", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_work_experiences_candidate_id", table_name="work_experiences")
    op.drop_table("work_experiences")
    for col in ("email_token_sent_at", "email_token_expires", "email_token_hash", "email_verified"):
        op.drop_column("candidates", col)
