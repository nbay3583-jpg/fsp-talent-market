import re

from fsp_market.notifications.email import OUTBOX
from tests.test_phase9_teamfit import NEED, _cand, _emp, env  # noqa: F401

DESC = "Разработка backend-сервисов на FastAPI и PostgreSQL, ревью кода, дежурства раз в месяц"


def _code_for(to: str) -> str:
    mail = [m for m in OUTBOX if m["to"] == to][-1]
    return re.search(r"\b(\d{6})\b", mail["body"]).group(1)


def _clear_cooldown(engine, email):
    from sqlalchemy import select, update
    from sqlalchemy.orm import Session

    from fsp_market.candidates.models import Candidate
    from fsp_market.employers.models import Employer

    with Session(engine) as s:
        s.execute(update(Candidate).where(Candidate.email == email).values(login_code_sent_at=None))
        s.execute(update(Employer).where(Employer.contact_email == email).values(login_code_sent_at=None))
        s.commit()
        _ = select


def test_candidate_register_logout_login_and_lockout(env):  # noqa: F811
    client, _ = env
    r = client.post("/api/candidates", json={"email": "Re@Login.io", "full_name": "Вход Повторный",
                                              "claimed_grade": "JUNIOR", "password": "correct-horse"})
    assert r.status_code == 201
    bad = client.post("/api/auth/login", json={"role": "candidate", "email": "re@login.io", "password": "nope"})
    unknown = client.post("/api/auth/login", json={"role": "candidate", "email": "who@x.io", "password": "nope"})
    assert bad.status_code == unknown.status_code == 401 and bad.json() == unknown.json()
    ok = client.post("/api/auth/login", json={"role": "candidate", "email": "re@login.io", "password": "correct-horse"})
    assert ok.status_code == 200
    h = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert client.get("/api/candidates/me", headers=h).json()["email"] == "Re@Login.io"
    # a candidate token never works for employer endpoints
    assert client.get("/api/employer/favorites", headers=h).status_code == 401
    for _ in range(5):
        client.post("/api/auth/login", json={"role": "candidate", "email": "re@login.io", "password": "x"})
    locked = client.post("/api/auth/login", json={"role": "candidate", "email": "re@login.io", "password": "correct-horse"})
    assert locked.status_code == 429


def test_employer_login_and_code_recovery(env):  # noqa: F811
    client, engine = env
    r = client.post("/api/employers", json={"company_name": "Код Лтд", "contact_email": "boss@kod.io", "password": "first-pass-1"})
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"role": "employer", "email": "boss@kod.io", "password": "first-pass-1"}).status_code == 200
    # wrong role pairing does not leak or authenticate
    assert client.post("/api/auth/login", json={"role": "candidate", "email": "boss@kod.io", "password": "first-pass-1"}).status_code == 401
    same = [client.post("/api/auth/code/request", json={"role": "employer", "email": e}).json() for e in ("boss@kod.io", "ghost@kod.io")]
    assert same[0] == same[1] == {"accepted": True}
    code = _code_for("boss@kod.io")
    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/api/auth/code/verify", json={"role": "employer", "email": "boss@kod.io", "code": wrong}).status_code == 401
    ok = client.post("/api/auth/code/verify", json={"role": "employer", "email": "boss@kod.io", "code": code, "new_password": "second-pass-2"})
    assert ok.status_code == 200
    h = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert client.get("/api/employers/me", headers=h).status_code == 200
    assert client.post("/api/auth/code/verify", json={"role": "employer", "email": "boss@kod.io", "code": code}).status_code == 401  # single use
    assert client.post("/api/auth/login", json={"role": "employer", "email": "boss@kod.io", "password": "second-pass-2"}).status_code == 200
    assert client.post("/api/auth/login", json={"role": "employer", "email": "boss@kod.io", "password": "first-pass-1"}).status_code == 401
    _clear_cooldown(engine, "boss@kod.io")


