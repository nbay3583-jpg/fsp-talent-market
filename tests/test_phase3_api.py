import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market.assessments.models import TaskVariant
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.variants import render_variant_fields
from fsp_market.db import Base, get_session
from fsp_market.main import app
from fsp_market.skills.models import VerifiedSkillLevel


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_backend_python(s)
        s.commit()

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def register(client, email="m@x.io", grade="MIDDLE"):
    r = client.post(
        "/api/candidates",
        json={"email": email, "full_name": "Mid Dev", "claimed_grade": grade},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def solve(client, headers, grade, correct, engine):
    start = client.post("/api/assessments", json={"target_grade": grade}, headers=headers)
    assert start.status_code == 201, start.text
    body = start.json()
    with Session(engine) as s:
        contracts = {v.id: v.scoring_contract["correct"] for v in s.scalars(select(TaskVariant))}
    answers = {
        t["variant_id"]: contracts[t["variant_id"]]
        if correct
        else next(k for k in "ABCD" if k != contracts[t["variant_id"]])
        for t in body["tasks"]
    }
    return body, client.post(
        f"/api/assessments/{body['attempt_id']}/submit", json={"answers": answers}, headers=headers
    )


def test_variant_rendering_is_reproducible():
    params = {"x": 1, "options": {"A": "a", "B": "b"}, "correct": "B", "dimension": "d"}
    a = render_variant_fields("q {x}", params, 7)
    assert a == render_variant_fields("q {x}", params, 7)
    assert a["prompt"] == "q 1" and a["scoring_contract"]["correct"] == "B"


def test_assigned_tasks_are_reproducible_and_hide_answers(env):
    client, _ = env
    h = register(client)
    first = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()
    again = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()
    assert first == again  # same in-progress attempt, same tasks
    assert (
        client.get(f"/api/assessments/{first['attempt_id']}", headers=h).json()["tasks"]
        == first["tasks"]
    )
    comps = {t["competency"] for t in first["tasks"]}
    assert comps == {"python", "sql", "api_fastapi", "testing", "docker_basics", "system_thinking"}
    assert "correct" not in str(first) and "scoring" not in str(first)
    assert len(first["tasks"]) <= 8  # short, a few minutes


def test_verified_flow_and_profile(env):
    client, engine = env
    h = register(client)
    _, r = solve(client, h, "MIDDLE", True, engine)
    assert r.status_code == 200
    out = r.json()
    assert out["verification_status"] == "VERIFIED" and out["claimed_grade"] == "MIDDLE"
    profile = client.get("/api/candidates/me/profile", headers=h).json()
    assert profile["verification_status"] == "VERIFIED" and profile["verified_grade"] == "MIDDLE"
    assert profile["specialization"] == "backend_python"
    assert profile["assessment"]["passed"] is True
    assert {s["skill"] for s in profile["skills"]} >= {"python", "sql", "api_fastapi"}
    sk = profile["skills"][0]
    assert sk["verified_level"] == "MIDDLE"
    assert (
        sk["evidence"][0]["type"] == "CORE_ASSESSMENT" and sk["evidence"][0]["strength"] == "HIGH"
    )
    assert "talent_score" not in profile
    assert profile["fsp"] == {"has_history": False, "evidence_items": 0}


def test_failed_middle_stays_claimed_middle_not_junior(env):
    client, engine = env
    h = register(client)
    _, r = solve(client, h, "MIDDLE", False, engine)
    assert r.json()["verification_status"] == "NOT_VERIFIED"
    profile = client.get("/api/candidates/me/profile", headers=h).json()
    assert profile["claimed_grade"] == "MIDDLE"
    assert profile["verification_status"] == "NOT_VERIFIED"
    assert profile["verified_grade"] is None
    assert profile["skills"] == []  # no evidence created on failure
    again = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h)
    assert again.status_code == 409  # cooldown


def test_scoring_is_deterministic(env):
    client, engine = env
    a, b = register(client, "a@x.io"), register(client, "b@x.io")
    # identical wrong answers on the same variants give identical scores
    ra = solve(client, a, "MIDDLE", False, engine)[1].json()
    rb = solve(client, b, "MIDDLE", False, engine)[1].json()
    assert ra["score"] == rb["score"] == 0.0


