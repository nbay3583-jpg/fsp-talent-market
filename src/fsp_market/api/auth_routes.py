"""Sign-in for existing accounts: password, or a one-time email code (also account recovery)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fsp_market.api.deps import SessionDep
from fsp_market.auth import credentials as cred
from fsp_market.auth.tokens import create_token
from fsp_market.candidates.models import Candidate
from fsp_market.config import get_settings
from fsp_market.employers.models import Employer
from fsp_market.notifications.email import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
SESSION_TTL = 12 * 3600
_GENERIC = "invalid credentials"


class LoginIn(BaseModel):
    role: Literal["candidate", "employer"]
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class CodeRequestIn(BaseModel):
    role: Literal["candidate", "employer"]
    email: str = Field(min_length=3, max_length=255)


class CodeVerifyIn(CodeRequestIn):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str | None = Field(default=None, min_length=cred.MIN_PASSWORD, max_length=200)


def _find(session: Session, role: str, email: str) -> Candidate | Employer | None:
    e = email.strip().lower()
    if role == "candidate":
        return session.scalar(select(Candidate).where(func.lower(Candidate.email) == e))
    return session.scalar(select(Employer).where(func.lower(Employer.contact_email) == e))


def _session_payload(role: str, acct: Candidate | Employer) -> dict[str, Any]:
    token = create_token(acct.id, get_settings().jwt_secret, ttl_seconds=SESSION_TTL, role=role)
    return {"role": role, "id": acct.id, "access_token": token}


@router.post("/login")
def login(body: LoginIn, session: Session = SessionDep) -> dict[str, Any]:
    acct = _find(session, body.role, body.email)
    if acct is not None and (wait := cred.locked_seconds(acct)):
        raise HTTPException(status_code=429, detail=f"too many attempts, retry in {wait}s")
    if acct is None or not cred.check_password(body.password, acct.password_hash):
        if acct is not None:
            cred.note_failure(acct)
            session.commit()
        raise HTTPException(status_code=401, detail=_GENERIC)
    cred.note_success(acct)
    session.commit()
    return _session_payload(body.role, acct)


@router.post("/code/request", status_code=202)
def request_code(body: CodeRequestIn, session: Session = SessionDep) -> dict[str, Any]:
    """Always answers the same way, so it cannot be used to discover which emails are registered."""
    out: dict[str, Any] = {"accepted": True}
    acct = _find(session, body.role, body.email)
    if acct is None:
        return out
    key = f"{body.role}:{acct.id}"
    code = cred.issue_code(acct, key)
    session.commit()
    if code is None:
        return out
    to = acct.email if body.role == "candidate" else acct.contact_email
    sent = send_email(
        to,
        "FSP Talent Market: код для входа",
        f"Ваш одноразовый код: {code}\nОн действует {cred.CODE_TTL_MINUTES} минут. "
        "Если вы не запрашивали вход, проигнорируйте письмо.",
    )
    if not sent and get_settings().demo_mode:  # demo only: no SMTP configured
        out["demo_code"] = code
    return out


@router.post("/code/verify")
def verify_code(body: CodeVerifyIn, session: Session = SessionDep) -> dict[str, Any]:
    acct = _find(session, body.role, body.email)
    if acct is not None and (wait := cred.locked_seconds(acct)):
        raise HTTPException(status_code=429, detail=f"too many attempts, retry in {wait}s")
    ok = acct is not None and cred.consume_code(acct, f"{body.role}:{acct.id}", body.code)
    if not ok:
        if acct is not None:
            cred.note_failure(acct)
        session.commit()
        raise HTTPException(status_code=401, detail="invalid or expired code")
    cred.note_success(acct)
    if body.new_password:  # recovery: the code proved ownership of the mailbox
        acct.password_hash = cred.hash_password(body.new_password)
    if body.role == "candidate":
        acct.email_verified = True
    session.commit()
    return _session_payload(body.role, acct)
