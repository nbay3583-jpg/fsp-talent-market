"""Invitation lifecycle and the consent-based contact unlock.

SENT -> VIEWED -> ACCEPTED -> CONTACTS_UNLOCKED   or   SENT/VIEWED -> DECLINED.
INVARIANT (enforced here, server-side): candidate contacts are released to an employer only
for an invitation in ACCEPTED / CONTACTS_UNLOCKED that this employer sent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import InvitationStatus as S
from fsp_market.employers.models import Employer
from fsp_market.invitations.models import Invitation
from fsp_market.matching.models import EmployerNeed, MatchRun

ALLOWED: dict[S, set[S]] = {
    S.SENT: {S.VIEWED, S.ACCEPTED, S.DECLINED},
    S.VIEWED: {S.ACCEPTED, S.DECLINED},
    S.ACCEPTED: {S.CONTACTS_UNLOCKED},
    S.DECLINED: set(),
    S.CONTACTS_UNLOCKED: set(),
}
CONTACT_STATES = frozenset({S.ACCEPTED, S.CONTACTS_UNLOCKED})
OPEN_STATES = frozenset({S.SENT, S.VIEWED})


class InvitationError(Exception):
    """Business-rule violation (maps to 409/422)."""


class InvalidTransition(InvitationError):
    pass


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def transition(inv: Invitation, new: S, now: datetime | None = None) -> None:
    current = S(inv.status)
    if new not in ALLOWED[current]:
        raise InvalidTransition(f"cannot move invitation from {current} to {new}")
    inv.status = new


def contacts_visible(inv: Invitation) -> bool:
    return S(inv.status) in CONTACT_STATES


def _check_need_terms(
    session: Session,
    need: EmployerNeed,
    candidate: Candidate,
    *,
    role: str | None,
    salary_from: int,
    salary_to: int,
    salary_type,
    work_format,
) -> None:
    """Server-side guard: an invitation for a saved need may not deviate from that need's
    essential terms nor go to a candidate the need's hard filters exclude."""
    from fsp_market.matching.engine import hard_filter
    from fsp_market.matching.facts import load_candidate_facts, load_need_spec
    from fsp_market.matching.policy import DEFAULT_POLICY

    if role and role.strip().casefold() != need.title.strip().casefold():
        raise InvitationError("role must match the saved need; use a standalone invitation instead")
    if str(salary_type) != str(need.salary_type):
        raise InvitationError(f"salary type must be {need.salary_type} as in the need")
    if salary_from < need.salary_from or salary_to > need.salary_to:
        raise InvitationError(
            f"salary range must stay within the need's {need.salary_from}-{need.salary_to}"
        )
    if str(work_format) not in {str(f) for f in need.work_formats}:
        raise InvitationError("work format is not allowed by the need")
    if candidate.work_formats and str(work_format) not in {str(f) for f in candidate.work_formats}:
        raise InvitationError("work format is not acceptable to the candidate")
    if candidate.salary_min is not None:
        offered_top = float(salary_to)
        cand_type = candidate.salary_type
        if cand_type and str(cand_type) != str(salary_type):
            rate = DEFAULT_POLICY.ndfl_rate
            offered_top = salary_to * (1 - rate) if str(salary_type) == "GROSS" else salary_to / (1 - rate)
        if offered_top < candidate.salary_min:
            raise InvitationError("offered salary is below the candidate's stated minimum")
    spec = load_need_spec(session, need)
    facts = load_candidate_facts(session, [candidate])[candidate.id]
    codes = hard_filter(spec, facts, DEFAULT_POLICY)
    if codes:
        raise InvitationError("candidate does not meet the need's hard requirements: " + ", ".join(codes))


def send_invitation(
    session: Session,
    employer_id: int,
    *,
    candidate_id: int,
    role: str | None,
    description: str,
    salary_from: int,
    salary_to: int,
    salary_type,
    work_format,
    message: str,
    company: str | None = None,
    need_id: int | None = None,
    match_run_id: int | None = None,
) -> Invitation:
    if salary_from <= 0 or salary_to < salary_from or salary_type is None:
        raise InvitationError("salary range (from > 0, to >= from) and GROSS/NET type are required")
    employer = session.get(Employer, employer_id)
    candidate = session.get(Candidate, candidate_id)
    if candidate is None or not (candidate.profile_visible and candidate.email_verified):
        raise LookupError("candidate not found")
    if not candidate.open_to_invitations:
        raise InvitationError("candidate does not accept invitations")
    need = None
    if need_id is not None:
        need = session.get(EmployerNeed, need_id)
        if need is None or need.employer_id != employer_id:
            raise LookupError("need not found")
        if (need.status or "OPEN") != "OPEN":
            raise InvitationError("need is closed; no new invitations can be sent for it")
        _check_need_terms(
            session, need, candidate, role=role, salary_from=salary_from, salary_to=salary_to,
            salary_type=salary_type, work_format=work_format,
        )
        role = need.title  # the role is fixed by the saved need
    if match_run_id is not None:
        run = session.get(MatchRun, match_run_id)
        if run is None or need is None or run.need_id != need.id:
            raise InvitationError("match run does not belong to this need")
    existing = session.scalars(
        select(Invitation).where(
            Invitation.employer_id == employer_id, Invitation.candidate_id == candidate_id
        )
    ).all()
    for old in existing:
        if old.need_id != need_id:  # another vacancy / standalone is a separate scenario
            continue
        status = S(old.status)
        if status in OPEN_STATES or status in CONTACT_STATES:
            raise InvitationError("an active invitation to this candidate already exists")
        if status == S.DECLINED and need_id is not None:
            raise InvitationError("candidate already declined an invitation for this need")
    inv = Invitation(
        employer_id=employer_id,
        candidate_id=candidate_id,
        need_id=need_id,
        match_run_id=match_run_id,
        company=company or employer.company_name,
        role=role or (need.title if need else ""),
        description=description,
        salary_from=salary_from,
        salary_to=salary_to,
        salary_type=salary_type,
        work_format=work_format,
        message=message,
        status=S.SENT,
    )
    if not inv.role:
        raise InvitationError("role is required")
    session.add(inv)
    session.flush()
    return inv