def test_fsp_history_is_evidence_not_grade(env):
    client, engine = env
    h = register(client)
    solve(client, h, "MIDDLE", False, engine)  # NOT_VERIFIED
    r = client.post("/api/candidates/me/fsp", json={"fsp_id": "FSP-1001"}, headers=h)
    assert r.status_code == 200 and r.json()["evidence_added"] >= 3
    profile = client.get("/api/candidates/me/profile", headers=h).json()
    assert profile["verification_status"] == "NOT_VERIFIED" and profile["verified_grade"] is None
    assert profile["fsp"]["has_history"] is True
    fsp = [e for s in profile["skills"] for e in s["evidence"] if e["type"] == "FSP_ACHIEVEMENT"]
    assert fsp and all(e["level"] is None for e in fsp)
    assert {s["skill"] for s in profile["skills"] if s["verified_level"]} == set()
    # idempotent
    again = client.post("/api/candidates/me/fsp", json={"fsp_id": "FSP-1001"}, headers=h)
    assert again.json()["evidence_added"] == 0


def test_candidate_without_fsp_history_works(env):
    client, engine = env
    h = register(client)
    r = client.post("/api/candidates/me/fsp", json={"fsp_id": "FSP-2002"}, headers=h)
    assert r.status_code == 200 and r.json() == {"evidence_added": 0, "has_history": False}
    _, res = solve(client, h, "MIDDLE", True, engine)
    assert res.json()["verification_status"] == "VERIFIED"
    profile = client.get("/api/candidates/me/profile", headers=h).json()
    assert profile["fsp"]["has_history"] is False and profile["verified_grade"] == "MIDDLE"
    # unverified FSP member is rejected, never silently trusted
    bad = client.post("/api/candidates/me/fsp", json={"fsp_id": "FSP-9999"}, headers=h)
    assert bad.status_code == 422


def test_fsp_after_verification_does_not_change_levels(env):
    client, engine = env
    h = register(client)
    solve(client, h, "MIDDLE", True, engine)
    with Session(engine) as s:
        before = s.scalar(select(func.count(VerifiedSkillLevel.id)))
    client.post("/api/candidates/me/fsp", json={"fsp_id": "FSP-1001"}, headers=h)
    profile = client.get("/api/candidates/me/profile", headers=h).json()
    assert profile["verified_grade"] == "MIDDLE"
    with Session(engine) as s:
        assert s.scalar(select(func.count(VerifiedSkillLevel.id))) == before


def test_auth_and_isolation(env):
    client, _ = env
    assert client.get("/api/candidates/me/profile").status_code == 401
    assert (
        client.get("/api/candidates/me/profile", headers={"Authorization": "Bearer x"}).status_code
        == 401
    )
    a, b = register(client, "a@x.io"), register(client, "b@x.io")
    attempt = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=a).json()
    assert client.get(f"/api/assessments/{attempt['attempt_id']}", headers=b).status_code == 404
    r = client.post(
        f"/api/assessments/{attempt['attempt_id']}/submit", json={"answers": {}}, headers=b
    )
    assert r.status_code == 404


def test_submission_validation(env):
    client, _ = env
    h = register(client)
    t = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()
    aid = t["attempt_id"]
    assert (
        client.post(f"/api/assessments/{aid}/submit", json={"answers": {}}, headers=h).status_code
        == 422
    )
    bad = {x["variant_id"]: "Z" for x in t["tasks"]}
    assert (
        client.post(f"/api/assessments/{aid}/submit", json={"answers": bad}, headers=h).status_code
        == 422
    )
    ok = {x["variant_id"]: "A" for x in t["tasks"]}
    assert (
        client.post(f"/api/assessments/{aid}/submit", json={"answers": ok}, headers=h).status_code
        == 200
    )
    assert (
        client.post(f"/api/assessments/{aid}/submit", json={"answers": ok}, headers=h).status_code
        == 409
    )


def test_anchor_flag_is_seeded(env):
    _, engine = env
    with Session(engine) as s:
        assert s.scalar(select(func.count(TaskVariant.id)).where(TaskVariant.is_anchor)) == 1


def test_token_roundtrip_tamper_expiry():
    from fsp_market.auth.tokens import InvalidToken, create_token, verify_token

    t = create_token(5, "s", ttl_seconds=10, now=100.0)
    assert verify_token(t, "s", now=105.0) == 5
    with pytest.raises(InvalidToken):
        verify_token(t, "other", now=105.0)
    with pytest.raises(InvalidToken):
        verify_token(t, "s", now=111.0)
    sig = t.split(".")[1]
    with pytest.raises(InvalidToken):
        verify_token(create_token(6, "s", 10, 100.0).split(".")[0] + "." + sig, "s", now=105.0)
    with pytest.raises(InvalidToken):
        verify_token("garbage", "s")
