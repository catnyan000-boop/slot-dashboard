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

bash "$ROOT_DIR/scripts/install_launchd.sh"
bash "$ROOT_DIR/scripts/install_dashboard_server_launchd.sh"

echo ""
echo "Install complete."
echo "Open the dashboard: http://localhost:8765"
