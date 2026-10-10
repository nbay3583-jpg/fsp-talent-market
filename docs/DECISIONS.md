# Decisions

- D1 Modular monolith over PostgreSQL; the evidence "graph" is relational. No queues, Redis, microservices or LLM dependency.
- D2 Deterministic grading and matching; no LLM decides grades, hard constraints, verification or contact unlock.
- D3 IRT-ready storage, no calibration claims.
- D4 Platform grade comes only from the Core Assessment. A failed attempt gives `NOT_VERIFIED` and keeps the claimed grade; there is no automatic downgrade. Same-target retry after a 7-day cooldown (MVP policy, not calibrated).
- D5 FSP is external evidence behind `FSPProvider` (mock in MVP); it never changes the grade; candidates without FSP history are first-class.
- D6 No arbitrary-code sandbox in the MVP (P0 = deterministic single-choice items: code reading, SQL/API reasoning); a gVisor-backed runner is roadmap.
- D7 Implementation used a Factory/Bonsai coding worker where it was fast; from Phase 2 the Factory API needed a bearer token that was not available, so the local Bonsai endpoint was called directly, and the controller wrote the modules where Bonsai stalled or produced incorrect code. Architecture was not affected.
- D8 Validation labels are hand-assigned independently of the scoring formula; only measured numbers are published (`artifacts/validation`).
- D9 Pass thresholds Junior 0.60 / Middle 0.70 / Senior 0.75, upper sublevel at 0.85; matching weights 0.40 / 0.20 / 0.15 / 0.10 / 0.10. Both are initial tunable configuration, not scientific constants.
- D10 Grade tolerance in matching is ±1 internal sublevel (target M2 → M1, M2, S1), never ±1 public grade.
- D11 Contacts are released only by `invitations.service.contacts_for` for an ACCEPTED/CONTACTS_UNLOCKED invitation of the requesting employer; hiding is server-side.
- D12 MVP authentication: signed bearer tokens issued at registration (no passwords) plus demo accounts when `DEMO_MODE=true`; Keycloak / FSP ID is the planned replacement behind the same dependency.

## 2026-10-10 — Core Assessment: 11 tasks per grade; CAT evaluated, not adopted

- Bank widened from 8 to 11 families per grade (33 total, 6–10 presets each; rubric `backend-core-2026.10.2`). Time limits 15/19/23 min.
- Computerised adaptive testing was tried on the existing bank (simulation, 20k synthetic candidates per grade, uniform ability, 11 items). The bank has one difficulty band per grade and no IRT calibration, so true CAT (item selection by information) is not defensible. The only sound variant is curtailment (stop when pass/fail is decided): pass/fail agreement with the full test was 100% and it saves 3.3 / 3.8 / 4.7 items (J/M/S) on average, but the sublevel (J1–S3), which needs the full score, becomes unreliable on a truncated attempt (and frozen variants + autosave assume a fixed set). **Not adopted**; the fixed 11-item test stays.
