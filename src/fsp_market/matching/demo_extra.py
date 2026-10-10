"""Extra synthetic demo candidates (34) on top of the 22 hand-written matching-demo personas.

Deterministic (fixed RNG seed), idempotent (by e-mail), used only by `python -m fsp_market.demo seed`
so the jury sees a pool of ~56 varied profiles; the hand-written set that the tests assert on is
left untouched. Names are invented; every account is a local fixture.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade, SalaryType
from fsp_market.evidence.service import add_professional_experience, add_self_reported_claim
from fsp_market.matching.demo_seed import run_core_assessment
from fsp_market.taxonomy.models import Specialization

FIRST = ["Ilya", "Maria", "Artem", "Sofia", "Roman", "Alisa", "Timur", "Polina", "Gleb", "Vera",
         "Nikita", "Daria", "Egor", "Alina", "Maxim", "Kristina", "Denis", "Olga", "Anton", "Zoya",
         "Stepan", "Irina", "Kirill", "Lada", "Matvey", "Ksenia", "Fedor", "Yana", "Leon", "Emma",
         "Ruslan", "Nadia", "Oleg", "Varya"]
LAST = ["Kuznetsov", "Smirnova", "Volkov", "Popova", "Sokolov", "Lebedeva", "Kozlov", "Novikova",
        "Morozov", "Petrova", "Orlov", "Belova", "Zaitsev", "Gusev", "Titov", "Fomina", "Davydov",
        "Kiselev", "Sorokin", "Medvedeva", "Tarasov", "Belyaev", "Komarov", "Nikitin", "Frolov",
        "Zhukova", "Makarov", "Vlasova", "Kalinin", "Mironova", "Antonov", "Rogov", "Suvorov", "Sidorova"]
CITIES = ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk", "Yekaterinburg", "Nizhny Novgorod",
          "Samara", "Tomsk", "Krasnodar", "Perm"]
SALARY = {"JUNIOR": (60000, 110000), "MIDDLE": (150000, 260000), "SENIOR": (260000, 400000)}
FORMATS = [["REMOTE"], ["REMOTE", "HYBRID"], ["HYBRID"], ["OFFICE", "HYBRID"], ["REMOTE", "OFFICE"]]
# (claimed grade, assessed grade | None, wrong competencies, count) -- outcomes depend on bank size
PLAN = [
    ("MIDDLE", "MIDDLE", set(), 4),
    ("MIDDLE", "MIDDLE", {"testing", "docker_basics"}, 4),
    ("MIDDLE", "MIDDLE", {"python"}, 2),
    ("MIDDLE", "MIDDLE", {"testing", "docker_basics", "system_thinking"}, 2),
    ("MIDDLE", "MIDDLE", {"testing", "docker_basics", "system_thinking", "api_fastapi"}, 2),  # not verified
    ("JUNIOR", "JUNIOR", set(), 4),
    ("JUNIOR", "JUNIOR", {"docker_basics", "system_thinking"}, 2),
    ("JUNIOR", "JUNIOR", {"python", "sql"}, 2),  # not verified
    ("SENIOR", "SENIOR", set(), 2),
    ("SENIOR", "SENIOR", {"testing"}, 3),
    ("SENIOR", "SENIOR", {"python", "sql"}, 1),  # not verified
    ("MIDDLE", None, set(), 3),  # registered, assessment not taken yet
    ("JUNIOR", None, set(), 2),
    ("SENIOR", None, set(), 1),
]


def seed_demo_extra(session: Session, now: datetime | None = None) -> int:
    """Create the extra candidates; return how many were added."""
    now = now or datetime.now(UTC)
    rng = random.Random("fsp-demo-extra-2026-10")
    specs = {s.code: s.id for s in session.scalars(select(Specialization))}
    rows = [row for row in PLAN for _ in range(row[3])]
    names = [(f, l) for f, l in zip(FIRST, LAST, strict=True)]
    rng.shuffle(names)
    added = 0
    for n, (claimed, assessed, wrong, _) in enumerate(rows):
        first, last = names[n]
        email = f"{first.lower()}.{last.lower()}@demo.example"
        if session.scalar(select(Candidate).where(Candidate.email == email)):
            continue
        lo, hi = SALARY[claimed]
        frontend = assessed is None and n % 2 == 0  # unassessed profiles: some are Frontend
        cand = Candidate(
            email=email,
            full_name=f"{first} {last}",
            specialization_id=specs["frontend_ts" if frontend else "backend_python"],
            claimed_grade=Grade(claimed),
            salary_min=rng.randrange(lo, hi, 10000),
            salary_type=SalaryType.GROSS if n % 3 else SalaryType.NET,
            work_formats=rng.choice(FORMATS),
            location=rng.choice(CITIES),
            profile_visible=n % 17 != 16,  # a couple are hidden from employers
            email_verified=True,
            open_to_invitations=n % 11 != 10,
            available_in_days=rng.choice([0, 7, 14, 30, 60]),
            phone=f"+7-901-{100 + n:03d}-00-{n:02d}",
        )
        session.add(cand)
        session.flush()
        if not frontend:
            for skill in rng.sample(["postgresql", "kafka"], rng.choice([0, 1, 1, 2])):
                add_professional_experience(
                    session, cand.id, skill, f"{skill} in production",
                    created_at=now - timedelta(days=rng.choice([20, 60, 150, 400])),
                )
            if rng.random() < 0.4:
                add_self_reported_claim(session, cand.id, "postgresql", Grade(claimed), "from CV")
        if assessed:
            run_core_assessment(session, cand, assessed, wrong, now)
        added += 1
    session.commit()
    return added
