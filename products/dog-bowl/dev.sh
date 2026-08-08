#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r backend/requirements.txt
fi

export APP_ENV=local
export PORT="${PORT:-8000}"
export JOBS_ROOT="$ROOT/data/jobs"
export CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"

# Start API in background
(
  cd backend
  ../.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"
) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

cd web
PIPELINE_API_URL="http://127.0.0.1:$PORT" npm run dev
