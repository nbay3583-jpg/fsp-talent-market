from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.candidates.models import Candidate
from fsp_market.db import Base, get_session
from fsp_market.main import app
from fsp_market.notifications.email import OUTBOX


@pytest.fixture()
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


def _register(client, email="e@x.io"):
    r = client.post(
        "/api/candidates", json={"email": email, "full_name": "E F", "claimed_grade": "MIDDLE"}
    )
    assert r.status_code == 201
    return r.json(), {"Authorization": f"Bearer {r.json()['access_token']}"}


def _token():
    return OUTBOX[-1]["body"].split("verify_email=")[1].split()[0]


def test_email_token_is_hashed_single_use_and_unlocks_visibility(env):
    client, engine = env
    _, h = _register(client)
    token = _token()
    with Session(engine) as s:
        c = s.scalar(select(Candidate))
        assert c.email_token_hash and token not in c.email_token_hash and not c.email_verified
    assert client.get("/api/candidates/me", headers=h).json()["email_verified"] is False
    assert client.post("/api/auth/verify-email", json={"token": "x" * 20}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400  # reuse
    assert client.get("/api/candidates/me", headers=h).json()["email_verified"] is True


def test_expired_token_rejected_and_resend_is_rate_limited(env):
    client, engine = env
    _, h = _register(client)
    token = _token()
    with Session(engine) as s:
        c = s.scalar(select(Candidate))
        c.email_token_expires = c.email_token_expires - timedelta(days=2)
        s.commit()
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400
    assert client.post("/api/candidates/me/email/resend", headers=h).status_code == 429


JOB = {
    "company": "Acme",
    "position": "Backend dev",
    "start_date": "2022-01-01",
    "end_date": None,
    "stack": ["python"],
    "tasks": "REST API и очереди",
}


def test_experience_crud_is_private_and_never_confirmed(env):
    client, _ = env
    _, h1 = _register(client, "a@x.io")
    _, h2 = _register(client, "b@x.io")
    r = client.post("/api/candidates/me/experience", headers=h1, json=JOB)
    assert r.status_code == 201 and r.json()["confirmed"] is False
    eid = r.json()["id"]
    bad = client.post("/api/candidates/me/experience", headers=h1, json={**JOB, "stack": ["nope"]})
    assert bad.status_code == 422
    back = client.post(
        "/api/candidates/me/experience", headers=h1, json={**JOB, "end_date": "2021-01-01"}
    )
    assert back.status_code == 422
    assert client.patch(f"/api/candidates/me/experience/{eid}", headers=h2, json={}).status_code == 404
    up = client.patch(f"/api/candidates/me/experience/{eid}", headers=h1, json={"position": "Lead"})
    assert up.json()["position"] == "Lead"
    assert len(client.get("/api/candidates/me/experience", headers=h1).json()["items"]) == 1
    assert client.get("/api/candidates/me/experience", headers=h2).json()["items"] == []
    assert client.delete(f"/api/candidates/me/experience/{eid}", headers=h1).status_code == 204
    assert client.get("/api/candidates/me/experience", headers=h1).json()["items"] == []
    assert client.get("/api/candidates/me/experience").status_code == 401


def test_context_fit_is_explainable_and_not_verification():
    from datetime import UTC, datetime

    from fsp_market.common.enums import Grade, SalaryType, VerificationStatus
    from fsp_market.matching import engine as eng
    from fsp_market.matching.facts import CandidateFacts, ExperienceFacts, NeedSkillSpec, NeedSpec

    need = NeedSpec(
        1, Grade.MIDDLE, None, 1, 2, SalaryType.GROSS, ("REMOTE",), None, None,
        (NeedSkillSpec("python", True, 1.0), NeedSkillSpec("postgresql", True, 1.0)),
        title="Backend интеграции", description="Платёжные интеграции и очереди",
    )

    def cand(stack, text):
        from datetime import date

        e = (ExperienceFacts("Acme", "Dev", tuple(stack), text, date(2023, 1, 1), None),)
        return CandidateFacts(1, 1, Grade.MIDDLE, VerificationStatus.UNVERIFIED, None, None,
                              None, None, ("REMOTE",), None, None, True, True, {}, e)

    now = datetime(2026, 10, 1, tzinfo=UTC)
    hi, why = eng.context_fit(need, cand(["python", "postgresql"], "Платёжные интеграции"), now)
    lo, _ = eng.context_fit(need, cand([], "Рисовал баннеры"), now)
    assert hi > 0.7 > lo == 0.0
    assert all("не подтверждено" in r.text for r in why)
    from dataclasses import replace

    assert eng.context_fit(need, replace(cand(["python"], ""), experience=()), now) == (0.0, [])
