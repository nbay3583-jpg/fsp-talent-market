"""API flow of independent exams: start/submit, profile, RBAC, and Core untouched."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments.models import TaskVariant
from tests.test_phase3_api import env, register  # noqa: F401


def _solve_exam(client, headers, engine, exam, grade, correct=True):
    start = client.post("/api/assessments", json={"target_grade": grade, "exam": exam}, headers=headers)
    assert start.status_code == 201, start.text
    body = start.json()
    assert body["exam"] == exam and 10 <= len(body["tasks"]) <= 12
    assert {t["competency"] for t in body["tasks"]} == {"api_fastapi" if exam == "fastapi" else "postgresql"}
    assert "correct" not in str(body)
    with Session(engine) as s:
        by_id = {v.id: v for v in s.scalars(select(TaskVariant))}
        answers = {}
        for t in body["tasks"]:
            contract = by_id[t["variant_id"]].scoring_contract
            answers[t["variant_id"]] = contract["correct"] if correct else next(
                k for k in t["options"] if k != contract["correct"]
            )
    res = client.post(f"/api/assessments/{body['attempt_id']}/submit", json={"answers": answers}, headers=headers)
    return body, res


def test_exam_end_to_end_and_core_grade_untouched(env):  # noqa: F811
    client, engine = env
    h = register(client, grade="SENIOR")
    cat = client.get("/api/exams", headers=h).json()
    assert {e["exam"] for e in cat} == {"fastapi", "postgresql"}
    _, res = _solve_exam(client, h, engine, "postgresql", "MIDDLE")
    assert res.status_code == 200 and res.json()["passed"] and res.json()["exam"] == "postgresql"
    p = client.get("/api/candidates/me/profile", headers=h).json()
    assert p["verified_grade"] is None and p["verification_status"] == "UNVERIFIED"
    assert p["claimed_grade"] == "SENIOR" and p["assessment"] is None
    assert p["tech_exams"][0]["skill"] == "postgresql"
    sk = next(s for s in p["skills"] if s["skill"] == "postgresql")
    assert sk["verified_level"] == "MIDDLE"
    assert sk["evidence"][0]["type"] == "TECHNOLOGY_ASSESSMENT"


def test_exam_is_private_to_its_candidate_and_validates_input(env):  # noqa: F811
    client, engine = env
    a = register(client, "a@x.io")
    b = register(client, "b@x.io")
    body, _ = _solve_exam(client, a, engine, "fastapi", "JUNIOR", correct=False)
    assert client.get(f"/api/assessments/{body['attempt_id']}", headers=b).status_code == 404
    bad = client.post("/api/assessments", json={"target_grade": "JUNIOR", "exam": "kafka"}, headers=a)
    assert bad.status_code == 422
    assert client.get("/api/exams").status_code in (401, 403)
