#!/usr/bin/env bash

set -eu

TARGET_PLIST="$HOME/Library/LaunchAgents/com.slot-dashboard.daily.plist"

if [ -f "$TARGET_PLIST" ]; then
  launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
  rm -f "$TARGET_PLIST"
  echo "removed: $TARGET_PLIST"
else
  echo "not installed: $TARGET_PLIST"
fi
