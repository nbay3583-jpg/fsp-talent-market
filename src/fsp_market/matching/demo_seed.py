"""Reproducible matching demo: ~22 candidates covering the conflict cases from the plan.

Verified candidates go through the REAL Core Assessment pipeline (start -> answers -> scoring),
so their evidence is genuine. Run: python -m fsp_market.matching.demo_seed
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.models import TaskFamily, TaskTemplate
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.service import (
    score_attempt,
    select_variants,
    start_attempt,
    submit_answers,
)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade, SalaryType, Sublevel
from fsp_market.employers.models import Employer
from fsp_market.evidence.fsp_link import attach_fsp_evidence
from fsp_market.evidence.service import add_professional_experience, add_self_reported_claim
from fsp_market.fsp.provider import (
    DEMO_ACHIEVEMENTS,
    DEMO_MEMBERS,
    FSPAchievement,
    FSPMember,
    MockFSPProvider,
)
from fsp_market.matching.service import create_need
from fsp_market.skills.models import Skill
from fsp_market.taxonomy.models import Competency, Specialization

EXTRA_SKILLS = {"postgresql": "PostgreSQL", "kafka": "Kafka"}
ALL = "ALL"  # every competency answered wrongly
PROVIDER = MockFSPProvider(
    DEMO_MEMBERS
    + [
        FSPMember("FSP-3003", "Cyber Only", True),
        FSPMember("FSP-4004", "Prod Dev", True),
        FSPMember("FSP-5005", "Algo Only", True),
    ],
    DEMO_ACHIEVEMENTS
    + [
        FSPAchievement("ach-4", "FSP-3003", "cybersecurity", "FSP CTF, winner", 2026, 1),
        FSPAchievement(
            "ach-5", "FSP-4004", "product_programming", "FSP Product Hackathon, finalist", 2026, 2
        ),
        FSPAchievement(
            "ach-6", "FSP-5005", "algorithmic_programming", "FSP Algo Cup, winner", 2026, 1
        ),
    ],
)

R, O, H = "REMOTE", "OFFICE", "HYBRID"
# key, name, claimed, assess (grade, wrong competencies) | None, salary (min, type) | None,
# formats, location, visible, open, experience {skill: age_days}, self-claims, fsp_id, specialization
C = [
    (
        "anna",
        "Anna Verified",
        "MIDDLE",
        ("MIDDLE", set()),
        (220000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 30},
        [],
        None,
        "backend_python",
    ),
    (
        "boris",
        "Boris Prodev",
        "MIDDLE",
        ("MIDDLE", set()),
        (230000, "GROSS"),
        [R, H],
        "Kazan",
        True,
        True,
        {"postgresql": 40},
        [],
        "FSP-4004",
        "backend_python",
    ),
    (
        "clara",
        "Clara Algo",
        "MIDDLE",
        ("MIDDLE", set()),
        (225000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 40},
        [],
        "FSP-5005",
        "backend_python",
    ),
    (
        "denis",
        "Denis Resume",
        "MIDDLE",
        ("MIDDLE", ALL),
        (210000, "GROSS"),
        [R],
        "Perth",
        True,
        True,
        {},
        ["postgresql", "kafka", "api_fastapi", "python", "sql"],
        None,
        "backend_python",
    ),
    (
        "elena",
        "Elena Quiet",
        "MIDDLE",
        ("MIDDLE", set()),
        (210000, "GROSS"),
        [R],
        "Omsk",
        True,
        True,
        {},
        [],
        None,
        "backend_python",
    ),
    (
        "fedor",
        "Fedor Expensive",
        "MIDDLE",
        ("MIDDLE", set()),
        (300000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 20},
        [],
        None,
        "backend_python",
    ),
    (
        "galina",
        "Galina Office",
        "MIDDLE",
        ("MIDDLE", set()),
        (200000, "GROSS"),
        [O],
        "Moscow",
        True,
        True,
        {"postgresql": 20},
        [],
        None,
        "backend_python",
    ),
    (
        "hana",
        "Hana Almost",
        "MIDDLE",
        ("MIDDLE", {"testing", "docker_basics"}),
        (205000, "GROSS"),
        [R],
        "Sochi",
        True,
        True,
        {"postgresql": 60},
        [],
        None,
        "backend_python",
    ),
    (
        "julia",
        "Julia Mone",
        "MIDDLE",
        ("MIDDLE", {"testing"}),
        (200000, "GROSS"),
        [R],
        "Tula",
        True,
        True,
        {"postgresql": 90},
        [],
        None,
        "backend_python",
    ),
    (
        "kirill",
        "Kirill Junior",
        "JUNIOR",
        ("JUNIOR", set()),
        (120000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {},
        [],
        None,
        "backend_python",
    ),
    (
        "lena",
        "Lena Hidden",
        "MIDDLE",
        ("MIDDLE", set()),
        (210000, "GROSS"),
        [R],
        "Moscow",
        False,
        True,
        {"postgresql": 10},
        [],
        None,
        "backend_python",
    ),
    (
        "misha",
        "Misha Closed",
        "MIDDLE",
        ("MIDDLE", set()),
        (210000, "GROSS"),
        [R],
        "Moscow",
        True,
        False,
        {"postgresql": 10},
        [],
        None,
        "backend_python",
    ),
    (
        "nina",
        "Nina Newcomer",
        "MIDDLE",
        ("MIDDLE", set()),
        (240000, "GROSS"),
        [R],
        "Pskov",
        True,
        True,
        {"postgresql": 25},
        [],
        "FSP-2002",
        "backend_python",
    ),
    (
        "oleg",
        "Oleg Frontend",
        "MIDDLE",
        None,
        (200000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {},
        [],
        None,
        "frontend_ts",
    ),
    (
        "pavel",
        "Pavel Kafka",
        "MIDDLE",
        ("MIDDLE", set()),
        (215000, "GROSS"),
        [R],
        "Ufa",
        True,
        True,
        {"kafka": 50},
        ["postgresql"],
        None,
        "backend_python",
    ),
    (
        "rita",
        "Rita Stale",
        "MIDDLE",
        ("MIDDLE", set()),
        (215000, "GROSS"),
        [R],
        "Tver",
        True,
        True,
        {"postgresql": 600, "kafka": 600},
        [],
        None,
        "backend_python",
    ),
    (
        "sergey",
        "Sergey Untested",
        "MIDDLE",
        None,
        (200000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {},
        ["postgresql", "api_fastapi"],
        None,
        "backend_python",
    ),
    (
        "tanya",
        "Tanya Net",
        "MIDDLE",
        ("MIDDLE", set()),
        (190000, "NET"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 15},
        [],
        None,
        "backend_python",
    ),
    (
        "ulyana",
        "Ulyana Edge",
        "MIDDLE",
        ("MIDDLE", set()),
        (250000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 15},
        [],
        None,
        "backend_python",
    ),
    (
        "viktor",
        "Viktor Over",
        "MIDDLE",
        ("MIDDLE", set()),
        (250001, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {"postgresql": 15},
        [],
        None,
        "backend_python",
    ),
    (
        "xenia",
        "Xenia Nosalary",
        "MIDDLE",
        ("MIDDLE", set()),
        None,
        [R, H],
        "Moscow",
        True,
        True,
        {"postgresql": 35},
        [],
        "FSP-3003",
        "backend_python",
    ),
    (
        "yuri",
        "Yuri Junior",
        "JUNIOR",
        ("JUNIOR", ALL),
        (100000, "GROSS"),
        [R],
        "Moscow",
        True,
        True,
        {},
        [],
        None,
        "backend_python",
    ),
]


def run_core_assessment(
    session: Session, cand: Candidate, grade: str, wrong, now: datetime
) -> None:
    attempt = start_attempt(session, cand.id, Grade(grade), now=now)
    answers = {}
    for v in select_variants(session, Grade(grade), attempt.id):
        comp = session.scalar(
            select(Competency.code)
            .join(TaskFamily, TaskFamily.competency_id == Competency.id)
            .join(TaskTemplate, TaskTemplate.family_id == TaskFamily.id)
            .where(TaskTemplate.id == v.template_id)
        )
        right = v.scoring_contract["correct"]
        bad = wrong == ALL or comp in wrong
        answers[v.id] = next(k for k in "ABCD" if k != right) if bad else right
    submit_answers(session, attempt.id, answers, now=now)
    score_attempt(session, attempt.id, now=now)


def seed_matching_demo(
    session: Session, now: datetime | None = None, with_need: bool = True
) -> dict:
    now = now or datetime.now(UTC)
    seed_backend_python(session)
    spec = session.scalar(select(Specialization).where(Specialization.code == "backend_python"))
    if session.scalar(select(Specialization).where(Specialization.code == "frontend_ts")) is None:
        session.add(Specialization(code="frontend_ts", name="Frontend / TypeScript"))
    for code, name in EXTRA_SKILLS.items():  # skills outside the six core competencies
        if session.scalar(select(Skill).where(Skill.code == code)) is None:
            session.add(Skill(code=code, name=name, competency_id=None))
    session.flush()
    specs = {s.code: s.id for s in session.scalars(select(Specialization))}
    for key, name, claimed, assess, sal, fmts, loc, vis, openi, exp, claims, fsp_id, sp in C:
        if session.scalar(select(Candidate).where(Candidate.email == f"{key}@demo.example")):
            continue
        cand = Candidate(
            email=f"{key}@demo.example",
            full_name=name,
            specialization_id=specs[sp],
            claimed_grade=Grade(claimed),
            salary_min=sal[0] if sal else None,
            salary_type=SalaryType(sal[1]) if sal else None,
            work_formats=fmts,
            location=loc,
            profile_visible=vis,
            open_to_invitations=openi,
            available_in_days=14,
            phone=f"+7-900-000-{len(key):02d}{ord(key[0]):03d}",
        )
        session.add(cand)
        session.flush()
        for skill in claims:
            add_self_reported_claim(session, cand.id, skill, Grade(claimed), "from CV")
        if assess:
            run_core_assessment(session, cand, assess[0], assess[1], now)
        for skill, age in exp.items():
            add_professional_experience(
                session,
                cand.id,
                skill,
                f"{skill} in production",
                created_at=now - timedelta(days=age),
            )
        if fsp_id:
            attach_fsp_evidence(session, cand.id, PROVIDER, fsp_id)
    employer = session.scalar(
        select(Employer).where(Employer.contact_email == "hr@demo-corp.example")
    )
    if employer is None:
        employer = Employer(company_name="Demo Corp", contact_email="hr@demo-corp.example")
        session.add(employer)
        session.flush()
    from fsp_market.matching.models import EmployerNeed

    need = None
    if with_need:
        need = session.scalar(select(EmployerNeed).where(EmployerNeed.employer_id == employer.id))
        if need is None:
            need = create_need(
                session,
                employer.id,
                title="Python Backend (FastAPI)",
                specialization=spec.code,
                target_grade=Grade.MIDDLE,
                target_sublevel=Sublevel.M2,
                required_skills=["api_fastapi", "postgresql"],
                optional_skills=["kafka", "docker_basics"],
                salary_from=200000,
                salary_to=250000,
                salary_type=SalaryType.GROSS,
                work_formats=[R],
                location=None,
                max_start_days=None,
                description="Remote Python backend, FastAPI + PostgreSQL",
            )
    session.commit()
    return {"employer_id": employer.id, "need_id": need.id if need else None}


def main() -> None:
    from fsp_market.auth.tokens import create_token
    from fsp_market.config import get_settings
    from fsp_market.db import get_engine

    with Session(get_engine()) as session:
        ids = seed_matching_demo(session)
    token = create_token(
        ids["employer_id"], get_settings().jwt_secret, 7 * 24 * 3600, role="employer"
    )
    print(f"employer_id={ids['employer_id']} need_id={ids['need_id']}\nemployer token={token}")


if __name__ == "__main__":
    main()
