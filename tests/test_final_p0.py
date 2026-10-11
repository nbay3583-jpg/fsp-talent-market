"""Regression tests for the final P0 fixes (items 3, 7, 10, 12, 15, 16 of the tester's list)."""

from fsp_market.notifications.email import OUTBOX
from tests.test_phase7_demo import (  # noqa: F401
    NEED,
    employer_with_need,
    env,
    login,
    take_assessment,
)

DESC = "Разработка backend-сервисов на FastAPI и PostgreSQL, ревью кода, дежурства раз в месяц"


def _match(client, eh, need_id):
    r = client.post(f"/api/employer/needs/{need_id}/match?limit=50", headers=eh)
    assert r.status_code == 201, r.text
    return r.json()


def _invite(client, eh, cid, need_id=None, **over):
    body = {"candidate_id": cid, "description": DESC, "salary_from": 200000, "salary_to": 250000,
            "salary_type": "GROSS", "work_format": "REMOTE", "message": "Привет!"}
    if need_id is None:
        body["role"] = "Backend Developer"
    else:
        body["need_id"] = need_id
    body.update(over)
    return client.post("/api/employer/invitations", json=body, headers=eh)


def _candidate_in_runs(client, eh, *need_ids):
    sets = [{r["candidate"]["candidate_id"] for r in _match(client, eh, n)["results"]} for n in need_ids]
    common = set.intersection(*sets)
    assert common, "demo pool must contain a candidate matching both needs"
    return min(common)


# --- №16: numeric answer 0 -----------------------------------------------------------------
def test_zero_numeric_answer_is_accepted_by_autosave_and_submit(env):  # noqa: F811
    client, _ = env
    h, _info = login(client, "candidate_alexey")
    start = client.post("/api/assessments", json={"target_grade": "MIDDLE"}, headers=h).json()
    ref = client.get(f"/api/demo/assessments/{start['attempt_id']}/reference-answers", headers=h).json()["answers"]
    answers = {t["variant_id"]: ref[str(t["variant_id"])] for t in start["tasks"]}
    number_tasks = [t for t in start["tasks"] if t["answer_type"] == "number"]
    assert number_tasks
    for forced in (0, "0"):
        vid = number_tasks[0]["variant_id"]
        put = client.put(f"/api/assessments/{start['attempt_id']}/answers", json={"answers": {vid: forced}}, headers=h)
        assert put.status_code == 200, put.text
    saved = client.get(f"/api/assessments/{start['attempt_id']}", headers=h).json()["saved_answers"]
    assert str(saved[str(vid)]) == "0"
    answers[vid] = 0
    done = client.post(f"/api/assessments/{start['attempt_id']}/submit", json={"answers": answers}, headers=h)
    assert done.status_code == 200, done.text


# --- №3: new candidate visibility ----------------------------------------------------------
def test_new_candidate_becomes_visible_only_after_email_verification(env):  # noqa: F811
    client, _ = env
    eh, _need = employer_with_need(client)
    reg = client.post("/api/candidates", json={"email": "fresh@new.io", "full_name": "Новый Кандидат",
                                               "claimed_grade": "MIDDLE"})
    assert reg.status_code == 201
    ch = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    cid = reg.json()["candidate_id"]

    def in_pool():
        pool = client.get("/api/employer/pool?limit=100", headers=eh).json()["candidates"]
        return any(c["candidate_id"] == cid for c in pool)

    me = client.get("/api/candidates/me", headers=ch).json()
    assert not in_pool() and me["preferences"]["published"] is False
    assert "email_not_verified" in me["preferences"]["publish_blockers"]
    assert client.get(f"/api/employer/candidates/{cid}", headers=eh).status_code == 404
    token = OUTBOX[-1]["body"].split("verify_email=")[1].split()[0]
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert in_pool()
    assert client.get("/api/candidates/me", headers=ch).json()["preferences"]["published"] is True
    # an explicit opt-out is respected
    assert client.patch("/api/candidates/me/preferences", headers=ch, json={"profile_visible": False}).status_code == 200
    assert not in_pool()


# --- №7: reproducible matching ------------------------------------------------------------
def test_identical_match_requests_are_identical(env):  # noqa: F811
    client, _ = env
    eh, need = employer_with_need(client)
    a, b = _match(client, eh, need["id"]), _match(client, eh, need["id"])
    assert a["run_id"] != b["run_id"]

    def strip(run):
        return [(r["rank"], r["candidate"]["candidate_id"], r["requirement_fit"], r["why"], r["gaps"])
                for r in run["results"]]

    assert strip(a) == strip(b) and a["excluded_summary"] == b["excluded_summary"]
    pa = client.get(f"/api/employer/match-runs/{a['run_id']}", headers=eh).json()
    assert pa["results"][0]["candidate"]["candidate_id"] == a["results"][0]["candidate"]["candidate_id"]


