# Matching mechanics

Two employer modes share the same candidate data and privacy rules.

## Mode 2: need-based matching

`Employer Need → Hard Constraints → Requirement Fit → ranked Match Run → WHY / GAPS`

A **Need** has role, specialisation, target grade (+ optional sublevel), required and optional skills (default weights 1.0 / 0.4, stored per need), salary range with GROSS/NET, acceptable work formats, optional city and latest start (days), description. No LLM parsing in P0.

### Hard constraints (before any scoring)

| constraint | rule |
|---|---|
| specialisation | must equal the need's |
| grade | **internal sublevel ±1**: target M2 → {M1, M2, S1}; without a target sublevel only the grade's own two sublevels. Verified candidates use their verified sublevel; others the whole range of the claimed grade. Never ±1 public grade |
| salary | candidate minimum ≤ need maximum (inclusive); NET↔GROSS converted at 13 % (policy parameter); unknown expectation does not exclude |
| work format | at least one shared format |
| location | only checked when the shared formats exclude REMOTE |
| availability | candidate start ≤ need's latest start, when both are set |
| visibility / consent | profile visible and open to invitations |

### Requirement Fit

`fit = Σ wᵢ·cᵢ / Σ wᵢ` over active components, × 0.6 for candidates whose grade is not VERIFIED (kept in the pool, ranked lower). Default weights (`matching/policy.py`, one place, snapshotted into every run): skill coverage 0.40, assessment 0.20, professional experience 0.15, relevant FSP 0.10, freshness 0.10 (a 0.05 semantic "context" slot exists but is inactive: no LLM). These are **initial tunable heuristics**, not a scientifically derived formula.

Skill credit: verified at or above the need's grade = 1.0; verified below = 0.5; professional experience only = 0.5 (reported as `WEAK_EVIDENCE`); claim only or nothing = 0. FSP counts only through skills relevant to the need. The result is shown as **"Соответствие этой потребности: XX %"** — fit to this need, never a candidate score.

### WHY / GAPS

Each reason has a machine code and Russian text, built only from facts in the data: WHY — `GRADE_VERIFIED`, `SKILL_VERIFIED`, `SKILL_EXPERIENCE`, `SALARY_OVERLAP`, `WORK_FORMAT_MATCH`, `FSP_RELEVANT`; GAPS — `GRADE_NOT_VERIFIED`, `SKILL_UNVERIFIED`, `SKILL_BELOW_TARGET`, `WEAK_EVIDENCE`. Works fully without an LLM.

### Match Run

`POST /api/employer/needs/{id}/match` stores an immutable `MatchRun` with the policy snapshot, the exclusion summary and the top 20 `MatchResult`s (stable order: fit ↓, verified first, candidate id). Reading a run supports `limit/offset`, `min_fit`, `verified_only`, `skill` without changing it; the UI shows the first 5 and "show more".

## Mode 1: Full Pool

`GET /api/employer/pool` — all *visible* candidates with filters: specialisation, platform grade, sublevel, verification status, verified skills, FSP history, work format, city, salary expectation. `NOT_VERIFIED` candidates stay findable.

## Privacy

Employer views (`matching/service.py: public_candidate`) show an abbreviated name, levels, verified skills, evidence summary, salary expectation. No email, phone, full name or FSP member id. Contacts appear only through an accepted invitation (see `invitations/`).

## ATS export

`GET /api/employer/match-runs/{run_id}/export?format=csv|json` returns the stored run (rank, candidate id, abbreviated name, grades, fit, formats, location, salary expectation, verified skills, WHY/GAP codes). Owner-only; no contacts. CSV has a UTF-8 BOM and neutralises formula-injection prefixes.
