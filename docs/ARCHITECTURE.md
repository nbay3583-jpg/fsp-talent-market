# Architecture

Modular monolith: **React + TypeScript** (Vite, served by nginx) → **FastAPI** → **PostgreSQL** (SQLAlchemy 2, Alembic). Docker Compose runs `db`, `backend`, `frontend`. No queues, no Redis, no microservices, no LLM dependency; CPU-only.

## Functional architecture

```
Candidate  --claims-->  Skill Claim ──┐
Core Assessment ──────> Skill Evidence ├──> Verified Skill Level ──> Evidence Profile ──┐
FSP achievement (mock) > Skill Evidence┘     (platform level per skill)                  │
Professional experience > Skill Evidence                                                  ▼
Employer Need ──> hard constraints ──> Requirement Fit + WHY/GAPS ──> Match Run (top 20) ──> Invitation (salary)
                  Full Pool (filters) ───────────────────────────────────────────────────────────┘      │
                                                                 candidate Accept ──> contacts unlocked ◄┘ (Decline: stay hidden)
```

Categorisation: a candidate's **category** is `specialization × public grade` (e.g. *Backend / Middle*), with internal sublevels J1 J2 M1 M2 S1 S2. Only Backend / Python is fully implemented; other specialisations stay in the taxonomy as data (a frontend specialisation row exists as a seed example). The grade is set only by the Core Assessment.

## Components (`src/fsp_market/`)

| module | responsibility |
|---|---|
| `api/` | FastAPI routers (candidate, employer, invitations, demo, validation), dependencies, role checks |
| `auth/` | HMAC-signed bearer tokens with a role claim; swappable behind the dependency for Keycloak |
| `taxonomy/` | specialisations, competencies, grade↔sublevel helpers |
| `candidates/`, `employers/` | entities; candidate preferences (salary, formats, visibility, consent flags) |
| `skills/` | `SkillClaim` (what is claimed), `SkillEvidence` (what supports it), `VerifiedSkillLevel` |
| `assessments/` | Family → Template → Preset → Variant, attempts, answers, results, scoring, seed |
| `evidence/` | evidence creation (Core Assessment, FSP, experience), Evidence Profile composition |
| `matching/` | policy, pure engine (constraints, fit, WHY/GAPS), match runs, Full Pool, employer-safe views |
| `invitations/` | invitation model, state machine, the only place that releases contacts |
| `fsp/` | `FSPProvider` interface, `MockFSPProvider`, discipline→skill mapping |
| `validation/` | fixed dataset, labels, baselines, metrics, assessment reference validation |
| `demo.py` | demo seed / reset |

## Data model (tables)

`specializations`, `competencies`, `skills`, `candidates`, `employers`, `skill_claims`, `skill_evidence`, `verified_skill_levels`, `task_families`, `task_templates`, `task_presets`, `task_variants`, `assessment_attempts`, `assessment_answers`, `assessment_results`, `employer_needs`, `need_skills`, `match_runs`, `match_results`, `invitations`. Migrations `0001`–`0004` in `src/fsp_market/migrations/versions/`. Variants store `seed` and `is_anchor`, results store sub-scores and rubric results (IRT-ready storage; **no calibration is claimed**).

## Invariants enforced in code (and covered by tests)

- Platform grade changes only through `score_attempt`; résumé, FSP, needs and fit never write it.
- A failed attempt sets `NOT_VERIFIED`, keeps the claimed grade, never lowers or invents a level.
- FSP evidence has no level; it cannot create or raise a `VerifiedSkillLevel`.
- Employer-facing views contain no email, phone, full name or FSP member id; contacts exist only in `invitations.service.contacts_for` for `ACCEPTED`/`CONTACTS_UNLOCKED` invitations of that employer.
- Salary range and GROSS/NET are validated server-side on every invitation.

## Deployment

`docker compose up --build`: backend image runs `alembic upgrade head`, then `python -m fsp_market.demo seed --if-demo-mode`, then uvicorn; nginx serves the SPA and proxies `/api`, `/health`, `/docs`, `/openapi.json`. Configuration (all optional, see `.env.example`): `DATABASE_URL`, `JWT_SECRET`, `ENVIRONMENT`, `DEMO_MODE`. With `ENVIRONMENT=production` the app refuses to start if `DEMO_MODE` is on or the token secret is a placeholder.

## Dependencies

Python 3.12; fastapi 0.142.2, starlette 1.7.0, uvicorn 0.54.0, sqlalchemy 2.1.3, alembic 1.20.0, psycopg 3.3.6, pydantic 2.13.5, pydantic-settings 2.15.0 (pinned in `constraints.txt`; dev: pytest, httpx, ruff). Frontend: react 18.3.1, vite 5.4.21, typescript 5.9.3, vitest 2.1.9 (locked in `package-lock.json`). Images: postgres:16-alpine, nginx:1.27-alpine, node:22-alpine, python:3.12-slim.
