from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import fsp_market.models  # noqa: F401
from fsp_market.common.enums import Grade, SalaryType, Sublevel, VerificationStatus
from fsp_market.db import Base, get_session
from fsp_market.main import app
from fsp_market.matching import engine as eng
from fsp_market.matching.demo_seed import seed_matching_demo
from fsp_market.matching.facts import CandidateFacts, NeedSkillSpec, NeedSpec, SkillFacts
from fsp_market.matching.policy import DEFAULT_POLICY

NOW = datetime(2026, 10, 6, tzinfo=UTC)

# ---------------------------------------------------------------- pure engine


def need(**kw) -> NeedSpec:
    base = {
        "specialization_id": 1,
        "target_grade": Grade.MIDDLE,
        "target_sublevel": Sublevel.M2,
        "salary_from": 200_000,
        "salary_to": 250_000,
        "salary_type": SalaryType.GROSS,
        "work_formats": ("REMOTE",),
        "location": None,
        "max_start_days": None,
        "skills": (NeedSkillSpec("api_fastapi", True, 1.0), NeedSkillSpec("kafka", False, 0.4)),
    }
    base.update(kw)
    return NeedSpec(**base)


def cand(**kw) -> CandidateFacts:
    base = {
        "candidate_id": 1,
        "specialization_id": 1,
        "claimed_grade": Grade.MIDDLE,
        "verification_status": VerificationStatus.VERIFIED,
        "verified_grade": Grade.MIDDLE,
        "verified_sublevel": Sublevel.M2,
        "salary_min": 220_000,
        "salary_type": SalaryType.GROSS,
        "work_formats": ("REMOTE",),
        "location": "Moscow",
        "available_in_days": 0,
        "profile_visible": True,
        "open_to_invitations": True,
        "skills": {},
    }
    base.update(kw)
    return CandidateFacts(**base)


def test_sublevel_tolerance_is_internal_not_public_grade():
    assert eng.allowed_sublevels(need()) == {Sublevel.M1, Sublevel.M2, Sublevel.M3}
    assert eng.allowed_sublevels(need(target_sublevel=None)) == {
        Sublevel.M1,
        Sublevel.M2,
        Sublevel.M3,
    }
    for sub, ok in [
        (Sublevel.M1, True),
        (Sublevel.M3, True),
        (Sublevel.J3, False),
        (Sublevel.S1, False),
    ]:
        got = eng.hard_filter(need(), cand(verified_sublevel=sub))
        assert (got == []) is ok, sub


def test_sublevel_tolerance_crosses_grade_border_only_by_policy():
    from dataclasses import replace

    from fsp_market.matching.policy import DEFAULT_POLICY

    edge = need(target_sublevel=Sublevel.M1)
    assert eng.allowed_sublevels(edge) == {Sublevel.J3, Sublevel.M1, Sublevel.M2}
    strict = replace(DEFAULT_POLICY, cross_grade_tolerance=False)
    assert eng.allowed_sublevels(edge, strict) == {Sublevel.M1, Sublevel.M2}
    top = need(target_sublevel=Sublevel.M3)
    assert eng.allowed_sublevels(top) == {Sublevel.M2, Sublevel.M3, Sublevel.S1}
    # J1..S3 scale ends: no wrap-around
    low = need(target_grade=Grade.JUNIOR, target_sublevel=Sublevel.J1)
    assert eng.allowed_sublevels(low) == {Sublevel.J1, Sublevel.J2}


def test_hard_filters_each_exclude():
    n = need()
    assert eng.hard_filter(n, cand(specialization_id=2)) == [eng.SPECIALIZATION_MISMATCH]
    assert eng.hard_filter(n, cand(salary_min=300_000)) == [eng.SALARY_MISMATCH]
    assert eng.hard_filter(n, cand(work_formats=("OFFICE",))) == [eng.WORK_FORMAT_MISMATCH]
    assert eng.hard_filter(n, cand(profile_visible=False)) == [eng.NOT_VISIBLE]
    assert eng.hard_filter(n, cand(open_to_invitations=False)) == [eng.NOT_OPEN]
    assert eng.hard_filter(
        n,
        cand(
            claimed_grade=None,
            verification_status=VerificationStatus.UNVERIFIED,
            verified_grade=None,
            verified_sublevel=None,
        ),
    ) == [eng.GRADE_UNKNOWN]
    assert eng.hard_filter(need(max_start_days=7), cand(available_in_days=30)) == [
        eng.AVAILABILITY_MISMATCH
    ]
    office = need(work_formats=("OFFICE",), location="Kazan")
    assert eng.hard_filter(office, cand(work_formats=("OFFICE",), location="Moscow")) == [
        eng.LOCATION_MISMATCH
    ]
    assert eng.hard_filter(office, cand(work_formats=("OFFICE",), location="kazan")) == []


