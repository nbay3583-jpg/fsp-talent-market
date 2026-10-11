"""Per-competency breakdown of one scored attempt, derived from what the attempt actually served.

Read-only: it re-reads `AssessmentResult.trace` (written at scoring time) and never changes the
scoring formula, thresholds or stored results. Task counts come from the attempt itself, not from
constants, so attempts with a different number of tasks per competency stay correct. Historical
results without a usable trace degrade to percent-only entries (`tasks` is None).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fsp_market.assessments import content
from fsp_market.assessments.models import AssessmentResult, TaskFamily, TaskVariant
from fsp_market.taxonomy.models import Competency

LIMITED_BELOW = 3  # fewer tasks than this: the direction is a spot check, not a measurement


def reliability(tasks: int | None) -> str:
    if tasks is None:
        return "unknown"
    if tasks == 0:
        return "none"
    return "limited" if tasks < LIMITED_BELOW else "moderate"


def _num(value: float) -> float:
    return round(value, 2)


def competency_breakdown(session: Session, result: AssessmentResult) -> list[dict[str, Any]]:
    order = [c["code"] for c in content.COMPETENCIES]
    scores: dict[str, float] = dict(result.subscores or {})
    trace = [t for t in (result.trace or []) if isinstance(t, dict) and t.get("family")]

    stats: dict[str, dict[str, Any]] = {}
    if trace:
        family_comp = dict(
            session.execute(
                select(TaskFamily.code, Competency.code).join(
                    Competency, Competency.id == TaskFamily.competency_id
                )
            ).all()
        )
        variant_ids = [t["variant_id"] for t in trace if t.get("variant_id") is not None]
        contracts = {
            vid: contract
            for vid, contract in session.execute(
                select(TaskVariant.id, TaskVariant.scoring_contract).where(
                    TaskVariant.id.in_(variant_ids)
                )
            ).all()
        }
        for t in trace:
            code = family_comp.get(t["family"])
            if code is None:
                continue
            s = stats.setdefault(
                code, {"tasks": 0, "answered": 0, "earned": 0.0, "max": 0.0, "max_known": True}
            )
            s["tasks"] += 1
            s["answered"] += 1 if t.get("answered") else 0
            s["earned"] += float(t.get("score") or 0.0)
            contract = contracts.get(t.get("variant_id"))
            if contract is None:
                s["max_known"] = False
            else:
                s["max"] += float(contract.get("points", 1.0))

    codes = [c for c in order if c in scores or c in stats]
    codes += [c for c in list(scores) + list(stats) if c not in codes]
    rows: list[dict[str, Any]] = []
    for code in order + [c for c in codes if c not in order]:
        s = stats.get(code)
        percent = scores.get(code)
        if s is None and percent is None:
            tasks: int | None = 0 if trace else None
            rows.append(
                {"competency": code, "percent": None, "tasks": tasks, "answered": None,
                 "points_earned": None, "points_max": None, "reliability": reliability(tasks)}
            )
            continue
        tasks = s["tasks"] if s else None
        exact = bool(s and s["max_known"] and s["max"] > 0)
        rows.append(
            {
                "competency": code,
                "percent": percent if percent is not None else (s["earned"] / s["max"] if exact else None),
                "tasks": tasks,
                "answered": s["answered"] if s else None,
                "points_earned": _num(s["earned"]) if exact else None,
                "points_max": _num(s["max"]) if exact else None,
                "reliability": reliability(tasks),
            }
        )
    return rows
