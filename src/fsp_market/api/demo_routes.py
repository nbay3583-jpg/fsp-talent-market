"""Demo-only helpers, active ONLY when DEMO_MODE=true (404 otherwise).

demo-login issues a token for a fixed fixture account (there are no passwords in the MVP; the real
path is registration, later Keycloak / FSP ID). reference-answers reveals the correct options of the
caller's OWN assessment so a jury can walk the flow in minutes; it must never be enabled in production.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.api.deps import CandidateDep, SessionDep
from fsp_market.assessments.models import AssessmentAttempt
from fsp_market.assessments.service import select_variants
from fsp_market.auth.tokens import create_token
from fsp_market.candidates.models import Candidate
from fsp_market.config import get_settings
from fsp_market.demo import DEMO_ACCOUNTS
from fsp_market.employers.models import Employer

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoLoginIn(BaseModel):
    account: str


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="demo mode is disabled")


@router.get("/config")
def demo_config() -> dict[str, Any]:
    on = get_settings().demo_mode
    return {
        "demo_mode": on,
        "accounts": (
            [
                {"key": k, **{f: v for f, v in a.items() if f != "email"}}
                for k, a in DEMO_ACCOUNTS.items()
            ]
            if on
            else []
        ),
    }


@router.post("/login")
def demo_login(body: DemoLoginIn, session: Session = SessionDep) -> dict[str, Any]:
    _require_demo()
    account = DEMO_ACCOUNTS.get(body.account)
    if account is None:
        raise HTTPException(status_code=404, detail="unknown demo account")
    secret = get_settings().jwt_secret
    if account["role"] == "employer":
        row = session.scalar(select(Employer).where(Employer.contact_email == account["email"]))
    else:
        row = session.scalar(select(Candidate).where(Candidate.email == account["email"]))
    if row is None:
        raise HTTPException(
            status_code=409, detail="demo data not seeded (run: python -m fsp_market.demo seed)"
        )
    token = create_token(row.id, secret, ttl_seconds=8 * 3600, role=str(account["role"]))
    return {
        "role": account["role"],
        "id": row.id,
        "access_token": token,
        "fsp_id": account["fsp_id"],
    }


@router.get("/assessments/{attempt_id}/reference-answers")
def reference_answers(
    attempt_id: int, candidate_id: int = CandidateDep, session: Session = SessionDep
) -> dict[str, Any]:
    _require_demo()
    attempt = session.get(AssessmentAttempt, attempt_id)
    if attempt is None or attempt.candidate_id != candidate_id:
        raise HTTPException(status_code=404, detail="assessment not found")
    variants = select_variants(session, attempt.target_grade, attempt.id)
    return {"answers": {str(v.id): v.scoring_contract["correct"] for v in variants}}
