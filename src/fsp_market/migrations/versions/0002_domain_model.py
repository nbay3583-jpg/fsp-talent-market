"""domain model"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact_email"),
    )
    op.create_table(
        "specializations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=True),
        sa.Column("claimed_grade", sa.String(length=32), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("verified_grade", sa.String(length=32), nullable=True),
        sa.Column("verified_sublevel", sa.String(length=32), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["specialization_id"],
            ["specializations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "competencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("specialization_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["specialization_id"],
            ["specializations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column(
            "target_grade",
            sa.Enum("JUNIOR", "MIDDLE", "SENIOR", name="grade", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "IN_PROGRESS",
                "SUBMITTED",
                "SCORED",
                name="attemptstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competencies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "task_families",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("competency_id", sa.Integer(), nullable=False),
        sa.Column(
            "target_grade",
            sa.Enum("JUNIOR", "MIDDLE", "SENIOR", name="grade", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "target_sublevel",
            sa.Enum(
                "J1", "J2", "M1", "M2", "S1", "S2", name="sublevel", native_enum=False, length=32
            ),
            nullable=True,
        ),
        sa.Column("difficulty_band", sa.Integer(), nullable=False),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("edge_case_classes", sa.JSON(), nullable=False),
        sa.Column("allowed_formats", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["competencies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "assessment_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column(
            "target_grade",
            sa.Enum("JUNIOR", "MIDDLE", "SENIOR", name="grade", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("subscores", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum(
                "UNVERIFIED",
                "VERIFIED",
                "NOT_VERIFIED",
                name="verificationstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "achieved_sublevel",
            sa.Enum(
                "J1", "J2", "M1", "M2", "S1", "S2", name="sublevel", native_enum=False, length=32
            ),
            nullable=True,
        ),
        sa.Column("rubric_result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
    )
    op.create_table(
        "skill_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("claimed_level", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "skill_id"),
    )
    op.create_table(
        "task_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column(
            "task_format",
            sa.Enum(
                "DETERMINISTIC_QUESTION",
                "CODE_READING",
                "SQL_REASONING",
                "API_REASONING",
                "RUBRIC_CHECK",
                name="taskformat",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("structure", sa.Text(), nullable=False),
        sa.Column("parameter_schema", sa.JSON(), nullable=False),
        sa.Column("scoring_rule", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["task_families.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "skill_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("strength", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=True),
        sa.Column("sublevel", sa.String(length=32), nullable=True),
        sa.Column("attempt_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["skill_claims.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["task_templates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "task_variants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("preset_id", sa.Integer(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("expected_behavior", sa.JSON(), nullable=False),
        sa.Column("scoring_contract", sa.JSON(), nullable=False),
        sa.Column("is_anchor", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["preset_id"],
            ["task_presets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["task_templates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "verified_skill_levels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("sublevel", sa.String(length=32), nullable=True),
        sa.Column("basis_evidence_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["basis_evidence_id"],
            ["skill_evidence.id"],
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["skill_claims.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id"),
    )
    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("subscores", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["task_variants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id", "variant_id", name="uq_assessment_answers_attempt_variant"
        ),
    )


def downgrade() -> None:
    op.drop_table("assessment_answers")
    op.drop_table("verified_skill_levels")
    op.drop_table("task_variants")
    op.drop_table("task_presets")
    op.drop_table("skill_evidence")
    op.drop_table("task_templates")
    op.drop_table("skill_claims")
    op.drop_table("assessment_results")
    op.drop_table("task_families")
    op.drop_table("skills")
    op.drop_table("assessment_attempts")
    op.drop_table("competencies")
    op.drop_table("candidates")
    op.drop_table("specializations")
    op.drop_table("employers")
