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

NEED = {
    "title": "Python Backend",
    "target_grade": "MIDDLE",
    "target_sublevel": "M2",
    "required_skills": ["api_fastapi", "postgresql"],
    "optional_skills": ["kafka"],
    "salary_from": 200000,
    "salary_to": 250000,
    "salary_type": "GROSS",
    "work_formats": ["REMOTE"],
}


@pytest.fixture(scope="module")
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_matching_demo(s)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def cand_headers(engine, email_key):
    with Session(engine) as s:
        c = s.scalar(select(Candidate).where(Candidate.email == f"{email_key}@demo.example"))
        token = create_token(c.id, get_settings().jwt_secret)
        return c.id, {"Authorization": f"Bearer {token}"}, c.email, c.full_name, c.phone


def employer(client, email):
    r = client.post("/api/employers", json={"company_name": "Acme", "contact_email": email}).json()
    return {"Authorization": f"Bearer {r['access_token']}"}


def invite_body(candidate_id, **kw):
    body = {
        "candidate_id": candidate_id,
        "description": "Разработка и поддержка backend-сервисов на FastAPI и PostgreSQL в продуктовой команде",
        "salary_from": 220000,
        "salary_to": 250000,
        "salary_type": "GROSS",
        "work_format": "REMOTE",
        "message": "Write to us in Telegram after you accept",
        "role": "Python Backend",
    }
    body.update(kw)
    return body


def flow_setup(client, engine, key, emp_email):
    eh = employer(client, emp_email)
    need = client.post("/api/employer/needs", json=NEED, headers=eh).json()
    run = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh).json()
    cid, ch, email, name, phone = cand_headers(engine, key)
    return eh, need, run, cid, ch, (email, name, phone)


def test_invitation_validation_requires_salary(env):
    client, engine = env
    eh, _, _, cid, _, _ = flow_setup(client, engine, "anna", "v1@x.io")
    for bad in (
        {"salary_from": None},
        {"salary_to": None},
        {"salary_type": None},
        {"salary_from": 0},
        {"salary_from": 300000, "salary_to": 250000},
        {"salary_type": "MAYBE"},
    ):
        body = invite_body(cid, **bad)
        assert client.post("/api/employer/invitations", json=body, headers=eh).status_code == 422, (
            bad
        )
    no_salary = invite_body(cid)
    for k in ("salary_from", "salary_to", "salary_type"):
        no_salary.pop(k)
    assert client.post("/api/employer/invitations", json=no_salary, headers=eh).status_code == 422
    ok = client.post("/api/employer/invitations", json=invite_body(cid), headers=eh)
    assert ok.status_code == 201
    out = ok.json()
    assert out["status"] == "SENT" and out["contacts_unlocked"] is False and "contacts" not in out
    assert (out["salary_from"], out["salary_to"], out["salary_type"]) == (220000, 250000, "GROSS")


def test_full_accept_flow_unlocks_contacts(env):
    client, engine = env
    eh, need, run, cid, ch, (email, name, phone) = flow_setup(client, engine, "boris", "acc@x.io")
    matched = {r["candidate"]["candidate_id"] for r in run["results"]}
    assert cid in matched
    # 1-4. candidate detail has NO contacts before any invitation
    detail = client.get(f"/api/employer/candidates/{cid}?need_id={need['id']}", headers=eh)
    assert detail.status_code == 200 and detail.json()["contact_status"] == "LOCKED"
    assert "contacts" not in detail.json()
    for secret in (email, name, phone):
        assert secret not in detail.text
    # 5. salary-backed invitation, tied to the match run
    sent = client.post(
        "/api/employer/invitations",
        headers=eh,
        json=invite_body(cid, need_id=need["id"], match_run_id=run["run_id"]),
    )
    assert sent.status_code == 201
    inv_id = sent.json()["id"]
    # still locked while SENT
    assert "contacts" not in client.get(f"/api/employer/invitations/{inv_id}", headers=eh).json()
    assert (
        client.get(f"/api/employer/candidates/{cid}", headers=eh).json()["contact_status"]
        == "LOCKED"
    )
    # 6. candidate sees the full terms, salary included, BEFORE accepting
    seen = client.get(f"/api/candidates/me/invitations/{inv_id}", headers=ch).json()
    assert seen["status"] == "VIEWED"
    assert (
        seen["company"],
        seen["role"],
        seen["salary_from"],
        seen["salary_to"],
        seen["salary_type"],
        seen["work_format"],
    ) == ("Acme", "Python Backend", 220000, 250000, "GROSS", "REMOTE")
    assert seen["description"] and seen["message"]
    assert (
        client.get(f"/api/employer/invitations/{inv_id}", headers=eh).json()["status"] == "VIEWED"
    )
    assert "contacts" not in client.get(f"/api/employer/invitations/{inv_id}", headers=eh).json()
    # 7. ACCEPT
    acc = client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=ch)
    assert acc.status_code == 200 and acc.json()["status"] == "CONTACTS_UNLOCKED"
    # 8-9. contacts appear for the authorised employer only
    after = client.get(f"/api/employer/invitations/{inv_id}", headers=eh).json()
    assert after["contacts_unlocked"] is True
    assert after["contacts"] == {"full_name": name, "email": email, "phone": phone}
    det = client.get(f"/api/employer/candidates/{cid}", headers=eh).json()
    assert det["contact_status"] == "UNLOCKED" and det["contacts"]["email"] == email
    other = employer(client, "other-acc@x.io")
    od = client.get(f"/api/employer/candidates/{cid}", headers=other).json()
    assert od["contact_status"] == "LOCKED" and "contacts" not in od  # unlock is per employer


