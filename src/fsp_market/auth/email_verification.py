"""One-time email verification tokens: random, only the SHA-256 is stored, single-use, expiring."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.config import get_settings
from fsp_market.notifications.email import send_email

RESEND_COOLDOWN_SECONDS = 60


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def issue_verification(session: Session, cand: Candidate) -> bool:
    """Creates a fresh token (invalidating the previous one) and emails the link."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    now = _now()
    cand.email_token_hash = _hash(token)
    cand.email_token_expires = now + timedelta(hours=settings.email_token_ttl_hours)
    cand.email_token_sent_at = now
    session.flush()
    link = f"{settings.public_base_url.rstrip('/')}/?verify_email={token}"
    return send_email(
        cand.email,
        "FSP Talent Market: подтвердите email",
        f"Здравствуйте, {cand.full_name}!\n\nПодтвердите адрес, перейдя по ссылке "
        f"(действует {settings.email_token_ttl_hours} ч):\n{link}\n\n"
        "Если вы не регистрировались, просто проигнорируйте письмо.",
    )


def cooldown_left(cand: Candidate) -> int:
    if cand.email_token_sent_at is None:
        return 0
    left = RESEND_COOLDOWN_SECONDS - int((_now() - _aware(cand.email_token_sent_at)).total_seconds())
    return max(left, 0)


def confirm(session: Session, token: str) -> Candidate | None:
    """Single-use: the stored hash is cleared on success. Returns None for any invalid token."""
    digest = _hash(token)
    cand = session.scalar(select(Candidate).where(Candidate.email_token_hash == digest))
    if cand is None or not hmac.compare_digest(cand.email_token_hash or "", digest):
        return None
    if cand.email_token_expires is None or _aware(cand.email_token_expires) < _now():
        return None
    cand.email_verified = True
    cand.email_token_hash = None
    cand.email_token_expires = None
    session.flush()
    return cand
