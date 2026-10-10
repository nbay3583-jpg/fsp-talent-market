"""Pure, reproducible Task Variant rendering: Template + verified Parameter Preset + seed -> fields.

No randomness and no LLM: the same (structure, preset parameters, seed) always yields the same
prompt, input data, expected behaviour and fixed scoring contract.
"""

from __future__ import annotations

from typing import Any

NON_PLACEHOLDER_PARAMS = frozenset({"options", "correct", "dimension", "type", "tolerance"})
ANSWER_TYPE = {"choice": "single", "set": "multi", "numeric": "number"}


def render_variant_fields(structure: str, params: dict[str, Any], seed: int) -> dict[str, Any]:
    placeholders = {k: v for k, v in params.items() if k not in NON_PLACEHOLDER_PARAMS}
    ctype = params.get("type", "choice")
    contract: dict[str, Any] = {
        "type": ctype,
        "correct": params["correct"],
        "dimension": params["dimension"],
        "points": 1.0,
    }
    if ctype == "numeric":
        contract["tolerance"] = params.get("tolerance", 0)
    return {
        "prompt": structure.format(**placeholders),
        "input_data": {
            "options": params.get("options"),
            "answer_type": ANSWER_TYPE[ctype],
            "seed": seed,
        },
        "expected_behavior": {"correct": params["correct"]},
        "scoring_contract": contract,
    }
