from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_id() -> str:
    """A new opaque string primary key (UUID4 text), portable across SQLite and PostgreSQL."""
    return str(uuid4())


def utcnow() -> datetime:
    """Timezone-aware current UTC time; the single clock used for column defaults."""
    return datetime.now(UTC)
