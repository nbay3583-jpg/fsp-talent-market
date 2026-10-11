"""Opt-in, idempotent importer of fictional FSP demo candidates.

Integration: place this module at src/fsp_market/demo_cv_import.py and the JSON
at artifacts/fsp_synthetic_candidates.json. Build the existing FSP backend image.

  python -m fsp_market.demo_cv_import                 # read-only dry run
  python -m fsp_market.demo_cv_import --apply         # writes, DEMO_MODE only

This module is intentionally NOT invoked by startup, Alembic or normal demo seed.
It does not copy or ingest any of the source CVs. Existing profiles are never updated.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401  (SQLAlchemy registry)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade, SalaryType, VerificationStatus
from fsp_market.config import get_settings
from fsp_market.db import get_engine
from fsp_market.evidence.service import add_self_reported_claim
from fsp_market.experience.models import WorkExperience
from fsp_market.skills.models import Skill
from fsp_market.taxonomy.models import Specialization

DEFAULT_DATA = Path("artifacts/fsp_synthetic_candidates.json")
FORMATS = {"REMOTE", "OFFICE", "HYBRID"}
SPECS = {"backend_python", "frontend_ts"}


def validate_dataset(obj: dict) -> list[dict]:
    if obj.get("dataset_kind") != "synthetic_demo_only" or obj.get("schema_version") != 1:
        raise ValueError("Only synthetic_demo_only schema_version=1 datasets are allowed")
    candidates = obj.get("profiles")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Missing profiles")
    seen = set()
    for c in candidates:
        key = c["email"]
        if not key.startswith("cv-syn-") or not key.endswith("@demo.example") or key in seen:
            raise ValueError("Not an isolated unique synthetic demo email")
        seen.add(key)
        if not c.get("is_synthetic") or c.get("specialization") not in SPECS:
            raise ValueError("Only synthetic candidates with existing supported specialization")
        Grade(c["claimed_grade"])
        SalaryType(c["salary_type"])
        if not c.get("work_formats") or not set(c["work_formats"]).issubset(FORMATS):
            raise ValueError("Invalid work formats")
        if not isinstance(c.get("salary_min"),int) or not 30000<=c["salary_min"]<=1000000:
            raise ValueError("Invalid synthetic salary")
        if any(k in c for k in ("phone", "url", "telegram", "resume", "full_cv")):
            raise ValueError("Dataset must not contain external contacts or raw resumes")
        for e in c["experience"]:
            if e["company"] != "Синтетическая демо-компания":
                raise ValueError("Only invented non-identifying company allowed")
            date.fromisoformat(e["start_date"])
            if e.get("end_date"):
                date.fromisoformat(e["end_date"])
    return candidates


def import_profiles(session: Session, obj: dict, apply: bool) -> dict:
    """Validate and (optionally) insert missing profiles. Existing e-mails are never touched."""
    profiles = validate_dataset(obj)
    specs = {s.code: s.id for s in session.scalars(select(Specialization))}
    skills = {s.code: s.id for s in session.scalars(select(Skill))}
    if not SPECS.issubset(specs):
        raise SystemExit("Missing specializations; run existing demo seed first")
    for p in profiles:
        unknown = (set(p["skill_claims"]) | {k for e in p["experience"] for k in e["stack"]}) - skills.keys()
        if unknown:
            raise SystemExit(f"Unknown skill codes in dataset: {sorted(unknown)}")
    emails = {p["email"] for p in profiles}
    already = set(session.scalars(select(Candidate.email).where(Candidate.email.in_(emails))))
    new = [p for p in profiles if p["email"] not in already]
    result = {"total": len(profiles), "existing": len(already), "to_add": len(new), "added": 0}
    if not apply:
        return result
    for p in new:
        c = Candidate(
            email=p["email"], full_name=p["full_name"],
            specialization_id=specs[p["specialization"]],
            claimed_grade=Grade(p["claimed_grade"]),
            verification_status=VerificationStatus.UNVERIFIED,
            verified_grade=None, verified_sublevel=None,
            salary_min=p["salary_min"], salary_type=SalaryType(p["salary_type"]),
            work_formats=p["work_formats"], location=p["location"],
            available_in_days=p["available_in_days"],
            email_verified=True, profile_visible=p["profile_visible"],
            open_to_invitations=p["open_to_invitations"], phone=None,
        )
        session.add(c)
        session.flush()
        for code in p["skill_claims"]:
            add_self_reported_claim(session, c.id, code, Grade(p["claimed_grade"]),
                                    "Синтетический демо-профиль; навыки заявлены, не подтверждены")
        for ex in p["experience"]:
            session.add(WorkExperience(
                candidate_id=c.id, company=ex["company"], position=ex["position"],
                start_date=date.fromisoformat(ex["start_date"]),
                end_date=date.fromisoformat(ex["end_date"]) if ex["end_date"] else None,
                stack=ex["stack"], tasks=ex["tasks"], projects=ex["projects"],
                achievements=ex["achievements"],
            ))
    session.commit()
    result["added"] = len(new)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Import fictional FSP demo candidates (opt in)")
    ap.add_argument("--file", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--apply", action="store_true", help="explicitly insert missing profiles")
    args = ap.parse_args()
    if not get_settings().demo_mode:
        raise SystemExit("Refusing to run: DEMO_MODE is not enabled")
    obj = json.loads(args.file.read_text(encoding="utf-8"))
    with Session(get_engine()) as session:
        r = import_profiles(session, obj, args.apply)
    print(f"dataset={obj['dataset_id']} total={r['total']} existing={r['existing']} to_add={r['to_add']} apply={args.apply}")
    if not args.apply:
        print("DRY RUN: database unchanged. Add --apply after explicit approval.")
    else:
        print(f"IMPORTED {r['added']} synthetic-only candidate(s), skipped {r['existing']} existing. "
              "No verification grades or contacts were created.")


if __name__ == "__main__":
    main()
