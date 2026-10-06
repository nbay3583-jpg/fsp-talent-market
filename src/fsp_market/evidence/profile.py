"""Evidence Profile composition. Deliberately has no global Talent Score: it lists claims,
the evidence behind each, and the platform-verified level per skill."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.models import AssessmentAttempt, AssessmentResult
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import EvidenceType
from fsp_market.skills.models import Skill, SkillClaim, SkillEvidence, VerifiedSkillLevel
from fsp_market.taxonomy.models import Specialization


def _value(x: Any) -> str | None:
    return None if x is None else str(getattr(x, "value", x))


def build_evidence_profile(session: Session, candidate_id: int) -> dict[str, Any]:
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise LookupError(f"candidate {candidate_id} not found")
    specialization = (
        session.get(Specialization, candidate.specialization_id)
        if candidate.specialization_id
        else None
    )

    latest = session.execute(
        select(AssessmentAttempt, AssessmentResult)
        .join(AssessmentResult, AssessmentResult.attempt_id == AssessmentAttempt.id)
        .where(AssessmentAttempt.candidate_id == candidate_id)
        .order_by(AssessmentAttempt.id.desc())
    ).first()
    assessment = None
    if latest:
        attempt, result = latest
        assessment = {
            "attempt_id": attempt.id,
            "target_grade": _value(result.target_grade),
            "verification_status": _value(result.verification_status),
            "passed": result.passed,
            "score": result.total_score,  # score of THIS assessment, not a talent score
            "competency_scores": result.subscores,
            "achieved_sublevel": _value(result.achieved_sublevel),
            "scored_at": attempt.scored_at.isoformat() if attempt.scored_at else None,
        }

    skills = []
    fsp_count = 0
    rows = session.execute(
        select(SkillClaim, Skill)
        .join(Skill, Skill.id == SkillClaim.skill_id)
        .where(SkillClaim.candidate_id == candidate_id)
        .order_by(Skill.code)
    ).all()
    for claim, skill in rows:
        verified = session.scalar(
            select(VerifiedSkillLevel).where(VerifiedSkillLevel.claim_id == claim.id)
        )
        evidence = session.scalars(
            select(SkillEvidence)
            .where(SkillEvidence.claim_id == claim.id)
            .order_by(SkillEvidence.id)
        ).all()
        fsp_count += sum(1 for e in evidence if e.evidence_type == EvidenceType.FSP_ACHIEVEMENT)
        skills.append(
            {
                "skill": skill.code,
                "name": skill.name,
                "claimed_level": _value(claim.claimed_level),
                "claim_source": claim.source,
                "verified_level": _value(verified.level) if verified else None,
                "verified_sublevel": _value(verified.sublevel) if verified else None,
                "evidence": [
                    {
                        "type": _value(e.evidence_type),
                        "strength": _value(e.strength),
                        "level": _value(e.level),
                        "title": e.title,
                        "attempt_id": e.attempt_id,
                        "details": e.details,
                    }
                    for e in evidence
                ],
            }
        )

    return {
        "candidate": {"id": candidate.id, "full_name": candidate.full_name},
        "specialization": specialization.code if specialization else None,
        "claimed_grade": _value(candidate.claimed_grade),
        "verification_status": _value(candidate.verification_status),
        "verified_grade": _value(candidate.verified_grade),
        "verified_sublevel": _value(candidate.verified_sublevel),
        "assessment": assessment,
        "skills": skills,
        "fsp": {"has_history": fsp_count > 0, "evidence_items": fsp_count},
    }
