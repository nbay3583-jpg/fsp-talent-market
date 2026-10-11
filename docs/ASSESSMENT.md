# Assessment mechanics (Backend / Python; separate technology exams)

> Release note (11 October 2026): **Core 17 tasks** for new attempts; independent **FastAPI** and **PostgreSQL** exams use the same engine (10 tasks each per grade). Tech exam results create separate skill evidence and do **not** change the Core grade. Newly added families have only 2 variants, and their question banks have not received independent expert fact-checking. The separate Pyodide Python Practice is a browser self-test, not evidence of a verified grade.

## Core Assessment mechanics (Backend / Python)

The Core Assessment is the **only** source of the platform grade.

## Structure

`Competency → Task Family → Task Format → Task Template → Parameter Preset → Task Variant → Fixed Scoring Contract`

- **Task Family** fixes competency, target grade, difficulty band, rubric (dimensions + weights), edge-case classes, allowed formats.
- **Task Template** fixes prompt structure, format, parameter schema, scoring rule.
- **Parameter Preset** is a hand-verified parameter set (no free-form generation, no LLM).
- **Task Variant** is a concrete instance: prompt, options, `seed`, expected behaviour, scoring contract, `is_anchor`.
- Variants of one family change domain, schema, endpoint, numbers or scenario; they keep competency, difficulty, rubric dimensions and scoring contract. Rendering is a pure function (`assessments/variants.py`): same template + preset + seed ⇒ same variant.

Core has six competencies (Python, SQL, API/FastAPI, Testing, Docker basics, System thinking). The original composition had **11 families per grade**; after the October 11 additive expansion **new attempts have 17 tasks**. Historical attempts and the legacy validation may retain 11-task composition. Original families had 6–10 presets; the added families have 2 alternatives per new slot. Time limits are 15 / 19 / 23 min for Junior / Middle / Senior. Formats used: code reading, SQL reasoning, API reasoning, deterministic/rubric questions (single choice). No arbitrary code execution.

## Flow and scoring

1. `POST /api/assessments {target_grade}` — the candidate's **own claim**; creates (or returns the existing) in-progress attempt. One variant per family is assigned: `variants[attempt_id % n]` — reproducible from the attempt id.
2. The client sees prompts and options only; the correct option never leaves the server (except the demo-only helper below).
3. `POST /api/assessments/{id}/submit` — must answer exactly the assigned tasks with valid options (else 422).
4. Scoring is exact-match and deterministic. Total score = earned/possible points. Pass thresholds: **Junior 0.60, Middle 0.70, Senior 0.75**; the upper sublevel (J2/M2/S2) needs ≥ 0.85.
5. Result `VERIFIED` (platform level + sublevel set) or `NOT_VERIFIED` (claimed grade kept, nothing lowered). A competency with score ≥ the grade's threshold creates `CORE_ASSESSMENT` evidence (strength HIGH) and a `VerifiedSkillLevel` for the matching skills (never lowering an existing higher level).
6. A failed attempt blocks the same target grade for **7 days** (anti grade-hopping; MVP policy, not calibrated). Another grade can be attempted at any time.

## Why it resists simple answer passing

- Different attempts get different variants of the same family; surface data, options and the position of the correct option differ, so a memorised "A, C, B…" sheet or a pasted answer to one variant does not carry over to its sibling.
- Answer keys are server-side only; submissions are validated against the assigned set; failed targets have a cooldown, so brute force by retries is slow.
- Honest limits: each family has 6–10 variants, so collusion resistance is moderate; the parameter-preset design is meant to scale to many more; there is no proctoring or plagiarism detection (roadmap). Attempts are 11 items; the guessing baseline is simulated in the validation results.

## Comparability and "no calibration" statement

Variants are comparable by the shared family contract, fixed rubric, an anchor task and validation — **not** by psychometric calibration. Data needed for later IRT is stored (family, template, variant, candidate, grade, sub-scores, timestamps) but no IRT/2PL model is fitted or claimed.

## Demo-only helper

With `DEMO_MODE=true`, `GET /api/demo/assessments/{id}/reference-answers` returns the correct options of the caller's **own** attempt so a jury can click through quickly. It returns 404 when demo mode is off and must never be enabled in production.
