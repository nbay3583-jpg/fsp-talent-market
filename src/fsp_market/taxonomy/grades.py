from __future__ import annotations

from fsp_market.common.enums import Grade, Sublevel

GRADE_SUBLEVELS: dict[Grade, tuple[Sublevel, Sublevel]] = {
    Grade.JUNIOR: (Sublevel.J1, Sublevel.J2),
    Grade.MIDDLE: (Sublevel.M1, Sublevel.M2),
    Grade.SENIOR: (Sublevel.S1, Sublevel.S2),
}

_SUBLEVEL_ORDER: list[Sublevel] = [
    Sublevel.J1,
    Sublevel.J2,
    Sublevel.M1,
    Sublevel.M2,
    Sublevel.S1,
    Sublevel.S2,
]


def sublevel_for_score(grade: Grade, score: float) -> Sublevel:
    first, second = GRADE_SUBLEVELS[grade]
    return first if score < 0.85 else second


def neighbour_sublevels(s: Sublevel) -> list[Sublevel]:
    idx = _SUBLEVEL_ORDER.index(s)
    neighbours: list[Sublevel] = [s]
    if idx > 0:
        neighbours.append(_SUBLEVEL_ORDER[idx - 1])
    if idx < len(_SUBLEVEL_ORDER) - 1:
        neighbours.append(_SUBLEVEL_ORDER[idx + 1])
    return neighbours
