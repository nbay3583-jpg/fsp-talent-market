"""Independent technology exams (FastAPI, PostgreSQL) on the SAME Assessment Engine.

An exam is a set of task families whose code starts with `tech.<exam>.`; attempts of an exam carry
`exam_code`. The Core Assessment keeps its `core.*` families and `exam_code IS NULL`. Questions come
from reviewed static banks, so a variant is fully deterministic (no LLM, no code execution).
"""

from __future__ import annotations

import random
from typing import Any

EXAMS: dict[str, dict[str, str]] = {
    "fastapi": {"skill": "api_fastapi", "name": "FastAPI", "competency": "api_fastapi"},
    # family rows need a competency FK; the SKILL being confirmed is `postgresql`, not core `sql`
    "postgresql": {"skill": "postgresql", "name": "PostgreSQL", "competency": "sql"},
}
TIME_LIMIT_SECONDS = {"JUNIOR": 12 * 60, "MIDDLE": 15 * 60, "SENIOR": 18 * 60}
_STRUCTURE = "{question}"


def family_prefix(exam: str) -> str:
    return f"tech.{exam}."


def _bank_gen(items: list[tuple[str, str, list[str]]], topic: str, name: str):
    def gen(rng: random.Random, i: int) -> dict[str, Any]:
        from fsp_market.assessments.content import choice

        question, correct, wrongs = items[i % len(items)]
        return choice(rng, correct, list(wrongs), topic, question=question)

    gen.__name__ = name
    return gen


def _template(code: str, items, topic: str) -> dict[str, Any]:
    return {
        "code": code,
        "task_format": "DETERMINISTIC_QUESTION",
        "structure": _STRUCTURE,
        "gen": _bank_gen(items, topic, code.replace(".", "_")),
        "presets": len(items),
        "dimensions": [topic],
    }


def _family(code: str, grade: str, competency: str, templates: list[dict[str, Any]]) -> dict[str, Any]:
    dims = [d for t in templates for d in t["dimensions"]]
    return {
        "code": code, "grade": grade, "competency": competency, "band": 1,
        "templates": templates,
        "rubric": [{"dimension": d, "weight": round(1 / len(dims), 6)} for d in dims],
    }


def build_families() -> list[dict[str, Any]]:
    from fsp_market.assessments import bank_core_extra, bank_fastapi, bank_postgresql

    out: list[dict[str, Any]] = []
    for exam, bank in (("fastapi", bank_fastapi.BANK), ("postgresql", bank_postgresql.BANK)):
        competency = EXAMS[exam]["competency"]
        for grade, slots in bank.items():
            for slot in slots:
                code = f"{family_prefix(exam)}{grade.lower()}.{slot['short']}"
                out.append(_family(code, grade, competency, [_template(code + ".q", slot["items"], slot["topic"])]))
    for grade, slots in bank_core_extra.BANK.items():  # deeper Core: extra families, new attempts only
        for slot in slots:
            code = f"core.{grade.lower()}.x_{slot['short']}"
            out.append(_family(code, grade, slot["competency"], [_template(code + ".q", slot["items"], slot["topic"])]))
    return out