# --- №12: need terms enforced server-side --------------------------------------------------
def test_need_invitation_cannot_change_need_terms(env):  # noqa: F811
    client, _ = env
    eh, need = employer_with_need(client)
    cid = _candidate_in_runs(client, eh, need["id"])
    nid = need["id"]
    assert _invite(client, eh, cid, nid, salary_type="NET").status_code == 409
    assert _invite(client, eh, cid, nid, salary_from=100000, salary_to=150000).status_code == 409
    assert _invite(client, eh, cid, nid, salary_from=300000, salary_to=400000).status_code == 409
    assert _invite(client, eh, cid, nid, work_format="OFFICE").status_code == 409
    assert _invite(client, eh, cid, nid, role="CEO").status_code == 409
    ok = _invite(client, eh, cid, nid, salary_from=210000, salary_to=240000)
    assert ok.status_code == 201, ok.text
    assert ok.json()["role"] == need["title"]


# --- №15: status per need; standalone separate ---------------------------------------------
def test_invitation_status_is_scoped_to_need_and_standalone_is_separate(env):  # noqa: F811
    client, _ = env
    eh, need_a = employer_with_need(client)
    need_b = client.post("/api/employer/needs", json={**NEED, "title": "Backend Python — платформа"}, headers=eh).json()
    cid = _candidate_in_runs(client, eh, need_a["id"], need_b["id"])
    assert _invite(client, eh, cid, need_a["id"]).status_code == 201
    assert _invite(client, eh, cid, need_a["id"]).status_code == 409  # same need: no duplicate

    def status(need):
        run = _match(client, eh, need["id"])
        row = next(r for r in run["results"] if r["candidate"]["candidate_id"] == cid)
        return row["candidate"]["invitation_status"]

    assert status(need_a) == "SENT"
    assert status(need_b) is None  # A does not leak into B
    assert _invite(client, eh, cid, need_b["id"]).status_code == 201
    assert _invite(client, eh, cid).status_code == 201  # standalone from the pool: its own scenario
    pool = client.get("/api/employer/pool?limit=100", headers=eh).json()["candidates"]
    assert next(c for c in pool if c["candidate_id"] == cid)["invitation_status"] == "SENT"


# --- №10: closing a need -------------------------------------------------------------------
def test_closed_need_keeps_history_but_blocks_new_work(env):  # noqa: F811
    client, _ = env
    eh, need = employer_with_need(client)
    run = _match(client, eh, need["id"])
    cid = run["results"][0]["candidate"]["candidate_id"]
    inv = _invite(client, eh, cid, need["id"])
    assert inv.status_code == 201
    closed = client.post(f"/api/employer/needs/{need['id']}/close", headers=eh).json()
    assert closed["status"] == "CLOSED" and closed["closed_at"]
    assert client.post(f"/api/employer/needs/{need['id']}/match", headers=eh).status_code == 409
    other = run["results"][1]["candidate"]["candidate_id"]
    assert _invite(client, eh, other, need["id"]).status_code == 409
    assert client.get(f"/api/employer/match-runs/{run['run_id']}", headers=eh).status_code == 200
    assert client.get(f"/api/employer/invitations/{inv.json()['id']}", headers=eh).json()["status"] == "SENT"
    reopened = client.post(f"/api/employer/needs/{need['id']}/reopen", headers=eh).json()
    assert reopened["status"] == "OPEN"
    assert client.post(f"/api/employer/needs/{need['id']}/match", headers=eh).status_code == 201


# --- №1: phone validation (server side) ---------------------------------------------------
def test_phone_is_validated_and_normalised(env):  # noqa: F811
    client, _ = env
    h, _info = login(client, "candidate_alexey")

    def patch(phone):
        return client.patch("/api/candidates/me/preferences", headers=h, json={"phone": phone})

    for bad in ("abc", "+7 900 12ab", "12345", "+7(900)" + "1" * 20):
        assert patch(bad).status_code == 422, bad
    for good, expected in (("+7 (900) 123-45-67", "+79001234567"), ("8 900 123 45 67", "+79001234567"),
                           ("+4915112345678", "+4915112345678")):
        assert patch(good).status_code == 200
        assert client.get("/api/candidates/me", headers=h).json()["phone"] == expected
    assert patch("").status_code == 200
    assert client.get("/api/candidates/me", headers=h).json()["phone"] is None