def test_salary_boundaries_and_net_conversion():
    assert eng.hard_filter(need(), cand(salary_min=250_000)) == []
    assert eng.hard_filter(need(), cand(salary_min=250_001)) == [eng.SALARY_MISMATCH]
    # 217,500 NET = 250,000 GROSS at 13% NDFL
    assert eng.hard_filter(need(), cand(salary_min=217_500, salary_type=SalaryType.NET)) == []
    assert eng.hard_filter(need(), cand(salary_min=217_600, salary_type=SalaryType.NET)) == [
        eng.SALARY_MISMATCH
    ]
    assert eng.hard_filter(need(), cand(salary_min=None)) == []


def test_not_verified_candidate_stays_eligible_with_penalty():
    nv = cand(
        verification_status=VerificationStatus.NOT_VERIFIED,
        verified_grade=None,
        verified_sublevel=None,
    )
    assert eng.hard_filter(need(), nv) == []  # kept in the pool
    skills = {
        "api_fastapi": SkillFacts(
            "api_fastapi", claimed=True, experience=True, latest_evidence_at=NOW
        )
    }
    weak = eng.requirement_fit(
        need(),
        cand(
            skills=skills,
            verification_status=VerificationStatus.NOT_VERIFIED,
            verified_grade=None,
            verified_sublevel=None,
        ),
        NOW,
    )
    strong = eng.requirement_fit(need(), cand(skills=skills), NOW)
    assert weak.fit < strong.fit
    assert any(g.code == "GRADE_NOT_VERIFIED" for g in weak.gaps)
    assert not any(w.code == "GRADE_VERIFIED" for w in weak.why)


def test_why_gaps_reflect_only_real_facts():
    skills = {
        "api_fastapi": SkillFacts(
            "api_fastapi",
            claimed=True,
            verified_level=Grade.MIDDLE,
            verified_sublevel=Sublevel.M2,
            latest_evidence_at=NOW,
        ),
        "kafka": SkillFacts("kafka", claimed=True),  # claim only
    }
    r = eng.requirement_fit(need(), cand(skills=skills), NOW)
    why = {(x.code, x.skill) for x in r.why}
    gaps = {(x.code, x.skill) for x in r.gaps}
    assert ("SKILL_VERIFIED", "api_fastapi") in why and ("GRADE_VERIFIED", None) in why
    assert ("SKILL_UNVERIFIED", "kafka") in gaps
    assert not any(c == "FSP_RELEVANT" for c, _ in why)  # no FSP data -> no FSP reason
    assert ("SKILL_VERIFIED", "kafka") not in why


def test_fit_is_deterministic_and_relevant_fsp_only_helps_relevant_skills():
    base = {
        "api_fastapi": SkillFacts(
            "api_fastapi", verified_level=Grade.MIDDLE, latest_evidence_at=NOW
        )
    }
    relevant = {
        "api_fastapi": SkillFacts(
            "api_fastapi",
            verified_level=Grade.MIDDLE,
            fsp_titles=("FSP Product",),
            latest_evidence_at=NOW,
        )
    }
    unrelated = dict(base, python=SkillFacts("python", fsp_titles=("FSP Algo",)))
    f0 = eng.requirement_fit(need(), cand(skills=base), NOW)
    assert f0 == eng.requirement_fit(need(), cand(skills=base), NOW)
    assert eng.requirement_fit(need(), cand(skills=relevant), NOW).fit > f0.fit
    assert eng.requirement_fit(need(), cand(skills=unrelated), NOW).fit == f0.fit


