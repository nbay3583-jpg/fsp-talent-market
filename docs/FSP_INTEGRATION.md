# FSP integration

No production FSP API or FSP ID stand was available, so the MVP integrates through an interface and a mock. Real access changes only the adapter, not the product.

```
FSPProvider (Protocol, fsp/provider.py)
├── get_member(fsp_id)        -> FSPMember | None
├── get_achievements(fsp_id)  -> list[FSPAchievement]
└── verify_member(fsp_id)     -> bool
```

`MockFSPProvider` serves fixtures: `FSP-1001` (verified member with 3 achievements: algorithmic, product programming, cybersecurity), `FSP-2002` (verified member **with no history**), `FSP-9999` (unverified member, rejected). Unknown ids return no member and no achievements; it never raises.

## From achievement to evidence

`evidence/fsp_link.py` verifies the member, then maps each achievement's discipline to the relevant skills (`fsp/mapping.py`: algorithmic → python; product programming → api_fastapi, sql, testing; cybersecurity → none in the Backend track) and stores one `FSP_ACHIEVEMENT` evidence row per skill (strength MEDIUM, no level, details: achievement id, discipline, year, place). Linking is idempotent.

Guarantees: FSP evidence **never changes the grade** or any `VerifiedSkillLevel`, adds no points, and counts in matching only for skills relevant to the need. A candidate with no FSP history (or an empty linked profile) works exactly like any other; the Evidence Profile shows an explicit empty state.

## Replacing the mock

1. Implement `FSPProvider` against the real FSP API / FSP ID (OIDC via Keycloak) and register it in `api/deps.py: get_fsp_provider`.
2. Replace the bearer-token issuing (`auth/tokens.py`, registration) with Keycloak-issued tokens behind `current_candidate_id` / `current_employer_id`; keep the role claim.
3. Extend `DISCIPLINE_SKILLS` for new disciplines; no change to the matching or grading code.

If the organisers publish a test stand or authorisation requirements, only steps 1–2 are affected.
