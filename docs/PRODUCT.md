# Product

**Thesis:** reverse recruiting on verified evidence. Not a job board, not résumé search, not a résumé scorer.

Candidate: profile → specialisation + claimed grade → parameterised Core Assessment → `VERIFIED` / `NOT_VERIFIED` → Evidence Profile (claims vs evidence, FSP evidence) → addressed invitations with a visible salary → Accept / Decline.

Employer: need → hard constraints → Requirement Fit with WHY / GAPS → candidate view (no contacts) → salary-backed invitation → contacts only after the candidate accepts. A second mode, Full Pool, lists the whole visible bank with filters.

Central abstraction: **Evidence Profile** — `Skill Claim → Skill Evidence → Verified Skill Level`; résumé data is context, FSP achievements are separate external evidence, and there is no universal Talent Score. "Fit" always means fit to one concrete need.

MVP scope: Backend / Python fully implemented (Junior / Middle / Senior, sublevels J1–S2); other specialisations exist only as taxonomy rows. Mock FSP provider. Roles: candidate, employer.

Non-goals (not built): calibrated IRT, arbitrary code execution sandbox, LLM judging, résumé parsing, universal score, ATS, anti-fraud, chat, vacancy marketplace, real Keycloak / FSP API, email delivery.
