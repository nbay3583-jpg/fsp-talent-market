#!/usr/bin/env python3
"""Smoke test of the canonical demo against a RUNNING stack (stdlib only).

    python scripts/smoke.py [BASE_URL]        # default http://localhost:8000 (or :3000 via the nginx proxy)

Needs DEMO_MODE=true and freshly seeded demo data (docker compose up, or `python -m fsp_market.demo reset`).
Walks: candidate assessment -> VERIFIED -> FSP evidence -> employer need -> match (WHY/GAPS) -> contacts
locked -> salary invitation -> ACCEPT -> contacts unlocked, then the DECLINE path keeps contacts hidden.
"""

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def call(method, path, token=None, body=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    if body is not None:
        req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    assert status == expect, f"{method} {path}: expected {expect}, got {status}: {raw[:200]!r}"
    return json.loads(raw) if raw else None


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def login(account):
    return call("POST", "/api/demo/login", body={"account": account})


def take_assessment(token, correct=True):
    start = call("POST", "/api/assessments", token, {"target_grade": "MIDDLE"}, 201)
    ref = call("GET", f"/api/demo/assessments/{start['attempt_id']}/reference-answers", token)["answers"]
    answers = {t["variant_id"]: ref[str(t["variant_id"])] if correct else next(k for k in "ABCD" if k != ref[str(t["variant_id"])]) for t in start["tasks"]}
    return call("POST", f"/api/assessments/{start['attempt_id']}/submit", token, {"answers": answers})


NEED = {"title": "Python Backend (FastAPI)", "target_grade": "MIDDLE", "target_sublevel": "M2", "required_skills": ["api_fastapi", "postgresql"],
        "optional_skills": ["kafka", "docker_basics"], "salary_from": 200000, "salary_to": 250000, "salary_type": "GROSS", "work_formats": ["REMOTE"]}

check(call("GET", "/health")["status"] == "ok", "health")
check(call("GET", "/openapi.json")["paths"], "OpenAPI available")

# candidate with FSP history
a = login("candidate_alexey")
res = take_assessment(a["access_token"])
check(res["verification_status"] == "VERIFIED" and res["claimed_grade"] == "MIDDLE", "Alexey: Backend/Middle VERIFIED")
check(call("POST", "/api/candidates/me/fsp", a["access_token"], {"fsp_id": a["fsp_id"]})["has_history"], "Alexey: FSP evidence attached")
prof = call("GET", "/api/candidates/me/profile", a["access_token"])
types = {e["type"] for s in prof["skills"] for e in s["evidence"]}
check({"CORE_ASSESSMENT", "FSP_ACHIEVEMENT"} <= types and "talent_score" not in prof, "Evidence Profile: claim vs evidence, no talent score")

# employer: need -> match
e = login("employer")["access_token"]
need = call("POST", "/api/employer/needs", e, NEED, 201)
run = call("POST", f"/api/employer/needs/{need['id']}/match?limit=20", e, expect=201)
names = [r["candidate"]["display_name"] for r in run["results"]]
check("Alexey D." in names, f"Alexey D. in shortlist (rank {names.index('Alexey D.') + 1 if 'Alexey D.' in names else '-'})")
check("Fedor E." not in names, "salary-mismatch candidate excluded")
mine = next(r for r in run["results"] if r["candidate"]["display_name"] == "Alexey D.")
check(mine["requirement_fit_label"].startswith("Соответствие этой потребности") and mine["why"] and mine["gaps"], "Requirement Fit + WHY + GAPS")
cid = mine["candidate"]["candidate_id"]
detail = call("GET", f"/api/employer/candidates/{cid}?need_id={need['id']}", e)
check(detail["contact_status"] == "LOCKED" and "alexey@demo.example" not in json.dumps(detail), "contacts hidden before acceptance")

# invitation -> accept -> unlock
inv = call("POST", "/api/employer/invitations", e, {"candidate_id": cid, "need_id": need["id"], "description": "FastAPI platform team", "salary_from": 220000,
           "salary_to": 250000, "salary_type": "GROSS", "work_format": "REMOTE", "message": "Hello!"}, 201)
seen = call("GET", f"/api/candidates/me/invitations/{inv['id']}", a["access_token"])
check((seen["salary_from"], seen["salary_to"], seen["salary_type"]) == (220000, 250000, "GROSS"), "candidate sees salary + GROSS before accepting")
check("contacts" not in call("GET", f"/api/employer/invitations/{inv['id']}", e), "still locked while VIEWED")
check(call("POST", f"/api/candidates/me/invitations/{inv['id']}/accept", a["access_token"])["status"] == "CONTACTS_UNLOCKED", "ACCEPT")
after = call("GET", f"/api/employer/invitations/{inv['id']}", e)
check(after.get("contacts", {}).get("email") == "alexey@demo.example", "contacts unlocked after ACCEPT")

# no-FSP candidate + DECLINE path
m = login("candidate_mila")
check(take_assessment(m["access_token"])["verification_status"] == "VERIFIED", "Mila (no FSP history): VERIFIED")
check(call("POST", "/api/candidates/me/fsp", m["access_token"], {"fsp_id": m["fsp_id"]}) == {"evidence_added": 0, "has_history": False}, "no FSP history handled")
run2 = call("POST", f"/api/employer/needs/{need['id']}/match?limit=20", e, expect=201)
mc = next(r["candidate"]["candidate_id"] for r in run2["results"] if r["candidate"]["display_name"] == "Mila N.")
inv2 = call("POST", "/api/employer/invitations", e, {"candidate_id": mc, "need_id": need["id"], "description": "d", "salary_from": 210000, "salary_to": 240000,
            "salary_type": "NET", "work_format": "REMOTE", "message": "m"}, 201)
check(call("POST", f"/api/candidates/me/invitations/{inv2['id']}/decline", m["access_token"])["status"] == "DECLINED", "DECLINE")
after2 = call("GET", f"/api/employer/invitations/{inv2['id']}", e)
check("contacts" not in after2 and "mila@demo.example" not in json.dumps(call("GET", f"/api/employer/candidates/{mc}", e)), "contacts stay hidden after DECLINE")

pool = call("GET", "/api/employer/pool?verification=NOT_VERIFIED&limit=50", e)
check(pool["total"] >= 1 and "@demo.example" not in json.dumps(pool), "Full Pool filter works, no contacts")
print("\nSMOKE OK: canonical demo passes against", BASE)
