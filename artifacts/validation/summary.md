Dataset: 32 candidates, 10 employer needs, 98 non-zero hand labels (of 320 pairs), relevant = grade >= 2. MVP validation on our own dataset, not a psychometric calibration.

| method | P@3 | P@5 | R@10 | nDCG@10 | hard-constraint violations in top-10 |
|---|---|---|---|---|---|
| keyword baseline | 0.200 | 0.260 | 0.498 | 0.395 | 50/100 (50.0%) |
| hard filters only | 0.733 | 0.580 | 0.785 | 0.763 | 0/80 (0.0%) |
| evidence matching | 0.933 | 0.780 | 0.982 | 1.000 | 0/80 (0.0%) |

Assessment (reference-solution validation, 42 synthetic cases): grade accuracy 1.000; variant stability 1.000 identical outcomes over 21 persona-grade pairs (max score difference 0.000); grade separation AUC JUNIOR 1.000, MIDDLE 1.000, SENIOR 1.000; disagreement over one sublevel 0.000; deterministic scoring: True; rubric/content violations: 0.

Random-guess false verification: JUNIOR 8.6% (2 items), MIDDLE 0.4% (6 items), SENIOR 5.4% (4 items).

Deterministic matching order: True. Failure cases recorded: 114 (see `artifacts/validation/latest.json`).
