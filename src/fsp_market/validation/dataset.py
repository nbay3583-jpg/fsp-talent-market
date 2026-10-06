"""Loads the fixed validation dataset and materialises it through the REAL pipeline
(Core Assessment -> evidence -> matching facts); nothing is faked at the database level."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fsp_market.assessments.seed import seed_backend_python
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import EvidenceType, Grade, SalaryType, Sublevel
from fsp_market.employers.models import Employer
from fsp_market.evidence.fsp_link import attach_fsp_evidence
from fsp_market.evidence.service import add_professional_experience, add_self_reported_claim
from fsp_market.fsp.provider import FSPAchievement, FSPMember, MockFSPProvider
from fsp_market.matching.demo_seed import run_core_assessment
from fsp_market.matching.service import create_need
from fsp_market.skills.models import Skill, SkillEvidence
from fsp_market.taxonomy.models import Specialization

DATA_DIR = Path(__file__).parent / "data"
FILES = ("candidates.json", "needs.json", "relevance.json")
REFERENCE_DATE = datetime(2026, 10, 6, tzinfo=UTC)
EXTRA_SKILLS = {"postgresql": "PostgreSQL", "kafka": "Kafka"}
# résumé keyword -> platform skill code (the keyword baseline and the claims use this mapping)
KEYWORD_SKILL = {
    "python": "python",
    "sql": "sql",
    "fastapi": "api_fastapi",
    "postgresql": "postgresql",
    "kafka": "kafka",
    "docker": "docker_basics",
    "testing": "testing",
    "system design": "system_thinking",
}
FSP_TITLES = {
    "algorithmic_programming": "FSP Algorithmic Programming (validation fixture)",
    "product_programming": "FSP Product Programming (validation fixture)",
    "cybersecurity": "FSP Cybersecurity (validation fixture)",
}


def _read(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def dataset_sha256() -> str:
    h = hashlib.sha256()
    for name in FILES:
        h.update(name.encode())
        h.update((DATA_DIR / name).read_bytes())
    return h.hexdigest()


def load_dataset() -> tuple[list[dict], list[dict], dict]:
    cands, needs, labels = (_read(n) for n in FILES)
    return cands["candidates"], needs["needs"], labels


def relevance_grades(labels: dict, need_id: str) -> dict[str, int]:
    return {c: int(v[0]) for c, v in labels["labels"][need_id].items()}


def build_database(session: Session, cands: list[dict], needs: list[dict]) -> dict:
    """Returns {'cand': {vid: db_id}, 'need': {vid: db_id}}."""
    now = REFERENCE_DATE
    seed_backend_python(session)
    session.add(Specialization(code="frontend_ts", name="Frontend / TypeScript"))
    for code, name in EXTRA_SKILLS.items():
        session.add(Skill(code=code, name=name, competency_id=None))
    session.flush()
    specs = {s.code: s.id for s in session.scalars(select(Specialization))}
    cand_ids: dict[str, int] = {}
    for c in cands:
        sal = c["salary"]
        row = Candidate(
            email=f"{c['id'].lower()}@validation.example",
            full_name=c["name"],
            specialization_id=specs[c["specialization"]],
            claimed_grade=Grade(c["claimed_grade"]),
            salary_min=sal["min"] if sal else None,
            salary_type=SalaryType(sal["type"]) if sal else None,
            work_formats=c["work_formats"],
            location=c["location"],
            available_in_days=c["available_in_days"],
            profile_visible=c["profile_visible"],
            open_to_invitations=c["open_to_invitations"],
        )
        session.add(row)
        session.flush()
        cand_ids[c["id"]] = row.id
        for kw in c["resume_keywords"]:  # CV keywords become self-reported claims (context only)
            if kw in KEYWORD_SKILL:
                add_self_reported_claim(
                    session, row.id, KEYWORD_SKILL[kw], Grade(c["claimed_grade"]), "CV"
                )
        if c["assessment"]:
            wrong = c["assessment"]["wrong"]
            run_core_assessment(session, row, c["assessment"]["grade"], wrong, now)
        for skill, days in c["experience_days_ago"].items():
            add_professional_experience(
                session,
                row.id,
                skill,
                f"{skill} in production",
                created_at=now - timedelta(days=days),
            )
        if c["fsp_disciplines"]:
            fsp_id = f"FSP-{c['id']}"
            provider = MockFSPProvider(
                [FSPMember(fsp_id, c["name"], True)],
                [
                    FSPAchievement(f"{fsp_id}-{i}", fsp_id, d, FSP_TITLES[d], 2026, 1)
                    for i, d in enumerate(c["fsp_disciplines"])
                ],
            )
            attach_fsp_evidence(session, row.id, provider, fsp_id)
    # pin assessment evidence timestamps so freshness does not depend on the wall clock
    session.execute(
        update(SkillEvidence)
        .where(SkillEvidence.evidence_type == EvidenceType.CORE_ASSESSMENT)
        .values(created_at=now)
    )
    employer = Employer(company_name="Validation Corp", contact_email="v@validation.example")
    session.add(employer)
    session.flush()
    need_ids: dict[str, int] = {}
    for n in needs:
        sub = Sublevel(n["target_sublevel"]) if n["target_sublevel"] else None
        need = create_need(
            session,
            employer.id,
            title=n["title"],
            specialization=n["specialization"],
            target_grade=Grade(n["target_grade"]),
            target_sublevel=sub,
            required_skills=n["required_skills"],
            optional_skills=n["optional_skills"],
            salary_from=n["salary_from"],
            salary_to=n["salary_to"],
            salary_type=SalaryType(n["salary_type"]),
            work_formats=n["work_formats"],
            location=n["location"],
            max_start_days=n["max_start_days"],
            description=n["title"],
        )
        need_ids[n["id"]] = need.id
    session.commit()
    return {"cand": cand_ids, "need": need_ids}
