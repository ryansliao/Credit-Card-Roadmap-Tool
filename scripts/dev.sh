#!/usr/bin/env bash
# scripts/dev.sh — run the Credit Card Optimizer locally (API + React dev server)
# Usage: ./scripts/dev.sh [--port 8000]
#
# First-time setup (run once, in order):
#   1. cp .env.example .env && fill in DATABASE_URL
#   2. cd backend && python3 -m app.seed_data
#   3. ./scripts/dev.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

PORT=8000

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ─── 1. Virtual environment ───────────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
  echo "→ Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# ─── 2. Install Python dependencies ──────────────────────────────────────────
echo "→ Checking Python dependencies..."
python3 -m pip install -q -r backend/requirements.txt

# ─── 3. Environment file check ───────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    echo ""
    echo "No .env found. Copy .env.example to .env and fill in DATABASE_URL."
    echo "Then re-run: ./scripts/dev.sh"
    exit 1
  fi
fi

# ─── 4. Install frontend dependencies (if not already installed) ──────────────
if [[ ! -d "frontend/node_modules" ]]; then
  echo "→ Installing frontend dependencies..."
  (cd frontend && npm install)
fi

# ─── 5. Start servers ─────────────────────────────────────────────────────────
echo ""
echo "→ Starting API on http://localhost:${PORT}"
echo "→ Starting React dev server on http://localhost:5173"
echo "   Press Ctrl+C to stop both."
echo ""

# Run FastAPI from backend/ so the `app` package is importable
(cd backend && python3 -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --reload \
  --reload-dir app) &
API_PID=$!

# Run Vite dev server in foreground
(cd frontend && npm run dev)

kill $API_PID 2>/dev/null || true
