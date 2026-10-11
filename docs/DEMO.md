# Demo guide

Start: `docker compose up --build` → http://localhost:3000 (API docs: http://localhost:8000/docs). Demo data is loaded automatically (`DEMO_MODE=true`).

Reset to the initial state: `docker compose exec backend python -m fsp_market.demo reset` (outside Docker: `python -m fsp_market.demo reset`). List accounts: `python -m fsp_market.demo accounts`.

Accounts (fixtures; with `DEMO_MODE=true` they sign in without a password; real registrations use email + password or a one-time code, SMTP is not configured so codes/links are not delivered by email): Alexey Demo (candidate with FSP history, `FSP-1001`), Mila Newcomer (candidate without FSP history, `FSP-2002`), Anna Verified (already VERIFIED), Hana Almost (NOT_VERIFIED Middle), Fedor Expensive (salary mismatch), Demo Corp (employer).

Canonical scenario and the decline path are in the root `README.md` (section "Демо-сценарий"). Automated proofs:

- `python scripts/smoke.py http://localhost:3000` — walks the whole canonical demo plus the decline path through the running stack;
- `tests/test_phase7_demo.py` — the same flow in-process, privacy sweep, reset;
- a headless-Chrome run of the UI flow was used during development (candidate → employer → accept → contacts → pool → validation page).

Validation page: header link "Валидация" (data from `artifacts/validation/latest.json`).

## Тестовые роли и новые сценарии

Кандидат: регистрация → письмо/демо-ссылка → выход → повторный вход паролем или кодом. Работодатель: подбор по потребности или самостоятельное приглашение из полного пула (`need_id=null`); тип зарплаты GROSS/NET переносится из потребности и может быть изменён вручную. Контакты видны только отправителю после ACCEPTED. Проверено автоматически: `tests/test_phase11_auth_invites.py`, `scripts/smoke.py`.
