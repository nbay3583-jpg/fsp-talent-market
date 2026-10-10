# FSP Talent Market

**Платформа обратного подбора IT-специалистов по подтверждённым компетенциям.**

Мы не ранжируем резюме. Кандидат подтверждает компетенции тестом и внешними данными, работодатель описывает потребность и получает короткий объяснимый список с причинами и пробелами, пишет адресно — **с обязательной зарплатой**, а контакты открываются **только после согласия кандидата**.

MVP для Федерации спортивного программирования (ФСП). Полностью реализован трек **Backend / Python** (Junior / Middle / Senior, подуровни J1–S2).

## Проблема и ключевая механика

Резюме — это заявки, а не доказательства; работодатель тонет в откликах, а кандидат рассылает резюме вслепую. Здесь:

- **Skill Claim → Skill Evidence → Verified Skill Level.** Заявка кандидата (резюме, профиль) — только контекст. Подтверждением становятся Core Assessment, достижения ФСП, профессиональный опыт (с разной силой сигнала). Общего «Talent Score» нет.
- **Платформенный грейд определяет только основной тест.** Не резюме, не ФСП, не вакансия, не Requirement Fit. Если Middle не подтверждён — кандидат остаётся с заявленным Middle и статусом `NOT_VERIFIED`; автоматического понижения до Junior нет.
- **Requirement Fit** — «Соответствие этой потребности»: соответствие *конкретной* потребности работодателя, а не оценка человека. Рядом всегда **WHY** (✓) и **GAPS** (△), собранные только из реальных данных.
- **Приглашение с зарплатой** (вилка + GROSS/NET обязательны, проверка на сервере) → кандидат видит условия до решения → **Accept / Decline** → при Accept контакты открываются работодателю; при Decline остаются скрыты.

### Candidate flow
Регистрация / демо-вход → профиль (специализация, целевой грейд, предпочтения) → параметризованный Core Assessment (~3–5 минут) → результат `VERIFIED` / `NOT_VERIFIED` → Evidence Profile (заявка vs подтверждение) → подключение ФСП ID (mock) → приглашения.

### Employer flow
Потребность (грейд/подуровень, обязательные и желательные навыки, вилка, формат, локация) → жёсткие ограничения → Requirement Fit → ранжированный список (WHY / GAPS) → карточка кандидата (контактов нет) → приглашение с зарплатой → статус → контакты после согласия. Второй режим: **Весь пул** с фильтрами.

## Быстрый старт

```bash
git clone <repo> && cd fsp-talent-market
docker compose up --build        # без .env: безопасные локальные значения по умолчанию
```

| что | адрес |
|---|---|
| приложение (React) | http://localhost:3000 |
| API + Swagger/OpenAPI | http://localhost:8000/docs · http://localhost:8000/openapi.json (также через :3000) |
| health | http://localhost:8000/health |

При старте backend сам применяет миграции (Alembic) и загружает демо-данные (`DEMO_MODE=true`, идемпотентно). Для других значений: `cp .env.example .env` и отредактируйте (там только имена и примеры; для всего, что не локальная демонстрация, смените `JWT_SECRET` и поставьте `DEMO_MODE=false` — при `ENVIRONMENT=production` сервис иначе не стартует). LLM и ключи API для основного сценария **не нужны**.

