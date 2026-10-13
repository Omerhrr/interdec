#!/bin/bash
# Interdec Platform — start both backend (FastAPI) and frontend (Nuxt)
# Backend: FastAPI + SQLAlchemy + SQLite  ->  http://localhost:8100
# Frontend: Nuxt 3 (SPA)                  ->  http://localhost:3000  (proxies /api to backend)

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Interdec Platform — starting services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ---------- Backend ----------
cd "$ROOT/backend" || exit 1
PY_SYS="$(command -v python3 || command -v python)"
if [ -z "$PY_SYS" ]; then echo "❌ Python 3 not found"; exit 1; fi
if [ ! -d ".venv" ]; then
  echo "[backend] creating venv…"
  "$PY_SYS" -m venv .venv || { echo "❌ could not create venv"; exit 1; }
fi
# Use the venv's interpreter (Linux/macOS: bin/, Windows Git Bash: Scripts/)
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY=".venv/Scripts/python.exe"; fi

echo "[backend] installing deps…"
"$PY" -m pip install -q -r "$ROOT/requirements.txt" || { echo "❌ pip install failed"; exit 1; }

echo "[backend] starting FastAPI on :8100…"
pkill -f "uvicorn app.main" 2>/dev/null
sleep 1
nohup "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8100 > "$ROOT/backend.log" 2>&1 &

# ---------- Frontend ----------
cd "$ROOT/frontend" || exit 1
if [ ! -d "node_modules" ]; then
  echo "[frontend] installing deps (first run, ~2 min)…"
  npm install --no-audit --no-fund || { echo "❌ npm install failed"; exit 1; }
fi

echo "[frontend] starting Nuxt on :3000…"
pkill -f "nuxt dev" 2>/dev/null
sleep 1
nohup npx nuxt dev --port 3000 --host 0.0.0.0 > "$ROOT/frontend.log" 2>&1 &

echo ""
echo "⏳ waiting for services…"
for i in $(seq 1 45); do
  sleep 2
  BE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/api/health 2>/dev/null)
  FE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null)
  if [ "$BE" = "200" ] && [ "$FE" = "200" ]; then
    echo ""
    echo "✅ All services up!"
    echo "   • App:       http://localhost:3000"
    echo "   • API:       http://localhost:8100/api/health"
    echo "   • API docs:  http://localhost:8100/docs"
    echo ""
    echo "   Demo logins are listed in README.md — change these passwords before real use."
    exit 0
  fi
done

echo "⚠️  Services taking long — check logs:"
echo "   tail -30 $ROOT/backend.log $ROOT/frontend.log"
