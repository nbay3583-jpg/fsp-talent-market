"""three internal sublevels per grade (J1..J3, M1..M3, S1..S3)

Schema: enum columns are non-native VARCHAR without CHECK constraints, so no DDL change is needed
for the wider value set. Data: the new sublevel of every PASSED legacy result is re-derived
deterministically from its stored total_score (the same score bands the application uses).
Whatever cannot be derived is NOT assigned silently: it is set to NULL ("needs clarification")
and matching falls back to the whole grade range. Employer needs keep their grade; the old target
sublevel is preserved in `legacy_target_sublevel` and the target is widened to the whole grade.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (min score for sublevel 2, min score for sublevel 3) -- mirrors taxonomy/grades.py at this revision
BANDS = {"JUNIOR": (0.75, 0.90), "MIDDLE": (0.80, 0.90), "SENIOR": (0.84, 0.92)}
PREFIX = {"JUNIOR": "J", "MIDDLE": "M", "SENIOR": "S"}
OLD_SPLIT = 0.85  # legacy: sublevel 2 from this score


def _new_sublevel(grade: str, score: float) -> str:
    second, third = BANDS[grade]
    return f"{PREFIX[grade]}{3 if score >= third else 2 if score >= second else 1}"


def _old_sublevel(grade: str, score: float) -> str:
    return f"{PREFIX[grade]}{2 if score >= OLD_SPLIT else 1}"


def _rederive(conn, derive) -> None:
    results = conn.execute(
        sa.text(
            "SELECT r.attempt_id, r.target_grade, r.total_score FROM assessment_results r "
            "WHERE r.passed = :t"
        ),
        {"t": True},
    ).fetchall()
    by_attempt = {}
    for attempt_id, grade, score in results:
        sub = derive(grade, float(score))
        by_attempt[attempt_id] = sub
        conn.execute(
            sa.text("UPDATE assessment_results SET achieved_sublevel = :s WHERE attempt_id = :a"),
            {"s": sub, "a": attempt_id},
        )
    for attempt_id, sub in by_attempt.items():
        conn.execute(
            sa.text("UPDATE skill_evidence SET sublevel = :s WHERE attempt_id = :a"),
            {"s": sub, "a": attempt_id},
        )
        conn.execute(
            sa.text(
                "UPDATE verified_skill_levels SET sublevel = :s WHERE basis_evidence_id IN "
                "(SELECT id FROM skill_evidence WHERE attempt_id = :a)"
            ),
            {"s": sub, "a": attempt_id},
        )
    # candidates: the newest passed attempt at the candidate's verified grade
    rows = conn.execute(
        sa.text(
            "SELECT c.id, c.verified_grade FROM candidates c "
            "WHERE c.verified_grade IS NOT NULL"
        )
    ).fetchall()
    for cand_id, grade in rows:
        attempt = conn.execute(
            sa.text(
                "SELECT a.id FROM assessment_attempts a JOIN assessment_results r "
                "ON r.attempt_id = a.id WHERE a.candidate_id = :c AND r.passed = :t "
                "AND r.target_grade = :g ORDER BY a.id DESC"
            ),
            {"c": cand_id, "g": grade, "t": True},
        ).first()
        sub = by_attempt.get(attempt[0]) if attempt else None
        conn.execute(
            sa.text("UPDATE candidates SET verified_sublevel = :s WHERE id = :c"),
            {"s": sub, "c": cand_id},
        )


def upgrade() -> None:
    op.add_column(
        "employer_needs", sa.Column("legacy_target_sublevel", sa.String(length=8), nullable=True)
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE employer_needs SET legacy_target_sublevel = target_sublevel, "
            "target_sublevel = NULL WHERE target_sublevel IS NOT NULL"
        )
    )
    _rederive(conn, _new_sublevel)


def downgrade() -> None:
    conn = op.get_bind()
    _rederive(conn, _old_sublevel)
    conn.execute(
        sa.text(
            "UPDATE employer_needs SET target_sublevel = legacy_target_sublevel "
            "WHERE legacy_target_sublevel IS NOT NULL"
        )
    )
    # any remaining 3rd sublevel (not backed by a stored score) collapses to the legacy 2nd
    for table, col in (
        ("candidates", "verified_sublevel"),
        ("skill_evidence", "sublevel"),
        ("verified_skill_levels", "sublevel"),
        ("assessment_results", "achieved_sublevel"),
        ("employer_needs", "target_sublevel"),
    ):
        for p in "JMS":
            conn.execute(sa.text(f"UPDATE {table} SET {col} = '{p}2' WHERE {col} = '{p}3'"))
    op.drop_column("employer_needs", "legacy_target_sublevel")
