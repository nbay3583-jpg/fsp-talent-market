"""Attach FSP achievements as external evidence. Never touches grade or verified levels."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.evidence.service import add_fsp_evidence
from fsp_market.fsp.mapping import skills_for
from fsp_market.fsp.provider import FSPProvider
from fsp_market.skills.models import Skill, SkillClaim, SkillEvidence


class FSPVerificationError(Exception):
    pass


def attach_fsp_evidence(
    session: Session, candidate_id: int, provider: FSPProvider, fsp_id: str
) -> int:
    """Returns the number of NEW evidence rows. A member with no history yields 0 (not an error)."""
    if not provider.verify_member(fsp_id):
        raise FSPVerificationError(f"FSP member {fsp_id!r} could not be verified")
    created = 0
    for achievement in provider.get_achievements(fsp_id):
        for skill_code in skills_for(achievement):
            already = session.scalars(
                select(SkillEvidence)
                .join(SkillClaim, SkillClaim.id == SkillEvidence.claim_id)
                .join(Skill, Skill.id == SkillClaim.skill_id)
                .where(SkillClaim.candidate_id == candidate_id, Skill.code == skill_code)
            ).all()
            if any(
                (e.details or {}).get("achievement_id") == achievement.achievement_id
                for e in already
            ):
                continue
            add_fsp_evidence(
                session,
                candidate_id,
                skill_code,
                achievement.title,
                {
                    "achievement_id": achievement.achievement_id,
                    "fsp_id": fsp_id,
                    "discipline": achievement.discipline,
                    "year": achievement.year,
                    "place": achievement.place,
                },
            )
            created += 1
    return created
