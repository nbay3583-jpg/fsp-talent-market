from alembic import op
from sqlalchemy import String

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        op.column("key", String(64), primary_key=True),
        op.column("value", String(255), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
