"""need OPEN/CLOSED status; invitation uniqueness per employer+candidate+need (standalone = own scope)"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_OPEN = "status IN ('SENT','VIEWED','ACCEPTED','CONTACTS_UNLOCKED')"


def upgrade() -> None:
    op.add_column(
        "employer_needs",
        sa.Column("status", sa.String(8), nullable=False, server_default="OPEN"),
    )
    op.add_column("employer_needs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "employer_needs",
        sa.Column("public_to_candidates", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_index("uq_invitations_one_open_per_pair", table_name="invitations")
    op.create_index(
        "uq_invitations_one_open_per_scope",
        "invitations",
        ["employer_id", "candidate_id", sa.text("coalesce(need_id, 0)")],
        unique=True,
        postgresql_where=sa.text(_OPEN),
        sqlite_where=sa.text(_OPEN),
    )


def downgrade() -> None:
    # Per-need invitations may now coexist; the old pair-level index is restored only if data allows it.
    op.drop_index("uq_invitations_one_open_per_scope", table_name="invitations")
    op.create_index(
        "uq_invitations_one_open_per_pair",
        "invitations",
        ["employer_id", "candidate_id"],
        unique=True,
        postgresql_where=sa.text(_OPEN),
        sqlite_where=sa.text(_OPEN),
    )
    op.drop_column("employer_needs", "public_to_candidates")
    op.drop_column("employer_needs", "closed_at")
    op.drop_column("employer_needs", "status")
