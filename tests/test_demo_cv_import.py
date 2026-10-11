"""Synthetic CV demo dataset: opt-in importer is idempotent, never verifies anything, respects specialization."""

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.demo_cv_import import import_profiles, validate_dataset
from fsp_market.skills.models import SkillClaim, SkillEvidence
from tests.test_phase9_teamfit import NEED, _emp, env  # noqa: F401

DATA = json.loads((Path(__file__).parents[1] / "artifacts" / "fsp_synthetic_candidates.json").read_text("utf-8"))


def _count(engine):
    with Session(engine) as s:
        return s.scalar(select(func.count()).select_from(Candidate))


def test_dataset_is_synthetic_and_contact_free():
    profiles = validate_dataset(DATA)
    assert len(profiles) == 14
    blob = json.dumps(DATA, ensure_ascii=False).lower()
    for bad in ("http", "t.me", "linkedin", "hh.ru", "+7", "@gmail", "@mail.ru", "@yandex"):
        assert bad not in blob
    assert all(p["email"].endswith("@demo.example") and "phone" not in p for p in profiles)


def test_import_dry_run_apply_and_idempotent(env):  # noqa: F811
    client, engine = env
    before = _count(engine)
    with Session(engine) as s:
        assert import_profiles(s, DATA, apply=False)["to_add"] == 14
    assert _count(engine) == before                       # dry-run writes nothing
    with Session(engine) as s:
        assert import_profiles(s, DATA, apply=True)["added"] == 14
    assert _count(engine) == before + 14
    with Session(engine) as s:
        r = import_profiles(s, DATA, apply=True)
    assert r["added"] == 0 and r["existing"] == 14 and _count(engine) == before + 14  # no duplicates

    with Session(engine) as s:
        syn = s.scalars(select(Candidate).where(Candidate.email.like("cv-syn-%"))).all()
        ids = [c.id for c in syn]
        assert all(str(c.verification_status) == "UNVERIFIED" and c.verified_grade is None and c.phone is None for c in syn)
        # only self-reported claims, no evidence at all, so nothing can look verified
        assert s.scalar(select(func.count()).select_from(SkillEvidence).join(SkillClaim).where(SkillClaim.candidate_id.in_(ids))) == 0
        assert {c.source for c in s.scalars(select(SkillClaim).where(SkillClaim.candidate_id.in_(ids)))} == {"self_reported"}
        front = {c.id for c in syn if c.email.startswith("cv-syn-f")}

    eh = _emp(client)
    need = client.post("/api/employer/needs", headers=eh, json=NEED).json()
    resp = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh)
    assert resp.status_code == 201, resp.text
    run = resp.json()
    got = {r["candidate"]["candidate_id"]: r for r in run["results"]}
    assert not (set(got) & front)                         # specialization is a hard filter
    for cid in set(got) & set(ids):
        assert got[cid]["candidate"]["verification_status"] == "UNVERIFIED"
        assert not got[cid]["candidate"].get("verified_grade")
