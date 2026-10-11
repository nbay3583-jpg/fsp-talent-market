import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def _build_config(tmp_path: Path) -> Config:
    migrations_dir = Path(__file__).resolve().parents[1] / "src" / "fsp_market" / "migrations"
    db_path = tmp_path / "migrations.db"
    config = Config()
    config.set_main_option("script_location", str(migrations_dir))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def test_upgrade_creates_app_meta_table(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    command.upgrade(config, "head")

    db_path = tmp_path / "migrations.db"
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row[0] for row in rows}

    assert "app_meta" in table_names


def test_downgrade_removes_app_meta_table(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    db_path = tmp_path / "migrations.db"
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row[0] for row in rows}

    assert "app_meta" not in table_names


def test_head_revision_is_0011(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    script_dir = ScriptDirectory.from_config(config)
    assert script_dir.get_heads() == ["0011"]


def test_domain_tables_created_and_removed(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    command.upgrade(config, "head")
    db_path = tmp_path / "migrations.db"
    expected = {
        "specializations",
        "competencies",
        "candidates",
        "employers",
        "skills",
        "skill_claims",
        "skill_evidence",
        "verified_skill_levels",
        "task_families",
        "task_templates",
        "task_presets",
        "task_variants",
        "assessment_attempts",
        "assessment_answers",
        "assessment_results",
        "employer_needs",
        "need_skills",
        "match_runs",
        "match_results",
        "invitations",
    }
    with sqlite3.connect(db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert expected <= names
    command.downgrade(config, "0001")
    with sqlite3.connect(db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not expected & names
    assert "app_meta" in names
