"""Per-direction results: counts come from the attempt, small samples are flagged, legacy results
degrade gracefully, and claim vs. evidence stays separated in the Evidence Profile."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401
from fsp_market.assessments.breakdown import competency_breakdown
from fsp_market.assessments.models import AssessmentResult
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.service import (
    attempt_variants,
    score_attempt,
    start_attempt,
    submit_answers,
    wrong_answer,
)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade, VerificationStatus
from fsp_market.db import Base
from fsp_market.evidence.profile import build_evidence_profile
from fsp_market.evidence.service import add_self_reported_claim
from fsp_market.skills.models import Skill

T0 = datetime(2026, 10, 6, tzinfo=UTC)
CODES = ["python", "sql", "api_fastapi", "testing", "docker_basics", "system_thinking"]


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_backend_python(s)
        s.add(Candidate(email="a@x.io", full_name="A", claimed_grade=Grade.MIDDLE))
        s.commit()
        yield s


def _take(session, correct: bool, grade=Grade.JUNIOR) -> AssessmentResult:
    attempt = start_attempt(session, 1, grade, now=T0)
    answers = {
        v.id: v.scoring_contract["correct"] if correct else wrong_answer(v)
        for v in attempt_variants(session, attempt)
    }
    submit_answers(session, attempt.id, answers, now=T0)
    return score_attempt(session, attempt.id, now=T0)


def test_counts_come_from_the_attempt(session):
    result = _take(session, correct=True)
    rows = {r["competency"]: r for r in competency_breakdown(session, result)}
    assert list(rows) == CODES
    assert sum(r["tasks"] for r in rows.values()) == len(result.trace) == 11
    for code, r in rows.items():
        assert r["percent"] == result.subscores[code]
        assert r["answered"] == r["tasks"]
        assert r["points_max"] == r["tasks"]  # 1 point per task
        assert r["points_earned"] == r["points_max"]
    assert any(r["reliability"] == "limited" for r in rows.values())  # 1-2 tasks: a spot check


def test_wrong_attempt_percentages_and_points(session):
    result = _take(session, correct=False)
    for r in competency_breakdown(session, result):
        assert r["percent"] == 0.0
        assert r["points_earned"] == 0.0
        assert r["points_max"] == r["tasks"]


def test_direction_without_tasks_is_not_assessed(session):
    result = _take(session, correct=True)
    result.trace = [t for t in result.trace if "docker" not in t["family"]]
    del result.subscores["docker_basics"]
    row = next(r for r in competency_breakdown(session, result) if r["competency"] == "docker_basics")
    assert row == {"competency": "docker_basics", "percent": None, "tasks": 0, "answered": None,
                   "points_earned": None, "points_max": None, "reliability": "none"}


def test_historical_result_without_trace_keeps_percent_only(session):
    result = _take(session, correct=True)
    result.trace = []
    rows = {r["competency"]: r for r in competency_breakdown(session, result)}
    assert rows["sql"]["percent"] == result.subscores["sql"]
    assert rows["sql"]["tasks"] is None and rows["sql"]["points_max"] is None
    assert rows["sql"]["reliability"] == "unknown"


def test_breakdown_does_not_change_stored_scores(session):
    result = _take(session, correct=False)
    before = (result.total_score, dict(result.subscores))
    competency_breakdown(session, result)
    session.refresh(result)
    assert (result.total_score, dict(result.subscores)) == before


def test_unverified_grade_stays_separate_from_claim_in_profile(session):
    _take(session, correct=False)
    skill = session.scalar(select(Skill).limit(1))
    add_self_reported_claim(session, 1, skill.code, Grade.SENIOR, "self")
    session.commit()
    p = build_evidence_profile(session, 1)
    assert p["claimed_grade"] == "JUNIOR"  # start_attempt records the target as the claim
    assert p["verification_status"] == VerificationStatus.NOT_VERIFIED.value
    assert p["verified_grade"] is None
    assert p["assessment"]["passed"] is False
    assert len(p["assessment"]["competency_breakdown"]) == 6
    claimed = next(s for s in p["skills"] if s["skill"] == skill.code)
    assert claimed["verified_level"] is None and claimed["confirmed"] is False
    assert claimed["claimed_level"] == "SENIOR"
