import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market.auth.tokens import create_token
from fsp_market.candidates.models import Candidate
from fsp_market.config import get_settings
from fsp_market.db import Base, get_session
from fsp_market.main import app
from fsp_market.matching.demo_seed import seed_matching_demo
from fsp_market.teamfit import compat

ANS = {k: 3 for k in compat.AXES}
NEED = {
    "title": "Python Backend lead",
    "target_grade": "MIDDLE",
    "target_sublevel": "M2",
    "required_skills": ["api_fastapi", "postgresql"],
    "optional_skills": [],
    "salary_from": 200000,
    "salary_to": 400000,
    "salary_type": "GROSS",
    "work_formats": ["REMOTE"],
}


@pytest.fixture(scope="module")
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_matching_demo(s)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def _cand(engine, key):
    with Session(engine) as s:
        c = s.scalar(select(Candidate).where(Candidate.email == f"{key}@demo.example"))
        return c.id, {"Authorization": f"Bearer {create_token(c.id, get_settings().jwt_secret)}"}


_N = iter(range(1000))


def _emp(client):
    r = client.post(
        "/api/employers", json={"company_name": "T", "contact_email": f"t{next(_N)}@x.io"}
    ).json()
    return {"Authorization": f"Bearer {r['access_token']}"}


def test_aggregate_hidden_below_three_and_anonymous(env):
    client, _ = env
    eh = _emp(client)
    need = client.post("/api/employer/needs", headers=eh, json=NEED).json()
    nid = need["id"]
    assert client.put(f"/api/employer/needs/{nid}/work-style", headers=eh, json={"answers": ANS}).status_code == 200
    token = client.post(f"/api/employer/needs/{nid}/team-survey", headers=eh).json()["token"]
    bad = client.post(f"/api/team-survey/{token}", json={"answers": {**ANS, "pace": 9}})
    assert bad.status_code == 422
    for i in range(2):
        assert client.post(f"/api/team-survey/{token}", json={"answers": {**ANS, "pace": 5}}).status_code == 201
    p = client.get(f"/api/employer/needs/{nid}/team-profile", headers=eh).json()
    assert p["employees"]["aggregate"] is None and p["employees"]["responses"] == 2
    assert p["source"] == "MANAGER" and "answers" not in str(p["employees"])
    client.post(f"/api/team-survey/{token}", json={"answers": {**ANS, "pace": 5}})
    p = client.get(f"/api/employer/needs/{nid}/team-profile", headers=eh).json()
    assert p["source"] == "BOTH" and p["employees"]["aggregate"]["pace"] == 5.0
    assert p["profile"]["pace"] == 4.0
    assert client.get("/api/team-survey/nope").status_code == 404


def test_favorites_are_private_and_do_not_invite(env):
    client, engine = env
    cid, _ = _cand(engine, "anna")
    e1, e2 = _emp(client), {"Authorization": "Bearer x"}
    assert client.post("/api/employer/favorites", headers=e1, json={"candidate_id": cid, "note": "позже"}).status_code == 201
    items = client.get("/api/employer/favorites", headers=e1).json()["items"]
    assert len(items) == 1 and "email" not in str(items) and items[0]["note"] == "позже"
    assert client.get("/api/employer/favorites", headers=e2).status_code == 401
    assert client.get("/api/candidates/me/invitations", headers=_cand(engine, "anna")[1]).json() == []
    assert client.delete(f"/api/employer/favorites/{cid}", headers=e1).status_code == 204
    assert client.get("/api/employer/favorites", headers=e1).json()["items"] == []


def test_candidate_recommendations_explain_both_sides(env):
    client, engine = env
    _, ch = _cand(engine, "anna")
    assert client.put("/api/candidates/me/goals", headers=ch, json={"interests": ["nope"]}).status_code == 422
    r = client.put("/api/candidates/me/goals", headers=ch, json={"interests": ["postgresql"], "career_goal": "LEAD"})
    assert r.status_code == 200
    assert client.put("/api/candidates/me/work-style", headers=ch, json={"answers": ANS}).status_code == 200
    eh = _emp(client)
    n = client.post("/api/employer/needs", headers=eh, json=NEED).json()
    # unpublished (internal) needs are never shown to candidates
    hidden = client.get("/api/candidates/me/recommendations", headers=ch).json()
    assert hidden["items"] == [] and hidden["general_feedback"]["unpublished_matching_needs"] >= 1
    assert "company" not in str(hidden["general_feedback"]) and NEED["title"] not in str(hidden)
    assert client.put(f"/api/employer/needs/{n['id']}/publication", headers=eh, json={"public": True}).status_code == 200
    rec = client.get("/api/candidates/me/recommendations", headers=ch).json()
    assert rec["total"] >= 1
    top = rec["items"][0]
    assert top["company"] and top["why"] and "mutual_fit" in top
    assert all(set(i) >= {"why", "gaps", "requirement_fit"} for i in rec["items"])
    assert client.get("/api/candidates/me/recommendations").status_code == 401
