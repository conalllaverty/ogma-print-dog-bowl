#!/usr/bin/env bash
# Start the designer locally: API on :8000, web on :3000.
# Run from anywhere:  bash studio/dev.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="$REPO/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "No venv at .venv — creating one."
  python3 -m venv .venv
  "$REPO/.venv/bin/pip" install -q --upgrade pip
  "$REPO/.venv/bin/pip" install -q -r requirements.txt
fi
# Cheap check that the venv actually has what we need (a venv can exist and be empty).
"$PY" -c "import fastapi, uvicorn, trimesh" 2>/dev/null || {
  echo "Installing Python deps…"; "$REPO/.venv/bin/pip" install -q -r requirements.txt; }

if [ ! -d studio/web/node_modules ]; then
  echo "Installing web deps…"
  (cd studio/web && npm install)
fi

cleanup() { echo; echo "Stopping…"; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "API  → http://127.0.0.1:8000/docs"
( cd "$REPO/studio" && PYTHONPATH="$REPO/studio" "$PY" -m uvicorn api.main:app --reload --port 8000 ) &

# Wait for the API before starting the web app, so the first page load isn't a
# blank picker with a fetch error.
for _ in $(seq 1 40); do
  curl -sf http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1 && break
  sleep 0.5
done

echo "Web  → http://127.0.0.1:3000"
( cd "$REPO/studio/web" && PIPELINE_API_URL=http://127.0.0.1:8000 npm run dev ) &

wait
