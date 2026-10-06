from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from fsp_market.auth.tokens import InvalidToken, verify_token
from fsp_market.config import get_settings
from fsp_market.db import get_session
from fsp_market.fsp.provider import FSPProvider, MockFSPProvider


def get_fsp_provider() -> FSPProvider:
    return MockFSPProvider()


def current_candidate_id(authorization: str | None = Header(default=None)) -> int:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return verify_token(token, get_settings().jwt_secret)
    except InvalidToken as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


SessionDep = Depends(get_session)
CandidateDep = Depends(current_candidate_id)
ProviderDep = Depends(get_fsp_provider)
__all__ = ["CandidateDep", "ProviderDep", "Session", "SessionDep"]


def current_employer_id(authorization: str | None = Header(default=None)) -> int:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return verify_token(token, get_settings().jwt_secret, role="employer")
    except InvalidToken as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


EmployerDep = Depends(current_employer_id)
