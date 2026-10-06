from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.models import AssessmentAttempt, AssessmentResult
from fsp_market.assessments.scoring import PASS_THRESHOLD
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import EvidenceStrength, EvidenceType, Grade
from fsp_market.skills.models import Skill, SkillClaim, SkillEvidence, VerifiedSkillLevel
from fsp_market.taxonomy.models import Competency

_ORDER = {Grade.JUNIOR: 0, Grade.MIDDLE: 1, Grade.SENIOR: 2}


def _skill(session: Session, skill_code: str) -> Skill:
    skill = session.scalar(select(Skill).where(Skill.code == skill_code))
    if skill is None:
        raise ValueError(f"unknown skill {skill_code!r}")
    return skill


def _get_or_create_claim(
    session: Session,
    candidate_id: int,
    skill_id: int,
    source: str,
    level: Grade | None = None,
    context: str | None = None,
) -> SkillClaim:
    claim = session.scalar(
        select(SkillClaim).where(
            SkillClaim.candidate_id == candidate_id, SkillClaim.skill_id == skill_id
        )
    )
    if claim is None:
        claim = SkillClaim(
            candidate_id=candidate_id,
            skill_id=skill_id,
            claimed_level=level,
            source=source,
            context=context,
        )
        session.add(claim)
        session.flush()
    return claim


def add_self_reported_claim(
    session: Session,
    candidate_id: int,
    skill_code: str,
    claimed_level: Grade | None,
    context: str | None,
) -> SkillClaim:
    """A claim only: self-reported data is context, never evidence."""
    skill = _skill(session, skill_code)
    return _get_or_create_claim(
        session, candidate_id, skill.id, "self_reported", claimed_level, context
    )


def add_fsp_evidence(
    session: Session,
    candidate_id: int,
    skill_code: str,
    title: str,
    details: dict | None = None,
) -> SkillEvidence:
    """Separate evidence type; never touches the candidate's grade or verified levels."""
    skill = _skill(session, skill_code)
    claim = _get_or_create_claim(session, candidate_id, skill.id, "fsp")
    evidence = SkillEvidence(
        claim_id=claim.id,
        evidence_type=EvidenceType.FSP_ACHIEVEMENT,
        strength=EvidenceStrength.MEDIUM,
        title=title,
        details=details,
    )
    session.add(evidence)
    session.flush()
    return evidence


def record_core_assessment_evidence(
    session: Session,
    candidate: Candidate,
    attempt: AssessmentAttempt,
    result: AssessmentResult,
    competency_scores: dict[str, float],
) -> list[SkillEvidence]:
    threshold = PASS_THRESHOLD[attempt.target_grade]
    created: list[SkillEvidence] = []
    for code, score in competency_scores.items():
        if score < threshold:
            continue
        skills = session.scalars(
            select(Skill)
            .join(Competency, Skill.competency_id == Competency.id)
            .where(Competency.code == code)
        ).all()
        for skill in skills:
            claim = _get_or_create_claim(
                session, candidate.id, skill.id, "core_assessment", attempt.target_grade
            )
            evidence = SkillEvidence(
                claim_id=claim.id,
                evidence_type=EvidenceType.CORE_ASSESSMENT,
                strength=EvidenceStrength.HIGH,
                level=attempt.target_grade,
                sublevel=result.achieved_sublevel,
                attempt_id=attempt.id,
            )
            session.add(evidence)
            session.flush()
            verified = session.scalar(
                select(VerifiedSkillLevel).where(VerifiedSkillLevel.claim_id == claim.id)
            )
            if verified is None:
                session.add(
                    VerifiedSkillLevel(
                        claim_id=claim.id,
                        level=attempt.target_grade,
                        sublevel=result.achieved_sublevel,
                        basis_evidence_id=evidence.id,
                    )
                )
            elif _ORDER[Grade(verified.level)] < _ORDER[attempt.target_grade]:
                verified.level = attempt.target_grade
                verified.sublevel = result.achieved_sublevel
                verified.basis_evidence_id = evidence.id
            created.append(evidence)
    session.flush()
    return created


def add_professional_experience(
    session: Session,
    candidate_id: int,
    skill_code: str,
    title: str,
    created_at=None,
) -> SkillEvidence:
    """Medium-strength evidence; never changes the platform grade."""
    skill = _skill(session, skill_code)
    claim = _get_or_create_claim(session, candidate_id, skill.id, "experience")
    evidence = SkillEvidence(
        claim_id=claim.id,
        evidence_type=EvidenceType.PROFESSIONAL_EXPERIENCE,
        strength=EvidenceStrength.MEDIUM,
        title=title,
    )
    if created_at is not None:
        evidence.created_at = created_at
    session.add(evidence)
    session.flush()
    return evidence
