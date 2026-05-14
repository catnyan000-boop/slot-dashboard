#!/usr/bin/env bash

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC_DIR="$ROOT_DIR/public"
PORT="8765"
HOST="127.0.0.1"

if [ ! -d "$PUBLIC_DIR" ]; then
  echo "Error: public directory not found: $PUBLIC_DIR" >&2
  exit 1
fi

if [ ! -f "$PUBLIC_DIR/index.html" ]; then
  echo "Error: public/index.html not found. Build the site before starting the dashboard server." >&2
  exit 1
fi

exec python3 - "$PUBLIC_DIR" "$HOST" "$PORT" <<'PY'
from __future__ import annotations

import errno
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

public_dir = Path(sys.argv[1]).resolve()
host = sys.argv[2]
port = int(sys.argv[3])


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(public_dir), **kwargs)


handler = partial(DashboardHandler)

try:
    with ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"dashboard server ready: http://localhost:{port}")
        print(f"serving directory: {public_dir}")
        httpd.serve_forever()
except OSError as exc:
    if exc.errno == errno.EADDRINUSE:
        print(
            f"Error: port {port} is already in use. "
            "Stop the other app using http://localhost:8765 and try again.",
            file=sys.stderr,
        )
    else:
        print(f"Error: dashboard server failed to start: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
