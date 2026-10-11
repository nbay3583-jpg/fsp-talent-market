"""Plain data views used by the pure matching engine, plus bulk loading from the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import (
    EvidenceType,
    Grade,
    SalaryType,
    Sublevel,
    VerificationStatus,
)
from fsp_market.experience.models import WorkExperience
from fsp_market.matching.models import EmployerNeed, NeedSkill
from fsp_market.skills.models import Skill, SkillClaim, SkillEvidence, VerifiedSkillLevel


@dataclass(frozen=True)
class SkillFacts:
    code: str
    claimed: bool = False  # self-reported / context only
    verified_level: Grade | None = None
    verified_sublevel: Sublevel | None = None
    experience: bool = False  # PROFESSIONAL_EXPERIENCE evidence
    fsp_titles: tuple[str, ...] = ()
    latest_evidence_at: datetime | None = None


@dataclass(frozen=True)
class ExperienceFacts:
    """A declared job (never verified): used only for the explainable Experience Context Fit."""

    company: str
    position: str
    stack: tuple[str, ...]
    text: str  # tasks + projects + achievements
    start: date
    end: date | None


@dataclass(frozen=True)
class CandidateFacts:
    candidate_id: int
    specialization_id: int | None
    claimed_grade: Grade | None
    verification_status: VerificationStatus
    verified_grade: Grade | None
    verified_sublevel: Sublevel | None
    salary_min: int | None
    salary_type: SalaryType | None
    work_formats: tuple[str, ...]
    location: str | None
    available_in_days: int | None
    profile_visible: bool
    open_to_invitations: bool
    skills: dict[str, SkillFacts] = field(default_factory=dict)
    experience: tuple[ExperienceFacts, ...] = ()


@dataclass(frozen=True)
class NeedSkillSpec:
    code: str
    required: bool
    weight: float


@dataclass(frozen=True)
class NeedSpec:
    specialization_id: int
    target_grade: Grade
    target_sublevel: Sublevel | None
    salary_from: int
    salary_to: int
    salary_type: SalaryType
    work_formats: tuple[str, ...]
    location: str | None
    max_start_days: int | None
    skills: tuple[NeedSkillSpec, ...]
    title: str = ""
    description: str = ""


def load_need_spec(session: Session, need: EmployerNeed) -> NeedSpec:
    rows = session.execute(
        select(NeedSkill, Skill.code)
        .join(Skill, Skill.id == NeedSkill.skill_id)
        .where(NeedSkill.need_id == need.id)
        .order_by(Skill.code)
    ).all()
    return NeedSpec(
        specialization_id=need.specialization_id,
        target_grade=Grade(need.target_grade),
        target_sublevel=Sublevel(need.target_sublevel) if need.target_sublevel else None,
        salary_from=need.salary_from,
        salary_to=need.salary_to,
        salary_type=SalaryType(need.salary_type),
        work_formats=tuple(need.work_formats),
        location=need.location,
        max_start_days=need.max_start_days,
        title=need.title,
        description=need.description or "",
        skills=tuple(
            NeedSkillSpec(code, ns.importance == "REQUIRED", ns.weight) for ns, code in rows
        ),
    )


def load_candidate_facts(
    session: Session, candidates: list[Candidate]
) -> dict[int, CandidateFacts]:
    """Bulk-loads claims/evidence/verified levels in 3 queries (no per-candidate N+1)."""
    ids = [c.id for c in candidates]
    skills: dict[int, dict[str, dict]] = {i: {} for i in ids}
    if ids:
        claim_rows = session.execute(
            select(SkillClaim.id, SkillClaim.candidate_id, Skill.code)
            .join(Skill, Skill.id == SkillClaim.skill_id)
            .where(SkillClaim.candidate_id.in_(ids))
            .order_by(SkillClaim.id)
        ).all()
        by_claim = {}
        for claim_id, cand_id, code in claim_rows:
            entry = {
                "claimed": True,
                "verified": None,
                "experience": False,
                "fsp": [],
                "last": None,
            }
            skills[cand_id][code] = entry
            by_claim[claim_id] = entry
        if by_claim:
            for ev in session.scalars(
                select(SkillEvidence).where(SkillEvidence.claim_id.in_(list(by_claim)))
            ):
                entry = by_claim[ev.claim_id]
                if ev.evidence_type == EvidenceType.PROFESSIONAL_EXPERIENCE:
                    entry["experience"] = True
                elif ev.evidence_type == EvidenceType.FSP_ACHIEVEMENT:
                    entry["fsp"].append(ev.title or "FSP achievement")
                stamp = ev.created_at
                if stamp is not None and (entry["last"] is None or stamp > entry["last"]):
                    entry["last"] = stamp
            for v in session.scalars(
                select(VerifiedSkillLevel).where(VerifiedSkillLevel.claim_id.in_(list(by_claim)))
            ):
                by_claim[v.claim_id]["verified"] = (Grade(v.level), v.sublevel)
    exp: dict[int, list[ExperienceFacts]] = {i: [] for i in ids}
    if ids:
        for w in session.scalars(
            select(WorkExperience)
            .where(WorkExperience.candidate_id.in_(ids))
            .order_by(WorkExperience.start_date.desc(), WorkExperience.id)
        ):
            exp[w.candidate_id].append(
                ExperienceFacts(
                    company=w.company,
                    position=w.position,
                    stack=tuple(w.stack or ()),
                    text=f"{w.position} {w.tasks} {w.projects} {w.achievements}",
                    start=w.start_date,
                    end=w.end_date,
                )
            )
    out = {}
    for c in candidates:
        sk = {}
        for code, e in skills[c.id].items():
            level, sub = e["verified"] or (None, None)
            sk[code] = SkillFacts(
                code=code,
                claimed=e["claimed"],
                verified_level=level,
                verified_sublevel=Sublevel(sub) if sub else None,
                experience=e["experience"],
                fsp_titles=tuple(e["fsp"]),
                latest_evidence_at=e["last"],
            )
        out[c.id] = CandidateFacts(
            candidate_id=c.id,
            specialization_id=c.specialization_id,
            claimed_grade=Grade(c.claimed_grade) if c.claimed_grade else None,
            verification_status=VerificationStatus(c.verification_status),
            verified_grade=Grade(c.verified_grade) if c.verified_grade else None,
            verified_sublevel=Sublevel(c.verified_sublevel) if c.verified_sublevel else None,
            salary_min=c.salary_min,
            salary_type=SalaryType(c.salary_type) if c.salary_type else None,
            work_formats=tuple(c.work_formats or ()),
            location=c.location,
            available_in_days=c.available_in_days,
            # published = the candidate wants it AND the email is verified
            profile_visible=bool(c.profile_visible and c.email_verified),
            open_to_invitations=c.open_to_invitations,
            skills=sk,
            experience=tuple(exp[c.id]),
        )
    return out
