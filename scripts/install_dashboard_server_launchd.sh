#!/usr/bin/env bash

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PATH="$ROOT_DIR/launchd/com.slot-dashboard.server.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/com.slot-dashboard.server.plist"
PORT="8765"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$ROOT_DIR/logs"

launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true

python3 - "$PORT" <<'PY'
from __future__ import annotations

import errno
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(
                f"Error: port {port} is already in use. "
                "Stop the other app using http://localhost:8765 and run the installer again.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        raise
PY

python3 - "$TEMPLATE_PATH" "$TARGET_PLIST" "$ROOT_DIR" <<'PY'
from pathlib import Path
import sys

template_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
project_root = sys.argv[3]

text = template_path.read_text(encoding="utf-8")
text = text.replace("__PROJECT_ROOT__", project_root)
target_path.write_text(text, encoding="utf-8")
PY

launchctl load "$TARGET_PLIST"

echo "installed: $TARGET_PLIST"
echo "loaded label: com.slot-dashboard.server"
echo "site url: http://localhost:8765"
