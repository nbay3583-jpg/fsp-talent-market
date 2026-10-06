"""One entry point: `python -m fsp_market.validation` (see __main__)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import fsp_market.models  # noqa: F401
from fsp_market.db import Base
from fsp_market.matching.policy import DEFAULT_POLICY
from fsp_market.validation import matching
from fsp_market.validation.assessment import run_assessment_validation
from fsp_market.validation.dataset import (
    build_database,
    dataset_sha256,
    load_dataset,
)
from fsp_market.validation.report import README_BEGIN, README_END, markdown, summary_markdown

LIMITATIONS = [
    (
        "Own dataset: the organisers did not provide a dataset or ground truth; labels were assigned by hand by the "
        "development team (not by independent experts), so the numbers measure agreement with our own judgement."
    ),
    (
        "Small and designed: 32 synthetic candidates and 10 needs, built to contain conflict cases. Results do not "
        "estimate performance on real candidates or real vacancies."
    ),
    (
        "Many candidates are 'perfect' fits by construction, which compresses nDCG/P@k differences between methods "
        "that already apply constraints."
    ),
    (
        "Label/engine similarity: the labelling rubric (constraints, verified vs experience-only evidence, sublevel "
        "adjacency) was written by the same team as the matching policy and follows similar logic. nDCG@10 = 1.0 for "
        "evidence matching therefore mostly shows that the engine implements the intended policy, not that it "
        "generalises. R@10 is capped below 1 for needs with more than 10 relevant candidates."
    ),
    "The keyword baseline is a deliberately simple résumé keyword search, not a tuned search engine.",
    "Skills outside the six Core competencies (PostgreSQL, Kafka) can only be evidenced by experience or claims.",
    (
        "Assessment: synthetic personas answer by rule, so grade accuracy and variant stability check the scoring "
        "pipeline, thresholds and content integrity. They are not test-retest reliability or psychometric calibration "
        "(no IRT/2PL is claimed)."
    ),
    (
        "Assessment depth is small: Junior has 2 items (python, sql only) and Senior has 4 (python, sql, api_fastapi, "
        "system_thinking); a random guesser is verified at a non-trivial rate on those short tests (see guessing_baseline)."
    ),
    "Single-choice items only; no arbitrary code execution, plagiarism or proctoring checks.",
    "Weights are initial tunable configuration; sensitivity configurations were fixed in advance, not optimised.",
]


def run_validation() -> dict[str, Any]:
    cands, needs, labels = load_dataset()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ids = build_database(session, cands, needs)
        base = matching.evaluate(session, cands, needs, labels, ids)
        sens = matching.sensitivity(session, cands, needs, labels, ids, base)
        det = matching.determinism_check(session, cands, needs, labels, ids)
    assessment = run_assessment_validation()
    assessment_det = assessment == run_assessment_validation()
    nonzero = sum(len(v) for v in labels["labels"].values())
    failures = base["failures"] + assessment["failures"]
    return {
        "dataset": {
            "version": labels["version"],
            "sha256": dataset_sha256(),
            "candidates": len(cands),
            "needs": len(needs),
            "label_cells": len(cands) * len(needs),
            "nonzero_labels": nonzero,
            "relevant_threshold": labels["relevant_threshold"],
        },
        "policy": DEFAULT_POLICY.snapshot(),
        "matching": {
            "summary": base["summary"],
            "per_need": base["per_need"],
            "rankings": base["rankings"],
            "sensitivity": sens,
            "deterministic": det,
        },
        "assessment": {**assessment, "deterministic": assessment_det},
        "failures": failures,
        "limitations": LIMITATIONS,
    }


def write_artifacts(res: dict[str, Any], out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    js, md = out / "latest.json", out / "latest.md"
    js.write_text(
        json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md.write_text(markdown(res), encoding="utf-8")
    (out / "summary.md").write_text(summary_markdown(res), encoding="utf-8")
    return js, md


def readme_block(res: dict[str, Any]) -> str:
    return f"{README_BEGIN}\n{summary_markdown(res)}{README_END}"


def update_readme(res: dict[str, Any], path: Path) -> bool:
    """Rewrites the generated block in README.md; returns True if the file changed."""
    text = path.read_text(encoding="utf-8")
    start, end = text.index(README_BEGIN), text.index(README_END) + len(README_END)
    new = text[:start] + readme_block(res) + text[end:]
    path.write_text(new, encoding="utf-8")
    return new != text
