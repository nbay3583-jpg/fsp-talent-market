"""INDEPENDENT hard-constraint checker, written from the dataset fields (not from the engine).

It exists so that 'hard constraint violation rate' is measured by a second implementation:
if the production filter and this checker disagree, the violation rate is non-zero.
"""

from __future__ import annotations

ORDER = ["J1", "J2", "M1", "M2", "S1", "S2"]
RANGE = {"JUNIOR": ["J1", "J2"], "MIDDLE": ["M1", "M2"], "SENIOR": ["S1", "S2"]}
NDFL = 0.13


def _allowed(need: dict) -> set[str]:
    if need["target_sublevel"] is None:
        return set(RANGE[need["target_grade"]])
    i = ORDER.index(need["target_sublevel"])
    return set(ORDER[max(0, i - 1) : i + 2])


def _to_need_type(amount: int, have: str, want: str) -> float:
    if have == want:
        return float(amount)
    return amount / (1 - NDFL) if have == "NET" else amount * (1 - NDFL)


def violations(need: dict, cand: dict, verified_sublevel: str | None) -> list[str]:
    out = []
    if cand["specialization"] != need["specialization"]:
        out.append("specialization")
    if not cand["profile_visible"]:
        out.append("not_visible")
    if not cand["open_to_invitations"]:
        out.append("not_open")
    levels = {verified_sublevel} if verified_sublevel else set(RANGE[cand["claimed_grade"]])
    if not levels & _allowed(need):
        out.append("grade")
    sal = cand["salary"]
    if sal and _to_need_type(sal["min"], sal["type"], need["salary_type"]) > need["salary_to"]:
        out.append("salary")
    shared = set(need["work_formats"]) & set(cand["work_formats"])
    if not shared:
        out.append("work_format")
    elif (
        "REMOTE" not in shared
        and need["location"]
        and cand["location"].lower() != need["location"].lower()
    ):
        out.append("location")
    if need["max_start_days"] is not None and cand["available_in_days"] > need["max_start_days"]:
        out.append("availability")
    return out
