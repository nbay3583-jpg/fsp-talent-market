"""candidate interests/goal/work style, need team profile inputs, team responses, favorites"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("interests", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("career_goal", sa.String(16), nullable=True))
    op.add_column("candidates", sa.Column("work_style", sa.JSON(), nullable=True))
    op.add_column("employer_needs", sa.Column("work_style", sa.JSON(), nullable=True))
    op.add_column("employer_needs", sa.Column("team_token_hash", sa.String(64), nullable=True))
    op.create_table(
        "team_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("need_id", sa.Integer(), sa.ForeignKey("employer_needs.id"), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_team_responses_need_id", "team_responses", ["need_id"])
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employer_id", sa.Integer(), sa.ForeignKey("employers.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("need_id", sa.Integer(), sa.ForeignKey("employer_needs.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("employer_id", "candidate_id"),
    )
    op.create_index("ix_favorites_employer_id", "favorites", ["employer_id"])


def downgrade() -> None:
    op.drop_index("ix_favorites_employer_id", table_name="favorites")
    op.drop_table("favorites")
    op.drop_index("ix_team_responses_need_id", table_name="team_responses")
    op.drop_table("team_responses")
    op.drop_column("employer_needs", "team_token_hash")
    op.drop_column("employer_needs", "work_style")
    for col in ("work_style", "career_goal", "interests"):
        op.drop_column("candidates", col)
