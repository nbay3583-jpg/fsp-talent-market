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


def test_head_revision_is_0001(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    script_dir = ScriptDirectory.from_config(config)
    assert script_dir.get_heads() == ["0001"]