def test_weights_are_configured_in_one_policy():
    assert abs(sum(DEFAULT_POLICY.weights.values()) - 1.0) < 1e-9
    # context = deterministic Experience Context Fit (declared experience, no LLM)
    assert "context" in DEFAULT_POLICY.active_components


# ---------------------------------------------------------------- API + demo data


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
    yield TestClient(app)
    app.dependency_overrides.clear()


def employer(client, email="hr@x.io"):
    r = client.post("/api/employers", json={"company_name": "X", "contact_email": email})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


NEED = {
    "title": "Python Backend",
    "target_grade": "MIDDLE",
    "target_sublevel": "M3",
    "required_skills": ["api_fastapi", "postgresql"],
    "optional_skills": ["kafka"],
    "salary_from": 200000,
    "salary_to": 250000,
    "salary_type": "GROSS",
    "work_formats": ["REMOTE"],
}


def run(client, h, need=NEED, limit=50):
    n = client.post("/api/employer/needs", json=need, headers=h)
    assert n.status_code == 201, n.text
    r = client.post(f"/api/employer/needs/{n.json()['id']}/match?limit={limit}", headers=h)
    assert r.status_code == 201, r.text
    return n.json(), r.json()


def by_name(res):
    return {x["candidate"]["display_name"]: x for x in res["results"]}


def test_gate_matched_pool_excludes_incompatible_and_explains(env):
    _, res = run(env, employer(env))
    names = by_name(res)
    for excluded in [
        "Fedor E.",
        "Viktor O.",
        "Galina O.",
        "Lena H.",
        "Misha C.",
        "Oleg F.",
        "Kirill J.",
        "Yuri J.",
    ]:
        assert excluded not in names, excluded
    for kept in ["Anna V.", "Ulyana E.", "Tanya N.", "Julia M.", "Hana A.", "Denis R.", "Nina N."]:
        assert kept in names, kept
    assert res["excluded_summary"]["SALARY_MISMATCH"] == 2
    for x in res["results"]:
        assert x["requirement_fit_label"].startswith("Соответствие этой потребности")
        assert x["why"] is not None and x["gaps"] is not None
        assert "talent_score" not in x
    ranks = [x["rank"] for x in res["results"]]
    assert ranks == sorted(ranks) == list(range(1, len(ranks) + 1))


def test_ranking_semantics(env):
    _, res = run(env, employer(env, "hr2@x.io"))
    n = by_name(res)
    fit = {k: v["requirement_fit"] for k, v in n.items()}
    assert fit["Boris P."] > fit["Anna V."]  # relevant FSP (FastAPI) helps
    assert fit["Clara A."] == fit["Anna V."]  # unrelated FSP (algorithms) does not
    assert fit["Nina N."] == fit["Anna V."]  # no FSP history: not penalised
    assert fit["Anna V."] > fit["Elena Q."]  # extra PostgreSQL evidence
    assert fit["Elena Q."] > fit["Denis R."]  # verified assessment beats strong-CV claims
    assert fit["Julia M."] < fit["Anna V."]  # M2: neighbour of the M3 target
    assert fit["Hana A."] < min(
        v for k, v in fit.items() if n[k]["candidate"]["verification_status"] == "VERIFIED"
    )
    assert n["Hana A."]["candidate"]["claimed_grade"] == "MIDDLE"  # never turned into Junior
    assert n["Denis R."]["candidate"]["verification_status"] == "NOT_VERIFIED"


def test_why_gaps_content_matches_evidence(env):
    _, res = run(env, employer(env, "hr3@x.io"))
    n = by_name(res)
    anna = {(w["code"], w["skill"]) for w in n["Anna V."]["why"]}
    assert ("SKILL_VERIFIED", "api_fastapi") in anna and ("SKILL_EXPERIENCE", "postgresql") in anna
    assert ("SALARY_OVERLAP", None) in anna and ("WORK_FORMAT_MATCH", None) in anna
    assert not any(c == "FSP_RELEVANT" for c, _ in anna)
    agaps = {(g["code"], g["skill"]) for g in n["Anna V."]["gaps"]}
    assert ("WEAK_EVIDENCE", "postgresql") in agaps and ("SKILL_UNVERIFIED", "kafka") in agaps
    assert ("FSP_RELEVANT", "api_fastapi") in {
        (w["code"], w["skill"]) for w in n["Boris P."]["why"]
    }
    denis = {(g["code"], g["skill"]) for g in n["Denis R."]["gaps"]}
    assert ("GRADE_NOT_VERIFIED", None) in denis and ("SKILL_UNVERIFIED", "postgresql") in denis
    assert not any(w["code"] == "SKILL_VERIFIED" for w in n["Denis R."]["why"])


