# Architecture (V1, approved)

Modular monolith. React+TypeScript (Vite) / FastAPI / PostgreSQL / Docker Compose. No queues, no Redis, no microservices.

```
backend/app/{auth,candidates,employers,taxonomy,evidence,assessments,matching,invitations,fsp,nlp,validation,common}
backend/tests  backend/alembic  backend/main.py (app entry)
frontend/  (Vite, React, TS)
docker-compose.yml  .env.example
```

## Assessment engine
Skill -> Grade -> Task Family -> Template -> Parameter Generator -> Variant -> Fixed Rubric -> Deterministic Tests. Seeded RNG per (template, seed) => reproducible variants. IRT-ready data is stored (family/template/variant/candidate/grade/result/sub-scores/time/timestamp/rubric) but NO calibration is claimed. Code runner: subprocess, timeout, CPU/memory rlimits, no network, temp dir. gVisor = roadmap.

## Matching
Stage 1 hard filters (specialization, verified grade, salary overlap, work format, location, availability). Stage 2 evidence ranking with configurable starting heuristics: 40 skill coverage / 20 assessment / 15 professional / 10 FSP / 10 freshness / 5 context. Structured reasons + gaps. Reciprocal: candidate hard preferences filter too.

## LLM boundary
May: rewrite task context, parse résumé/need text, human-readable explanations. Must not: grade, execute code, reject, unlock contacts. Core decisions deterministic.

## Auth
Token (JWT) + argon2/bcrypt, roles candidate/employer; Keycloak-swappable behind a dependency.

## Layout note
Factory scopes workers to `src/`, `tests/`, `docs/`; hence backend = `src/fsp_market`, frontend = `src/ui`.
