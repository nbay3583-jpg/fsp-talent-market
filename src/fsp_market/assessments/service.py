"""Core Assessment use-cases: start (frozen variant selection + server deadline), autosave,
submit, expiry and scoring.

Timing policy (explicit, server-side):
* `deadline_at = started_at + time_limit` (UTC) is the only source of truth; the browser merely
  renders the remaining time.
* Answers are autosaved (`save_draft`); a reload or a network drop loses nothing.
* A submission/autosave after `deadline_at + GRACE_SECONDS` is NOT accepted: the attempt is
  auto-finalised from the answers that were already saved before the deadline (unanswered tasks
  score 0) and the result is marked `expired`.
"""

from __future__ import annotations

import random
import secrets
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments import content
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
GRACE_SECONDS = 5  # tolerance for network delay on the last click, nothing more


class CooldownError(Exception):
    pass


class AssessmentError(Exception):
    pass


class DeadlinePassed(AssessmentError):
    """The attempt ran out of time (it has been auto-finalised from saved answers)."""


def utcnow() -> datetime:
    """Patch point for tests that need to move the clock."""
    return datetime.now(UTC)


def _now(now: datetime | None) -> datetime:
    return now or utcnow()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ------------------------------------------------------------------ selection


def _family_variants(session: Session, family: TaskFamily) -> list[TaskVariant]:
    return list(
        session.scalars(
            select(TaskVariant)
            .join(TaskTemplate, TaskVariant.template_id == TaskTemplate.id)
            .where(TaskTemplate.family_id == family.id)
            .order_by(TaskVariant.id)
        )
    )


def _seen_variant_ids(session: Session, candidate_id: int, grade: Grade) -> set[int]:
    seen: set[int] = set()
    for ids in session.scalars(
        select(AssessmentAttempt.variant_ids).where(
            AssessmentAttempt.candidate_id == candidate_id,
            AssessmentAttempt.target_grade == grade,
        )
    ):
        seen.update(ids or [])
    return seen


def pick_variants(
    session: Session, grade: Grade, seed: int, avoid: set[int] | None = None
) -> list[TaskVariant]:
    """One variant per active family of the grade; deterministic for a given seed. Variants the
    candidate has already seen at this grade are avoided while unseen ones remain."""
    rng = random.Random(f"{content.RUBRIC_VERSION}|{grade}|{seed}")
    avoid = avoid or set()
    families = session.scalars(
        select(TaskFamily)
        .where(TaskFamily.target_grade == grade, TaskFamily.is_active.is_(True))
        .order_by(TaskFamily.id)
    ).all()
    chosen: list[TaskVariant] = []
    for family in families:
        variants = _family_variants(session, family)
        if not variants:
            continue
        fresh = [v for v in variants if v.id not in avoid] or variants
        chosen.append(rng.choice(fresh))
    return chosen


def attempt_variants(session: Session, attempt: AssessmentAttempt) -> list[TaskVariant]:
    """The variants frozen at start (legacy attempts: the variants they were answered with)."""
    if attempt.variant_ids is not None:
        by_id = {v.id: v for v in session.scalars(
            select(TaskVariant).where(TaskVariant.id.in_(attempt.variant_ids))
        )}
        return [by_id[i] for i in attempt.variant_ids if i in by_id]
    answered = session.scalars(
        select(AssessmentAnswer.variant_id).where(AssessmentAnswer.attempt_id == attempt.id)
    ).all()
    if answered:
        return list(session.scalars(select(TaskVariant).where(TaskVariant.id.in_(answered))))
    return pick_variants(session, attempt.target_grade, attempt.id)  # legacy, unanswered


# ------------------------------------------------------------------ lifecycle


