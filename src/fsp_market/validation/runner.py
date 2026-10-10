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
        "Собственный набор данных: организаторы не предоставили датасет и эталонную разметку; метки расставлены "
        "вручную командой разработки (не независимыми экспертами), поэтому цифры показывают согласие с нашей "
        "собственной оценкой."
    ),
    (
        "Малый и специально составленный набор: 32 синтетических кандидата и 10 потребностей с конфликтными "
        "случаями. Результаты не оценивают качество на реальных кандидатах и реальных вакансиях."
    ),
    (
        "Многие кандидаты по построению являются «идеальными» совпадениями, что сглаживает разницу nDCG/P@k между "
        "методами, которые уже применяют ограничения."
    ),
    (
        "Сходство разметки и алгоритма: правила разметки (ограничения, подтверждённый опыт против опыта без "
        "проверки, соседние подуровни) написаны той же командой, что и политика подбора, и устроены схоже. "
        "Поэтому nDCG@10 = 1.0 у подбора по подтверждённым компетенциям в основном показывает, что алгоритм "
        "реализует задуманную политику, а не что он обобщается. R@10 ограничен сверху единицей для потребностей, "
        "у которых больше 10 релевантных кандидатов."
    ),
    "Базовый поиск по ключевым словам намеренно прост: это поиск по резюме, а не настроенная поисковая система.",
    "Навыки вне шести основных компетенций (PostgreSQL, Kafka) подтверждаются только опытом или заявками.",
    (
        "Оценка: синтетические персоны отвечают по правилу, поэтому точность грейда и стабильность вариантов "
        "проверяют конвейер оценивания, пороги и целостность контента. Это не надёжность повторного тестирования "
        "и не психометрическая калибровка (IRT/2PL не заявляется)."
    ),
    (
        "Глубина оценки ограничена: по 11 заданий на грейд (6 компетенций), на семейство — 6–10 проверенных "
        "вариантов; вероятность пройти оценку случайным угадыванием оценена симуляцией (см. guessing_baseline), "
        "но это не психометрическая надёжность."
    ),
    "Только задания с одним вариантом ответа; нет выполнения произвольного кода, проверки на плагиат и прокторинга.",
    "Веса — начальная настраиваемая конфигурация; конфигурации чувствительности заданы заранее, а не подбирались.",
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
