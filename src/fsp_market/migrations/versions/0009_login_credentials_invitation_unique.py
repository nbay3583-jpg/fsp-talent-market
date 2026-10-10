"""password / one-time-code sign-in columns; one open invitation per employer+candidate"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_COLS = [
    ("password_hash", sa.String(255), {"nullable": True}),
    ("login_failures", sa.Integer(), {"nullable": False, "server_default": "0"}),
    ("login_locked_until", sa.DateTime(timezone=True), {"nullable": True}),
    ("login_code_hash", sa.String(64), {"nullable": True}),
    ("login_code_expires", sa.DateTime(timezone=True), {"nullable": True}),
    ("login_code_sent_at", sa.DateTime(timezone=True), {"nullable": True}),
    ("login_code_attempts", sa.Integer(), {"nullable": False, "server_default": "0"}),
]
_OPEN = "status IN ('SENT','VIEWED','ACCEPTED','CONTACTS_UNLOCKED')"


def upgrade() -> None:
    for table in ("candidates", "employers"):
        for name, type_, kw in _COLS:
            op.add_column(table, sa.Column(name, type_, **kw))
    op.create_index(
        "uq_invitations_one_open_per_pair",
        "invitations",
        ["employer_id", "candidate_id"],
        unique=True,
        postgresql_where=sa.text(_OPEN),
        sqlite_where=sa.text(_OPEN),
    )


def downgrade() -> None:
    op.drop_index("uq_invitations_one_open_per_pair", table_name="invitations")
    for table in ("candidates", "employers"):
        for name, _t, _kw in reversed(_COLS):
            op.drop_column(table, name)
