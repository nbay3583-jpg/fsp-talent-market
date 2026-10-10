"""Grade / sublevel policy. Public grades stay Junior / Middle / Senior; each has three internal
sublevels (1 beginning, 2 confident, 3 advanced). The score bands below are an MVP configuration,
NOT psychometrically calibrated thresholds."""

from __future__ import annotations

from fsp_market.common.enums import SUBLEVEL_ORDER, Grade, Sublevel

GRADE_SUBLEVELS: dict[Grade, tuple[Sublevel, Sublevel, Sublevel]] = {
    Grade.JUNIOR: (Sublevel.J1, Sublevel.J2, Sublevel.J3),
    Grade.MIDDLE: (Sublevel.M1, Sublevel.M2, Sublevel.M3),
    Grade.SENIOR: (Sublevel.S1, Sublevel.S2, Sublevel.S3),
}

# (minimum total score for sublevel 2, minimum total score for sublevel 3). Below the first value
# (but passed) the result is sublevel 1. Pass thresholds live in assessments/scoring.py; each band
# splits the interval [pass threshold, 1.0] into three roughly equal parts.
SUBLEVEL_BANDS: dict[Grade, tuple[float, float]] = {
    Grade.JUNIOR: (0.75, 0.90),
    Grade.MIDDLE: (0.80, 0.90),
    Grade.SENIOR: (0.84, 0.92),
}

SUBLEVEL_LABEL_RU = {1: "базовый", 2: "уверенный", 3: "сильный"}


def sublevel_label_ru(sublevel: Sublevel | str) -> str:
    return SUBLEVEL_LABEL_RU[int(str(sublevel)[1])]


def sublevel_for_score(grade: Grade, score: float) -> Sublevel:
    """Deterministic sublevel for a PASSED attempt at `grade` with total score in [0, 1]."""
    second, third = SUBLEVEL_BANDS[grade]
    first_s, second_s, third_s = GRADE_SUBLEVELS[grade]
    if score >= third:
        return third_s
    if score >= second:
        return second_s
    return first_s


def neighbour_sublevels(s: Sublevel, tolerance: int = 1) -> list[Sublevel]:
    """The sublevel itself plus +-tolerance positions on the ordered J1 -> S3 scale."""
    idx = SUBLEVEL_ORDER.index(s)
    lo, hi = max(0, idx - tolerance), min(len(SUBLEVEL_ORDER) - 1, idx + tolerance)
    return list(SUBLEVEL_ORDER[lo : hi + 1])