def test_decline_keeps_contacts_hidden(env):
    client, engine = env
    eh, _, _, cid, ch, (email, name, phone) = flow_setup(client, engine, "clara", "dec@x.io")
    inv_id = client.post("/api/employer/invitations", json=invite_body(cid), headers=eh).json()[
        "id"
    ]
    r = client.post(f"/api/candidates/me/invitations/{inv_id}/decline", headers=ch)
    assert r.status_code == 200 and r.json()["status"] == "DECLINED"
    view = client.get(f"/api/employer/invitations/{inv_id}", headers=eh)
    assert view.json()["status"] == "DECLINED" and "contacts" not in view.json()
    det = client.get(f"/api/employer/candidates/{cid}", headers=eh)
    assert det.json()["contact_status"] == "LOCKED"
    for secret in (email, name, phone):
        assert secret not in view.text and secret not in det.text
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=ch).status_code
        == 409
    )


def test_state_machine_transitions(env):
    from fsp_market.common.enums import InvitationStatus as S
    from fsp_market.invitations import service as svc
    from fsp_market.invitations.models import Invitation

    def inv(status):
        return Invitation(status=status, candidate_id=1, employer_id=1)

    ok = [
        (S.SENT, S.VIEWED),
        (S.SENT, S.ACCEPTED),
        (S.SENT, S.DECLINED),
        (S.VIEWED, S.ACCEPTED),
        (S.VIEWED, S.DECLINED),
        (S.ACCEPTED, S.CONTACTS_UNLOCKED),
    ]
    for a, b in ok:
        i = inv(a)
        svc.transition(i, b)
        assert i.status == b
    bad = [
        (S.DECLINED, S.ACCEPTED),
        (S.DECLINED, S.VIEWED),
        (S.ACCEPTED, S.DECLINED),
        (S.CONTACTS_UNLOCKED, S.DECLINED),
        (S.CONTACTS_UNLOCKED, S.ACCEPTED),
        (S.VIEWED, S.SENT),
        (S.SENT, S.CONTACTS_UNLOCKED),
        (S.VIEWED, S.CONTACTS_UNLOCKED),
    ]
    for a, b in bad:
        with pytest.raises(svc.InvalidTransition):
            svc.transition(inv(a), b)
    assert not svc.contacts_visible(inv(S.SENT)) and not svc.contacts_visible(inv(S.VIEWED))
    assert not svc.contacts_visible(inv(S.DECLINED))
    assert svc.contacts_visible(inv(S.ACCEPTED)) and svc.contacts_visible(inv(S.CONTACTS_UNLOCKED))


def test_api_rejects_invalid_transitions_and_duplicates(env):
    client, engine = env
    eh, _, _, cid, ch, _ = flow_setup(client, engine, "nina", "tr@x.io")
    inv_id = client.post("/api/employer/invitations", json=invite_body(cid), headers=eh).json()[
        "id"
    ]
    assert (
        client.post("/api/employer/invitations", json=invite_body(cid), headers=eh).status_code
        == 409
    )
    # SENT -> ACCEPTED directly is allowed (SENT/VIEWED -> ACCEPTED)
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=ch).status_code
        == 200
    )
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=ch).status_code
        == 409
    )
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/decline", headers=ch).status_code
        == 409
    )


