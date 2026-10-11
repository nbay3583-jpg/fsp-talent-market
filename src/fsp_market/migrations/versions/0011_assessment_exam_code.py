"""independent technology exams: attempts carry an exam code (NULL = Core Assessment)"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assessment_attempts", sa.Column("exam_code", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("assessment_attempts", "exam_code")