def test_deterministic_and_refinement_does_not_change_run(env):
    h = employer(env, "hr4@x.io")
    _, a = run(env, h)
    _, b = run(env, h)
    strip = lambda r: [
        (x["rank"], x["candidate"]["candidate_id"], x["requirement_fit"]) for x in r["results"]
    ]
    assert strip(a) == strip(b)
    refined = env.get(
        f"/api/employer/match-runs/{a['run_id']}?verified_only=true&min_fit=0.6&limit=3", headers=h
    ).json()
    assert refined["filtered_total"] < refined["matched_total"] and len(refined["results"]) <= 3
    assert all(x["requirement_fit"] >= 0.6 for x in refined["results"])
    again = env.get(f"/api/employer/match-runs/{a['run_id']}?limit=50", headers=h).json()
    assert strip(again) == strip(a)  # original run intact
    page2 = env.get(f"/api/employer/match-runs/{a['run_id']}?limit=3&offset=3", headers=h).json()
    assert [x["rank"] for x in page2["results"]] == [4, 5, 6]


def test_full_pool_filters_and_privacy(env):
    h = employer(env, "hr5@x.io")
    pool = env.get("/api/employer/pool?limit=100", headers=h).json()
    names = {c["display_name"] for c in pool["candidates"]}
    assert "Lena H." not in names  # hidden profile never listed
    assert {
        "Denis R.",
        "Hana A.",
        "Fedor E.",
        "Oleg F.",
    } <= names  # NOT_VERIFIED / mismatches remain findable
    q = lambda s: {
        c["display_name"]
        for c in env.get(f"/api/employer/pool?limit=100&{s}", headers=h).json()["candidates"]
    }
    assert q("grade=JUNIOR") == {"Kirill J.", "Yuri J."}
    assert "Hana A." in q("verification=NOT_VERIFIED") and "Anna V." not in q(
        "verification=NOT_VERIFIED"
    )
    assert q("verification=VERIFIED") >= {"Anna V."} and "Denis R." not in q(
        "verification=VERIFIED"
    )
    assert q("skill=api_fastapi&skill=sql") >= {"Anna V."} and "Denis R." not in q(
        "skill=api_fastapi"
    )
    assert q("has_fsp=true") == {
        "Boris P.",
        "Clara A.",
    }  # cyber-only / empty FSP history = no evidence
    assert "Anna V." in q("has_fsp=false")
    assert q("work_format=OFFICE") == {"Galina O."}
    assert "Fedor E." not in q("salary_max=250000") and "Anna V." in q("salary_max=250000")
    assert q("sublevel=M3") >= {"Anna V."} and "Julia M." not in q("sublevel=M3")
    assert q("location=moscow") >= {"Anna V."} and "Boris P." not in q("location=moscow")
    blob = env.get("/api/employer/pool?limit=100", headers=h).text
    for secret in ["@demo.example", "email", "phone", "full_name", "FSP-1001", "fsp_id"]:
        assert secret not in blob, secret


