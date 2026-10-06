# VALIDATION REPORT

MVP validation on a self-made, reproducible dataset. The organisers provided no official dataset or ground truth. This is **not** a psychometric calibration and the numbers do not describe real candidates.

Dataset: version 1, sha256 `2f491079cc219481…`, 32 candidates, 10 needs, 320 label cells (98 non-zero), relevant = grade >= 2.

## Matching

| method | P@3 | P@5 | R@10 | nDCG@10 | hard-constraint violations in top-10 |
|---|---|---|---|---|---|
| keyword baseline | 0.200 | 0.260 | 0.498 | 0.395 | 50/100 (50.0%) |
| hard filters only | 0.733 | 0.580 | 0.785 | 0.763 | 0/80 (0.0%) |
| evidence matching | 0.933 | 0.780 | 0.982 | 1.000 | 0/80 (0.0%) |

Deterministic ordering (two runs identical): **True**

### Sensitivity of the evidence-matching weights

| config | P@5 | nDCG@10 | top-5 Jaccard vs default | top-1 same as default |
|---|---|---|---|---|
| default | 0.780 | 1.000 | 1.000 | 1.000 |
| assessment_heavy | 0.780 | 0.999 | 1.000 | 0.900 |
| fsp_heavy | 0.780 | 0.989 | 1.000 | 0.600 |

Configurations were fixed in advance and not tuned on the labels.

## Assessment (reference-solution validation)

- reference cases: 42 (7 personas x 3 grades x 2 equivalent variants)
- grade accuracy vs hand-written expectations: **1.000**
- highest verified grade accuracy per persona: 1.000
- variant stability: identical outcome on 1.000 of 21 persona-grade pairs; mean |score diff| 0.000, max 0.000
- disagreement of more than one sublevel: 0.000
- rubric / content checks: 0 violations

| grade test | AUC (knowers vs others) | score margin | competencies covered | items per attempt |
|---|---|---|---|---|
| JUNIOR | 1.000 | 1.000 | 2/6 | 2 |
| MIDDLE | 1.000 | 1.000 | 6/6 | 6 |
| SENIOR | 1.000 | 1.000 | 4/6 | 4 |

Random-guess false verification rate (500 seeded guessers):

- JUNIOR: 8.6% (2 items)
- MIDDLE: 0.4% (6 items)
- SENIOR: 5.4% (4 items)

Anchors: backend.api.middle.api_validation.t1.v1 solved by P-MIDDLE, P-SENIOR

## Failure cases

Total recorded: 114 (full list in `latest.json`). First entries per source:

- `keyword_baseline:V-N01:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 1; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `keyword_baseline:V-N01:V-C24:top5-false-positive` expected: relevance 0 (<2); actual: returned at rank 2; reason: violates hard constraint(s): salary (method does not apply constraints)
- `keyword_baseline:V-N01:V-C30:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 3; reason: candidate is UNVERIFIED; method ranks unverified context in the top-5
- `keyword_baseline:V-N01:V-C05:missed-relevant` expected: relevance 2 in top-10; actual: not in top-10; reason: no keyword overlap with the need
- `hard_filters_only:V-N01:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `hard_filters_only:V-N01:V-C18:missed-relevant` expected: relevance 3 in top-10; actual: not in top-10; reason: relevant candidate ranked 11, outside the top-10
- `hard_filters_only:V-N01:V-C20:missed-relevant` expected: relevance 3 in top-10; actual: not in top-10; reason: relevant candidate ranked 13, outside the top-10
- `hard_filters_only:V-N02:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 3; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `evidence_matching:V-N03:V-C27:top5-false-positive` expected: relevance 0 (<2); actual: returned at rank 5; reason: passes constraints but labelled irrelevant (no relevant evidence for this need)
- `evidence_matching:V-N04:V-C13:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `evidence_matching:V-N05:V-C19:missed-relevant` expected: relevance 2 in top-10; actual: not in top-10; reason: relevant candidate ranked 11, outside the top-10
- `evidence_matching:V-N06:V-C08:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5

Counts by source: evidence_matching=10, hard_filters_only=32, keyword_baseline=72

## Known limitations

- Own dataset: the organisers did not provide a dataset or ground truth; labels were assigned by hand by the development team (not by independent experts), so the numbers measure agreement with our own judgement.
- Small and designed: 32 synthetic candidates and 10 needs, built to contain conflict cases. Results do not estimate performance on real candidates or real vacancies.
- Many candidates are 'perfect' fits by construction, which compresses nDCG/P@k differences between methods that already apply constraints.
- Label/engine similarity: the labelling rubric (constraints, verified vs experience-only evidence, sublevel adjacency) was written by the same team as the matching policy and follows similar logic. nDCG@10 = 1.0 for evidence matching therefore mostly shows that the engine implements the intended policy, not that it generalises. R@10 is capped below 1 for needs with more than 10 relevant candidates.
- The keyword baseline is a deliberately simple résumé keyword search, not a tuned search engine.
- Skills outside the six Core competencies (PostgreSQL, Kafka) can only be evidenced by experience or claims.
- Assessment: synthetic personas answer by rule, so grade accuracy and variant stability check the scoring pipeline, thresholds and content integrity. They are not test-retest reliability or psychometric calibration (no IRT/2PL is claimed).
- Assessment depth is small: Junior has 2 items (python, sql only) and Senior has 4 (python, sql, api_fastapi, system_thinking); a random guesser is verified at a non-trivial rate on those short tests (see guessing_baseline).
- Single-choice items only; no arbitrary code execution, plagiarism or proctoring checks.
- Weights are initial tunable configuration; sensitivity configurations were fixed in advance, not optimised.
