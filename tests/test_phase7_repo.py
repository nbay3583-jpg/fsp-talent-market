"""Submission-readiness checks: README numbers come from the artifact, config safety, repo hygiene."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from fsp_market.config import get_settings
from fsp_market.main import assert_safe_configuration
from fsp_market.validation.report import README_BEGIN, README_END, summary_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_readme_validation_block_matches_the_artifact():
    res = json.loads((ROOT / "artifacts/validation/latest.json").read_text(encoding="utf-8"))
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text[text.index(README_BEGIN) + len(README_BEGIN) : text.index(README_END)]
    assert block.strip() == summary_markdown(res).strip(), (
        "run: python -m fsp_market.validation --update-readme"
    )
    assert (ROOT / "artifacts/validation/summary.md").read_text(
        encoding="utf-8"
    ) == summary_markdown(res)


def test_production_refuses_demo_mode_and_placeholder_secret(monkeypatch):
    def configure(**env):
        for k in ("ENVIRONMENT", "DEMO_MODE", "JWT_SECRET"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    try:
        configure(
            ENVIRONMENT="production", DEMO_MODE="true", JWT_SECRET="a-real-long-random-secret-value"
        )
        with pytest.raises(RuntimeError):
            assert_safe_configuration()
        configure(
            ENVIRONMENT="production", DEMO_MODE="false", JWT_SECRET="change-me-long-random-string"
        )
        with pytest.raises(RuntimeError):
            assert_safe_configuration()
        configure(
            ENVIRONMENT="production",
            DEMO_MODE="false",
            JWT_SECRET="a-real-long-random-secret-value",
        )
        assert_safe_configuration()  # safe configuration starts
        configure(ENVIRONMENT="local", DEMO_MODE="true")
        assert_safe_configuration()
    finally:
        get_settings.cache_clear()


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return out.stdout.splitlines()


def test_no_secrets_or_local_paths_are_tracked():
    files = _tracked()
    assert ".env" not in files and not any(
        f.endswith((".db", ".sqlite", ".sqlite3", ".pem", ".key")) for f in files
    )
    patterns = [
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"sk-[A-Za-z0-9]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"/Users/[a-z]",
        r"ghp_[A-Za-z0-9]{20,}",
    ]
    for f in files:
        if f.endswith("package-lock.json") or not (ROOT / f).is_file():
            continue
        try:
            text = (ROOT / f).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pat in patterns:
            assert not re.search(pat, text), f"{pat} in {f}"
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "change-me" in env_example and "DEMO_MODE" in env_example


def test_compose_runs_without_dotenv_and_exposes_expected_ports():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "env_file" not in compose  # fresh clone must work without a .env
    assert '"8000:8000"' in compose and '"3000:80"' in compose
    assert "alembic upgrade head" in (ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
