"""Ranking metrics. Pure functions, no dependencies; every number in the report comes from here."""

from __future__ import annotations

import math


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Relevant items in the top-k divided by k (k, not len(ranked): short lists are penalised)."""
    return sum(1 for c in ranked[:k] if c in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        raise ValueError("recall is undefined without relevant items")
    return sum(1 for c in ranked[:k] if c in relevant) / len(relevant)


def dcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    """Exponential gain 2^g - 1, discount log2(rank + 1)."""
    return sum((2 ** grades.get(c, 0) - 1) / math.log2(i + 2) for i, c in enumerate(ranked[:k]))


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    ideal = sorted(grades, key=lambda c: (-grades[c], c))
    best = dcg_at_k(ideal, grades, k)
    return dcg_at_k(ranked, grades, k) / best if best else 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
