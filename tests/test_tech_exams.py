"""Independent technology exams: same engine, separate attempts, one skill each, grade untouched."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401
from fsp_market.assessments import tech_exams
from fsp_market.assessments.models import AssessmentAttempt
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.service import (
    CooldownError,
    attempt_variants,
    score_attempt,
    start_attempt,
    submit_answers,
    wrong_answer,
)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import EvidenceType, Grade, VerificationStatus
from fsp_market.db import Base
from fsp_market.evidence.profile import build_evidence_profile
from fsp_market.skills.models import Skill, SkillEvidence, VerifiedSkillLevel

T0 = datetime(2026, 10, 11, tzinfo=UTC)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_backend_python(s)
        s.add(Candidate(email="a@x.io", full_name="A", claimed_grade=Grade.SENIOR))
        s.commit()
        yield s


def _take(session, grade, correct, exam=None, now=T0):
    attempt = start_attempt(session, 1, grade, now=now, exam=exam)
    answers = {
        v.id: v.scoring_contract["correct"] if correct else wrong_answer(v)
        for v in attempt_variants(session, attempt)
    }
    submit_answers(session, attempt.id, answers, now=now)
    return attempt, score_attempt(session, attempt.id, now=now)


@pytest.mark.parametrize("exam", ["fastapi", "postgresql"])
@pytest.mark.parametrize("grade", list(Grade))
def test_exam_has_10_to_12_tasks_and_is_isolated_from_core(session, exam, grade):
    attempt = start_attempt(session, 1, grade, now=T0, exam=exam)
    variants = attempt_variants(session, attempt)
    assert 10 <= len(variants) <= 12
    assert attempt.exam_code == exam
    core = start_attempt(session, 1, grade, now=T0 + timedelta(days=1))
    assert core.exam_code is None
    assert not set(attempt.variant_ids) & set(core.variant_ids)
    assert 15 <= len(core.variant_ids) <= 18  # deeper Core for new attempts


def test_passed_exam_confirms_skill_but_not_overall_grade(session):
    cand = session.get(Candidate, 1)
    _, result = _take(session, Grade.MIDDLE, True, exam="fastapi")
    session.commit()
    session.refresh(cand)
    assert result.passed and list(result.subscores) == ["api_fastapi"]
    assert cand.verified_grade is None
    assert cand.verification_status == VerificationStatus.UNVERIFIED
    assert cand.claimed_grade == Grade.SENIOR  # an exam never rewrites the claim
    ev = session.scalars(select(SkillEvidence)).all()
    assert [e.evidence_type for e in ev] == [EvidenceType.TECHNOLOGY_ASSESSMENT]
    level = session.scalar(select(VerifiedSkillLevel))
    assert level.level == Grade.MIDDLE
    p = build_evidence_profile(session, 1)
    assert p["assessment"] is None  # Core section is not polluted by an exam
    assert p["verified_grade"] is None
    assert [(e["exam"], e["passed"]) for e in p["tech_exams"]] == [("fastapi", True)]
    sk = next(s for s in p["skills"] if s["skill"] == "api_fastapi")
    assert sk["verified_level"] == "MIDDLE" and sk["claimed_level"] is None


def test_failed_exam_creates_no_evidence_and_cooldown_is_per_exam(session):
    _, result = _take(session, Grade.JUNIOR, False, exam="postgresql")
    assert not result.passed
    assert session.scalars(select(SkillEvidence)).all() == []
    with pytest.raises(CooldownError):
        start_attempt(session, 1, Grade.JUNIOR, now=T0 + timedelta(days=1), exam="postgresql")
    start_attempt(session, 1, Grade.JUNIOR, now=T0 + timedelta(days=1), exam="fastapi")
    start_attempt(session, 1, Grade.JUNIOR, now=T0 + timedelta(days=1))  # Core unaffected


def test_no_double_credit_skill_level_is_single_and_only_goes_up(session):
    _take(session, Grade.MIDDLE, True, exam="fastapi")
    _take(session, Grade.JUNIOR, True, exam="fastapi", now=T0 + timedelta(days=1))
    levels = session.scalars(select(VerifiedSkillLevel)).all()
    assert len(levels) == 1 and levels[0].level == Grade.MIDDLE
    skill = session.scalar(select(Skill).where(Skill.code == "api_fastapi"))
    assert skill is not None
    assert len(session.scalars(select(SkillEvidence)).all()) == 2  # history kept


def test_postgresql_skill_exists_and_is_not_a_core_competency(session):
    skill = session.scalar(select(Skill).where(Skill.code == "postgresql"))
    assert skill is not None and skill.competency_id is None
    assert tech_exams.EXAMS["postgresql"]["skill"] == "postgresql"


def test_core_attempts_do_not_see_exam_history(session):
    _take(session, Grade.JUNIOR, False, exam="fastapi")
    attempt = start_attempt(session, 1, Grade.JUNIOR, now=T0)  # no cooldown from the exam
    assert session.get(AssessmentAttempt, attempt.id).exam_code is None
