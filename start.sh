#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.codex-venv"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT=5001
FRONTEND_PORT=8000

cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
  echo "Loading local environment from .env..."
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Creating Python environment..."
  python3 -m venv "$VENV_DIR"
fi

echo "Installing backend packages..."
"$VENV_DIR/bin/python" -m pip install -q flask flask-cors requests

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "Stopping existing server on port $port..."
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

cleanup() {
  echo
  echo "Stopping servers..."
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

stop_port "$BACKEND_PORT"
stop_port "$FRONTEND_PORT"

echo "Starting backend: http://127.0.0.1:$BACKEND_PORT"
FLASK_ENV=development "$VENV_DIR/bin/python" backend/score.py &
BACKEND_PID=$!

echo "Starting frontend: http://127.0.0.1:$FRONTEND_PORT/index.html"
python3 -m http.server "$FRONTEND_PORT" --directory "$FRONTEND_DIR" &
FRONTEND_PID=$!

echo
echo "Scoreboard is running:"
echo "  Frontend: http://127.0.0.1:$FRONTEND_PORT/index.html"
echo "  Backend:  http://127.0.0.1:$BACKEND_PORT/score"
echo
echo "Press Ctrl+C to stop both."

wait
