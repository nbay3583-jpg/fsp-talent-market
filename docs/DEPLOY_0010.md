# Update plan: existing VPS → commit with migration 0010 (NOT executed)

Migration 0010 (`employer_needs.status/closed_at/public_to_candidates`, invitation uniqueness per employer+candidate+need) is additive for data; it was rehearsed on a restored copy of the local DB (0009 → 0010 → downgrade 0009 → 0010 with data kept).

## Preconditions
1. Explicit owner approval to touch `fsp.tradefon.ru`; work only inside the FSP compose project (`docker-compose.deploy.yml`, `.env.deploy`), never other containers/volumes.
2. `git fetch && git log --oneline -1 origin/hardening/mvp-2026-10-10` equals the tested SHA; the tree on the VPS is clean.

## Steps
1. **Backup (mandatory, verify it is non-empty):**
   `docker compose -f docker-compose.deploy.yml --env-file .env.deploy exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > ~/fsp-backup-$(date +%F-%H%M).dump && ls -la ~/fsp-backup-*.dump`
   Optionally also copy the dump off the host.
2. Record rollback target: `git rev-parse HEAD` (current deployed SHA) and `docker compose ... exec backend alembic current` (expected 0009).
3. Pull: `git pull --ff-only` (no force, no reset).
4. Rebuild only the app services (never `down -v`, never touch `pgdata`):
   `docker compose -f docker-compose.deploy.yml --env-file .env.deploy up -d --build backend frontend`
   The backend entrypoint runs `alembic upgrade head` → idempotent demo seed → uvicorn.
5. Verify: `alembic current` = 0010; `curl -s 127.0.0.1:8720/health`; run `python scripts/smoke.py http://127.0.0.1:8720`; open the site, log in as a demo candidate and employer, run one match.

## Rollback
- **App-only (preferred, schema is backward compatible):** `git checkout <previous SHA>` and rebuild backend/frontend. The 0009 code ignores the new columns, but the old pair-level unique index is replaced; this is harmless for old code.
- **Schema:** `docker compose ... exec backend alembic downgrade 0009` (fails safely if two active invitations to one candidate from one employer for different needs exist; then keep 0010 and roll back only the app).
- **Data (last resort):** stop backend, `pg_restore --clean --if-exists -d "$POSTGRES_DB"` from the dump taken in step 1, restart.

## Notes
- No `demo reset`, no volume removal. New behaviour visible to users: newly registered candidates are published after email verification; needs are shown to candidates only when the employer ticks "visible to candidates".
- SMTP is not configured: verification links are shown in the UI in demo mode only.

## Delivery via rsync (how this VPS is actually updated)
The VPS tree `/opt/fsp-talent-market` is not a git checkout (`DEPLOYED_SHA` marks the release), so steps 2–4 above are automated by `scripts/deploy-vps.sh`
(run from the Mac with `DEPLOY_CONFIRM=yes`): `git archive HEAD` → rsync to `/opt/fsp-release-<sha>` → as root on the host: pg_dump -Fc + code tarball into `/opt/fsp-backups`,
rsync into `/opt/fsp-talent-market` (keeps `.env*`, `docker-compose.deploy.yml`), rebuild backend+frontend only, wait for `/health` and `alembic current = 0010`,
automatic code-only rollback from the tarball on failure. `.env.deploy` is root-only, hence the SSH host `marakand-prod` (root) rather than `hermes-prod-nl` (deploy).
