#!/bin/bash
# Interdec Platform — start both backend (FastAPI) and frontend (Nuxt)
# Backend: FastAPI + SQLAlchemy + SQLite  ->  http://localhost:8100
# Frontend: Nuxt 3 (SPA)                  ->  http://localhost:3000  (proxies /api to backend)

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Interdec Platform — starting services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ---------- Backend ----------
cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
  echo "[backend] creating venv…"
  python3 -m venv .venv 2>/dev/null || true
fi
echo "[backend] installing deps…"
python3 -m pip install -q fastapi "uvicorn[standard]" sqlalchemy pydantic \
  "python-jose[cryptography]" "passlib[bcrypt]" "bcrypt==4.0.1" python-multipart 2>/dev/null || true

echo "[backend] starting FastAPI on :8100…"
pkill -f "uvicorn app.main" 2>/dev/null
sleep 1
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8100 > "$ROOT/backend.log" 2>&1 &

# ---------- Frontend ----------
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "[frontend] installing deps (first run, ~2 min)…"
  npm install --no-audit --no-fund
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
    echo "   Login: Joshua.n@interdecng.com / 123456  (platform admin)"
    echo "          sales@interdecng.com   / sales123  (sales + user)"
    echo "          viewer@interdecng.com  / viewer123 (reports viewer)"
    exit 0
  fi
done

echo "⚠️  Services taking long — check logs:"
echo "   tail -30 $ROOT/backend.log $ROOT/frontend.log"
