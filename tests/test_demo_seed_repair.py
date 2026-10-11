"""Production regression: dataset/demo candidates seeded before email_verified existed must stay in pools."""

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market import demo
from fsp_market.candidates.models import Candidate
from fsp_market.db import Base


def test_seed_repairs_unverified_demo_candidates_but_not_real_ones():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        demo.seed(s)
        total = s.scalar(select(func.count()).select_from(Candidate))
        s.execute(update(Candidate).values(email_verified=False))  # state of the old production DB
        s.add(Candidate(email="real@person.io", full_name="Real Person", claimed_grade="JUNIOR", password_hash="x"))
        s.commit()
        demo.seed(s)
        verified = s.scalar(select(func.count()).select_from(Candidate).where(Candidate.email_verified.is_(True)))
        assert verified == total                                    # every seeded fixture is verified again
        real = s.scalar(select(Candidate).where(Candidate.email == "real@person.io"))
        assert real.email_verified is False                         # a real registrant is never auto-verified
