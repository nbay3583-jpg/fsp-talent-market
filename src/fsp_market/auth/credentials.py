"""Password and one-time-code sign-in for candidates and employers (stdlib only).

Passwords: scrypt with a per-user salt. One-time codes: 6 digits, HMAC-hashed, 15 min, 5 attempts.
Brute force: 5 failed passwords lock the account for 15 minutes.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.config import get_settings

MAX_FAILURES = 5
LOCK_MINUTES = 15
CODE_TTL_MINUTES = 15
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_SECONDS = 30
MIN_PASSWORD = 8
_N, _R, _P = 2**14, 8, 1


class CredentialsMixin:
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    login_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    login_code_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_code_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_code_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str | None) -> bool:
    if not stored:
        hashlib.scrypt(b"x", salt=b"0" * 16, n=_N, r=_R, p=_P, dklen=32)  # keep timing similar
        return False
    try:
        _, salt, digest = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=_N, r=_R, p=_P, dklen=32)
        return hmac.compare_digest(got.hex(), digest)
    except ValueError:
        return False


def locked_seconds(acct: Any) -> int:
    if acct.login_locked_until is None:
        return 0
    return max(int((_aware(acct.login_locked_until) - _now()).total_seconds()), 0)


def note_failure(acct: Any) -> None:
    acct.login_failures = (acct.login_failures or 0) + 1
    if acct.login_failures >= MAX_FAILURES:
        acct.login_locked_until = _now() + timedelta(minutes=LOCK_MINUTES)
        acct.login_failures = 0


def note_success(acct: Any) -> None:
    acct.login_failures = 0
    acct.login_locked_until = None


def _code_hash(code: str, acct_key: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{acct_key}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(acct: Any, acct_key: str) -> str | None:
    """Returns the plaintext code, or None while the resend cooldown is running."""
    if acct.login_code_sent_at is not None:
        age = (_now() - _aware(acct.login_code_sent_at)).total_seconds()
        if age < CODE_RESEND_SECONDS:
            return None
    code = f"{secrets.randbelow(10**6):06d}"
    acct.login_code_hash = _code_hash(code, acct_key)
    acct.login_code_expires = _now() + timedelta(minutes=CODE_TTL_MINUTES)
    acct.login_code_sent_at = _now()
    acct.login_code_attempts = 0
    return code


def consume_code(acct: Any, acct_key: str, code: str) -> bool:
    """Single use; wrong guesses are counted and the code dies after CODE_MAX_ATTEMPTS."""
    if not acct.login_code_hash or acct.login_code_expires is None:
        return False
    if _aware(acct.login_code_expires) < _now() or acct.login_code_attempts >= CODE_MAX_ATTEMPTS:
        acct.login_code_hash = None
        return False
    if not hmac.compare_digest(acct.login_code_hash, _code_hash(code, acct_key)):
        acct.login_code_attempts += 1
        return False
    acct.login_code_hash = None
    acct.login_code_expires = None
    return True

