#!/usr/bin/env bash
# Safe update of the EXISTING FSP VPS deployment (migration 0010). Run from the Mac, repo root:
#   DEPLOY_PREFLIGHT=1 ./scripts/deploy-vps.sh      # read-only checks on the server, changes nothing
#   DEPLOY_CONFIRM=yes ./scripts/deploy-vps.sh      # real deploy
# Source = `git archive HEAD` (tracked files only), delivered by rsync. Touches only the compose project
# `fsp-talent-market` in /opt/fsp-talent-market. Never `down`, never volumes, never `demo reset`, never
# a bulk delete. Runs as root over SSH because .env.deploy is root-only (0600).
set -Eeuo pipefail
HOST="${FSP_SSH_HOST:-marakand-prod}"          # root on the same machine as hermes-prod-nl
APP=/opt/fsp-talent-market
BK=/opt/fsp-backups
PROJECT=fsp-talent-market
BRANCH=hardening/mvp-2026-10-10
cd "$(dirname "$0")/.."
SHA="$(git rev-parse --short HEAD)"
MODE=deploy
if [ "${DEPLOY_PREFLIGHT:-}" = "1" ]; then MODE=preflight
elif [ "${DEPLOY_CONFIRM:-}" != "yes" ]; then echo "Set DEPLOY_PREFLIGHT=1 (read-only) or DEPLOY_CONFIRM=yes to deploy $SHA to $HOST:$APP"; exit 2; fi

if [ "$MODE" = deploy ]; then
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked files are modified; commit first"; exit 2; }
  git fetch -q origin
  [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ] || { echo "HEAD is not pushed to origin/$BRANCH"; exit 2; }
  STAGE="/opt/fsp-release-$SHA"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  git archive HEAD | tar -x -C "$TMP"
  [ -f "$TMP/docker-compose.deploy.yml" ] && [ -d "$TMP/src/fsp_market/migrations/versions" ] || { echo "archive looks wrong"; exit 2; }
  echo "== sending $SHA to $HOST:$STAGE"
  rsync -a --delete "$TMP"/ "$HOST:$STAGE/"
fi
echo "== mode=$MODE sha=$SHA host=$HOST"

# The remote script is stored in a temp file first: docker/pg tools would otherwise swallow the script from stdin.
ssh "$HOST" "f=\$(mktemp /tmp/fsp-deploy-XXXXXX.sh) && cat > \"\$f\" && { bash \"\$f\" $MODE $SHA ${STAGE:--} $APP $BK $PROJECT; rc=\$?; rm -f \"\$f\"; exit \$rc; }" <<'REMOTE'
set -Eeuo pipefail
MODE=$1; SHA=$2; STAGE=$3; APP=$4; BK=$5; PROJECT=$6
TS=$(date +%Y%m%d-%H%M%S)
fail() { echo "!! $*" >&2; exit 1; }
trap 'echo "!! failed at line $LINENO (exit $?)" >&2' ERR

# ---- preflight (read-only) -------------------------------------------------------------------
[ "$(id -u)" = 0 ] || fail "must run as root"
exec 9>/var/lock/fsp-deploy.lock; flock -n 9 || fail "another FSP deploy is running"
command -v rsync >/dev/null && command -v docker >/dev/null || fail "rsync/docker missing"
[ -d "$APP" ] && [ -f "$APP/docker-compose.deploy.yml" ] || fail "$APP or its docker-compose.deploy.yml missing"
[ -f "$APP/.env.deploy" ] || fail ".env.deploy missing"
ENV_SUM=$(sha256sum "$APP/.env.deploy" | cut -d' ' -f1)
ENV_STAT=$(stat -c '%U:%G %a' "$APP/.env.deploy")
[ -d "$BK" ] && [ -w "$BK" ] || fail "backup dir $BK missing or not writable"
FREE_KB=$(df --output=avail -k "$BK" | tail -1)
[ "$FREE_KB" -gt 2097152 ] || fail "less than 2 GiB free for backups"
cd "$APP"
DC="docker compose -p $PROJECT -f docker-compose.deploy.yml --env-file .env.deploy"
SERVICES=$($DC config --services | sort | tr '\n' ' ')
[ "$SERVICES" = "backend db frontend " ] || fail "unexpected compose services: $SERVICES"
for s in db backend frontend; do
  [ -n "$($DC ps -q $s)" ] || fail "service $s is not running in project $PROJECT"
