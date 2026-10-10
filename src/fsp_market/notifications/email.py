"""Outgoing email. SMTP is configured through ENV (SMTP_HOST/PORT/USER/PASSWORD/FROM).

Without SMTP_HOST nothing leaves the process: the message is logged (without the secret link in
production) and kept in OUTBOX so tests and local development can read it.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from fsp_market.config import get_settings

log = logging.getLogger(__name__)
OUTBOX: list[dict[str, str]] = []  # dev/test only, capped
_OUTBOX_MAX = 100


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True when handed to an SMTP server; never raises into the request path."""
    s = get_settings()
    if not s.smtp_host:
        OUTBOX.append({"to": to, "subject": subject, "body": body})
        del OUTBOX[:-_OUTBOX_MAX]
        log.warning("SMTP is not configured: email to %s was not sent", to)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("failed to send email to %s", to)
        return False
    return True
