"""Requirement Fit policy: initial TUNABLE configuration, not a scientifically derived formula.

All matching weights and tolerances live here and are snapshotted into every MatchRun.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class MatchingPolicy:
    # Component weights (starting heuristics from the architecture doc). `context` is the
    # optional semantic component: not used in P0 (no LLM), so it is excluded from the sum.
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "skill_coverage": 0.40,
            "assessment": 0.20,
            "professional": 0.15,
            "fsp": 0.10,
            "freshness": 0.10,
            "context": 0.05,
        }
    )
    active_components: tuple[str, ...] = (
        "skill_coverage",
        "assessment",
        "professional",
        "fsp",
        "freshness",
    )
    required_skill_weight: float = 1.0
    optional_skill_weight: float = 0.4
    sublevel_tolerance: int = 1  # +-1 INTERNAL sublevel, never +-1 public grade
    # Whether the +-1 neighbourhood may cross a public-grade border (M1 -> J3 / M3 -> S1).
    cross_grade_tolerance: bool = True
    not_verified_factor: float = 0.6  # ranking penalty for candidates without verification
    skill_credit_verified: float = 1.0
    skill_credit_below_target: float = 0.5  # verified, but at a lower grade than the need
    skill_credit_experience_only: float = 0.5  # professional experience without verification
    ndfl_rate: float = 0.13  # NET -> GROSS conversion when salary types differ (assumption)
    freshness_full_days: int = 180
    freshness_zero_days: int = 720
    match_pool_size: int = 20  # persisted per run; API pages over it (UI shows first 5-10)

    def snapshot(self) -> dict:
        return asdict(self)


DEFAULT_POLICY = MatchingPolicy()
