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

# Some shells/dev setups export ELECTRON_RUN_AS_NODE=1, which makes the electron
# binary run as plain Node — then require("electron") returns a path string and
# ipcMain/app are undefined (crash at startup). Force it off for the GUI launch.
unset ELECTRON_RUN_AS_NODE

PY313="$(command -v python3.13 || true)"
START_REMOTE=1
[ "${1:-}" = "--no-remote" ] && START_REMOTE=0

# Free a TCP port by killing whatever listens on it (handles orphans from a
# previous run that was hard-killed, e.g. Ctrl-C leaving Django behind).
free_port() {
  local port="$1" pids
  # `|| true` so a no-match grep doesn't trip `set -e`/pipefail when the port is free.
  pids="$(ss -ltnpH "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  if [ -n "$pids" ]; then
    echo "[ports] freeing :$port (killing $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

echo "[ports] checking 8000 / 9000 / 5173..."
free_port 8000
free_port 5173
[ "$START_REMOTE" = "1" ] && free_port 9000

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

cleanup() {
  [ -n "$REMOTE_PID" ] && kill "$REMOTE_PID" 2>/dev/null || true
  # Electron may orphan its spawned Django child on a hard exit; free it too.
  free_port 8000
  [ "$START_REMOTE" = "1" ] && free_port 9000
}
trap cleanup EXIT INT TERM

# --- frontend deps + Electron --------------------------------------------
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[frontend] npm install..."
  ( cd "$ROOT/frontend" && npm install )
fi
echo "[frontend] launching Electron app..."
( cd "$ROOT/frontend" && npm run electron:dev )
