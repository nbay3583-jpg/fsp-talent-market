from __future__ import annotations

from fsp_market.common.enums import Grade

PASS_THRESHOLD: dict[Grade, float] = {
    Grade.JUNIOR: 0.6,
    Grade.MIDDLE: 0.7,
    Grade.SENIOR: 0.75,
}


def score_answer(contract: dict, answer) -> float:
    """Score a single answer against its deterministic contract.

    Returns 1.0 when the answer satisfies the contract, 0.0 otherwise.
    Raises ValueError for an unknown contract type.
    """
    contract_type = contract.get("type")

    if contract_type == "choice":
        correct = contract.get("correct")
        return 1.0 if answer == correct else 0.0

    if contract_type == "set":
        correct = contract.get("correct")
        try:
            return 1.0 if set(answer) == set(correct) else 0.0
        except TypeError:
            return 0.0

    if contract_type == "numeric":
        correct = contract.get("correct")
        tolerance = contract.get("tolerance", 0.0)
        try:
            return 1.0 if abs(float(answer) - float(correct)) <= float(tolerance) else 0.0
        except (TypeError, ValueError):
            return 0.0

    raise ValueError(f"Unknown contract type: {contract_type!r}")
