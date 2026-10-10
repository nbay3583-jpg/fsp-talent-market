"""Employer-side use-cases: needs, match runs, full pool, privacy-safe candidate views."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import SkillImportance, Sublevel, VerificationStatus
from fsp_market.matching.engine import hard_filter, requirement_fit
from fsp_market.matching.facts import CandidateFacts, load_candidate_facts, load_need_spec
from fsp_market.matching.models import EmployerNeed, MatchResult, MatchRun, NeedSkill
from fsp_market.matching.policy import DEFAULT_POLICY, MatchingPolicy
from fsp_market.skills.models import Skill
from fsp_market.taxonomy.models import Specialization

FIT_LABEL = "Соответствие этой потребности"


class NeedError(ValueError):
    pass


def create_need(
    session: Session,
    employer_id: int,
    *,
    title: str,
    specialization: str,
    target_grade,
    target_sublevel: Sublevel | None,
    required_skills: list[str],
    optional_skills: list[str],
    salary_from: int,
    salary_to: int,
    salary_type,
    work_formats: list[str],
    location: str | None,
    max_start_days: int | None,
    description: str,
    policy: MatchingPolicy = DEFAULT_POLICY,
) -> EmployerNeed:
    if salary_from > salary_to or salary_from <= 0:
        raise NeedError("salary range must be positive and salary_from <= salary_to")
    if not work_formats:
        raise NeedError("at least one work format is required")
    spec = session.scalar(select(Specialization).where(Specialization.code == specialization))
    if spec is None:
        raise NeedError(f"unknown specialization {specialization!r}")
    if target_sublevel is not None:
        from fsp_market.common.enums import SUBLEVEL_GRADE

        if SUBLEVEL_GRADE[target_sublevel] != target_grade:
            raise NeedError("target_sublevel does not belong to target_grade")
    codes = list(dict.fromkeys(required_skills + optional_skills))
    if len(codes) != len(required_skills) + len(optional_skills):
        raise NeedError("a skill cannot be listed twice")
    skills = {s.code: s for s in session.scalars(select(Skill).where(Skill.code.in_(codes)))}
    missing = [c for c in codes if c not in skills]
    if missing:
        raise NeedError(f"unknown skills: {', '.join(missing)}")
    need = EmployerNeed(
        employer_id=employer_id,
        title=title,
        specialization_id=spec.id,
        target_grade=target_grade,
        target_sublevel=target_sublevel,
        salary_from=salary_from,
        salary_to=salary_to,
        salary_type=salary_type,
        work_formats=list(work_formats),
        location=location,
        max_start_days=max_start_days,
        description=description,
    )
    session.add(need)
    session.flush()
    for code in required_skills:
        session.add(
            NeedSkill(
                need_id=need.id,
                skill_id=skills[code].id,
                importance=SkillImportance.REQUIRED,
                weight=policy.required_skill_weight,
            )
        )
    for code in optional_skills:
        session.add(
            NeedSkill(
                need_id=need.id,
                skill_id=skills[code].id,
                importance=SkillImportance.OPTIONAL,
                weight=policy.optional_skill_weight,
            )
        )
    session.flush()
    return need


def need_to_dict(session: Session, need: EmployerNeed) -> dict[str, Any]:
    rows = session.execute(
        select(NeedSkill, Skill.code)
        .join(Skill, Skill.id == NeedSkill.skill_id)
        .where(NeedSkill.need_id == need.id)
        .order_by(NeedSkill.importance, Skill.code)
    ).all()
    return {
        "id": need.id,
        "title": need.title,
        "target_grade": need.target_grade,
        "target_sublevel": need.target_sublevel,
        "required_skills": [
            {"skill": c, "weight": ns.weight} for ns, c in rows if ns.importance == "REQUIRED"
        ],
        "optional_skills": [
            {"skill": c, "weight": ns.weight} for ns, c in rows if ns.importance == "OPTIONAL"
        ],
        "salary_from": need.salary_from,
        "salary_to": need.salary_to,
        "salary_type": need.salary_type,
        "work_formats": need.work_formats,
        "location": need.location,
        "max_start_days": need.max_start_days,
        "description": need.description,
    }


def _all_candidates(session: Session) -> list[Candidate]:
    return list(session.scalars(select(Candidate).order_by(Candidate.id)))


def run_match(
    session: Session,
    need: EmployerNeed,
    *,
    now: datetime | None = None,
    policy: MatchingPolicy = DEFAULT_POLICY,
) -> MatchRun:
    """Hard constraints first, then Requirement Fit; persists the top `match_pool_size`."""
    now = now or datetime.now(UTC)
    spec = load_need_spec(session, need)
    candidates = _all_candidates(session)
    facts = load_candidate_facts(session, candidates)
    excluded: Counter[str] = Counter()
    scored = []
    for c in candidates:
        codes = hard_filter(spec, facts[c.id], policy)
        if codes:
            excluded.update(codes)
            continue
        fit = requirement_fit(spec, facts[c.id], now, policy)
        verified = facts[c.id].verification_status == VerificationStatus.VERIFIED
        scored.append((-fit.fit, not verified, c.id, fit, facts[c.id]))
    scored.sort(key=lambda t: t[:3])  # fit desc, verified first, candidate id: stable
    run = MatchRun(
        need_id=need.id,
        policy={**policy.snapshot(), "evaluated_at": now.isoformat()},
        candidates_considered=len(candidates),
        excluded_summary=dict(sorted(excluded.items())),
    )
    session.add(run)
    session.flush()
    for rank, (_, _, cand_id, fit, cf) in enumerate(scored[: policy.match_pool_size], start=1):
        session.add(
            MatchResult(
                run_id=run.id,
                candidate_id=cand_id,
                rank=rank,
                requirement_fit=fit.fit,
                components=fit.components,
                why=[r.as_dict() for r in fit.why],
                gaps=[r.as_dict() for r in fit.gaps],
                verification_status=str(cf.verification_status),
            )
        )
    session.flush()
    return run


def _display_name(full_name: str) -> str:
    parts = full_name.split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]


def public_candidate(c: Candidate, f: CandidateFacts) -> dict[str, Any]:
    """Employer-safe view: NO email, phone, full name or FSP member id."""
    return {
        "candidate_id": c.id,
        "display_name": _display_name(c.full_name),
        "specialization_id": c.specialization_id,
        "claimed_grade": c.claimed_grade,
        "verification_status": c.verification_status,
        "verified_grade": c.verified_grade,
        "verified_sublevel": c.verified_sublevel,
        "work_formats": list(f.work_formats),
        "location": c.location,
        "salary_expectation": (
            {"min": c.salary_min, "type": c.salary_type} if c.salary_min is not None else None
        ),
        "available_in_days": c.available_in_days,
        "has_fsp": any(s.fsp_titles for s in f.skills.values()),
        # declared job history: context only, never verification
        "work_experience": [
            {
                "position": e.position,
                "company": e.company,
                "start_date": e.start.isoformat(),
                "end_date": e.end.isoformat() if e.end else None,
                "stack": list(e.stack),
                "confirmed": False,
            }
            for e in f.experience
        ],
        "skills": [
            {
                "skill": s.code,
                "verified_level": s.verified_level,
                "verified_sublevel": s.verified_sublevel,
                "has_professional_experience": s.experience,
                "fsp_achievements": list(s.fsp_titles),
                "claimed_only": bool(s.claimed and not s.verified_level and not s.experience),
            }
            for s in sorted(f.skills.values(), key=lambda s: s.code)
        ],
    }


def run_results(
    session: Session,
    run: MatchRun,
    *,
    limit: int = 10,
    offset: int = 0,
    min_fit: float | None = None,
    verified_only: bool = False,
    skill: str | None = None,
) -> dict[str, Any]:
    """Refinement is read-side filtering over the stored run; the run itself never changes."""
    results = list(
        session.scalars(
            select(MatchResult).where(MatchResult.run_id == run.id).order_by(MatchResult.rank)
        )
    )
    cands = {
        c.id: c
        for c in session.scalars(
            select(Candidate).where(Candidate.id.in_([r.candidate_id for r in results] or [0]))
        )
    }
    facts = load_candidate_facts(session, list(cands.values()))
    rows = []
    for r in results:
        cf = facts[r.candidate_id]
        if min_fit is not None and r.requirement_fit < min_fit:
            continue
        if verified_only and r.verification_status != VerificationStatus.VERIFIED:
            continue
        if skill and not (skill in cf.skills and cf.skills[skill].verified_level):
            continue
        rows.append(
            {
                "rank": r.rank,
                "requirement_fit": r.requirement_fit,
                "requirement_fit_label": f"{FIT_LABEL}: {round(r.requirement_fit * 100)}%",
                "components": r.components,
                "why": r.why,
                "gaps": r.gaps,
                "candidate": public_candidate(cands[r.candidate_id], cf),
            }
        )
    return {
        "run_id": run.id,
        "need_id": run.need_id,
        "candidates_considered": run.candidates_considered,
        "excluded_summary": run.excluded_summary,
        "matched_total": len(results),
        "filtered_total": len(rows),
        "limit": limit,
        "offset": offset,
        "results": rows[offset : offset + limit],
    }


def full_pool(
    session: Session,
    *,
    specialization: str | None = None,
    grade: str | None = None,
    sublevel: str | None = None,
    verification: str | None = None,
    skills: list[str] | None = None,
    has_fsp: bool | None = None,
    work_format: str | None = None,
    location: str | None = None,
    salary_max: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Whole visible candidate bank with filters. Visibility is enforced here, not by callers."""
    q = select(Candidate).where(Candidate.profile_visible.is_(True)).order_by(Candidate.id)
    if specialization:
        q = q.join(Specialization, Specialization.id == Candidate.specialization_id).where(
            Specialization.code == specialization
        )
    if verification:
        q = q.where(Candidate.verification_status == verification)
    candidates = list(session.scalars(q))
    facts = load_candidate_facts(session, candidates)
    out = []
    for c in candidates:
        f = facts[c.id]
        # platform level for verified candidates, claimed level otherwise
        level = (
            c.verified_grade
            if c.verification_status == VerificationStatus.VERIFIED
            else c.claimed_grade
        )
        if grade and level != grade:
            continue
        if sublevel and c.verified_sublevel != sublevel:
            continue
        if skills and not all(s in f.skills and f.skills[s].verified_level for s in skills):
            continue
        if has_fsp is not None and any(s.fsp_titles for s in f.skills.values()) != has_fsp:
            continue
        if work_format and work_format not in f.work_formats:
            continue
        if location and (c.location or "").casefold() != location.casefold():
            continue
        if salary_max is not None and c.salary_min is not None and c.salary_min > salary_max:
            continue
        out.append(public_candidate(c, f))
    return {
        "total": len(out),
        "limit": limit,
        "offset": offset,
        "candidates": out[offset : offset + limit],
    }


def candidate_detail(
    session: Session, candidate_id: int, need: EmployerNeed | None, now: datetime | None = None
) -> dict[str, Any] | None:
    c = session.get(Candidate, candidate_id)
    if c is None or not c.profile_visible:
        return None
    f = load_candidate_facts(session, [c])[c.id]
    detail = public_candidate(c, f)
    detail["fit"] = None
    if need is not None:
        spec = load_need_spec(session, need)
        policy = DEFAULT_POLICY
        exclusions = hard_filter(spec, f, policy)
        if exclusions:
            detail["fit"] = {"eligible": False, "exclusions": exclusions}
        else:
            fit = requirement_fit(spec, f, now or datetime.now(UTC), policy)
            detail["fit"] = {
                "eligible": True,
                "requirement_fit": fit.fit,
                "requirement_fit_label": f"{FIT_LABEL}: {round(fit.fit * 100)}%",
                "components": fit.components,
                "why": [r.as_dict() for r in fit.why],
                "gaps": [r.as_dict() for r in fit.gaps],
            }
    return detail
