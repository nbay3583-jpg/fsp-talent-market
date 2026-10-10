"""Matching 2.0, the candidate's side: do the VACANCY and TEAM meet the candidate's wishes?

Pure, deterministic and explainable. Advisory only: nothing here excludes a candidate or touches
the verified grade; work-style axes are descriptive preferences, not psychological assessment.
"""

from __future__ import annotations

from typing import Any

MIN_TEAM_RESPONSES = 3  # below this the team aggregate is never shown (privacy)

# key -> (axis label, low pole, high pole); answers are integers 1..5
AXES: dict[str, tuple[str, str, str]] = {
    "autonomy": ("Самостоятельность", "чёткие указания", "самостоятельное принятие решений"),
    "communication": ("Коммуникация", "письменная и асинхронная", "созвоны и живое общение"),
    "pace": ("Темп", "размеренный", "быстрый, с высокой динамикой"),
    "structure": ("Процессы", "гибкие договорённости", "чёткие регламенты"),
    "feedback": ("Обратная связь", "редкая и по итогам", "частая и в ходе работы"),
    "collaboration": ("Формат работы", "преимущественно индивидуальная", "командная, парная"),
}
CAREER_GOALS = {"GROW": "расти в грейде", "DEPTH": "углублять экспертизу", "LEAD": "двигаться к лидерству"}
_LEAD_WORDS = ("лид", "lead", "ментор", "менто", "руковод", "тимлид")
_GRADE_RANK = {"JUNIOR": 0, "MIDDLE": 1, "SENIOR": 2}


def validate_answers(answers: dict[str, Any]) -> dict[str, int]:
    if set(answers) != set(AXES):
        raise ValueError("answers must cover exactly: " + ", ".join(AXES))
    out = {}
    for k, v in answers.items():
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            raise ValueError(f"{k}: integer 1..5 expected")
        out[k] = v
    return out


def aggregate(responses: list[dict[str, int]]) -> dict[str, Any]:
    """Only the per-axis mean, and only when at least MIN_TEAM_RESPONSES people answered."""
    n = len(responses)
    if n < MIN_TEAM_RESPONSES:
        return {
            "responses": n,
            "aggregate": None,
            "note": f"Агрегат скрыт: нужно минимум {MIN_TEAM_RESPONSES} анонимных ответа "
            "(защита личных данных сотрудников).",
        }
    mean = {k: round(sum(r[k] for r in responses) / n, 1) for k in AXES}
    return {"responses": n, "aggregate": mean, "note": None}


def combine(manager: dict[str, int] | None, employees: dict[str, Any]) -> dict[str, Any]:
    """Team profile BOTH: manager's view, enriched with the anonymous aggregate when allowed."""
    agg = employees.get("aggregate")
    if manager and agg:
        profile = {k: round((manager[k] + agg[k]) / 2, 1) for k in AXES}
        source = "BOTH"
    elif agg:
        profile, source = dict(agg), "EMPLOYEES"
    elif manager:
        profile, source = {k: float(v) for k, v in manager.items()}, "MANAGER"
    else:
        profile, source = None, "NONE"
    return {"profile": profile, "source": source}


def work_style_compat(candidate: dict[str, int] | None, team: dict[str, float] | None):
    if not candidate or not team:
        return None
    axes = []
    for k, (label, _lo, _hi) in AXES.items():
        diff = abs(candidate[k] - team[k])
        axes.append({"axis": k, "label": label, "match": "close" if diff <= 1 else "different"})
    close = sum(1 for a in axes if a["match"] == "close")
    return {"axes": axes, "close": close, "total": len(axes)}


def reverse_fit(
    *,
    interests: list[str],
    career_goal: str | None,
    candidate_grade: str | None,
    need_skills: set[str],
    need_grade: str,
    need_text: str,
    work_style: dict[str, int] | None,
    team_profile: dict[str, float] | None,
) -> dict[str, Any]:
    why: list[dict] = []
    gaps: list[dict] = []
    score_parts: list[float] = []
    if interests:
        hit = sorted(set(interests) & need_skills)
        if hit:
            score_parts.append(len(hit) / len(set(interests)))
            why.append({"code": "INTEREST_MATCH", "text": f"Вакансия связана с вашими интересами: {', '.join(hit)}"})
        else:
            score_parts.append(0.0)
            gaps.append({"code": "INTEREST_GAP", "text": "В вакансии нет технологий из ваших интересов"})
    if career_goal == "GROW" and candidate_grade:
        up = _GRADE_RANK[need_grade] > _GRADE_RANK[candidate_grade]
        score_parts.append(1.0 if up else 0.0)
        (why if up else gaps).append(
            {"code": "GOAL_GROWTH", "text": "Вакансия выше вашего текущего грейда — есть рост"}
            if up
            else {"code": "GOAL_GROWTH_GAP", "text": "Вакансия не выше вашего текущего грейда, роста в грейде нет"}
        )
    elif career_goal == "LEAD":
        lead = any(w in need_text.casefold() for w in _LEAD_WORDS)
        score_parts.append(1.0 if lead else 0.0)
        (why if lead else gaps).append(
            {"code": "GOAL_LEAD", "text": "В описании есть элементы лидерства или наставничества"}
            if lead
            else {"code": "GOAL_LEAD_GAP", "text": "В описании не упомянуто лидерство или наставничество"}
        )
    ws = work_style_compat(work_style, team_profile)
    if ws:
        score_parts.append(ws["close"] / ws["total"])
        far = [a["label"] for a in ws["axes"] if a["match"] == "different"]
        why.append({"code": "STYLE_CLOSE", "text": f"Рабочий стиль близок по {ws['close']} из {ws['total']} осей"})
        if far:
            gaps.append({"code": "STYLE_DIFF", "text": f"Различия в стиле работы: {', '.join(far)} — это повод обсудить, не отказ"})
    return {
        "score": round(sum(score_parts) / len(score_parts), 4) if score_parts else None,
        "why": why,
        "gaps": gaps,
        "work_style": ws,
    }
