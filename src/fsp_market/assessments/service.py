from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.models import (
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentResult,
    TaskFamily,
    TaskTemplate,
    TaskVariant,
)
from fsp_market.assessments.scoring import PASS_THRESHOLD, score_answer
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import AttemptStatus, Grade, VerificationStatus
from fsp_market.evidence.service import record_core_assessment_evidence
from fsp_market.taxonomy.grades import sublevel_for_score
from fsp_market.taxonomy.models import Competency

COOLDOWN_DAYS = 7


class CooldownError(Exception):
    pass


class AssessmentError(Exception):
    pass


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def start_attempt(
    session: Session, candidate_id: int, target_grade: Grade, now: datetime | None = None
) -> AssessmentAttempt:
    now = _now(now)
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise AssessmentError(f"candidate {candidate_id} not found")
    failed = session.execute(
        select(AssessmentAttempt.scored_at)
        .join(AssessmentResult, AssessmentResult.attempt_id == AssessmentAttempt.id)
        .where(
            AssessmentAttempt.candidate_id == candidate_id,
            AssessmentAttempt.target_grade == target_grade,
            AssessmentResult.verification_status == VerificationStatus.NOT_VERIFIED,
        )
    ).scalars()
    cutoff = now - timedelta(days=COOLDOWN_DAYS)
    if any(scored and _aware(scored) > cutoff for scored in failed):
        raise CooldownError(f"cooldown: {COOLDOWN_DAYS} days after a failed {target_grade} attempt")
    attempt = AssessmentAttempt(
        candidate_id=candidate_id, target_grade=target_grade, started_at=now
    )
    candidate.claimed_grade = target_grade  # the candidate's own claim; never inferred
    session.add(attempt)
    session.flush()
    return attempt


def select_variants(session: Session, target_grade: Grade, attempt_id: int) -> list[TaskVariant]:
    families = session.scalars(
        select(TaskFamily).where(TaskFamily.target_grade == target_grade).order_by(TaskFamily.id)
    ).all()
    chosen: list[TaskVariant] = []
    for family in families:
        variants = session.scalars(
            select(TaskVariant)
            .join(TaskTemplate, TaskVariant.template_id == TaskTemplate.id)
            .where(TaskTemplate.family_id == family.id)
            .order_by(TaskVariant.id)
        ).all()
        if variants:
            chosen.append(variants[attempt_id % len(variants)])
    return chosen


def submit_answers(
    session: Session, attempt_id: int, answers: dict[int, object], now: datetime | None = None
) -> AssessmentAttempt:
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.status != AttemptStatus.IN_PROGRESS:
        raise AssessmentError(f"attempt {attempt_id} is not in progress")
    for variant_id, answer in answers.items():
        session.add(AssessmentAnswer(attempt_id=attempt_id, variant_id=variant_id, answer=answer))
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = _now(now)
    session.flush()
    return attempt


def score_attempt(
    session: Session, attempt_id: int, now: datetime | None = None
) -> AssessmentResult:
    now = _now(now)
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.status != AttemptStatus.SUBMITTED:
        raise AssessmentError(f"attempt {attempt_id} is not submitted")
    answers = session.scalars(
        select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt_id)
    ).all()

    earned_total = possible_total = 0.0
    competency = defaultdict(lambda: [0.0, 0.0])  # code -> [earned, possible]
    dimension = defaultdict(lambda: [0.0, 0.0])
    for answer in answers:
        variant = session.get(TaskVariant, answer.variant_id)
        contract = variant.scoring_contract
        points = float(contract.get("points", 1.0))
        dim = contract.get("dimension", "general")
        earned = points * score_answer(contract, answer.answer)
        answer.score = earned
        answer.subscores = {dim: earned}
        code = session.scalar(
            select(Competency.code)
            .join(TaskFamily, TaskFamily.competency_id == Competency.id)
            .join(TaskTemplate, TaskTemplate.family_id == TaskFamily.id)
            .where(TaskTemplate.id == variant.template_id)
        )
        for bucket, key in ((competency, code), (dimension, dim)):
            bucket[key][0] += earned
            bucket[key][1] += points
        earned_total += earned
        possible_total += points

    total = earned_total / possible_total if possible_total else 0.0
    passed = total >= PASS_THRESHOLD[attempt.target_grade]
    competency_scores = {k: e / p for k, (e, p) in competency.items() if p}
    sublevel = sublevel_for_score(attempt.target_grade, total) if passed else None
    result = AssessmentResult(
        attempt_id=attempt.id,
        target_grade=attempt.target_grade,
        total_score=total,
        subscores=competency_scores,
        passed=passed,
        verification_status=VerificationStatus.VERIFIED
        if passed
        else VerificationStatus.NOT_VERIFIED,
        achieved_sublevel=sublevel,
        rubric_result={k: e / p for k, (e, p) in dimension.items() if p},
    )
    session.add(result)
    attempt.status = AttemptStatus.SCORED
    attempt.scored_at = now

    candidate = session.get(Candidate, attempt.candidate_id)
    candidate.last_attempt_at = now
    if passed:
        candidate.verification_status = VerificationStatus.VERIFIED
        candidate.verified_grade = attempt.target_grade
        candidate.verified_sublevel = sublevel
    else:
        # Claimed grade stays as the candidate chose; no automatic downgrade to a lower grade.
        candidate.verification_status = VerificationStatus.NOT_VERIFIED
    session.flush()
    if passed:
        record_core_assessment_evidence(session, candidate, attempt, result, competency_scores)
    return result