def test_rbac_candidates_and_employers_are_isolated(env):
    client, engine = env
    eh, _, _, cid, ch, (email, _name, _phone) = flow_setup(client, engine, "elena", "rb1@x.io")
    inv_id = client.post("/api/employer/invitations", json=invite_body(cid), headers=eh).json()[
        "id"
    ]
    _, other_ch, *_ = cand_headers(engine, "julia")
    other_eh = employer(client, "rb2@x.io")
    # another candidate cannot read / view / accept / decline
    for call in (
        client.get(f"/api/candidates/me/invitations/{inv_id}", headers=other_ch),
        client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=other_ch),
        client.post(f"/api/candidates/me/invitations/{inv_id}/decline", headers=other_ch),
    ):
        assert call.status_code == 404
    assert client.get("/api/candidates/me/invitations", headers=other_ch).json() == []
    # another employer cannot read it, and it is absent from their list
    assert client.get(f"/api/employer/invitations/{inv_id}", headers=other_eh).status_code == 404
    assert client.get("/api/employer/invitations", headers=other_eh).json() == []
    # untouched by the failed attempts
    assert client.get(f"/api/employer/invitations/{inv_id}", headers=eh).json()["status"] == "SENT"
    # roles are not interchangeable and anonymous is rejected
    assert client.get("/api/employer/invitations", headers=ch).status_code == 401
    assert client.get("/api/candidates/me/invitations", headers=eh).status_code == 401
    assert client.get("/api/employer/invitations").status_code == 401
    assert client.post(f"/api/candidates/me/invitations/{inv_id}/accept").status_code == 401
    # only the target candidate can accept, and the other employer still sees nothing
    assert (
        client.post(f"/api/candidates/me/invitations/{inv_id}/accept", headers=ch).status_code
        == 200
    )
    assert client.get(f"/api/employer/invitations/{inv_id}", headers=other_eh).status_code == 404
    assert email not in client.get("/api/employer/invitations", headers=other_eh).text


def test_cannot_invite_hidden_closed_or_foreign_need(env):
    client, engine = env
    eh = employer(client, "inv-guard@x.io")
    for key, code in (("lena", 404), ("misha", 409)):
        cid, *_ = cand_headers(engine, key)
        assert (
            client.post("/api/employer/invitations", json=invite_body(cid), headers=eh).status_code
            == code
        )
    cid, *_ = cand_headers(engine, "xenia")
    other = employer(client, "inv-guard2@x.io")
    foreign = client.post("/api/employer/needs", json=NEED, headers=other).json()["id"]
    r = client.post("/api/employer/invitations", json=invite_body(cid, need_id=foreign), headers=eh)
    assert r.status_code == 404
    assert (
        client.post("/api/employer/invitations", json=invite_body(99999), headers=eh).status_code
        == 404
    )


def test_no_employer_endpoint_leaks_contacts_before_accept(env):
    client, engine = env
    eh, need, run, *_ = flow_setup(client, engine, "anna", "leak@x.io")
    secrets = []
    with Session(engine) as s:
        for c in s.scalars(select(Candidate)):
            secrets += [c.email, c.full_name]
            if c.phone:
                secrets.append(c.phone)
    urls = [
        "/api/employer/pool?limit=100",
        f"/api/employer/match-runs/{run['run_id']}?limit=50",
        "/api/employer/invitations",
    ] + [f"/api/employer/candidates/{i}?need_id={need['id']}" for i in range(1, 23)]
    texts = [client.get(u, headers=eh).text for u in urls] + [json_dump(run)]
    for text in texts:
        for secret in secrets:
            assert secret not in text, secret


def json_dump(obj):
    import json

    return json.dumps(obj, ensure_ascii=False)


def test_matching_pool_and_profile_unaffected(env):
    client, _engine = env
    eh = employer(client, "reg@x.io")
    need = client.post("/api/employer/needs", json=NEED, headers=eh).json()
    run = client.post(f"/api/employer/needs/{need['id']}/match?limit=50", headers=eh).json()
    assert {r["candidate"]["display_name"] for r in run["results"]} >= {"Anna V.", "Boris P."}
    assert client.get("/api/employer/pool?limit=100", headers=eh).json()["total"] >= 20
    reg = client.post(
        "/api/candidates", json={"email": "z@x.io", "full_name": "Z Y", "claimed_grade": "MIDDLE"}
    ).json()
    zh = {"Authorization": f"Bearer {reg['access_token']}"}
    assert client.get("/api/candidates/me/profile", headers=zh).status_code == 200
