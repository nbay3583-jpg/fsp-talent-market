from __future__ import annotations

from fsp_market.common.enums import Grade

PASS_THRESHOLD: dict[Grade, float] = {
    Grade.JUNIOR: 0.6,
    Grade.MIDDLE: 0.7,
    Grade.SENIOR: 0.75,
}


def score_answer(contract: dict, answer) -> float:
    """Score one answer against its deterministic contract, 0.0 .. 1.0.

    choice  - exact option key.
    set     - multi-select: (right picked - wrong picked) / right, floored at 0 (no free points
              for ticking everything).
    numeric - |answer - correct| <= tolerance; accepts "12" or "12,5".
    Raises ValueError for an unknown contract type.
    """
    contract_type = contract.get("type")

    if contract_type == "choice":
        return 1.0 if answer == contract.get("correct") else 0.0

    if contract_type == "set":
        correct = set(contract.get("correct") or [])
        try:
            picked = set(answer)
        except TypeError:
            return 0.0
        if not correct or not picked:
            return 0.0
        return max(0.0, (len(picked & correct) - len(picked - correct)) / len(correct))

    if contract_type == "numeric":
        try:
            value = float(str(answer).replace(",", ".").strip())
            return (
                1.0
                if abs(value - float(contract["correct"])) <= float(contract.get("tolerance", 0))
                else 0.0
            )
        except (TypeError, ValueError, KeyError):
            return 0.0

    raise ValueError(f"Unknown contract type: {contract_type!r}")
