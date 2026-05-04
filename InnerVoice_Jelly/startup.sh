#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$SCRIPT_DIR/dist/index.html" ]; then
  export LUNA_STATIC_DIR="$SCRIPT_DIR/dist"
elif [ -f "$APP_ROOT/dist/index.html" ]; then
  export LUNA_STATIC_DIR="$APP_ROOT/dist"
fi

cd "$SCRIPT_DIR"

PORT_TO_USE="${PORT:-8000}"

exec gunicorn \
  -w 1 \
  -k uvicorn.workers.UvicornWorker \
  -b "0.0.0.0:${PORT_TO_USE}" \
  backend:app
