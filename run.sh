#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -x "backend/.venv/bin/python" ]; then
  python3 -m venv "backend/.venv"
fi
"backend/.venv/bin/python" -m pip install -r "backend/requirements.txt"

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js/npm is required. Install Node.js 20+ and retry." >&2
  exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install)
fi

(cd backend && ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACK_PID=$!
trap 'kill $BACK_PID 2>/dev/null || true' EXIT

cd "$ROOT/frontend"
npm run dev -- --host 127.0.0.1 --port 5173