### Без Docker (разработка)

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" -c constraints.txt
export DATABASE_URL=sqlite:////tmp/fsp.db DEMO_MODE=true
.venv/bin/alembic upgrade head && .venv/bin/python -m fsp_market.demo seed
.venv/bin/uvicorn fsp_market.main:app --port 8000            # backend
cd src/ui && npm ci && npm run dev                            # frontend на :5173 (proxy на :8000)
```

## Демо-аккаунты

Паролей нет (в MVP вход выдаётся при регистрации; боевой путь — FSP ID / Keycloak). Кнопки «Демо-вход» на главной работают только при `DEMO_MODE=true`:

| аккаунт | что показывает |
|---|---|
| **Alexey Demo** (`alexey@demo.example`) | канонический кандидат: ещё не проходил тест; ФСП ID `FSP-1001` есть история |
| **Mila Newcomer** | кандидат **без** истории ФСП (`FSP-2002`): всё работает, уровень не страдает |
| Anna Verified | уже `VERIFIED` Middle M2 |
| Hana Almost | `NOT_VERIFIED` Middle: остаётся Middle, не Junior |
| Fedor Expensive | зарплата 300k — отсекается жёстким ограничением |
| **Demo Corp** | работодатель без потребностей |

Сброс демо в исходное состояние: `docker compose exec backend python -m fsp_market.demo reset` (удаляет все данные приложения и заново загружает демо; валидационный датасет отдельный и не затрагивается).

## Демо-сценарий (≈5 минут)

1. Демо-вход **Alexey Demo** → «Core Assessment» → «Начать тест» → «Демо: заполнить эталонными ответами» (или ответьте сами) → «Отправить» → **Backend / Middle (M2) VERIFIED**.
2. «Evidence Profile»: таблица **заявка → подтверждение**, у навыков — «Основной тест», сила, уровень платформы. «Подключить ФСП ID (mock)» → появляются достижения ФСП как отдельное подтверждение (грейд не меняют).
3. «Выйти» → **Demo Corp** → форма потребности уже заполнена (Python Backend, Middle M2, FastAPI + PostgreSQL, удалённо, 200 000–250 000 ₽ GROSS) → «Подобрать кандидатов».
4. Список: «Соответствие этой потребности: XX%», **WHY / GAPS**; «Отсеяно по жёстким ограничениям» (в т.ч. по зарплате). «Открыть кандидата» → контакты 🔒 скрыты.
5. Отправить приглашение: вилка, **GROSS/NET выбирается явно**. 
6. Выйти → **Alexey Demo** → «Приглашения» → зарплата видна крупно до решения → **«Принять и открыть контакты»**.
7. Выйти → **Demo Corp** → «Отправленные приглашения»: статус и 🔓 контакты открыты по согласию кандидата.
8. Путь отказа: тот же сценарий с **Mila Newcomer** → «Отклонить» → контакты остаются скрыты.
9. «Весь пул» — фильтры (грейд, статус, навык, ФСП, формат, зарплата), карточка без контактов. «Валидация» — реальные метрики.

Автоматическая проверка того же сценария на запущенном стеке: `python scripts/smoke.py http://localhost:3000`.

## Архитектура

Модульный монолит: **React + TypeScript (Vite)** → **FastAPI** → **PostgreSQL** (SQLAlchemy 2, Alembic), Docker Compose (db, backend, frontend/nginx). Подробнее: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
src/fsp_market/
  api/          HTTP-слой (candidate, employer, invitations, demo, validation)
  auth/         подписанные bearer-токены с ролью (заменяемо на Keycloak)
  taxonomy/     специализации, компетенции, грейды и подуровни
  candidates/ employers/ skills/   сущности; Skill Claim / Evidence / Verified Skill Level
  assessments/  Family → Template → Preset → Variant, детерминированная оценка, seed
  evidence/     создание подтверждений, Evidence Profile, привязка ФСП
  matching/     жёсткие ограничения, Requirement Fit, WHY/GAPS, match run, Full Pool
  invitations/  приглашения, state machine, разблокировка контактов
  fsp/          FSPProvider + MockFSPProvider
  validation/   воспроизводимая валидация (датасет, разметка, метрики)
  demo.py       seed / reset демо