def mark_viewed(inv: Invitation, now: datetime | None = None) -> None:
    if S(inv.status) == S.SENT:
        transition(inv, S.VIEWED)
        inv.viewed_at = _now(now)


def accept(inv: Invitation, now: datetime | None = None) -> None:
    """Candidate consent: ACCEPTED, then contacts are unlocked in the same step."""
    now = _now(now)
    transition(inv, S.ACCEPTED)
    inv.viewed_at = inv.viewed_at or now
    inv.responded_at = now
    transition(inv, S.CONTACTS_UNLOCKED)
    inv.contacts_unlocked_at = now


def decline(inv: Invitation, now: datetime | None = None) -> None:
    now = _now(now)
    transition(inv, S.DECLINED)
    inv.responded_at = now


def contacts_for(session: Session, inv: Invitation) -> dict[str, Any] | None:
    """The ONLY place that serialises private candidate contacts for an employer."""
    if not contacts_visible(inv):
        return None
    c = session.get(Candidate, inv.candidate_id)
    return {"full_name": c.full_name, "email": c.email, "phone": c.phone}


def unlocked_contacts(session: Session, employer_id: int, candidate_id: int) -> dict | None:
    inv = session.scalar(
        select(Invitation)
        .where(Invitation.employer_id == employer_id, Invitation.candidate_id == candidate_id)
        .where(Invitation.status.in_([str(s) for s in CONTACT_STATES]))
        .order_by(Invitation.id.desc())
    )
    return contacts_for(session, inv) if inv else None


def terms(inv: Invitation) -> dict[str, Any]:
    """Everything the candidate must see BEFORE accepting, salary range included."""
    return {
        "company": inv.company,
        "role": inv.role,
        "description": inv.description,
        "salary_from": inv.salary_from,
        "salary_to": inv.salary_to,
        "salary_type": inv.salary_type,
        "work_format": inv.work_format,
        "message": inv.message,
    }


def _stamp(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def candidate_view(inv: Invitation) -> dict[str, Any]:
    return {
        "id": inv.id,
        **terms(inv),
        "status": inv.status,
        "created_at": _stamp(inv.created_at),
        "viewed_at": _stamp(inv.viewed_at),
        "responded_at": _stamp(inv.responded_at),
    }


def invitation_statuses(
    session: Session,
    employer_id: int,
    candidate_ids: list[int],
    need_id: int | None = None,
) -> dict[int, dict]:
    """Latest invitation (id, status) of this employer per candidate IN THE GIVEN SCENARIO:
    `need_id` for a vacancy context, None for standalone (pool / profile without a need)."""
    if not candidate_ids:
        return {}
    cond = Invitation.need_id.is_(None) if need_id is None else Invitation.need_id == need_id
    rows = session.scalars(
        select(Invitation)
        .where(Invitation.employer_id == employer_id, Invitation.candidate_id.in_(candidate_ids))
        .where(cond)
        .order_by(Invitation.id)
    )
    return {r.candidate_id: {"invitation_id": r.id, "invitation_status": str(r.status)} for r in rows}


def annotate(
    session: Session,
    employer_id: int,
    candidates: list[dict[str, Any]],
    need_id: int | None = None,
) -> None:
    """Adds invitation_id / invitation_status (or None) to public candidate dicts in place."""
    found = invitation_statuses(
        session, employer_id, [c["candidate_id"] for c in candidates], need_id
    )
    for c in candidates:
        info = found.get(c["candidate_id"], {})
        c["invitation_id"] = info.get("invitation_id")
        c["invitation_status"] = info.get("invitation_status")


def employer_view(session: Session, inv: Invitation) -> dict[str, Any]:
    from fsp_market.matching.facts import load_candidate_facts
    from fsp_market.matching.service import public_candidate

    cand = session.get(Candidate, inv.candidate_id)
    card = public_candidate(cand, load_candidate_facts(session, [cand])[cand.id]) if cand else None
    out = {
        "id": inv.id,
        "candidate_id": inv.candidate_id,
        "candidate": (
            {
                k: card[k]
                for k in (
                    "display_name",
                    "specialization",
                    "claimed_grade",
                    "verification_status",
                    "verified_grade",
                    "verified_sublevel",
                )
            }
            if card
            else None
        ),
        "need_id": inv.need_id,
        **terms(inv),
        "status": inv.status,
        "created_at": _stamp(inv.created_at),
        "viewed_at": _stamp(inv.viewed_at),
        "responded_at": _stamp(inv.responded_at),
        "contacts_unlocked": contacts_visible(inv),
    }
    contacts = contacts_for(session, inv)
    if contacts is not None:  # key is absent (not null) while locked
        out["contacts"] = contacts
    return out
