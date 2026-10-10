"""Work-style questionnaire, BOTH team profile, favorites and personal recommendations."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, EmployerDep, SessionDep
from fsp_market.api.employer_routes import _own_need
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import VerificationStatus
from fsp_market.config import get_settings
from fsp_market.employers.models import Employer
from fsp_market.matching import service as matching
from fsp_market.matching.engine import hard_filter, requirement_fit
from fsp_market.matching.facts import load_candidate_facts, load_need_spec
from fsp_market.matching.models import EmployerNeed
from fsp_market.matching.policy import DEFAULT_POLICY
from fsp_market.skills.models import Skill
from fsp_market.teamfit import compat
from fsp_market.teamfit.models import Favorite, TeamResponse

router = APIRouter(prefix="/api", tags=["teamfit"])
MAX_RESPONSES_PER_NEED = 100


class AnswersIn(BaseModel):
    answers: dict[str, int]


class GoalsIn(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=15)
    career_goal: str | None = None


class FavoriteIn(BaseModel):
    candidate_id: int
    need_id: int | None = None
    note: str = Field(default="", max_length=500)


def _valid(answers: dict[str, int]) -> dict[str, int]:
    try:
        return compat.validate_answers(answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/work-style/questions")
def questions() -> dict[str, Any]:
    return {
        "scale": {"min": 1, "max": 5},
        "note": "Добровольная анкета о предпочтениях в работе. Это не оценка личности и не "
        "психологический тест; результат не влияет на подтверждённый грейд и не исключает кандидатов.",
        "axes": [
            {"key": k, "label": label, "low": lo, "high": hi}
            for k, (label, lo, hi) in compat.AXES.items()
        ],
        "career_goals": compat.CAREER_GOALS,
    }


# ------------------------------------------------------------------ candidate side
@router.put("/candidates/me/work-style")
def set_work_style(
    body: AnswersIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    cand = session.get(Candidate, candidate_id)
    cand.work_style = _valid(body.answers)
    session.commit()
    return {"work_style": cand.work_style}


@router.get("/candidates/me/work-style")
def get_work_style(candidate_id: int = CandidateDep, session: Session = SessionDep):
    cand = session.get(Candidate, candidate_id)
    return {
        "work_style": cand.work_style,
        "interests": cand.interests or [],
        "career_goal": cand.career_goal,
    }


@router.put("/candidates/me/goals")
def set_goals(
    body: GoalsIn, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    if body.career_goal is not None and body.career_goal not in compat.CAREER_GOALS:
        raise HTTPException(status_code=422, detail="unknown career_goal")
    known = set(session.scalars(select(Skill.code).where(Skill.code.in_(body.interests or ["-"]))))
    unknown = sorted(set(body.interests) - known)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown skills: {', '.join(unknown)}")
    cand = session.get(Candidate, candidate_id)
    cand.interests, cand.career_goal = list(dict.fromkeys(body.interests)), body.career_goal
    session.commit()
    return {"interests": cand.interests, "career_goal": cand.career_goal}


def team_profile(session: Session, need: EmployerNeed) -> dict[str, Any]:
    rows = [r for (r,) in session.execute(select(TeamResponse.answers).where(TeamResponse.need_id == need.id))]
    employees = compat.aggregate(rows)
    return {"manager": need.work_style, "employees": employees, **compat.combine(need.work_style, employees)}


def reverse_for(session: Session, cand: Candidate, need: EmployerNeed, spec=None) -> dict[str, Any]:
    spec = spec or load_need_spec(session, need)
    grade = cand.verified_grade if cand.verification_status == VerificationStatus.VERIFIED else cand.claimed_grade
    return compat.reverse_fit(
        interests=list(cand.interests or []),
        career_goal=cand.career_goal,
        candidate_grade=str(grade) if grade else None,
        need_skills={s.code for s in spec.skills},
        need_grade=str(need.target_grade),
        need_text=f"{need.title} {need.description or ''}",
        work_style=cand.work_style,
        team_profile=team_profile(session, need)["profile"],
    )


@router.get("/candidates/me/recommendations")
def candidate_recommendations(
    limit: int = 5, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    """Open needs ranked for THIS candidate, with WHY/GAPS of both directions. Read-only."""
    cand = session.get(Candidate, candidate_id)
    facts = load_candidate_facts(session, [cand])[cand.id]
    now = datetime.now(UTC)
    # UNVERIFIED = no assessment finished yet; NOT_VERIFIED is a real (possibly low) result
    assessed = cand.verification_status != VerificationStatus.UNVERIFIED
    out = []
    for need in session.scalars(select(EmployerNeed).order_by(EmployerNeed.id)):
        spec = load_need_spec(session, need)
        if hard_filter(spec, facts, DEFAULT_POLICY, ignore_visibility=True):
            continue
        fit = requirement_fit(spec, facts, now, DEFAULT_POLICY)
        rev = reverse_for(session, cand, need, spec)
        both = fit.fit if rev["score"] is None else round((fit.fit + rev["score"]) / 2, 4)
        if not assessed:  # no completed assessment: a number would be meaningless, not "0%"
            fit_value = both = None
        else:
            fit_value = fit.fit
        employer = session.get(Employer, need.employer_id)
        out.append(
            {
                "need_id": need.id,
                "title": need.title,
                "company": employer.company_name,
                "target_grade": need.target_grade,
                "salary_from": need.salary_from,
                "salary_to": need.salary_to,
                "salary_type": need.salary_type,
                "work_formats": need.work_formats,
                "fit_state": "ready" if assessed else "insufficient_data",
                "requirement_fit": fit_value,
                "reverse_fit": rev["score"],
                "mutual_fit": both,
                "why": [r.as_dict() for r in fit.why] + rev["why"],
                "gaps": [r.as_dict() for r in fit.gaps] + rev["gaps"],
            }
        )
    out.sort(key=lambda r: (r["mutual_fit"] is None, -(r["mutual_fit"] or 0), r["need_id"]))
    next_action = None
    if not assessed:
        next_action = "take_assessment"
    elif not cand.work_style and not cand.interests:
        next_action = "fill_preferences"
    return {
        "items": out[: max(1, min(limit, 20))],
        "total": len(out),
        "assessed": assessed,
        "next_action": next_action,
    }


# ------------------------------------------------------------------ employer side
@router.put("/employer/needs/{need_id}/work-style")
def set_need_style(
    need_id: int, body: AnswersIn, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    need = _own_need(session, need_id, employer_id)
    need.work_style = _valid(body.answers)
    session.commit()
    return team_profile(session, need)


@router.post("/employer/needs/{need_id}/team-survey")
def create_team_survey(
    need_id: int, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    """Issues (or rotates) the anonymous survey link; only its hash is stored."""
    need = _own_need(session, need_id, employer_id)
    token = secrets.token_urlsafe(24)
    need.team_token_hash = _hash(token)
    session.commit()
    base = get_settings().public_base_url.rstrip("/")
    return {"token": token, "url": f"{base}/?team_survey={token}"}


@router.get("/employer/needs/{need_id}/team-profile")
def get_team_profile(
    need_id: int, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    return team_profile(session, _own_need(session, need_id, employer_id))


def _need_by_token(session: Session, token: str) -> EmployerNeed:
    need = session.scalar(select(EmployerNeed).where(EmployerNeed.team_token_hash == _hash(token)))
    if need is None:
        raise HTTPException(status_code=404, detail="survey link is invalid")
    return need


@router.get("/team-survey/{token}")
def survey_info(token: str, session: Session = SessionDep) -> dict[str, Any]:
    need = _need_by_token(session, token)
    return {"title": need.title, **questions()}


@router.post("/team-survey/{token}", status_code=201)
def survey_submit(token: str, body: AnswersIn, session: Session = SessionDep) -> dict[str, Any]:
    need = _need_by_token(session, token)
    answers = _valid(body.answers)
    count = session.scalar(select(func.count()).select_from(TeamResponse).where(TeamResponse.need_id == need.id))
    if count >= MAX_RESPONSES_PER_NEED:
        raise HTTPException(status_code=429, detail="response limit reached")
    session.add(TeamResponse(need_id=need.id, answers=answers))  # no identity is recorded
    session.commit()
    return {"accepted": True}


@router.get("/employer/needs/{need_id}/compat/{candidate_id}")
def candidate_compat(
    need_id: int, candidate_id: int, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    need = _own_need(session, need_id, employer_id)
    cand = session.get(Candidate, candidate_id)
    if cand is None or not cand.profile_visible:
        raise HTTPException(status_code=404, detail="candidate not found")
    rev = reverse_for(session, cand, need)
    return {"reverse_fit": rev["score"], "why": rev["why"], "gaps": rev["gaps"], "work_style": rev["work_style"]}


@router.get("/employer/recommendations")
def employer_recommendations(
    per_need: int = 3, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    now = datetime.now(UTC)
    cands = list(session.scalars(select(Candidate).where(Candidate.profile_visible.is_(True))))
    facts = load_candidate_facts(session, cands)
    items = []
    for need in session.scalars(
        select(EmployerNeed).where(EmployerNeed.employer_id == employer_id).order_by(EmployerNeed.id)
    ):
        spec = load_need_spec(session, need)
        scored = []
        for c in cands:
            f = facts[c.id]
            if hard_filter(spec, f, DEFAULT_POLICY):
                continue
            fit = requirement_fit(spec, f, now, DEFAULT_POLICY)
            rev = reverse_for(session, c, need, spec)
            mutual = fit.fit if rev["score"] is None else round((fit.fit + rev["score"]) / 2, 4)
            scored.append((-mutual, c.id, c, f, fit, rev, mutual))
        scored.sort(key=lambda t: t[:2])
        items.append(
            {
                "need_id": need.id,
                "title": need.title,
                "candidates": [
                    {
                        "mutual_fit": mutual,
                        "requirement_fit": fit.fit,
                        "reverse_fit": rev["score"],
                        "why": [r.as_dict() for r in fit.why] + rev["why"],
                        "gaps": [r.as_dict() for r in fit.gaps] + rev["gaps"],
                        "candidate": matching.public_candidate(c, f),
                    }
                    for _, _, c, f, fit, rev, mutual in scored[: max(1, min(per_need, 10))]
                ],
            }
        )
    return {"items": items}


# ------------------------------------------------------------------ favorites
@router.post("/employer/favorites", status_code=201)
def add_favorite(
    body: FavoriteIn, employer_id: int = EmployerDep, session: Session = SessionDep
) -> dict[str, Any]:
    cand = session.get(Candidate, body.candidate_id)
    if cand is None or not cand.profile_visible:
        raise HTTPException(status_code=404, detail="candidate not found")
    if body.need_id is not None:
        _own_need(session, body.need_id, employer_id)
    fav = session.scalar(
        select(Favorite).where(Favorite.employer_id == employer_id, Favorite.candidate_id == cand.id)
    )
    if fav is None:
        fav = Favorite(employer_id=employer_id, candidate_id=cand.id)
        session.add(fav)
    fav.need_id, fav.note = body.need_id, body.note
    session.commit()
    return {"candidate_id": cand.id, "need_id": fav.need_id, "note": fav.note}


@router.delete("/employer/favorites/{candidate_id}", status_code=204)
def remove_favorite(
    candidate_id: int, employer_id: int = EmployerDep, session: Session = SessionDep
) -> None:
    fav = session.scalar(
        select(Favorite).where(Favorite.employer_id == employer_id, Favorite.candidate_id == candidate_id)
    )
    if fav is not None:
        session.delete(fav)
        session.commit()


@router.get("/employer/favorites")
def list_favorites(employer_id: int = EmployerDep, session: Session = SessionDep) -> dict[str, Any]:
    """Saved candidates; a candidate who hid their profile disappears from the list."""
    favs = list(
        session.scalars(
            select(Favorite).where(Favorite.employer_id == employer_id).order_by(Favorite.id.desc())
        )
    )
    cands = {
        c.id: c
        for c in session.scalars(
            select(Candidate).where(
                Candidate.id.in_([f.candidate_id for f in favs] or [0]),
                Candidate.profile_visible.is_(True),
            )
        )
    }
    facts = load_candidate_facts(session, list(cands.values()))
    return {
        "items": [
            {
                "note": f.note,
                "need_id": f.need_id,
                "candidate": matching.public_candidate(cands[f.candidate_id], facts[f.candidate_id]),
            }
            for f in favs
            if f.candidate_id in cands
        ]
    }
