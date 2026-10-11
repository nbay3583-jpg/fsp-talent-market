"""Demo state: python -m fsp_market.demo {seed|reset|accounts}  (run `alembic upgrade head` first).

seed   idempotent: assessment content, 22 matching-demo candidates + 34 extra generated profiles (58 total incl. 2 fresh), two FRESH canonical-demo
       candidates (never assessed), the demo employer. Safe to re-run.
reset  deletes ALL application rows, then seeds again -> canonical demo is back to its start.
       The validation dataset is separate (in-memory, see fsp_market.validation) and is not touched.
Demo accounts are local fixtures only: there are no passwords and no real secrets.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401  (registers every table)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade, SalaryType
from fsp_market.config import get_settings
from fsp_market.db import Base, get_engine
from fsp_market.evidence.service import add_professional_experience
from fsp_market.matching.demo_extra import seed_demo_extra
from fsp_market.matching.demo_seed import seed_matching_demo
from fsp_market.taxonomy.models import Specialization

# key -> (role, email, display label, FSP id to suggest when linking, description)
DEMO_ACCOUNTS: dict[str, dict[str, str | None]] = {
    "candidate_alexey": {
        "role": "candidate",
        "email": "alexey@demo.example",
        "label": "Алексей Демо (кандидат, есть история ФСП)",
        "fsp_id": "FSP-1001",
        "note": "Основной демо-сценарий: оценка ещё не пройдена. Пройдите основную оценку компетенций, затем подключите FSP-1001.",
    },
    "candidate_mila": {
        "role": "candidate",
        "email": "mila@demo.example",
        "label": "Мила — новый кандидат (без истории ФСП)",
        "fsp_id": "FSP-2002",
        "note": "Оценка ещё не пройдена. Участник ФСП без достижений — сценарий показывает, что отсутствие истории ФСП не мешает подбору.",
    },
    "candidate_verified": {
        "role": "candidate",
        "email": "anna@demo.example",
        "label": "Анна — профиль подтверждён (Middle)",
        "fsp_id": None,
        "note": "Оценка уже пройдена. Можно посмотреть готовый профиль подтверждённых компетенций и получение приглашений.",
    },
    "candidate_not_verified": {
        "role": "candidate",
        "email": "hana@demo.example",
        "label": "Хана — грейд не подтверждён (Middle)",
        "fsp_id": None,
        "note": "Middle не подтверждён. Заявленный грейд Middle сохраняется — автоматического понижения до Junior нет.",
    },
    "candidate_salary_mismatch": {
        "role": "candidate",
        "email": "fedor@demo.example",
        "label": "Фёдор — зарплата выше бюджета (300 000 ₽)",
        "fsp_id": None,
        "note": "Ожидаемая зарплата выше бюджета демо-вакансии — кандидат исключается обязательным ограничением.",
    },
    "employer": {
        "role": "employer",
        "email": "hr@demo-corp.example",
        "label": "Демо-компания (работодатель)",
        "fsp_id": None,
        "note": "Демо-работодатель. Создайте потребность и запустите подбор кандидатов.",
    },
}

FRESH = (
    ("alexey@demo.example", "Alexey Demo", "+7-900-111-22-33", 225000),
    ("mila@demo.example", "Mila Newcomer", "+7-900-444-55-66", 215000),
)


def repair_seeded_verification(session: Session) -> int:
    """Seeded fixtures (@demo.example, no password) are published by definition. Rows created before
    the seed set email_verified would otherwise drop out of every pool since publication requires it."""
    rows = session.scalars(
        select(Candidate).where(
            Candidate.email.like("%@demo.example"),
            Candidate.password_hash.is_(None),
            Candidate.email_verified.is_(False),
        )
    ).all()
    for row in rows:
        row.email_verified = True
    return len(rows)


def seed(session: Session) -> dict:
    ids = seed_matching_demo(session, with_need=False)
    seed_demo_extra(session)
    repair_seeded_verification(session)
    spec = session.scalar(select(Specialization).where(Specialization.code == "backend_python"))
    for email, name, phone, salary in FRESH:
        if session.scalar(select(Candidate).where(Candidate.email == email)) is None:
            row = Candidate(
                email=email,
                full_name=name,
                phone=phone,
                specialization_id=spec.id,
                claimed_grade=Grade.MIDDLE,
                salary_min=salary,
                salary_type=SalaryType.GROSS,
                work_formats=["REMOTE"],
                location="Moscow",
                available_in_days=14,
                profile_visible=True,
                email_verified=True,
                open_to_invitations=True,
            )
            session.add(row)
            session.flush()
            # professional experience is separate, medium-strength evidence; it never sets the grade
            add_professional_experience(
                session,
                row.id,
                "postgresql",
                "PostgreSQL в продакшене",
                created_at=datetime.now(UTC) - timedelta(days=60),
            )
    session.commit()
    return ids


def reset(session: Session) -> dict:
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    return seed(session)


def main() -> None:
    parser = argparse.ArgumentParser(prog="fsp_market.demo")
    parser.add_argument("command", choices=["seed", "reset", "accounts"])
    parser.add_argument(
        "--if-demo-mode", action="store_true", help="do nothing unless DEMO_MODE=true"
    )
    args = parser.parse_args()
    if args.command == "accounts":
        for key, a in DEMO_ACCOUNTS.items():
            print(f"{key:28} {a['email']:28} {a['label']}")
        return
    if args.if_demo_mode and not get_settings().demo_mode:
        print("DEMO_MODE is off: demo data not seeded")
        return
    with Session(get_engine()) as session:
        (reset if args.command == "reset" else seed)(session)
    print(f"demo {args.command}: ok")


if __name__ == "__main__":
    main()
