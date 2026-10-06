"""Pure, reproducible Task Variant rendering: Template + verified Parameter Preset + seed -> fields.

No randomness and no LLM: the same (structure, preset parameters, seed) always yields the same
prompt, input data, expected behaviour and fixed scoring contract.
"""

from __future__ import annotations

from typing import Any

NON_PLACEHOLDER_PARAMS = frozenset({"options", "correct", "dimension"})


def render_variant_fields(structure: str, params: dict[str, Any], seed: int) -> dict[str, Any]:
    placeholders = {k: v for k, v in params.items() if k not in NON_PLACEHOLDER_PARAMS}
    return {
        "prompt": structure.format(**placeholders),
        "input_data": {"options": params["options"], "seed": seed},
        "expected_behavior": {"correct": params["correct"]},
        "scoring_contract": {
            "type": "choice",
            "correct": params["correct"],
            "dimension": params["dimension"],
            "points": 1.0,
        },
    }
