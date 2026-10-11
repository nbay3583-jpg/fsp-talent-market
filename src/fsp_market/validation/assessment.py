"""MVP reference-solution validation of the Core Assessment (NOT psychometric calibration).

Reference personas answer by a fixed rule (which grade's questions they 'know', plus optional
per-competency slips). The expected outcome per persona and grade is written by hand below,
independently of the scoring code, and compared with what the real pipeline produces.
Synthetic personas check rules, thresholds and content integrity; they say nothing about how
real candidates would score.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401
from fsp_market.assessments.models import TaskFamily, TaskTemplate, TaskVariant
from fsp_market.assessments.scoring import PASS_THRESHOLD, score_answer
from fsp_market.assessments.seed import seed_backend_python
from fsp_market.assessments.service import (
    score_attempt,
    start_attempt,
    submit_answers,
    wrong_answer,
)
from fsp_market.candidates.models import Candidate
from fsp_market.common.enums import Grade
from fsp_market.db import Base
from fsp_market.taxonomy.models import Competency
from fsp_market.validation import metrics

NOW = datetime(2026, 10, 6, tzinfo=UTC)
GRADES = ["JUNIOR", "MIDDLE", "SENIOR"]
SUBLEVELS = ["J1", "J2", "J3", "M1", "M2", "M3", "S1", "S2", "S3"]
EXPECTED_COMPETENCIES = [
    "python",
    "sql",
    "api_fastapi",
    "testing",
    "docker_basics",
    "system_thinking",
]
V, N = "VERIFIED", "NOT_VERIFIED"

# knows: grades whose questions the persona answers correctly; slips: competencies answered wrongly
# at that grade. expected: (status, sublevel) per attempted grade, derived by hand from the
# thresholds (J .6 / M .7 / S .75), 11 items per grade, and the sublevel bands of taxonomy/grades.py.
PERSONAS = [
    {
        "id": "P-JUNIOR",
        "desc": "knows Junior material only",
        "knows": ["JUNIOR"],
        "slips": {},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (N, None), "SENIOR": (N, None)},
    },
    {
        "id": "P-MIDDLE",
        "desc": "knows Junior + Middle material",
        "knows": ["JUNIOR", "MIDDLE"],
        "slips": {},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (V, "M3"), "SENIOR": (N, None)},
    },
    {
        "id": "P-SENIOR",
        "desc": "knows everything",
        "knows": GRADES,
        "slips": {},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (V, "M3"), "SENIOR": (V, "S3")},
    },
    {
        "id": "P-WEAK",
        "desc": "answers every question wrongly",
        "knows": [],
        "slips": {},
        "expected": {"JUNIOR": (N, None), "MIDDLE": (N, None), "SENIOR": (N, None)},
    },
    {
        "id": "P-MIDDLE-HIGH",
        "desc": "Middle, slips on testing + docker (9/11 = 0.818 -> M2)",
        "knows": ["JUNIOR", "MIDDLE"],
        "slips": {"MIDDLE": ["testing", "docker_basics"]},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (V, "M2"), "SENIOR": (N, None)},
    },
    {
        "id": "P-MIDDLE-LOW",
        "desc": "Middle, slips on testing + docker + system + API (6/11 = 0.545 < 0.7)",
        "knows": ["JUNIOR", "MIDDLE"],
        "slips": {"MIDDLE": ["testing", "docker_basics", "system_thinking", "api_fastapi"]},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (N, None), "SENIOR": (N, None)},
    },
    {
        "id": "P-SENIOR-EDGE",
        "desc": "Senior, slips on testing (10/11 = 0.909 -> S2)",
        "knows": GRADES,
        "slips": {"SENIOR": ["testing"]},
        "expected": {"JUNIOR": (V, "J3"), "MIDDLE": (V, "M3"), "SENIOR": (V, "S2")},
    },
]
KNOWLEDGE_RANK = {"P-WEAK": 0, "P-JUNIOR": 1, "P-MIDDLE": 2, "P-SENIOR": 3}


def _fresh_db() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_backend_python(session)
    session.commit()
    return session


def _families(session: Session, grade: str):
    return session.scalars(
        select(TaskFamily)
        .where(
            TaskFamily.target_grade == grade,
            TaskFamily.code.like("core.%"),
            TaskFamily.code.notlike("%.x\\_%", escape="\\"),  # the fixed 11-task reference composition
        )
        .order_by(TaskFamily.id)
    ).all()


def _variants(session: Session, family: TaskFamily) -> list[TaskVariant]:
    return session.scalars(
        select(TaskVariant)
        .join(TaskTemplate, TaskTemplate.id == TaskVariant.template_id)
        .where(TaskTemplate.family_id == family.id)
        .order_by(TaskVariant.id)
    ).all()


def _competency(session: Session, family: TaskFamily) -> str:
    return session.scalar(select(Competency.code).where(Competency.id == family.competency_id))


def _answer(persona: dict, grade: str, comp: str, variant: TaskVariant):
    knows = grade in persona["knows"] and comp not in persona["slips"].get(grade, [])
    return variant.scoring_contract["correct"] if knows else wrong_answer(variant)


def _take(
    session: Session, persona: dict, grade: str, rotation: int, serial: int
) -> dict[str, Any]:
    cand = Candidate(
        email=f"{persona['id']}-{grade}-{rotation}-{serial}@a.example", full_name="Ref Persona"
    )
    session.add(cand)
    session.flush()
    chosen = []
    for fam in _families(session, grade):
        variants = _variants(session, fam)
        chosen.append((fam, variants[rotation % len(variants)]))  # force a specific variant
    attempt = start_attempt(
        session, cand.id, Grade(grade), now=NOW, seed=rotation, variant_ids=[v.id for _, v in chosen]
    )
    answers = {v.id: _answer(persona, grade, _competency(session, fam), v) for fam, v in chosen}
    submit_answers(session, attempt.id, answers, now=NOW)
    r = score_attempt(session, attempt.id, now=NOW)
    return {
        "status": str(r.verification_status),
        "sublevel": str(r.achieved_sublevel) if r.achieved_sublevel else None,
        "score": round(r.total_score, 4),
        "items": len(answers),
    }


def _rubric_checks(session: Session) -> dict[str, Any]:
    problems: list[str] = []
    for fam in session.scalars(select(TaskFamily).order_by(TaskFamily.id)):
        dims = {r["dimension"] for r in fam.rubric}
        if abs(sum(r["weight"] for r in fam.rubric) - 1.0) > 1e-9:
            problems.append(f"{fam.code}: rubric weights do not sum to 1")
        variants = _variants(session, fam)
        if len(variants) < 2:
            problems.append(f"{fam.code}: fewer than 2 variants")
        shown = {(v.prompt, repr(v.input_data["options"])) for v in variants}
        if len(shown) != len(variants):
            problems.append(f"{fam.code}: duplicate variants")
        if {v.scoring_contract["points"] for v in variants} != {1.0}:
            problems.append(f"{fam.code}: scoring points differ between variants")
        for v in variants:
            sc, opts = v.scoring_contract, v.input_data["options"]
            if sc["dimension"] not in dims:
                problems.append(f"{v.code}: dimension {sc['dimension']!r} not in family rubric")
            if sc["type"] == "numeric":
                continue
            correct = sc["correct"] if sc["type"] == "set" else [sc["correct"]]
            if not opts or len(opts) < 2 or any(c not in opts for c in correct):
                problems.append(f"{v.code}: correct option missing from options")
            if len(set(opts.values())) != len(opts):
                problems.append(f"{v.code}: duplicate option texts")
            if sc["type"] == "choice" and len(opts) != 4:
                problems.append(f"{v.code}: expected 4 options")
    return {"violations": len(problems), "details": problems}


def _coverage(session: Session) -> dict[str, Any]:
    matrix: dict[str, dict[str, dict[str, int]]] = {c: {} for c in EXPECTED_COMPETENCIES}
    for g in GRADES:
        for fam in _families(session, g):
            cell = matrix[_competency(session, fam)].setdefault(g, {"families": 0, "variants": 0})
            cell["families"] += 1
            cell["variants"] += len(_variants(session, fam))
    covered = {g: sum(1 for c in EXPECTED_COMPETENCIES if g in matrix[c]) for g in GRADES}
    return {
        "matrix": matrix,
        "competencies_covered": covered,
        "coverage_ratio": {g: round(covered[g] / len(EXPECTED_COMPETENCIES), 4) for g in GRADES},
        "items_per_attempt": {g: len(_families(session, g)) for g in GRADES},
    }


def _guessing(session: Session, trials: int = 500) -> dict[str, Any]:
    """Seeded random guesser (uniform over the 4 options): how often is it falsely VERIFIED?"""
    out = {}
    for grade in GRADES:
        fams = _families(session, grade)
        passes = 0
        for t in range(trials):
            rng = random.Random(f"{grade}-{t}")
            correct = 0.0
            for v in (_variants(session, f)[0] for f in fams):
                sc = v.scoring_contract
                if sc["type"] == "numeric":
                    guess = rng.randint(0, 20)
                elif sc["type"] == "set":
                    keys = sorted(v.input_data["options"])
                    guess = rng.sample(keys, rng.randint(1, len(keys)))
                else:
                    guess = rng.choice(sorted(v.input_data["options"]))
                correct += score_answer(sc, guess)
            passes += correct / len(fams) >= PASS_THRESHOLD[Grade(grade)]
        out[grade] = {
            "items": len(fams),
            "trials": trials,
            "false_verification_rate": round(passes / trials, 4),
        }
    return out


def run_assessment_validation() -> dict[str, Any]:
    session = _fresh_db()
    try:
        cases, serial = [], 0
        for p in PERSONAS:
            for g in GRADES:
                for rot in (0, 1):
                    serial += 1
                    r = _take(session, p, g, rot, serial)
                    exp_status, exp_sub = p["expected"][g]
                    cases.append(
                        {
                            "persona": p["id"],
                            "grade": g,
                            "rotation": rot,
                            **r,
                            "expected_status": exp_status,
                            "expected_sublevel": exp_sub,
                            "match": r["status"] == exp_status and r["sublevel"] == exp_sub,
                        }
                    )
        n = len(cases)
        accuracy = sum(c["match"] for c in cases) / n
        # variant stability: same persona + grade, variant rotation 0 vs 1
        stable, diffs, unstable = 0, [], []
        for p in PERSONAS:
            for g in GRADES:
                a, b = (
                    next(
                        c
                        for c in cases
                        if (c["persona"], c["grade"], c["rotation"]) == (p["id"], g, r)
                    )
                    for r in (0, 1)
                )
                same = (a["status"], a["sublevel"]) == (b["status"], b["sublevel"])
                stable += same
                diffs.append(abs(a["score"] - b["score"]))
                if not same or a["score"] != b["score"]:
                    unstable.append(
                        {
                            "id": f"variant-divergence:{p['id']}:{g}",
                            "expected": "same outcome on both equivalent variants",
                            "actual": f"rot0={a['status']}/{a['sublevel']}/{a['score']} rot1={b['status']}/{b['sublevel']}/{b['score']}",
                            "probable_reason": "an equivalent variant is easier or harder than its sibling (content defect)",
                        }
                    )
        pairs = len(PERSONAS) * len(GRADES)
        # disagreement of more than one sublevel (a missed verification counts as a disagreement)
        exp_verified = [c for c in cases if c["expected_status"] == V]

        def far(c):
            if c["status"] != V:
                return True
            return abs(SUBLEVELS.index(c["sublevel"]) - SUBLEVELS.index(c["expected_sublevel"])) > 1

        disagree = sum(far(c) for c in exp_verified)

        # highest verified grade per persona vs expected
        def highest(cs):
            ok = [g for g in GRADES if any(c["grade"] == g and c["status"] == V for c in cs)]
            return ok[-1] if ok else None

        hv = []
        for p in PERSONAS:
            exp_ok = [g for g in GRADES if p["expected"][g][0] == V]
            hv.append(
                highest([c for c in cases if c["persona"] == p["id"]])
                == (exp_ok[-1] if exp_ok else None)
            )
        # discrimination on each grade test between personas that know the grade and those that do not
        disc = {}
        core = [p for p in PERSONAS if p["id"] in KNOWLEDGE_RANK]
        for g in GRADES:
            score = {
                p["id"]: next(
                    c["score"]
                    for c in cases
                    if c["persona"] == p["id"] and c["grade"] == g and c["rotation"] == 0
                )
                for p in core
            }
            knowers = [score[p["id"]] for p in core if g in p["knows"]]
            others = [score[p["id"]] for p in core if g not in p["knows"]]
            wins = sum(k > o for k in knowers for o in others)
            disc[g] = {
                "auc_knowers_vs_others": round(wins / (len(knowers) * len(others)), 4),
                "margin": round(min(knowers) - max(others), 4),
                "mean_score_by_persona": {k: v for k, v in sorted(score.items())},
            }
        # anchors
        anchors = []
        for v in session.scalars(select(TaskVariant).where(TaskVariant.is_anchor)):
            fam = session.scalar(
                select(TaskFamily)
                .join(TaskTemplate, TaskTemplate.family_id == TaskFamily.id)
                .where(TaskTemplate.id == v.template_id)
            )
            solved = [
                p["id"]
                for p in core
                if _answer(p, fam.target_grade, _competency(session, fam), v)
                == v.scoring_contract["correct"]
            ]
            anchors.append({"variant": v.code, "family": fam.code, "solved_by": sorted(solved)})
        failures = [
            {
                "id": f"boundary-or-grade-mismatch:{c['persona']}:{c['grade']}:rot{c['rotation']}",
                "expected": f"{c['expected_status']}/{c['expected_sublevel']}",
                "actual": f"{c['status']}/{c['sublevel']} (score {c['score']})",
                "probable_reason": "threshold or item-count effect on a boundary persona",
            }
            for c in cases
            if not c["match"]
        ] + unstable
        return {
            "kind": "MVP-проверка на эталонных решениях (синтетические персоны); не психометрическая калибровка",
            "cases": n,
            "personas": [{"id": p["id"], "description": p["desc"]} for p in PERSONAS],
            "grade_accuracy": round(accuracy, 4),
            "highest_grade_accuracy": round(sum(hv) / len(hv), 4),
            "variant_stability": {
                "identical_outcome_rate": round(stable / pairs, 4),
                "mean_abs_score_diff": round(metrics.mean(diffs), 4),
                "max_abs_score_diff": round(max(diffs), 4),
                "pairs": pairs,
            },
            "disagreement_over_one_sublevel_rate": round(disagree / len(exp_verified), 4),
            "discrimination": disc,
            "coverage": _coverage(session),
            "rubric_checks": _rubric_checks(session),
            "anchors": anchors,
            "guessing_baseline": _guessing(session),
            "pass_thresholds": {g: PASS_THRESHOLD[Grade(g)] for g in GRADES},
            "outcomes": cases,
            "failures": failures,
        }
    finally:
        session.close()
