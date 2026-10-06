"""FSP discipline -> relevant skill codes. Evidence relevance only: no points, no grade logic."""

from __future__ import annotations

from fsp_market.fsp.provider import FSPAchievement

DISCIPLINE_SKILLS: dict[str, tuple[str, ...]] = {
    "algorithmic_programming": ("python",),
    "product_programming": ("api_fastapi", "sql", "testing"),
    "cybersecurity": (),  # no relevant skill in the Backend/Python track -> no evidence
}


def skills_for(achievement: FSPAchievement) -> tuple[str, ...]:
    return DISCIPLINE_SKILLS.get(achievement.discipline, ())
