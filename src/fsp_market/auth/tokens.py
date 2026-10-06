"""Stateless signed bearer tokens (HMAC-SHA256). Keycloak-swappable behind the API dependency."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class InvalidToken(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def create_token(
    subject: int, secret: str, ttl_seconds: int = 3600, now: float | None = None
) -> str:
    issued = time.time() if now is None else now
    payload = _b64(json.dumps({"sub": subject, "exp": int(issued + ttl_seconds)}).encode())
    return f"{payload}.{_sign(payload, secret)}"


def verify_token(token: str, secret: str, now: float | None = None) -> int:
    payload, _, signature = token.partition(".")
    if not payload or not signature or not hmac.compare_digest(signature, _sign(payload, secret)):
        raise InvalidToken("bad signature")
    try:
        claims = json.loads(_unb64(payload))
        subject, exp = int(claims["sub"]), int(claims["exp"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidToken("malformed token") from exc
    if exp <= (time.time() if now is None else now):
        raise InvalidToken("expired")
    return subject
