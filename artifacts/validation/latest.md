# VALIDATION REPORT

MVP validation on a self-made, reproducible dataset. The organisers provided no official dataset or ground truth. This is **not** a psychometric calibration and the numbers do not describe real candidates.

Dataset: version 1, sha256 `3dce3f9c8f7b4deb…`, 32 candidates, 10 needs, 320 label cells (98 non-zero), relevant = grade >= 2.

## Matching

| method | P@3 | P@5 | R@10 | nDCG@10 | hard-constraint violations in top-10 |
|---|---|---|---|---|---|
| keyword baseline | 0.200 | 0.260 | 0.498 | 0.395 | 56/100 (56.0%) |
| hard filters only | 0.800 | 0.660 | 0.885 | 0.816 | 0/70 (0.0%) |
| evidence matching | 0.933 | 0.780 | 0.982 | 0.980 | 0/70 (0.0%) |

Deterministic ordering (two runs identical): **True**

### Sensitivity of the evidence-matching weights

| config | P@5 | nDCG@10 | top-5 Jaccard vs default | top-1 same as default |
|---|---|---|---|---|
| default | 0.780 | 0.980 | 1.000 | 1.000 |
| assessment_heavy | 0.780 | 0.979 | 1.000 | 0.900 |
| fsp_heavy | 0.780 | 0.971 | 1.000 | 0.600 |

Configurations were fixed in advance and not tuned on the labels.

## Assessment (reference-solution validation)

- reference cases: 42 (7 personas x 3 grades x 2 equivalent variants)
- grade accuracy vs hand-written expectations: **1.000**
- highest verified grade accuracy per persona: 1.000
- variant stability: identical outcome on 1.000 of 21 persona-grade pairs; mean |score diff| 0.000, max 0.000
- disagreement of more than one sublevel: 0.000
- rubric / content checks: 0 violations

| grade test | AUC (knowers vs others) | score margin | competencies covered | items per attempt |
|---|---|---|---|---|
| JUNIOR | 1.000 | 1.000 | 6/6 | 8 |
| MIDDLE | 1.000 | 1.000 | 6/6 | 8 |
| SENIOR | 1.000 | 1.000 | 6/6 | 8 |

Random-guess false verification rate (500 seeded guessers):

- JUNIOR: 1.6% (8 items)
- MIDDLE: 0.2% (8 items)
- SENIOR: 0.0% (8 items)

Anchors:

## Failure cases

Total recorded: 104 (full list in `latest.json`). First entries per source:

- `keyword_baseline:V-N01:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 1; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `keyword_baseline:V-N01:V-C24:top5-false-positive` expected: relevance 0 (<2); actual: returned at rank 2; reason: violates hard constraint(s): salary (method does not apply constraints)
- `keyword_baseline:V-N01:V-C30:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 3; reason: candidate is UNVERIFIED; method ranks unverified context in the top-5
- `keyword_baseline:V-N01:V-C05:missed-relevant` expected: relevance 2 in top-10; actual: not in top-10; reason: no keyword overlap with the need
- `hard_filters_only:V-N01:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `hard_filters_only:V-N01:V-C18:missed-relevant` expected: relevance 3 in top-10; actual: not in top-10; reason: relevant candidate ranked 11, outside the top-10
- `hard_filters_only:V-N01:V-C20:missed-relevant` expected: relevance 3 in top-10; actual: not in top-10; reason: relevant candidate ranked 13, outside the top-10
- `hard_filters_only:V-N02:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 3; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `evidence_matching:V-N03:V-C04:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 5; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `evidence_matching:V-N04:V-C13:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5
- `evidence_matching:V-N05:V-C19:missed-relevant` expected: relevance 2 in top-10; actual: not in top-10; reason: relevant candidate ranked 11, outside the top-10
- `evidence_matching:V-N06:V-C08:top5-false-positive` expected: relevance 1 (<2); actual: returned at rank 4; reason: candidate is NOT_VERIFIED; method ranks unverified context in the top-5

Counts by source: evidence_matching=8, hard_filters_only=24, keyword_baseline=72

## Known limitations

- Собственный набор данных: организаторы не предоставили датасет и эталонную разметку; метки расставлены вручную командой разработки (не независимыми экспертами), поэтому цифры показывают согласие с нашей собственной оценкой.
- Малый и специально составленный набор: 32 синтетических кандидата и 10 потребностей с конфликтными случаями. Результаты не оценивают качество на реальных кандидатах и реальных вакансиях.
- Многие кандидаты по построению являются «идеальными» совпадениями, что сглаживает разницу nDCG/P@k между методами, которые уже применяют ограничения.
- Сходство разметки и алгоритма: правила разметки (ограничения, подтверждённый опыт против опыта без проверки, соседние подуровни) написаны той же командой, что и политика подбора, и устроены схоже. Поэтому nDCG@10 = 1.0 у подбора по подтверждённым компетенциям в основном показывает, что алгоритм реализует задуманную политику, а не что он обобщается. R@10 ограничен сверху единицей для потребностей, у которых больше 10 релевантных кандидатов.
- Базовый поиск по ключевым словам намеренно прост: это поиск по резюме, а не настроенная поисковая система.
- Навыки вне шести основных компетенций (PostgreSQL, Kafka) подтверждаются только опытом или заявками.
- Оценка: синтетические персоны отвечают по правилу, поэтому точность грейда и стабильность вариантов проверяют конвейер оценивания, пороги и целостность контента. Это не надёжность повторного тестирования и не психометрическая калибровка (IRT/2PL не заявляется).
- Глубина оценки невелика: у Junior 2 задания (только Python и SQL), у Senior 4 (Python, SQL, API/FastAPI, системное мышление); случайно угадывающий проходит такие короткие оценки с заметной вероятностью (см. guessing_baseline).
- Только задания с одним вариантом ответа; нет выполнения произвольного кода, проверки на плагиат и прокторинга.
- Веса — начальная настраиваемая конфигурация; конфигурации чувствительности заданы заранее, а не подбирались.