def start_attempt(
    session: Session,
    candidate_id: int,
    target_grade: Grade,
    now: datetime | None = None,
    seed: int | None = None,
    variant_ids: list[int] | None = None,
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
    seed = secrets.randbelow(2**31) if seed is None else seed
    if variant_ids is None:
        avoid = _seen_variant_ids(session, candidate_id, target_grade)
        variant_ids = [v.id for v in pick_variants(session, target_grade, seed, avoid)]
    limit = content.TIME_LIMIT_SECONDS[str(target_grade)]
    attempt = AssessmentAttempt(
        candidate_id=candidate_id,
        target_grade=target_grade,
        started_at=now,
        deadline_at=now + timedelta(seconds=limit),
        time_limit_seconds=limit,
        seed=seed,
        rubric_version=content.RUBRIC_VERSION,
        variant_ids=variant_ids,
        draft_answers={},
    )
    candidate.claimed_grade = target_grade  # the candidate's own claim; never inferred
    session.add(attempt)
    session.flush()
    return attempt


def ensure_deadline(attempt: AssessmentAttempt, now: datetime) -> None:
    """Legacy in-progress attempts (created before timing existed) get a fresh full window."""
    if attempt.deadline_at is None and attempt.status == AttemptStatus.IN_PROGRESS:
        limit = content.TIME_LIMIT_SECONDS[str(attempt.target_grade)]
        attempt.time_limit_seconds = limit
        attempt.deadline_at = now + timedelta(seconds=limit)


def remaining_seconds(attempt: AssessmentAttempt, now: datetime | None = None) -> int:
    if attempt.deadline_at is None:
        return attempt.time_limit_seconds or 0
    left = (_aware(attempt.deadline_at) - _now(now)).total_seconds()
    return max(0, int(left))


def is_expired(attempt: AssessmentAttempt, now: datetime | None = None) -> bool:
    if attempt.deadline_at is None or attempt.status != AttemptStatus.IN_PROGRESS:
        return False
    return _now(now) > _aware(attempt.deadline_at) + timedelta(seconds=GRACE_SECONDS)


def save_draft(
    session: Session,
    attempt: AssessmentAttempt,
    answers: dict[int, Any],
    now: datetime | None = None,
) -> None:
    now = _now(now)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise AssessmentError("assessment already submitted")
    if is_expired(attempt, now):
        finalize_expired(session, attempt, now)
        raise DeadlinePassed("time is over; saved answers were submitted automatically")
    allowed = {v.id for v in attempt_variants(session, attempt)}
    draft = dict(attempt.draft_answers or {})
    for vid, answer in answers.items():
        if vid not in allowed:
            raise AssessmentError(f"task {vid} is not part of this attempt")
        draft[str(vid)] = {"answer": answer, "saved_at": now.isoformat()}
    attempt.draft_answers = draft  # reassign: JSON column change tracking
    session.flush()


def finalize_expired(
    session: Session, attempt: AssessmentAttempt, now: datetime | None = None
) -> AssessmentResult:
    """Score an out-of-time attempt from the answers saved before the deadline."""
    now = _now(now)
    attempt.expired = True
    drafts = {int(k): v["answer"] for k, v in (attempt.draft_answers or {}).items()}
    submit_answers(session, attempt.id, drafts, now=_aware(attempt.deadline_at or now))
    return score_attempt(session, attempt.id, now=now)


def submit_answers(
    session: Session, attempt_id: int, answers: dict[int, object], now: datetime | None = None
) -> AssessmentAttempt:
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.status != AttemptStatus.IN_PROGRESS:
        raise AssessmentError(f"attempt {attempt_id} is not in progress")
    now = _now(now)
    saved = attempt.draft_answers or {}
    for variant_id, answer in answers.items():
        stamp = saved.get(str(variant_id), {}).get("saved_at")
        elapsed = None
        if stamp:
            elapsed = (datetime.fromisoformat(stamp) - _aware(attempt.started_at)).total_seconds()
        session.add(
            AssessmentAnswer(
                attempt_id=attempt_id,
                variant_id=variant_id,
                answer=answer,
                duration_seconds=elapsed,
            )
        )
    attempt.status = AttemptStatus.SUBMITTED
    attempt.submitted_at = now
    session.flush()
    return attempt


def score_attempt(
    session: Session, attempt_id: int, now: datetime | None = None
) -> AssessmentResult:
    now = _now(now)
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.status != AttemptStatus.SUBMITTED:
        raise AssessmentError(f"attempt {attempt_id} is not submitted")
    answers = {
        a.variant_id: a
        for a in session.scalars(
            select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt_id)
        )
    }
    variants = attempt_variants(session, attempt)

    earned_total = possible_total = 0.0
    competency = defaultdict(lambda: [0.0, 0.0])  # code -> [earned, possible]
    dimension = defaultdict(lambda: [0.0, 0.0])
    trace: list[dict[str, Any]] = []
    for variant in variants:
        answer = answers.get(variant.id)
        contract = variant.scoring_contract
        points = float(contract.get("points", 1.0))
        dim = contract.get("dimension", "general")
        earned = points * score_answer(contract, answer.answer) if answer else 0.0  # unanswered: 0
        if answer is not None:
            answer.score = earned
            answer.subscores = {dim: earned}
        code, family_code, band = session.execute(
            select(Competency.code, TaskFamily.code, TaskFamily.difficulty_band)
            .join(TaskFamily, TaskFamily.competency_id == Competency.id)
            .join(TaskTemplate, TaskTemplate.family_id == TaskFamily.id)
            .where(TaskTemplate.id == variant.template_id)
        ).one()
        for bucket, key in ((competency, code), (dimension, dim)):
            bucket[key][0] += earned
            bucket[key][1] += points
        earned_total += earned
        possible_total += points
        trace.append(
            {
                "family": family_code,
                "template_id": variant.template_id,
                "variant_id": variant.id,
                "variant_code": variant.code,
                "seed": variant.seed,
                "attempt_seed": attempt.seed,
                "difficulty_band": band,
                "rubric_version": attempt.rubric_version,
                "dimension": dim,
                "answered": answer is not None,
                "answer": answer.answer if answer else None,
                "score": earned,
                "elapsed_seconds": answer.duration_seconds if answer else None,
            }
        )

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
        trace=trace,
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


def wrong_answer(variant: TaskVariant) -> Any:
    """A deterministic incorrect answer of the right shape (demo / validation personas)."""
    contract = variant.scoring_contract
    correct = contract["correct"]
    if contract["type"] == "numeric":
        return correct + 1
    options = sorted(variant.input_data["options"])
    if contract["type"] == "set":
        return [next(k for k in options if k not in correct)]
    return next(k for k in options if k != correct)
