"""Canonical demo end-to-end over the HTTP API, privacy audit, demo reset and demo-mode gating."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market import demo
from fsp_market.candidates.models import Candidate
from fsp_market.config import get_settings
from fsp_market.db import Base, get_session
from fsp_market.main import app
from fsp_market.skills.models import SkillEvidence

NEED = {
    "title": "Python Backend (FastAPI)",
    "target_grade": "MIDDLE",
    "target_sublevel": "M2",
    "required_skills": ["api_fastapi", "postgresql"],
    "optional_skills": ["kafka", "docker_basics"],
    "salary_from": 200000,
    "salary_to": 250000,
    "salary_type": "GROSS",
    "work_formats": ["REMOTE"],
}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        demo.seed(s)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app), engine
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def login(client, account):
    r = client.post("/api/demo/login", json={"account": account})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def take_assessment(client, h, correct=True):
    start = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()
    profile = "strong" if correct else "weak"
    ref = client.get(
        f"/api/demo/assessments/{start['attempt_id']}/reference-answers?profile={profile}",
        headers=h,
    ).json()["answers"]
    answers = {t["variant_id"]: ref[str(t["variant_id"])] for t in start["tasks"]}
    return client.post(
        f"/api/assessments/{start['attempt_id']}/submit", json={"answers": answers}, headers=h
    ).json()


def employer_with_need(client):
    eh, _ = login(client, "employer")
    need = client.post("/api/employer/needs", json=NEED, headers=eh)
    assert need.status_code == 201
    return eh, need.json()


def test_canonical_demo_accept_path(env):
    client, _engine = env
    # CANDIDATE: assessment -> VERIFIED -> evidence profile -> FSP evidence
    ch, info = login(client, "candidate_alexey")
    assert (
        client.get("/api/candidates/me/profile", headers=ch).json()["verification_status"]
        == "UNVERIFIED"
    )
    result = take_assessment(client, ch)
    assert result["verification_status"] == "VERIFIED" and result["claimed_grade"] == "MIDDLE"
    link = client.post("/api/candidates/me/fsp", json={"fsp_id": info["fsp_id"]}, headers=ch).json()
    assert link["has_history"] is True
    prof = client.get("/api/candidates/me/profile", headers=ch).json()
    assert prof["verified_grade"] == "MIDDLE" and prof["fsp"]["has_history"] is True
    kinds = {e["type"] for s in prof["skills"] for e in s["evidence"]}
    assert {"CORE_ASSESSMENT", "FSP_ACHIEVEMENT"} <= kinds and "talent_score" not in prof
    # EMPLOYER: need -> match -> WHY/GAPS -> detail without contacts
    eh, need = employer_with_need(client)
    run = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh).json()
    mine = next(r for r in run["results"] if r["candidate"]["display_name"] == "Alexey D.")
    assert mine["requirement_fit_label"].startswith("Соответствие этой потребности")
    assert any(w["code"] == "SKILL_VERIFIED" and w["skill"] == "api_fastapi" for w in mine["why"])
    assert any(w["code"] == "FSP_RELEVANT" for w in mine["why"]) and mine["gaps"]
    assert "Fedor E." not in {
        r["candidate"]["display_name"] for r in run["results"]
    }  # salary mismatch excluded
    cid = mine["candidate"]["candidate_id"]
    detail = client.get(f"/api/employer/candidates/{cid}?need_id={need['id']}", headers=eh)
    assert detail.json()["contact_status"] == "LOCKED"
    for secret in ("alexey@demo.example", "+7-900-111-22-33", "Alexey Demo"):
        assert secret not in detail.text
    # invitation with explicit salary type -> candidate sees salary -> accept -> contacts
    sent = client.post(
        "/api/employer/invitations",
        headers=eh,
        json={
            "candidate_id": cid,
            "need_id": need["id"],
            "match_run_id": run["run_id"],
            "description": "FastAPI platform team",
            "salary_from": 220000,
            "salary_to": 250000,
            "salary_type": "GROSS",
            "work_format": "REMOTE",
            "message": "Hi!",
        },
    )
    assert sent.status_code == 201 and "contacts" not in sent.json()
    inv = client.get("/api/candidates/me/invitations", headers=ch).json()[0]
    seen = client.get(f"/api/candidates/me/invitations/{inv['id']}", headers=ch).json()
    assert (seen["salary_from"], seen["salary_to"], seen["salary_type"]) == (
        220000,
        250000,
        "GROSS",
    )
    assert (
        client.post(f"/api/candidates/me/invitations/{inv['id']}/accept", headers=ch).json()[
            "status"
        ]
        == "CONTACTS_UNLOCKED"
    )
    after = client.get(f"/api/employer/invitations/{inv['id']}", headers=eh).json()
    assert after["contacts"] == {
        "full_name": "Alexey Demo",
        "email": "alexey@demo.example",
        "phone": "+7-900-111-22-33",
    }
    assert (
        client.get(f"/api/employer/candidates/{cid}", headers=eh).json()["contact_status"]
        == "UNLOCKED"
    )


def test_canonical_demo_decline_path_and_no_fsp_candidate(env):
    client, _ = env
    ch, info = login(client, "candidate_mila")
    assert take_assessment(client, ch)["verification_status"] == "VERIFIED"
    link = client.post("/api/candidates/me/fsp", json={"fsp_id": info["fsp_id"]}, headers=ch).json()
    assert link == {
        "evidence_added": 0,
        "has_history": False,
    }  # no FSP history: works, not penalised
    prof = client.get("/api/candidates/me/profile", headers=ch).json()
    assert prof["verified_grade"] == "MIDDLE" and prof["fsp"]["has_history"] is False
    eh, need = employer_with_need(client)
    run = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh).json()
    cid = next(
        r["candidate"]["candidate_id"]
        for r in run["results"]
        if r["candidate"]["display_name"] == "Mila N."
    )
    inv_id = client.post(
        "/api/employer/invitations",
        headers=eh,
        json={
            "candidate_id": cid,
            "need_id": need["id"],
            "description": "d",
            "salary_from": 210000,
            "salary_to": 240000,
            "salary_type": "NET",
            "work_format": "REMOTE",
            "message": "m",
        },
    ).json()["id"]
    seen = client.get(f"/api/candidates/me/invitations/{inv_id}", headers=ch).json()
    assert seen["salary_type"] == "NET"
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/decline", headers=ch).json()["status"]
        == "DECLINED"
    )
    view = client.get(f"/api/employer/invitations/{inv_id}", headers=eh)
    assert view.json()["status"] == "DECLINED" and "contacts" not in view.json()
    assert "mila@demo.example" not in client.get(f"/api/employer/candidates/{cid}", headers=eh).text


def test_not_verified_demo_candidate(env):
    client, _ = env
    ch, _ = login(client, "candidate_mila")
    result = take_assessment(client, ch, correct=False)
    assert result["verification_status"] == "NOT_VERIFIED" and result["claimed_grade"] == "MIDDLE"
    prof = client.get("/api/candidates/me/profile", headers=ch).json()
    assert prof["claimed_grade"] == "MIDDLE" and prof["verified_grade"] is None
    # a failed test creates no assessment evidence and no verified level (experience evidence is separate)
    assert all(e["type"] != "CORE_ASSESSMENT" for s in prof["skills"] for e in s["evidence"])
    assert all(s["verified_level"] is None for s in prof["skills"])
    hana, _ = login(client, "candidate_not_verified")
    p = client.get("/api/candidates/me/profile", headers=hana).json()
    assert (
        p["verification_status"] == "NOT_VERIFIED"
        and p["claimed_grade"] == "MIDDLE"
        and p["verified_grade"] is None
    )


def test_full_pool_secondary_flow(env):
    client, _ = env
    eh, _ = login(client, "employer")
    pool = client.get("/api/employer/pool?limit=100&verification=NOT_VERIFIED", headers=eh).json()
    assert pool["total"] >= 1 and all(
        c["verification_status"] == "NOT_VERIFIED" for c in pool["candidates"]
    )
    one = client.get(
        f"/api/employer/candidates/{pool['candidates'][0]['candidate_id']}", headers=eh
    )
    assert one.status_code == 200 and one.json()["contact_status"] == "LOCKED"


def test_privacy_audit_no_contact_in_any_employer_response(env):
    client, engine = env
    eh, need = employer_with_need(client)
    run = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh)
    with Session(engine) as s:
        secrets = [
            x for c in s.scalars(select(Candidate)) for x in (c.email, c.full_name, c.phone) if x
        ]
    texts = [
        run.text,
        client.get("/api/employer/pool?limit=100", headers=eh).text,
        client.get("/api/employer/invitations", headers=eh).text,
    ]
    texts += [
        client.get(f"/api/employer/candidates/{i}?need_id={need['id']}", headers=eh).text
        for i in range(1, 25)
    ]
    for t in texts:
        for secret in secrets:
            assert secret not in t, secret


def test_demo_mode_gating(env, monkeypatch):
    client, _ = env
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    assert client.get("/api/demo/config").json() == {"demo_mode": False, "accounts": []}
    assert client.post("/api/demo/login", json={"account": "employer"}).status_code == 404
    reg = client.post(
        "/api/candidates", json={"email": "n@x.io", "full_name": "N M", "claimed_grade": "MIDDLE"}
    ).json()
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    a = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()[
        "attempt_id"
    ]
    assert client.get(f"/api/demo/assessments/{a}/reference-answers", headers=h).status_code == 404


def test_reference_answers_only_for_own_attempt(env):
    client, _ = env
    a, _ = login(client, "candidate_alexey")
    b, _ = login(client, "candidate_mila")
    attempt = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=a).json()[
        "attempt_id"
    ]
    assert (
        client.get(f"/api/demo/assessments/{attempt}/reference-answers", headers=b).status_code
        == 404
    )
    assert client.post("/api/demo/login", json={"account": "nobody"}).status_code == 404


def test_reset_returns_demo_to_initial_state_and_seed_is_idempotent(env):
    client, engine = env
    ch, _ = login(client, "candidate_alexey")
    take_assessment(client, ch)
    eh, _ = employer_with_need(client)
    with Session(engine) as s:
        before = s.scalar(select(func.count(Candidate.id)))
        demo.seed(s)  # re-run: no duplicates
        assert s.scalar(select(func.count(Candidate.id))) == before
        assert s.scalar(select(func.count(SkillEvidence.id))) > 0
        demo.reset(s)
        assert s.scalar(select(func.count(Candidate.id))) == before
    ch2, _ = login(client, "candidate_alexey")
    assert (
        client.get("/api/candidates/me/profile", headers=ch2).json()["verification_status"]
        == "UNVERIFIED"
    )
    eh2, _ = login(client, "employer")
    assert client.get("/api/employer/needs", headers=eh2).json() == []
    assert (
        take_assessment(client, ch2)["verification_status"] == "VERIFIED"
    )  # demo works again after reset
    del eh


def test_profile_catalog_and_validation_summary(env):
    client, _ = env
    ch, _ = login(client, "candidate_alexey")
    me = client.get("/api/candidates/me", headers=ch).json()
    assert me["email"] == "alexey@demo.example" and me["preferences"]["salary_min"] == 225000
    upd = client.patch(
        "/api/candidates/me/profile",
        json={"full_name": "Alexey D. Demo", "claimed_grade": "SENIOR"},
        headers=ch,
    )
    assert upd.json()["claimed_grade"] == "SENIOR"
    assert (
        client.patch(
            "/api/candidates/me/profile", json={"specialization": "nope"}, headers=ch
        ).status_code
        == 422
    )
    cat = client.get("/api/catalog").json()
    assert "backend_python" in {s["code"] for s in cat["specializations"]} and cat["grades"][
        "MIDDLE"
    ] == ["M1", "M2", "M3"]
    skills = {s["code"]: s["verifiable"] for s in cat["skills"]}
    assert skills["api_fastapi"] is True and skills["postgresql"] is False
    summary = client.get("/api/validation/summary")
    if summary.status_code == 200:  # artifacts exist when run from the repo root
        body = summary.json()
        with open("artifacts/validation/latest.json", encoding="utf-8") as fh:
            art = json.load(fh)
        assert body["matching"] == art["matching"]["summary"]  # served numbers are the stored ones


def test_employer_me_and_roles(env):
    client, _ = env
    eh, info = login(client, "employer")
    assert client.get("/api/employers/me", headers=eh).json()["company_name"] == "Демо-компания"
    ch, _ = login(client, "candidate_alexey")
    assert client.get("/api/employers/me", headers=ch).status_code == 401
    assert info["role"] == "employer"
