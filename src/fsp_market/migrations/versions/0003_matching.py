"""matching"""

import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_needs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employer_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=False),
        sa.Column("target_grade", sa.String(length=32), nullable=False),
        sa.Column("target_sublevel", sa.String(length=8), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("salary_type", sa.String(length=8), nullable=False),
        sa.Column("work_formats", sa.JSON(), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("max_start_days", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["specialization_id"],
            ["specializations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "match_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("need_id", sa.Integer(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("candidates_considered", sa.Integer(), nullable=False),
        sa.Column("excluded_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["need_id"],
            ["employer_needs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "match_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("requirement_fit", sa.Float(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("why", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["match_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "candidate_id"),
    )
    op.create_table(
        "need_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("need_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("importance", sa.String(length=16), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["need_id"],
            ["employer_needs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("need_id", "skill_id"),
    )
    op.add_column("candidates", sa.Column("salary_min", sa.Integer(), nullable=True))
    op.add_column("candidates", sa.Column("salary_type", sa.String(length=8), nullable=True))
    op.add_column("candidates", sa.Column("work_formats", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("location", sa.String(length=128), nullable=True))
    op.add_column("candidates", sa.Column("available_in_days", sa.Integer(), nullable=True))
    op.add_column(
        "candidates",
        sa.Column("profile_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "candidates",
        sa.Column("open_to_invitations", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("candidates", "open_to_invitations")
    op.drop_column("candidates", "profile_visible")
    op.drop_column("candidates", "available_in_days")
    op.drop_column("candidates", "location")
    op.drop_column("candidates", "work_formats")
    op.drop_column("candidates", "salary_type")
    op.drop_column("candidates", "salary_min")
    op.drop_table("need_skills")
    op.drop_table("match_results")
    op.drop_table("match_runs")
    op.drop_table("employer_needs")