src/ui/         React-приложение     tests/   pytest     artifacts/validation/   результаты
```

Стек и проверенные версии: Python 3.12, FastAPI 0.142.2, Starlette 1.7.0, Uvicorn 0.54.0, SQLAlchemy 2.1.3, Alembic 1.20.0, psycopg 3.3.6, Pydantic 2.13.5 (pin: `constraints.txt`); PostgreSQL 16 (docker), nginx 1.27; Node 22, React 18.3.1, Vite 5.4.21, TypeScript 5.9.3, Vitest 2.1.9.

## Как работает оценка (кратко)

Цепочка **Competency → Task Family → Task Format → Task Template → Parameter Preset → Task Variant → Fixed Scoring Contract**. Внутри семьи варианты меняют домен, схему, endpoint, числа, сценарий, но сохраняют компетенцию, сложность, рубрику и контракт оценки. Параметры — заранее проверенные пресеты, не произвольная генерация LLM. Оценка детерминирована (без LLM, без исполнения кода кандидата). Порог: Junior 0.60, Middle 0.70, Senior 0.75; верхний подуровень (J2/M2/S2) от 0.85. Повторная попытка того же грейда после неуспеха — через 7 дней. Подробнее и о том, почему тест устойчив к простой передаче ответов: [docs/ASSESSMENT.md](docs/ASSESSMENT.md). IRT/2PL-калибровку мы **не** заявляем.

## Как работает подбор (кратко)

1. **Жёсткие ограничения** до скоринга: специализация, допуск по **внутреннему подуровню ±1** (цель M2 → M1/M2/S1; не «±1 публичный грейд»), зарплата (с пересчётом NET↔GROSS), формат, локация, срок выхода, видимость профиля, согласие на приглашения.
2. **Requirement Fit** = взвешенная сумма: покрытие навыков, результат теста, профессиональный опыт, релевантные достижения ФСП, свежесть. Веса — в одном `MatchingPolicy`, это начальная настраиваемая конфигурация, а не «научная истина». `NOT_VERIFIED` кандидат не удаляется, но ранжируется ниже.
3. **WHY / GAPS** — коды причин (`GRADE_VERIFIED`, `SKILL_VERIFIED`, `FSP_RELEVANT`, `SKILL_UNVERIFIED`, `WEAK_EVIDENCE`, …) и текст, только из реальных фактов. Подробнее: [docs/MATCHING.md](docs/MATCHING.md).

## Интеграция с ФСП

`FSPProvider` с методами `get_member()`, `get_achievements()`, `verify_member()`. В MVP — `MockFSPProvider` (боевых API у нас нет). Достижения ФСП — **отдельный тип подтверждения** `FSP_ACHIEVEMENT`, привязаны к релевантным навыкам, **не меняют грейд** и не дают «+баллов»; кандидат без истории ФСП работает полноценно. Схема подключения реального FSP ID / Keycloak — [docs/FSP_INTEGRATION.md](docs/FSP_INTEGRATION.md).

## Валидация

Методика: [docs/VALIDATION_METHOD.md](docs/VALIDATION_METHOD.md). Организаторы не предоставили официальный датасет и ground truth, поэтому используется **собственный воспроизводимый набор** (разметка составлена вручную до запуска алгоритма). Это MVP-валидация, **а не психометрическая калибровка**. Запуск одной командой: `python -m fsp_market.validation` (пересоздаёт `artifacts/validation/latest.{json,md}`; `--check` проверяет воспроизводимость).

### Реальные результаты

Блок ниже генерируется кодом из `artifacts/validation/latest.json`; руками числа не правятся (тест сверяет его с артефактом).

<!-- VALIDATION:BEGIN (generated by python -m fsp_market.validation --update-readme) -->
Dataset: 32 candidates, 10 employer needs, 98 non-zero hand labels (of 320 pairs), relevant = grade >= 2. MVP validation on our own dataset, not a psychometric calibration.

| method | P@3 | P@5 | R@10 | nDCG@10 | hard-constraint violations in top-10 |
|---|---|---|---|---|---|
| keyword baseline | 0.200 | 0.260 | 0.498 | 0.395 | 56/100 (56.0%) |
| hard filters only | 0.800 | 0.660 | 0.885 | 0.816 | 0/70 (0.0%) |
| evidence matching | 0.933 | 0.780 | 0.982 | 0.980 | 0/70 (0.0%) |

Assessment (reference-solution validation, 42 synthetic cases): grade accuracy 1.000; variant stability 1.000 identical outcomes over 21 persona-grade pairs (max score difference 0.000); grade separation AUC JUNIOR 1.000, MIDDLE 1.000, SENIOR 1.000; disagreement over one sublevel 0.000; deterministic scoring: True; rubric/content violations: 0.

Random-guess false verification: JUNIOR 1.6% (8 items), MIDDLE 0.2% (8 items), SENIOR 0.0% (8 items).

Deterministic matching order: True. Failure cases recorded: 104 (see `artifacts/validation/latest.json`).
<!-- VALIDATION:END -->

Ограничения эксперимента — в `artifacts/validation/latest.md` (раздел Known limitations).

## API и OpenAPI

Swagger UI: `/docs`, схема: `/openapi.json`. Группы: `candidate` (регистрация, профиль, assessment, Evidence Profile, ФСП), `employer` (потребности, подбор, Full Pool, карточка кандидата), `invitations`, `validation`, `demo` (только при `DEMO_MODE=true`). Ошибки — стандартный `{"detail": ...}` (401 нет/неверный токен, 404 чужой объект, 409 конфликт состояния, 422 валидация).

## Privacy / RBAC

- Две роли (candidate, employer), токен подписан и несёт роль: токен кандидата не открывает employer-API и наоборот.
- Кандидат видит только свои данные и приглашения; работодатель — только свои потребности, подборы и приглашения. Чужой объект → 404.
- Контакты (email, телефон, полное имя) **никогда** не сериализуются в ответах работодателю, пока приглашение не `ACCEPTED`/`CONTACTS_UNLOCKED`; единственная точка выдачи — `invitations/service.py: contacts_for`. Скрытие — на сервере, не во фронтенде. Работодателю видны «Имя Ф.», уровень, подтверждённые навыки, зарплатные ожидания.
- Скрытый профиль и «не принимаю приглашения» уважаются в подборе, пуле и при отправке приглашения. Зарплатная вилка в приглашении проверяется на сервере.
- Секретов в репозитории нет; `.env` в `.gitignore`; демо-значения помечены как dev-only.

## Известные ограничения

Только один полностью реализованный трек (Backend / Python); вопросы — single-choice (без исполнения кода, без proctoring/antiplagiat); тесты Junior (2 вопроса) и Senior (4) короткие и угадываются заметно чаще, чем Middle (см. результаты валидации); навыки вне шести компетенций (PostgreSQL, Kafka) подтверждаются только опытом; FSP — mock; вход без паролей (регистрация выдаёт токен); письма/уведомления не реализованы; веса matching — начальная конфигурация; валидация — на собственном небольшом наборе.

## Roadmap

Real FSP ID / Keycloak, подтверждение email, Technology Assessment (глубина по одной технологии), безопасный Python-runner (gVisor), второй трек специализации, калибровка заданий на реальных данных (IRT), semantic-реранкинг и разбор резюме (опционально, через адаптер, не влияющие на грейд).

## Вход и учётные записи

Регистрация: email + пароль (≥ 8 символов); кандидат подтверждает email по ссылке. Повторный вход: `POST /api/auth/login` (email + пароль) либо одноразовый код `POST /api/auth/code/request` → `POST /api/auth/code/verify` (он же восстановление доступа). 5 неверных паролей блокируют аккаунт на 15 минут; ответы не раскрывают, существует ли email. Токен живёт 12 часов. Демо-вход (`DEMO_MODE=true`) работает по-прежнему.

## Публичный стенд (staging)

`docker-compose.deploy.yml` + `.env.deploy` (из `.env.deploy.example`, секреты не в git): изолированные db/backend/frontend, frontend на `127.0.0.1:8720`, HTTPS даёт reverse proxy хоста. `ENVIRONMENT` не должен быть `production` при `DEMO_MODE=true`. Тома БД не удаляются при обновлении (`up -d --build`).

## Ограничения MVP

Email-доставка проверена только через OUTBOX/демо-ссылку (SMTP не подключён); интеграция с ФСП — mock-адаптер; валидация модели — на синтетических данных (см. `docs/VALIDATION.md`); браузерная проверка UI desktop/mobile вручную не проводилась.

## Команды разработки

```bash
.venv/bin/python -m pytest tests -q                       # backend tests
(cd src/ui && npm test && npm run build)                  # frontend tests + typecheck + build
.venv/bin/python -m fsp_market.validation --check         # воспроизводимость валидации
.venv/bin/alembic upgrade head                            # миграции
./scripts/final-check                                     # всё вместе (+ smoke, если стек запущен)
python -m fsp_market.demo reset                           # сброс демо
```
