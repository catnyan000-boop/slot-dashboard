#!/usr/bin/env bash

set -eu

TARGET_PLIST="$HOME/Library/LaunchAgents/com.slot-dashboard.daily.plist"

if [ -f "$TARGET_PLIST" ]; then
  launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
  rm -f "$TARGET_PLIST"
  echo "removed: $TARGET_PLIST"
  echo "removed schedule: 02:30 / 04:00 / 05:30"
else
  echo "not installed: $TARGET_PLIST"
fi
