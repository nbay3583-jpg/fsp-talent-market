# Product

**Thesis:** reverse recruiting on verified evidence. Not a job board, not résumé search, not a résumé scorer.

## Flows
- Candidate: profile -> specialization+declared grade -> parameterized assessment -> Evidence Profile -> Verified Category -> Verified Talent Pool.
- Employer: describe need -> hard constraints -> evidence-based reciprocal matching -> 3-10 candidates with WHY/GAPS -> salary-backed invitation -> candidate accepts (HARDSHAKE) -> contacts unlocked.

## Central abstraction: Evidence Profile
SKILL CLAIM -> 1..n EVIDENCE (sources: assessment, FSP achievement, professional experience, recent challenge). Résumé = context, never verification. No universal Talent Score. "92% MATCH" = fit to THIS need only.

## MVP scope
Specializations: Backend, Frontend, Data/ML, DevOps. Grades: Junior/Middle/Senior (<=12 categories). Python-only code assessment. Mock FSP provider. Candidate and employer roles.

## Hardshake
SENT -> VIEWED -> (DECLINED | ACCEPTED -> CONTACTS_UNLOCKED). Invariant: contacts visible iff status is ACCEPTED. Salary range mandatory (server-enforced).

## Non-goals
Calibrated IRT, SFIA, crypto unlock, mandatory gVisor, knowledge graph, microservices, LLM-as-judge, arbitrary LLM tests, universal score, ATS integrations, decay maths.
