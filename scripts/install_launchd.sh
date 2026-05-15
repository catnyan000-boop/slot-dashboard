#!/usr/bin/env bash

set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_PATH="$ROOT_DIR/launchd/com.slot-dashboard.daily.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/com.slot-dashboard.daily.plist"

mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$ROOT_DIR/logs"

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

launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
launchctl load "$TARGET_PLIST"

echo "installed: $TARGET_PLIST"
echo "loaded label: com.slot-dashboard.daily"
echo "scheduled runs: 02:30 / 04:00 / 05:30"
echo "goal: dashboard refresh completed by 06:00 when the Mac is awake"
echo "manual run: launchctl kickstart -k gui/$(id -u)/com.slot-dashboard.daily"
