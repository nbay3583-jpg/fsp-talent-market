"""Demo seed: python -m fsp_market.demo  (run `alembic upgrade head` first).

Seeds the Backend/Python assessment content and two demo candidates:
  * demo.fsp@example.com    -> FSP-1001 (has FSP history)
  * demo.nofsp@example.com  -> FSP-2002 (verified member, NO achievements) / no FSP at all
Prints bearer tokens so the flow can be driven with curl or the OpenAPI docs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.seed import seed_backend_python
from fsp_market.auth.tokens import create_token
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade
from fsp_market.config import get_settings
from fsp_market.db import get_engine
from fsp_market.taxonomy.models import Specialization

DEMO_CANDIDATES = (
    ("demo.fsp@example.com", "Alexey Demo", "FSP-1001"),
    ("demo.nofsp@example.com", "Nina Newcomer", "FSP-2002"),
)


def seed_demo(session: Session) -> list[tuple[Candidate, str]]:
    seed_backend_python(session)
    spec = session.scalar(select(Specialization).where(Specialization.code == "backend_python"))
    out = []
    for email, name, fsp_id in DEMO_CANDIDATES:
        cand = session.scalar(select(Candidate).where(Candidate.email == email))
        if cand is None:
            cand = Candidate(
                email=email, full_name=name, specialization_id=spec.id, claimed_grade=Grade.MIDDLE
            )
            session.add(cand)
            session.flush()
        out.append((cand, fsp_id))
    session.commit()
    return out


def main() -> None:
    with Session(get_engine()) as session:
        for cand, fsp_id in seed_demo(session):
            token = create_token(cand.id, get_settings().jwt_secret, ttl_seconds=7 * 24 * 3600)
            print(f"{cand.email}  id={cand.id}  fsp_id={fsp_id}\n  token={token}")


if __name__ == "__main__":
    main()
