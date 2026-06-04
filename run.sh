#!/usr/bin/env bash
# CiXiS dev launcher.
# Starts the optional remote QR-menu server (:9000), then launches the Electron
# desktop app (which itself spawns the local Django backend on :8000).
#
# Usage:
#   ./run.sh            # remote server + Electron app
#   ./run.sh --no-remote
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY313="$(command -v python3.13 || true)"
START_REMOTE=1
[ "${1:-}" = "--no-remote" ] && START_REMOTE=0

# --- backend venv + setup -------------------------------------------------
if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
  echo "[backend] creating venv..."
  ( cd "$ROOT/backend" && "${PY313:-python3}" -m venv .venv && .venv/bin/pip install -q -r requirements.txt )
fi
( cd "$ROOT/backend" && .venv/bin/python manage.py migrate --noinput >/dev/null \
  && .venv/bin/python manage.py init_settings >/dev/null \
  && .venv/bin/python manage.py seed_menu >/dev/null )
echo "[backend] ready (Electron will run it on :8000)"

REMOTE_PID=""
if [ "$START_REMOTE" = "1" ]; then
  if [ ! -x "$ROOT/remote/.venv/bin/python" ]; then
    echo "[remote] creating venv..."
    ( cd "$ROOT/remote" && "${PY313:-python3}" -m venv .venv && .venv/bin/pip install -q -r requirements.txt )
  fi
  ( cd "$ROOT/remote" && .venv/bin/python manage.py migrate --noinput >/dev/null )
  echo "[remote] starting on http://127.0.0.1:9000 (public menu: /menu/cixis-cafe/)"
  ( cd "$ROOT/remote" && CIXIS_API_KEY=dev-cixis-key .venv/bin/python manage.py runserver 127.0.0.1:9000 --noreload ) &
  REMOTE_PID=$!
fi

cleanup() { [ -n "$REMOTE_PID" ] && kill "$REMOTE_PID" 2>/dev/null || true; }
trap cleanup EXIT

# --- frontend deps + Electron --------------------------------------------
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[frontend] npm install..."
  ( cd "$ROOT/frontend" && npm install )
fi
echo "[frontend] launching Electron app..."
( cd "$ROOT/frontend" && npm run electron:dev )
