#!/usr/bin/env bash
# Start backend (FastAPI) and frontend (Vite) together for local dev.
# Usage: ./run.sh   — Ctrl-C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$ROOT/backend/.env" ]; then
  echo "!! backend/.env missing — copy backend/.env.example and add GEMINI_API_KEY" >&2
  exit 1
fi

# 8100 by default — port 8000 is often taken by other tooling in this env.
BACKEND_PORT="${BACKEND_PORT:-8100}"

echo "▶ backend  → http://localhost:${BACKEND_PORT}"
( cd "$ROOT/backend" && uvicorn app.main:app --reload --port "$BACKEND_PORT" ) &
BACK=$!

echo "▶ frontend → http://localhost:5173"
export VITE_BACKEND="http://localhost:${BACKEND_PORT}"
( cd "$ROOT/frontend" && npm run dev ) &
FRONT=$!

trap 'echo; echo "stopping…"; kill $BACK $FRONT 2>/dev/null || true' INT TERM
wait
