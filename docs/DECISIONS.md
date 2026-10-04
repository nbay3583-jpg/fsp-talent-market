# Decisions
- D1 Modular monolith, Postgres relational "evidence graph".
- D2 Deterministic grading; LLM never decides.
- D3 IRT-ready storage, no calibration claims.
- D4 No auto-downgrade of declared grade; "not confirmed" is a state.
- D5 FSP = evidence via MockFSPProvider behind an interface; zero-FSP candidates first-class.
- D6 Process-level code sandbox for MVP; gVisor roadmap.
- D7 Implementation by Factory coding worker on local-heavy-primary (Bonsai); Claude architects/reviews. No cloud fallback.
- D8 Validation labels independent of the scoring formula; only measured numbers published.