def test_code_login_verifies_candidate_email(env):  # noqa: F811
    client, _ = env
    client.post("/api/candidates", json={"email": "code@c.io", "full_name": "Код Кандидат", "claimed_grade": "JUNIOR"})
    client.post("/api/auth/code/request", json={"role": "candidate", "email": "code@c.io"})
    tok = client.post("/api/auth/code/verify", json={"role": "candidate", "email": "code@c.io", "code": _code_for("code@c.io")}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/api/candidates/me", headers=h).json()["email_verified"] is True


def _invite(client, eh, cid, **over):
    body = {"candidate_id": cid, "role": "Python Backend", "description": DESC, "salary_from": 200000,
            "salary_to": 260000, "salary_type": "NET", "work_format": "REMOTE", "message": "Привет!"}
    body.update(over)
    return client.post("/api/employer/invitations", headers=eh, json=body)


def test_standalone_invitation_validation_duplicates_and_privacy(env):  # noqa: F811
    client, engine = env
    cid, ch = _cand(engine, "anna")
    eh, other = _emp(client), _emp(client)
    assert _invite(client, eh, cid, role="").status_code == 422          # no role, no need
    assert _invite(client, eh, cid, description="Работа в команде").status_code == 422
    assert _invite(client, eh, cid, description="коротко").status_code == 422
    assert _invite(client, eh, cid, salary_type="BRUTTO").status_code == 422
    assert _invite(client, eh, cid, salary_to=1000).status_code == 422
    ok = _invite(client, eh, cid)
    assert ok.status_code == 201, ok.text
    inv = ok.json()
    assert inv["need_id"] is None and inv["salary_type"] == "NET"
    assert inv["candidate"]["display_name"] and inv["candidate"]["specialization"]
    assert "contacts" not in inv and "email" not in str(inv)
    assert _invite(client, eh, cid).status_code == 409                    # duplicate blocked
    pool = client.get("/api/employer/pool", headers=eh).json()["candidates"]
    row = next(c for c in pool if c["candidate_id"] == cid)
    assert row["invitation_status"] == "SENT" and row["specialization"]
    assert client.get(f"/api/employer/invitations/{inv['id']}", headers=other).status_code == 404
    assert client.get(f"/api/employer/candidates/{cid}", headers=eh).json()["contact_status"] == "LOCKED"
    # candidate declines -> still no contacts
    assert client.post(f"/api/candidates/me/invitations/{inv['id']}/decline", headers=ch).status_code == 200
    assert "contacts" not in client.get(f"/api/employer/invitations/{inv['id']}", headers=eh).json()
    assert client.get(f"/api/employer/candidates/{cid}", headers=eh).json()["invitation_status"] == "DECLINED"
    # a candidate cannot use employer endpoints
    assert client.post("/api/employer/invitations", headers=ch, json={}).status_code == 401


def test_invitation_from_need_accept_unlocks_contacts_for_sender_only(env):  # noqa: F811
    client, engine = env
    cid, ch = _cand(engine, "anna")
    eh, other = _emp(client), _emp(client)
    need = client.post("/api/employer/needs", headers=eh, json={**NEED, "salary_type": "NET"}).json()
    assert need["salary_type"] == "NET"
    r = _invite(client, eh, cid, need_id=need["id"], role=None, salary_type=need["salary_type"])
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["salary_type"] == "NET" and inv["need_id"] == need["id"] and inv["role"] == need["title"]
    mine = client.get("/api/candidates/me/invitations", headers=ch).json()
    seen = next(i for i in mine if i["id"] == inv["id"])
    assert seen["salary_type"] == "NET" and "Задач" in seen["description"] or len(seen["description"]) >= 20
    assert "contacts" not in client.get(f"/api/employer/invitations/{inv['id']}", headers=eh).json()
    ok = client.post(f"/api/candidates/me/invitations/{inv['id']}/accept", headers=ch)
    assert ok.status_code == 200
    after = client.get(f"/api/employer/invitations/{inv['id']}", headers=eh).json()
    assert after["contacts"]["email"] and after["status"] == "CONTACTS_UNLOCKED"
    detail = client.get(f"/api/employer/candidates/{cid}", headers=eh).json()
    assert detail["contact_status"] == "UNLOCKED" and detail["invitation_status"] == "CONTACTS_UNLOCKED"
    foreign = client.get(f"/api/employer/candidates/{cid}", headers=other).json()
    assert foreign["contact_status"] == "LOCKED" and "contacts" not in foreign
    assert client.get(f"/api/employer/invitations/{inv['id']}", headers=other).status_code == 404