def test_candidate_detail_and_privacy(env):
    h = employer(env, "hr6@x.io")
    n, res = run(env, h)
    anna = by_name(res)["Anna V."]["candidate"]["candidate_id"]
    d = env.get(f"/api/employer/candidates/{anna}?need_id={n['id']}", headers=h)
    assert d.status_code == 200
    body = d.json()
    assert body["fit"]["eligible"] is True and body["fit"]["why"] and "gaps" in body["fit"]
    assert body["verification_status"] == "VERIFIED"
    for secret in ["@demo.example", "Anna Verified", "email", "phone"]:
        assert secret not in d.text
    fedor = by_name(
        env.get("/api/employer/pool?limit=100", headers=h).json()
        | {
            "results": [
                {"candidate": c}
                for c in env.get("/api/employer/pool?limit=100", headers=h).json()["candidates"]
            ]
        }
    )["Fedor E."]
    ex = env.get(
        f"/api/employer/candidates/{fedor['candidate']['candidate_id']}?need_id={n['id']}",
        headers=h,
    ).json()
    assert ex["fit"] == {"eligible": False, "exclusions": ["SALARY_MISMATCH"]}
    lena = env.get("/api/employer/candidates/11", headers=h)  # Lena (hidden) is candidate #11
    assert lena.status_code == 404


def test_auth_roles_and_isolation(env):
    a, b = employer(env, "a@x.io"), employer(env, "b@x.io")
    n, res = run(env, a)
    assert env.get(f"/api/employer/needs/{n['id']}", headers=b).status_code == 404
    assert env.post(f"/api/employer/needs/{n['id']}/match", headers=b).status_code == 404
    assert env.get(f"/api/employer/match-runs/{res['run_id']}", headers=b).status_code == 404
    assert env.get("/api/employer/pool").status_code == 401
    cand = env.post(
        "/api/candidates", json={"email": "c@x.io", "full_name": "C D", "claimed_grade": "MIDDLE"}
    ).json()
    ch = {"Authorization": f"Bearer {cand['access_token']}"}
    assert (
        env.get("/api/employer/pool", headers=ch).status_code == 401
    )  # candidate token != employer
    assert (
        env.get("/api/candidates/me/profile", headers=a).status_code == 401
    )  # employer token != candidate


def test_need_validation(env):
    h = employer(env, "v@x.io")
    bad = dict(NEED, salary_from=300000)
    assert env.post("/api/employer/needs", json=bad, headers=h).status_code == 422
    assert (
        env.post(
            "/api/employer/needs", json=dict(NEED, required_skills=["nope"]), headers=h
        ).status_code
        == 422
    )
    assert (
        env.post(
            "/api/employer/needs", json=dict(NEED, target_sublevel="J1"), headers=h
        ).status_code
        == 422
    )
    assert (
        env.post("/api/employer/needs", json=dict(NEED, work_formats=[]), headers=h).status_code
        == 422
    )


def test_candidate_preferences_endpoint(env):
    cand = env.post(
        "/api/candidates", json={"email": "p@x.io", "full_name": "P Q", "claimed_grade": "MIDDLE"}
    ).json()
    ch = {"Authorization": f"Bearer {cand['access_token']}"}
    prefs = {
        "salary_min": 180000,
        "salary_type": "NET",
        "work_formats": ["REMOTE"],
        "profile_visible": True,
    }
    # publishing the profile requires a confirmed email
    blocked = env.patch("/api/candidates/me/preferences", headers=ch, json=prefs)
    assert blocked.status_code == 403
    from fsp_market.notifications.email import OUTBOX

    token = OUTBOX[-1]["body"].split("verify_email=")[1].split()[0]
    assert env.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    r = env.patch("/api/candidates/me/preferences", headers=ch, json=prefs)
    assert r.status_code == 200


def test_ats_export_csv_and_json_are_private_and_owner_only(env):
    h = employer(env, "ats@x.io")
    _, res = run(env, h)
    rid = res["run_id"]
    js = env.get(f"/api/employer/match-runs/{rid}/export?format=json", headers=h)
    assert js.status_code == 200 and "attachment" in js.headers["content-disposition"]
    rows = js.json()["candidates"]
    assert [r["rank"] for r in rows] == sorted(r["rank"] for r in rows) and len(rows) == len(res["results"])
    csv_text = env.get(f"/api/employer/match-runs/{rid}/export", headers=h).text
    assert csv_text.lstrip("﻿").startswith("rank,candidate_id,display_name")
    for secret in ("@demo.example", "+7-900", "Anna Verified"):
        assert secret not in csv_text and secret not in js.text
    other = employer(env, "other-ats@x.io")
    assert env.get(f"/api/employer/match-runs/{rid}/export", headers=other).status_code == 404
