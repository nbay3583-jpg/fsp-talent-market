"""Read-only view of the stored validation artifact (produced by `python -m fsp_market.validation`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from fsp_market.config import get_settings

router = APIRouter(prefix="/api", tags=["validation"])


@router.get("/validation/summary")
def validation_summary() -> dict[str, Any]:
    path = Path(get_settings().validation_artifact)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="validation artifact not found")
    res = json.loads(path.read_text(encoding="utf-8"))
    a = res["assessment"]
    return {
        "dataset": res["dataset"],
        "matching": res["matching"]["summary"],
        "sensitivity": res["matching"]["sensitivity"],
        "deterministic_ordering": res["matching"]["deterministic"],
        "assessment": {
            k: a[k]
            for k in (
                "kind",
                "cases",
                "grade_accuracy",
                "highest_grade_accuracy",
                "variant_stability",
                "disagreement_over_one_sublevel_rate",
                "discrimination",
                "coverage",
                "guessing_baseline",
                "rubric_checks",
                "deterministic",
            )
        },
        "failures_recorded": len(res["failures"]),
        "limitations": res["limitations"],
    }
