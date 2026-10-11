#!/usr/bin/env bash
# Safe update of the EXISTING FSP VPS deployment (migration 0010). Run from the Mac, repo root:
#   DEPLOY_CONFIRM=yes ./scripts/deploy-vps.sh
# Source is `git archive HEAD` (tracked files only; no .env, no .git, no local junk), delivered by rsync.
# Touches only /opt/fsp-talent-market (project fsp-talent-market); never `down -v`, never the db volume,
# never `demo reset`. Runs as root over SSH because .env.deploy is root-only (0600).
set -euo pipefail
HOST="${FSP_SSH_HOST:-marakand-prod}"          # root@ same machine as hermes-prod-nl
APP=/opt/fsp-talent-market
BK=/opt/fsp-backups
cd "$(dirname "$0")/.."
SHA="$(git rev-parse --short HEAD)"
[ "${DEPLOY_CONFIRM:-}" = "yes" ] || { echo "Set DEPLOY_CONFIRM=yes to deploy $SHA to $HOST:$APP"; exit 2; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked files are modified; commit first"; exit 2; }
git fetch -q origin && [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/hardening/mvp-2026-10-10)" ] \
  || { echo "HEAD is not pushed to origin/hardening/mvp-2026-10-10"; exit 2; }
echo "== deploying $SHA to $HOST"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git archive HEAD | tar -x -C "$TMP"
STAGE="/opt/fsp-release-$SHA"
rsync -a --delete "$TMP"/ "$HOST:$STAGE/"

ssh "$HOST" bash -s -- "$SHA" "$STAGE" "$APP" "$BK" <<'REMOTE'
set -euo pipefail
SHA=$1; STAGE=$2; APP=$3; BK=$4
TS=$(date +%Y%m%d-%H%M%S)
cd "$APP"
DC="docker compose -f docker-compose.deploy.yml --env-file .env.deploy"
echo "== before: $(cat DEPLOYED_SHA 2>/dev/null || echo unknown), alembic: $($DC exec -T backend alembic current 2>&1 | tail -1)"
count() { $DC exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select (select count(*) from candidates),(select count(*) from employers),(select count(*) from invitations),(select count(*) from employer_needs)"'; }
BEFORE=$(count); echo "== rows before (candidates|employers|invitations|needs): $BEFORE"

echo "== backup"
$DC exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BK/fsp-before-0010-$TS.dump"
[ -s "$BK/fsp-before-0010-$TS.dump" ] || { echo "EMPTY BACKUP - abort"; exit 1; }
tar czf "$BK/code-before-0010-$TS.tgz" --exclude='.env*' -C "$APP" .
ls -la "$BK/fsp-before-0010-$TS.dump" "$BK/code-before-0010-$TS.tgz"

echo "== sync code (keeps .env*, docker-compose.deploy.yml, DEPLOYED_SHA)"
rsync -a --chown=deploy:deploy --exclude='.env*' --exclude='docker-compose.deploy.yml' --exclude=DEPLOYED_SHA "$STAGE"/ "$APP"/

echo "== rebuild backend+frontend only (alembic upgrade head runs at start)"
if ! $DC up -d --build backend frontend; then FAIL=1; fi
ok=0
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8720/health >/dev/null 2>&1 && [ "$($DC exec -T backend alembic current 2>/dev/null | tail -1 | cut -c1-4)" = "0010" ]; then ok=1; break; fi
  sleep 3
done
if [ "$ok" != 1 ] || [ "${FAIL:-0}" = 1 ]; then
  echo "!! health/migration check FAILED - rolling back APP CODE only (schema 0010 is backward compatible, data untouched)"
  find "$APP" -mindepth 1 -maxdepth 1 ! -name '.env*' ! -name docker-compose.deploy.yml -exec rm -rf {} +
  tar xzf "$BK/code-before-0010-$TS.tgz" -C "$APP"
  $DC up -d --build backend frontend
  echo "rolled back; full-data restore (last resort): pg_restore --clean --if-exists from $BK/fsp-before-0010-$TS.dump"
  exit 1
fi
echo "$SHA" > DEPLOYED_SHA
AFTER=$(count); echo "== rows after: $AFTER"
[ "$BEFORE" = "$AFTER" ] || echo "NOTE: row counts differ (live traffic or demo seed); compare manually"
echo "== OK: alembic $($DC exec -T backend alembic current | tail -1), health $(curl -s http://127.0.0.1:8720/health)"
echo "rollback files: $BK/fsp-before-0010-$TS.dump  $BK/code-before-0010-$TS.tgz   (stage dir $STAGE can be deleted)"
REMOTE
echo "== done. Check https://fsp.tradefon.ru in a browser."
