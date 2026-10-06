"""Matching validation: three methods on ONE dataset, scored against hand-made relevance labels."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.candidates.models import Candidate
from fsp_market.matching.engine import hard_filter
from fsp_market.matching.facts import load_candidate_facts, load_need_spec
from fsp_market.matching.models import EmployerNeed, MatchResult
from fsp_market.matching.policy import DEFAULT_POLICY, MatchingPolicy
from fsp_market.matching.service import run_match
from fsp_market.validation import constraints, metrics
from fsp_market.validation.dataset import (
    KEYWORD_SKILL,
    REFERENCE_DATE,
    relevance_grades,
)

METHODS = ("keyword_baseline", "hard_filters_only", "evidence_matching")
LABELS = {
    "keyword_baseline": "keyword baseline",
    "hard_filters_only": "hard filters only",
    "evidence_matching": "evidence matching",
}
SKILL_KEYWORD = {v: k for k, v in KEYWORD_SKILL.items()}
TOP_K = 10


def keyword_ranking(need: dict, cands: list[dict]) -> list[str]:
    """Résumé keyword search: required keyword = 2 points, optional = 1; NO constraints and NO
    verification. Candidates with no keyword hit are not returned. Ties broken by id."""
    scored = []
    for c in cands:
        kws = set(c["resume_keywords"])
        pts = sum(2 for s in need["required_skills"] if SKILL_KEYWORD[s] in kws)
        pts += sum(1 for s in need["optional_skills"] if SKILL_KEYWORD[s] in kws)
        if pts:
            scored.append((-pts, c["id"]))
    return [cid for _, cid in sorted(scored)]


def hard_filter_ranking(session: Session, db_need: EmployerNeed, ids: dict[str, int]) -> list[str]:
    """Production hard constraints only; survivors in a fixed arbitrary order (candidate id)."""
    spec = load_need_spec(session, db_need)
    rows = list(session.scalars(select(Candidate).order_by(Candidate.id)))
    facts = load_candidate_facts(session, rows)
    inverse = {v: k for k, v in ids.items()}
    return [inverse[c.id] for c in rows if not hard_filter(spec, facts[c.id])]


def evidence_ranking(
    session: Session, db_need: EmployerNeed, ids: dict[str, int], policy: MatchingPolicy
) -> tuple[list[str], dict[str, float]]:
    run = run_match(session, db_need, now=REFERENCE_DATE, policy=policy)
    session.flush()
    inverse = {v: k for k, v in ids.items()}
    rows = session.scalars(
        select(MatchResult).where(MatchResult.run_id == run.id).order_by(MatchResult.rank)
    ).all()
    return [inverse[r.candidate_id] for r in rows], {
        inverse[r.candidate_id]: r.requirement_fit for r in rows
    }


def _need_metrics(ranked: list[str], grades: dict[str, int], threshold: int) -> dict[str, float]:
    relevant = {c for c, g in grades.items() if g >= threshold}
    return {
        "p@3": metrics.precision_at_k(ranked, relevant, 3),
        "p@5": metrics.precision_at_k(ranked, relevant, 5),
        "r@10": metrics.recall_at_k(ranked, relevant, 10),
        "ndcg@10": metrics.ndcg_at_k(ranked, grades, 10),
    }


def violation_stats(
    ranked: list[str], need: dict, by_id: dict[str, dict], sublevels: dict[str, str | None]
) -> dict[str, Any]:
    top = ranked[:TOP_K]
    bad = {c: constraints.violations(need, by_id[c], sublevels[c]) for c in top}
    bad = {c: v for c, v in bad.items() if v}
    return {"returned": len(top), "violating": len(bad), "details": bad}


def evaluate(
    session: Session,
    cands: list[dict],
    needs: list[dict],
    labels: dict,
    ids: dict,
    policy: MatchingPolicy = DEFAULT_POLICY,
    with_failures: bool = True,
) -> dict[str, Any]:
    threshold = labels["relevant_threshold"]
    by_id = {c["id"]: c for c in cands}
    db_sub = {
        vid: (row.verified_sublevel if row.verified_sublevel else None)
        for vid, row in ((vid, session.get(Candidate, dbid)) for vid, dbid in ids["cand"].items())
    }
    per_need: dict[str, dict] = {m: {} for m in METHODS}
    rankings: dict[str, dict[str, list[str]]] = {m: {} for m in METHODS}
    fits: dict[str, dict[str, float]] = {}
    viol = {m: {"returned": 0, "violating": 0} for m in METHODS}
    failures: list[dict] = []
    for need in needs:
        db_need = session.get(EmployerNeed, ids["need"][need["id"]])
        grades = relevance_grades(labels, need["id"])
        ev_ranked, ev_fit = evidence_ranking(session, db_need, ids["cand"], policy)
        fits[need["id"]] = ev_fit
        ranked_by = {
            "keyword_baseline": keyword_ranking(need, cands),
            "hard_filters_only": hard_filter_ranking(session, db_need, ids["cand"]),
            "evidence_matching": ev_ranked,
        }
        for m in METHODS:
            ranked = ranked_by[m]
            rankings[m][need["id"]] = ranked
            per_need[m][need["id"]] = _need_metrics(ranked, grades, threshold)
            v = violation_stats(ranked, need, by_id, db_sub)
            viol[m]["returned"] += v["returned"]
            viol[m]["violating"] += v["violating"]
            if with_failures:
                failures += _failures(m, need, ranked, grades, threshold, v, by_id, ids, session)
    summary = {}
    for m in METHODS:
        rows = list(per_need[m].values())
        summary[m] = {
            k: round(metrics.mean([r[k] for r in rows]), 4)
            for k in ("p@3", "p@5", "r@10", "ndcg@10")
        }
        r = viol[m]
        summary[m]["constraint_violation_rate@10"] = (
            round(r["violating"] / r["returned"], 4) if r["returned"] else 0.0
        )
        summary[m]["constraint_violations@10"] = r["violating"]
        summary[m]["returned@10"] = r["returned"]
    return {
        "summary": summary,
        "per_need": {
            m: {n: {k: round(v, 4) for k, v in d.items()} for n, d in per_need[m].items()}
            for m in METHODS
        },
        "rankings": rankings,
        "evidence_fit": fits,
        "failures": failures,
    }


def _failures(method, need, ranked, grades, threshold, v, by_id, ids, session) -> list[dict]:
    out = []
    for pos, cid in enumerate(ranked[:5], start=1):
        g = grades.get(cid, 0)
        if g >= threshold:
            continue
        reasons = v["details"].get(cid)
        if reasons:
            why = f"violates hard constraint(s): {', '.join(reasons)}" + (
                " (method does not apply constraints)" if method == "keyword_baseline" else ""
            )
        else:
            row = session.get(Candidate, ids["cand"][cid])
            if row.verification_status != "VERIFIED":
                why = f"candidate is {row.verification_status}; method ranks unverified context in the top-5"
            elif g == 1:
                why = "labelled partially relevant (e.g. verified skills below the need's grade or a missing required skill)"
            else:
                why = "passes constraints but labelled irrelevant (no relevant evidence for this need)"
        out.append(
            {
                "id": f"{method}:{need['id']}:{cid}:top5-false-positive",
                "method": method,
                "need": need["id"],
                "candidate": cid,
                "expected": f"relevance {g} (<{threshold})",
                "actual": f"returned at rank {pos}",
                "probable_reason": why,
            }
        )
    relevant = [c for c, g in grades.items() if g >= threshold]
    for cid in sorted(relevant):
        if cid in ranked[:TOP_K]:
            continue
        if cid in ranked:
            why = f"relevant candidate ranked {ranked.index(cid) + 1}, outside the top-{TOP_K}"
        elif method == "evidence_matching" or method == "hard_filters_only":
            why = "excluded by a production hard constraint although labelled relevant"
        else:
            why = "no keyword overlap with the need"
        out.append(
            {
                "id": f"{method}:{need['id']}:{cid}:missed-relevant",
                "method": method,
                "need": need["id"],
                "candidate": cid,
                "expected": f"relevance {grades[cid]} in top-{TOP_K}",
                "actual": "not in top-10",
                "probable_reason": why,
            }
        )
    return out


def sensitivity(session: Session, cands, needs, labels, ids, base: dict) -> dict[str, Any]:
    """Weight sensitivity. Configurations are fixed a priori (not tuned on the labels)."""
    configs = {
        "default": DEFAULT_POLICY,
        "assessment_heavy": replace(
            DEFAULT_POLICY,
            weights={**DEFAULT_POLICY.weights, "assessment": 0.40, "skill_coverage": 0.25},
        ),
        "fsp_heavy": replace(
            DEFAULT_POLICY, weights={**DEFAULT_POLICY.weights, "fsp": 0.30, "skill_coverage": 0.25}
        ),
    }
    out = {}
    base_rank = base["rankings"]["evidence_matching"]
    for name, policy in configs.items():
        res = evaluate(session, cands, needs, labels, ids, policy, with_failures=False)
        rk = res["rankings"]["evidence_matching"]
        jac, top1 = [], []
        for n in rk:
            a, b = set(rk[n][:5]), set(base_rank[n][:5])
            jac.append(len(a & b) / len(a | b) if a | b else 1.0)
            top1.append(1.0 if rk[n][:1] == base_rank[n][:1] else 0.0)
        out[name] = {
            **{
                k: res["summary"]["evidence_matching"][k] for k in ("p@3", "p@5", "r@10", "ndcg@10")
            },
            "top5_jaccard_vs_default": round(metrics.mean(jac), 4),
            "top1_same_as_default": round(metrics.mean(top1), 4),
            "weights": {k: policy.weights[k] for k in policy.active_components},
        }
    return out


def determinism_check(session, cands, needs, labels, ids) -> bool:
    a = evaluate(session, cands, needs, labels, ids, with_failures=False)["rankings"]
    b = evaluate(session, cands, needs, labels, ids, with_failures=False)["rankings"]
    return a == b
