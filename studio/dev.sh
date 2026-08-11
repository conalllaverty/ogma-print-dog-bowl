#!/usr/bin/env bash
# Start the designer locally: API on :8000, web on :3000.
# Run from anywhere:  bash studio/dev.sh   (or: make dev)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

WEB="$REPO/studio/web"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

# --------------------------------------------------------------------------
# A stale port is worse than a busy one.
#
# `next dev` politely moves to 3001 when 3000 is taken, which sounds helpful and
# is not: the tab you already have open keeps talking to whatever old build is
# still squatting on 3000, and you debug a version of the code that no longer
# exists. Refuse to start instead, and say which process to kill.
# --------------------------------------------------------------------------
port_owner() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null | head -1
  elif command -v fuser >/dev/null 2>&1; then
    fuser "$1/tcp" 2>/dev/null | tr -d ' ' | head -1
  fi
}

for port_var in API_PORT WEB_PORT; do
  port="${!port_var}"
  pid="$(port_owner "$port" || true)"
  if [ -n "$pid" ]; then
    name="$(ps -p "$pid" -o comm= 2>/dev/null || echo '?')"
    echo "Port $port is already in use by pid $pid ($name)."
    echo "  Stop it first:  kill $pid"
    echo "  Or run on another port:  ${port_var}=$((port + 10)) bash studio/dev.sh"
    exit 1
  fi
done

# --------------------------------------------------------------------------
# Dependencies.
#
# The check is "are the installed deps older than the manifest", NOT "does
# node_modules exist". Those differ exactly when a dependency has been *added*
# since the last install — which is how adding `three` produced a build error
# on a machine that already had node_modules. npm writes
# node_modules/.package-lock.json on every install, so its mtime is the honest
# record of when the tree last matched the manifest.
# --------------------------------------------------------------------------
PY="$REPO/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "No venv at .venv — creating one."
  python3 -m venv .venv
  "$REPO/.venv/bin/pip" install -q --upgrade pip
fi

needs_pip=0
"$PY" -c "import fastapi, uvicorn, trimesh, shapely, manifold3d" 2>/dev/null || needs_pip=1
if [ "$REPO/requirements.txt" -nt "$REPO/.venv/pyvenv.cfg" ]; then needs_pip=1; fi
if [ "$needs_pip" = 1 ]; then
  echo "Installing Python deps…"
  "$REPO/.venv/bin/pip" install -q -r requirements.txt
  touch "$REPO/.venv/pyvenv.cfg"
fi

STAMP="$WEB/node_modules/.package-lock.json"
if [ ! -e "$STAMP" ] || [ "$WEB/package.json" -nt "$STAMP" ] || [ "$WEB/package-lock.json" -nt "$STAMP" ]; then
  echo "Installing web deps…"
  (cd "$WEB" && npm install)
fi

# No phone-home from a local dev server.
export NEXT_TELEMETRY_DISABLED=1

cleanup() { echo; echo "Stopping…"; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "API  → http://127.0.0.1:$API_PORT/docs"
( cd "$REPO/studio" && PYTHONPATH="$REPO/studio" "$PY" -m uvicorn api.main:app --reload --port "$API_PORT" ) &

# Wait for the API before starting the web app, so the first page load isn't a
# blank picker with a fetch error.
for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.5
done

echo "Web  → http://127.0.0.1:$WEB_PORT"
( cd "$WEB" && PIPELINE_API_URL="http://127.0.0.1:$API_PORT" npm run dev -- --port "$WEB_PORT" ) &

wait
