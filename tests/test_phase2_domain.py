from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401
from fsp_market.assessments.models import (
    AssessmentResult,
    TaskFamily,
    TaskPreset,
    TaskTemplate,
    TaskVariant,
)
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.service import (
    CooldownError,
    score_attempt,
    attempt_variants,
    wrong_answer,
    start_attempt,
    submit_answers,
)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import (
    SUBLEVEL_GRADE,
    EvidenceType,
    Grade,
    Sublevel,
    VerificationStatus,
)
from fsp_market.db import Base
from fsp_market.evidence.service import add_fsp_evidence, add_self_reported_claim
from fsp_market.skills.models import SkillClaim, SkillEvidence, VerifiedSkillLevel
from fsp_market.taxonomy.models import Competency, Specialization

T0 = datetime(2026, 10, 6, tzinfo=UTC)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_backend_python(s)
        s.add(Candidate(email="a@x.io", full_name="A"))
        s.commit()
        yield s


def _take(session, grade: Grade, correct: bool, now: datetime):
    attempt = start_attempt(session, 1, grade, now=now)
    answers = {}
    for v in attempt_variants(session, attempt):
        answers[v.id] = v.scoring_contract["correct"] if correct else wrong_answer(v)
    submit_answers(session, attempt.id, answers, now=now)
    return score_attempt(session, attempt.id, now=now)


def test_taxonomy_and_sublevels(session):
    assert session.scalar(select(Specialization.code)) == "backend_python"
    codes = set(session.scalars(select(Competency.code)))
    assert codes == {"python", "sql", "api_fastapi", "testing", "docker_basics", "system_thinking"}
    assert {s: g for s, g in SUBLEVEL_GRADE.items()}[Sublevel.M2] == Grade.MIDDLE
    assert len(Sublevel) == 9


def test_seed_is_idempotent_and_parameterized(session):
    seed_backend_python(session)
    session.commit()
    assert session.scalar(select(func.count(TaskFamily.id))) == 24
    n_variants = session.scalar(select(func.count(TaskVariant.id)))
    assert n_variants == session.scalar(select(func.count(TaskPreset.id))) >= 24 * 6
    seed_backend_python(session)
    session.commit()
    assert session.scalar(select(func.count(TaskVariant.id))) == n_variants  # idempotent
    for family in session.scalars(select(TaskFamily)):
        variants = session.scalars(
            select(TaskVariant).join(TaskTemplate).where(TaskTemplate.family_id == family.id)
        ).all()
        assert len(variants) >= 6
        shown = {(v.prompt, repr(v.input_data["options"])) for v in variants}
        assert len(shown) == len(variants)  # what the learner sees differs
        assert {v.scoring_contract["points"] for v in variants} == {1.0}  # contract fixed
        dims = {r["dimension"] for r in family.rubric}
        assert {v.scoring_contract["dimension"] for v in variants} <= dims


def test_passed_middle_is_verified_with_core_evidence(session):
    result = _take(session, Grade.MIDDLE, True, T0)
    cand = session.get(Candidate, 1)
    assert result.verification_status == VerificationStatus.VERIFIED
    assert (cand.verified_grade, cand.claimed_grade) == (Grade.MIDDLE, Grade.MIDDLE)
    assert cand.verified_sublevel == Sublevel.M3  # perfect score -> advanced Middle
    ev = session.scalars(select(SkillEvidence)).all()
    assert ev and {e.evidence_type for e in ev} == {EvidenceType.CORE_ASSESSMENT}
    assert session.scalar(select(func.count(VerifiedSkillLevel.id))) >= 5


def test_failed_middle_is_not_verified_and_never_downgraded(session):
    result = _take(session, Grade.MIDDLE, False, T0)
    cand = session.get(Candidate, 1)
    assert result.verification_status == VerificationStatus.NOT_VERIFIED
    assert cand.claimed_grade == Grade.MIDDLE
    assert cand.verification_status == VerificationStatus.NOT_VERIFIED
    assert cand.verified_grade is None and cand.verified_sublevel is None  # not Junior
    assert session.scalar(select(func.count(VerifiedSkillLevel.id))) == 0
    assert session.scalar(select(func.count(SkillEvidence.id))) == 0


def test_cooldown_after_failed_attempt_then_retry_allowed(session):
    _take(session, Grade.MIDDLE, False, T0)
    with pytest.raises(CooldownError):
        start_attempt(session, 1, Grade.MIDDLE, now=T0 + timedelta(days=2))
    # a different (lower) assessment is possible, and so is a retry after cooldown
    start_attempt(session, 1, Grade.JUNIOR, now=T0 + timedelta(days=2))
    retry = _take(session, Grade.MIDDLE, True, T0 + timedelta(days=8))
    assert retry.verification_status == VerificationStatus.VERIFIED
    assert session.scalar(select(func.count(AssessmentResult.id))) == 2


def test_claim_is_not_evidence_and_fsp_does_not_change_grade(session):
    add_self_reported_claim(session, 1, "sql", Grade.SENIOR, "4 years in CV")
    assert session.scalar(select(func.count(SkillEvidence.id))) == 0
    add_fsp_evidence(session, 1, "python", "FSP Algorithmic Programming finalist")
    cand = session.get(Candidate, 1)
    assert cand.verified_grade is None and cand.verification_status == VerificationStatus.UNVERIFIED
    ev = session.scalar(select(SkillEvidence))
    assert ev.evidence_type == EvidenceType.FSP_ACHIEVEMENT and ev.level is None
    assert session.scalar(select(func.count(VerifiedSkillLevel.id))) == 0
    assert session.scalar(select(func.count(SkillClaim.id))) == 2


def test_fsp_after_verification_keeps_verified_level(session):
    _take(session, Grade.MIDDLE, True, T0)
    before = session.get(Candidate, 1).verified_grade
    add_fsp_evidence(session, 1, "python", "FSP win")
    assert session.get(Candidate, 1).verified_grade == before
