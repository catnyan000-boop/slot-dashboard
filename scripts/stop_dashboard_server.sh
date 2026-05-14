#!/usr/bin/env bash

set -eu

TARGET_PLIST="$HOME/Library/LaunchAgents/com.slot-dashboard.server.plist"

if [ -f "$TARGET_PLIST" ]; then
  launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
  echo "stopped launchd service: com.slot-dashboard.server"
else
  echo "dashboard server launchd plist is not installed: $TARGET_PLIST"
fi
