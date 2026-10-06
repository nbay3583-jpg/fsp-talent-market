# Matching and assessment validation (MVP)

**This is MVP validation, not a psychometric calibration.** The organisers did not provide an official
dataset or ground truth, so we use our own fixed, reproducible validation set. All numbers quoted anywhere
come from `artifacts/validation/latest.json` / `latest.md`, which are produced by code; nothing is typed in by hand.

## Run it

```
.venv/bin/python -m fsp_market.validation            # runs everything, writes artifacts/validation/latest.{json,md}
.venv/bin/python -m fsp_market.validation --check    # re-runs and fails if the stored artifacts differ
```

Needs no database server (in-memory SQLite), no network, no LLM. The same data and code give byte-identical
`latest.json` (verified across separate processes; the file has no timestamps). Artifacts must be regenerated and
committed whenever the data, labels, matching policy or assessment content change
(`tests/test_phase6_validation.py` fails if they are stale).

## Where the data comes from

`src/fsp_market/validation/data/` (version-controlled):

| file | content |
|---|---|
| `candidates.json` | 32 hand-designed profiles: claimed grade, assessment behaviour, salary, formats, location, experience, résumé keywords, FSP disciplines, a note on why the profile exists |
| `needs.json` | 10 employer needs (grade/sublevel, required and optional skills, salary + GROSS/NET, formats, location, start limit) |
| `relevance.json` | hand-made relevance labels (0-3) with a tag explaining each |

Profiles are loaded through the real pipeline: verified candidates take the actual Core Assessment (their answers are
fixed per profile), then evidence, FSP mapping and matching facts are created by the production code. Conflict cases:
strong CV + failed test, weak CV + strong test, relevant and irrelevant FSP evidence, salary mismatch (also exact
boundary and NET), work-format mismatch, NOT_VERIFIED Middle, no FSP history, missing required skill, strong optional
skills but a failed hard constraint, hidden / closed profiles, other specialisation, availability.

## How the labels were made

Scale: 0 irrelevant (fails a hard constraint or has no relevant evidence), 1 partially relevant, 2 relevant,
3 highly relevant. Each non-zero label carries a rubric tag (see `tags` in `relevance.json`). They were assigned by
hand from the dataset facts and written **before** the matching code was run on this dataset; the matching score was
never an input. Pairs not listed are 0. Relevant = grade >= 2. Limitation: one team wrote both the rubric and the
matching policy, and the rubric follows similar logic (see below).

## Methods compared (same candidates, same needs, same labels)

1. **Keyword baseline** - résumé keyword search over the candidate's keyword list: required keyword 2 points,
   optional 1, ties by id. No constraints and no verified evidence.
2. **Hard filters only** - the production hard constraints, survivors in candidate-id order (no ranking).
3. **Evidence matching** - the production pipeline: hard constraints, then Requirement Fit
   (skill coverage, assessment, professional experience, relevant FSP evidence, freshness), with NOT_VERIFIED
   candidates kept but penalised.

## Metrics

Per need, macro-averaged over needs: Precision@3, Precision@5 (denominator k), Recall@10, nDCG@10 (gain 2^g-1,
discount log2(rank+1), ideal ordering from all labels). *Hard-constraint violation rate*: share of the returned
top-10 that violates a constraint according to an **independent** checker (`validation/constraints.py`, a second
implementation written from the dataset fields, not from the engine). Ordering determinism: two runs compared.
Sensitivity: three weight configurations fixed in advance (default, assessment-heavy, FSP-heavy); top-5 overlap and
top-1 agreement versus default. Weights were not tuned on the labels.

## Assessment validation

Seven synthetic reference personas (Junior-like, Middle-like, Senior-like, weak, and boundary cases) answer by a fixed
rule; the expected outcome per persona and grade is written by hand from the thresholds and item counts. Each case runs
on both equivalent variants of every task family. Reported: grade accuracy, highest-grade accuracy, variant stability
(identical outcome and score difference between equivalent variants), disagreement of more than one sublevel,
discrimination between personas that know a grade and those that do not, competency coverage per grade, rubric/content
integrity checks, anchors, and a seeded random-guess false-verification rate. This is **reference-solution
validation**: it checks rules, thresholds and content, and says nothing about real candidates or test-retest reliability.

## Known limitations

Listed in `latest.md` (generated). In short: own dataset and labels, small and designed set, perfect-fit candidates
compress differences, label/engine similarity, simple keyword baseline, Junior (2 items) and Senior (4 items) tests are
short and guessable at a visible rate, single-choice items only.