done
PREV_SHA=$(cat DEPLOYED_SHA 2>/dev/null || echo unknown)
PREV_ALEMBIC=$($DC exec -T backend alembic current 2>&1 | tail -1)
count() { $DC exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select (select count(*) from candidates),(select count(*) from employers),(select count(*) from invitations),(select count(*) from employer_needs)"'; }
BEFORE=$(count)
echo "== deployed=$PREV_SHA alembic='$PREV_ALEMBIC' rows(cand|emp|inv|needs)=$BEFORE free=$((FREE_KB/1024))MiB"
echo "== services: $SERVICES env=$ENV_STAT"

# dump -> pg_restore --list (validates the custom-format archive and its table of contents)
check_dump_stream() {
  local n
  n=$($DC exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
      | $DC exec -T db sh -c 'pg_restore --list' | grep -c 'TABLE DATA') || true
  [ "${n:-0}" -ge 10 ] || fail "pg_dump stream check failed (TABLE DATA entries: ${n:-0})"
  echo "== pg_dump stream OK ($n tables with data)"
}
if [ "$MODE" = preflight ]; then
  check_dump_stream
  echo "== PREFLIGHT OK (nothing was changed)"; exit 0
fi

# ---- backup ------------------------------------------------------------------------------------
[ -d "$STAGE/src/fsp_market/migrations/versions" ] || fail "stage $STAGE is incomplete"
DUMP="$BK/fsp-before-0010-$TS.dump"; CODE="$BK/code-before-0010-$TS.tgz"
$DC exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DUMP.part"
[ -s "$DUMP.part" ] || fail "empty database backup"
N=$($DC exec -T db sh -c 'pg_restore --list' < "$DUMP.part" | grep -c 'TABLE DATA') || true
[ "${N:-0}" -ge 10 ] || fail "backup is not a valid pg_dump archive (TABLE DATA entries: ${N:-0})"
mv "$DUMP.part" "$DUMP"; chmod 600 "$DUMP"
tar czf "$CODE.part" --exclude='.env*' -C "$APP" .
# grep -c (not -q): -q exits early, tar then gets SIGPIPE and pipefail reports a false failure
M=$(tar tzf "$CODE.part" | grep -c 'src/fsp_market/migrations/versions/.*\.py$') || true
[ "${M:-0}" -ge 9 ] || fail "code backup lacks migrations (found ${M:-0})"
mv "$CODE.part" "$CODE"
sha256sum "$DUMP" "$CODE" > "$BK/fsp-before-0010-$TS.sha256"
ls -la "$DUMP" "$CODE"

# ---- release -----------------------------------------------------------------------------------
sync_code() {  # $1 = source dir; additive only (no --delete); env, compose file and DEPLOYED_SHA are never touched
  rsync -a --chown=deploy:deploy --exclude='.env*' --exclude='docker-compose.deploy.yml' --exclude=DEPLOYED_SHA "$1"/ "$APP"/
}
healthy() {  # backend answers and DB is at 0010
  for _ in $(seq 1 40); do
    if curl -fsS http://127.0.0.1:8720/health >/dev/null 2>&1 \
       && [ "$($DC exec -T backend alembic current 2>/dev/null | tail -1 | cut -c1-4)" = "0010" ]; then return 0; fi
    sleep 3
  done
  return 1
}
rollback() {
  echo "!! rolling back APP CODE only (schema stays at 0010 - old code works with it; data untouched; no files deleted)"
  local prev; prev=$(mktemp -d /opt/fsp-rollback-XXXXXX)
  tar xzf "$CODE" -C "$prev"
  sync_code "$prev"
  rm -rf -- "${prev:?}"      # our own mktemp dir only
  $DC up -d --build --no-deps backend frontend || true
  curl -fsS http://127.0.0.1:8720/health >/dev/null 2>&1 && echo "== rollback: health OK" || echo "!! rollback: health still failing - restore manually from $DUMP"
  echo "   last-resort data restore: $DC exec -T db sh -c 'pg_restore --clean --if-exists -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"' < $DUMP"
}
sync_code "$STAGE"
if ! { $DC up -d --build --no-deps backend frontend && healthy; }; then rollback; exit 1; fi

# ---- verify ------------------------------------------------------------------------------------
[ "$(sha256sum "$APP/.env.deploy" | cut -d' ' -f1)" = "$ENV_SUM" ] && [ "$(stat -c '%U:%G %a' "$APP/.env.deploy")" = "$ENV_STAT" ] \
  || echo "!! WARNING: .env.deploy changed - investigate"
echo "$SHA" > DEPLOYED_SHA
AFTER=$(count)
echo "== rows after: $AFTER (before: $BEFORE)"
echo "== OK: sha=$SHA alembic=$($DC exec -T backend alembic current | tail -1) health=$(curl -s http://127.0.0.1:8720/health)"
echo "== backups: $DUMP  $CODE  (+ .sha256). Stage dir $STAGE may be deleted manually."
REMOTE
echo "== done ($MODE)"
