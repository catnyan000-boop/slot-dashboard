#!/usr/bin/env bash

set -eu

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

pause_if_tty() {
  if [ -t 0 ]; then
    printf "Press Enter to close..."
    read -r _ || true
  fi
}

trap pause_if_tty EXIT

bash "$ROOT_DIR/scripts/uninstall_dashboard_server_launchd.sh"
bash "$ROOT_DIR/scripts/uninstall_launchd.sh"

echo ""
echo "Uninstall complete."
