import pytest

from fsp_market.config import get_settings
from fsp_market.teamfit import compat
from tests.test_phase9_teamfit import NEED, _cand, _emp, env  # noqa: F401


def test_partial_answers_are_not_neutral_and_need_three_shared_axes():
    assert compat.validate_answers({"pace": 5}) == {"pace": 5}
    with pytest.raises(ValueError):
        compat.validate_answers({})
    with pytest.raises(ValueError):
        compat.validate_answers({"nope": 3})
    team = {k: 3.0 for k in compat.AXES}
    assert compat.work_style_compat({"pace": 3, "autonomy": 3}, team) is None  # < 3 shared axes
    ws = compat.work_style_compat({"pace": 3, "autonomy": 5, "feedback": 3}, team)
    assert ws["total"] == 3 and ws["close"] == 2  # unanswered axes are not compared at all


def test_aggregate_counts_only_answered_axes():
    rows = [{"pace": 5}, {"pace": 3, "autonomy": 1}, {"pace": 4}]
    agg = compat.aggregate(rows)["aggregate"]
    assert agg == {"pace": 4.0}  # autonomy has 1 answer < 3, so it is hidden


def test_recommendations_insufficient_data_without_assessment(env):  # noqa: F811
    client, _ = env
    r = client.post("/api/candidates", json={"email": "new@x.io", "full_name": "Новый Кандидат",
                                              "claimed_grade": "MIDDLE"})
    assert r.status_code == 201
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    eh = _emp(client)
    n = client.post("/api/employer/needs", headers=eh, json=NEED).json()
    assert client.put(f"/api/employer/needs/{n['id']}/publication", headers=eh, json={"public": True}).status_code == 200
    rec = client.get("/api/candidates/me/recommendations", headers=h).json()
    assert rec["assessed"] is False and rec["next_action"] == "take_assessment"
    assert rec["items"] and all(i["fit_state"] == "insufficient_data" and i["mutual_fit"] is None for i in rec["items"])


def test_assessed_candidate_keeps_numeric_fit(env):  # noqa: F811
    client, engine = env
    _, ch = _cand(engine, "anna")
    eh = _emp(client)
    n = client.post("/api/employer/needs", headers=eh, json=NEED).json()
    assert client.put(f"/api/employer/needs/{n['id']}/publication", headers=eh, json={"public": True}).status_code == 200
    items = client.get("/api/candidates/me/recommendations", headers=ch).json()["items"]
    assert items and all(i["fit_state"] == "ready" and i["requirement_fit"] is not None for i in items)


def test_catalog_marks_unavailable_specialization_and_blocks_assessment(env):  # noqa: F811
    client, _ = env
    specs = {s["code"]: s for s in client.get("/api/catalog").json()["specializations"]}
    assert specs["backend_python"]["assessment_available"] is True
    assert specs["frontend_ts"]["assessment_available"] is False
    r = client.post("/api/candidates", json={"email": "fe@x.io", "full_name": "Фронт Энд",
                                              "claimed_grade": "JUNIOR", "specialization": "frontend_ts"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    a = client.post("/api/assessments", headers=h, json={"target_grade": "JUNIOR"})
    assert a.status_code == 409 and "not available" in a.json()["detail"]
    labels = client.get("/api/catalog").json()["sublevel_labels"]
    assert labels["M1"] == "базовый" and labels["M3"] == "сильный"


def test_email_resend_reports_real_delivery_and_hides_link_outside_demo(env, monkeypatch):  # noqa: F811
    client, _ = env
    r = client.post("/api/candidates", json={"email": "mail@x.io", "full_name": "Почта Тест", "claimed_grade": "JUNIOR"})
    assert r.json()["email_verification_sent"] is False  # no SMTP in tests: not claimed as sent
    assert "demo_verification_link" not in r.json() or get_settings().demo_mode
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    import fsp_market.auth.email_verification as ev

    monkeypatch.setattr(ev, "RESEND_COOLDOWN_SECONDS", 0)
    out = client.post("/api/candidates/me/email/resend", headers=h).json()
    assert out["sent"] is False
    assert ("demo_verification_link" in out) == get_settings().demo_mode
