#!/usr/bin/env bash

set -eu -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PUBLIC_DIR="$ROOT_DIR/public"
PAGES_BRANCH="${PAGES_BRANCH:-gh-pages}"
PAGES_REMOTE="${PAGES_REMOTE:-origin}"
PAGES_REMOTE_URL="${PAGES_REMOTE_URL:-}"
PAGES_DRY_RUN="${PAGES_DRY_RUN:-0}"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/slot-pages-deploy.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

required_files=(
  "index.html"
  "assets/app.js"
  "assets/style.css"
  "data/latest.json"
  "data/targets.json"
)

forbidden_path() {
  case "$1" in
    data/raw|data/raw/*) return 0 ;;
    logs|logs/*) return 0 ;;
    reports|reports/*) return 0 ;;
    *.db|*.sqlite|*.sqlite3|*.log|*.env|*.py|*.pyc) return 0 ;;
    *cookie*|*cookies*) return 0 ;;
  esac
  return 1
}

echo "== validate public output for GitHub Pages =="

if [ ! -d "$PUBLIC_DIR" ]; then
  echo "missing public directory: $PUBLIC_DIR" >&2
  exit 1
fi

for rel_path in "${required_files[@]}"; do
  if [ ! -f "$PUBLIC_DIR/$rel_path" ]; then
    echo "missing required public file: $rel_path" >&2
    exit 1
  fi
done

while IFS= read -r path; do
  rel_path="${path#$PUBLIC_DIR/}"
  if forbidden_path "$rel_path"; then
    echo "forbidden path detected in public/: $rel_path" >&2
    exit 1
  fi
done < <(find "$PUBLIC_DIR" -mindepth 1 -print)

if rg -n --hidden \
  -e 'data/raw' \
  -e 'raw_path' \
  -e 'db_path' \
  -e '\.db\b' \
  -e '/Users/' \
  -e 'sqlite' \
  -e 'cookie' \
  -e 'api[_-]?key' \
  -e 'authorization' \
  "$PUBLIC_DIR" >/dev/null; then
  echo "forbidden content detected in public/" >&2
  rg -n --hidden \
    -e 'data/raw' \
    -e 'raw_path' \
    -e 'db_path' \
    -e '\.db\b' \
    -e '/Users/' \
    -e 'sqlite' \
    -e 'cookie' \
    -e 'api[_-]?key' \
    -e 'authorization' \
    "$PUBLIC_DIR" || true
  exit 1
fi

echo "required files: OK"
echo "forbidden path scan: OK"
echo "forbidden content scan: OK"

DEPLOY_DIR="$TMP_DIR/pages"
mkdir -p "$DEPLOY_DIR"
(cd "$PUBLIC_DIR" && tar cf - .) | (cd "$DEPLOY_DIR" && tar xpf -)
touch "$DEPLOY_DIR/.nojekyll"

if [ "$PAGES_DRY_RUN" = "1" ]; then
  echo "dry run: skipping git push"
  echo "staged public files:"
  find "$DEPLOY_DIR" -type f | sed "s|$DEPLOY_DIR/||" | sort
  exit 0
fi

if [ -z "$PAGES_REMOTE_URL" ]; then
  PAGES_REMOTE_URL="$(git remote get-url "$PAGES_REMOTE" 2>/dev/null || true)"
fi

if [ -z "$PAGES_REMOTE_URL" ]; then
  echo "no git remote configured. Set PAGES_REMOTE_URL or add remote '$PAGES_REMOTE'." >&2
  exit 1
fi

git init -b "$PAGES_BRANCH" "$DEPLOY_DIR" >/dev/null
git -C "$DEPLOY_DIR" config user.name "$(git config user.name || echo 'slot-dashboard bot')"
git -C "$DEPLOY_DIR" config user.email "$(git config user.email || echo 'slot-dashboard@example.invalid')"
git -C "$DEPLOY_DIR" add -A
git -C "$DEPLOY_DIR" commit -m "Deploy dashboard $(date '+%Y-%m-%d %H:%M:%S %z')" >/dev/null
git -C "$DEPLOY_DIR" remote add origin "$PAGES_REMOTE_URL"
git -C "$DEPLOY_DIR" push --force origin "HEAD:$PAGES_BRANCH"

pages_url=""
case "$PAGES_REMOTE_URL" in
  git@github.com:*.git)
    repo_path="${PAGES_REMOTE_URL#git@github.com:}"
    repo_path="${repo_path%.git}"
    owner="${repo_path%%/*}"
    repo="${repo_path#*/}"
    pages_url="https://${owner}.github.io/${repo}/"
    ;;
  https://github.com/*/*.git)
    repo_path="${PAGES_REMOTE_URL#https://github.com/}"
    repo_path="${repo_path%.git}"
    owner="${repo_path%%/*}"
    repo="${repo_path#*/}"
    pages_url="https://${owner}.github.io/${repo}/"
    ;;
esac

echo "deployed branch: $PAGES_BRANCH"
if [ -n "$pages_url" ]; then
  echo "project pages URL: $pages_url"
fi
