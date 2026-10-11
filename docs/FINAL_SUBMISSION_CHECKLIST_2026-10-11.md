# Final submission checklist — FSP Talent Market / LCT 2026

**Deadline:** 11 October 2026, 23:59 Moscow time. Source: official `ФСП спец. трек ТЗ.pdf`, sections 3.3–3.5, 5.2 and 6, plus the 37-slide official LCT template.

## Required submission (official §5.2)

- [ ] Link to **source repository**. Current implementation is in [`hardening/mvp-2026-10-10`](https://github.com/nbay3583-jpg/fsp-talent-market/tree/hardening/mvp-2026-10-10), while `main` is older (33 commits behind at preflight). **Grant jury access if repo is private**, or explicitly link the correct branch; do not merge branches without approval.
- [ ] Link to final **presentation PPTX or PDF**. Check file opens and all mandatory slides are filled.
- [ ] Public runnable prototype: **https://fsp.tradefon.ru**; provide jury demo access and a complete candidate → assessment → need → invitation → accept → contacts walkthrough.
- [ ] Link to **technical accompanying documentation PDF/DOC** (not only scattered Markdown): architecture, assessment variant rationale, matching and categorisation, validation datasets/baselines/metrics and limitations, mock-to-real FSP integration, API/OpenAPI, exact dependency versions, reproducible local deployment.
- [ ] **Submit through competition portal and save confirmation**. Uploading to GitHub or deploying the site alone does NOT constitute entry submission.

## Official presentation slides 7–11

- **7:** FSP problem title / solution name.
- **8:** brief solution, uniqueness, captain, team size, city/region.
- **9:** actual team names, roles, messenger/telephone and job/school fields. Do not invent personal data.
- **10:** team background, major development challenges and solutions.
- **11:** technical/marketing/business substance and roadmap.

## Facts for final pitch and technical PDF

- Reverse recruiting is core (§2): **35%** of the scoring rubric; assessment + validation **25%**. Show WHY/GAPS, salary range in RUB and mandatory GROSS/NET, and release of candidate contacts only after explicit acceptance.
- Backend/Python: graded Core Assessment, **17 questions for new attempts**; historical validation references 11-task composition. Grades: Junior/Middle/Senior, nine sublevels J1–S3.
- FastAPI/PostgreSQL: independent tests, **10 questions per grade**, separate skill evidence, not a replacement for the overall grade. New banks have limited two-variant slots and no independent human fact-check.
- Python Practice: Pyodide **0.27.7**, seven in-browser tests on `second_largest`, an 8s execution limit. **Not independent verification**, no effect on core grade or matching; user manually observed 7/7 on production.
- FSP registry: no real API supplied; adapter + mock achievements. Candidates without FSP history still work.
- SMTP delivery not configured; demo email confirmation uses outbox/verification link. Do not claim a production mail provider.
- Validation dataset: 32 synthetic candidates, 10 employer needs; internally reported P@5 **0.780** for evidence matching versus **0.260** keyword baseline. Not external proof or psychometric calibration.

## Release gate

- [ ] Verify actual production SHA == intended published GitHub SHA; migration `0011` applied; API and non-FSP apps healthy.
- [ ] Verify desktop and mobile, assistant button, Core/Tech exams, role permissions, invitation privacy and Pyodide.
- [ ] Regenerate final PPTX/PDF and technical PDF **after** changes. Check dates, names, team fields, links, and readable screenshots.
- [ ] Keep user/test candidate #198 untouched unless there is a separate, safe cleanup plan.

**Status at document creation:** repo/docs reviewed; final slide/PDF generation, deployed SHA verification, team fields and portal submission remain unconfirmed. Do not mark submitted before receiving portal confirmation.