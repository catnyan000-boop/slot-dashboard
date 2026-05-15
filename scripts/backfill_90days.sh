#!/usr/bin/env bash

set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
REPORTS_DIR="$ROOT_DIR/reports"
OUT_LOG="$LOG_DIR/backfill_90days.out.log"
ERR_LOG="$LOG_DIR/backfill_90days.err.log"

mkdir -p "$LOG_DIR" "$REPORTS_DIR"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/slot-backfill-90days.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ "${BACKFILL_90DAYS_REDIRECTED:-0}" != "1" ]; then
  export BACKFILL_90DAYS_REDIRECTED=1
  OUT_PIPE="$TMP_DIR/stdout.pipe"
  ERR_PIPE="$TMP_DIR/stderr.pipe"
  mkfifo "$OUT_PIPE" "$ERR_PIPE"
  tee "$OUT_LOG" <"$OUT_PIPE" &
  tee "$ERR_LOG" <"$ERR_PIPE" >&2 &
  exec >"$OUT_PIPE" 2>"$ERR_PIPE"
fi

TARGET_DATE="$(
  python3 - <<'PY'
from datetime import date, timedelta
print((date.today() + timedelta(days=1)).isoformat())
PY
)"

export PYTHONWARNINGS="ignore:urllib3 v2 only supports OpenSSL 1.1.1+"
SOURCE="slorepo"
DAYS=90
SLEEP_SECONDS=2.0

display_name() {
  case "$1" in
    cosmo_obu) echo "コスモジャパン大府" ;;
    marushin_777) echo "マルシン777" ;;
    apan_kobo) echo "APANCLUB弘法通り" ;;
    keiz_galerie_apita) echo "KEIZギャラリエアピタ" ;;
    *) echo "$1" ;;
  esac
}

STORES=(
  "cosmo_obu"
  "marushin_777"
  "apan_kobo"
  "keiz_galerie_apita"
)

FETCH_STATUS_TSV="$TMP_DIR/fetch_statuses.tsv"
PARSE_STATUS_TSV="$TMP_DIR/parse_statuses.tsv"
>"$FETCH_STATUS_TSV"
>"$PARSE_STATUS_TSV"

echo "== slorepo 90-day backfill =="
echo "target_date: $TARGET_DATE"
echo "source: $SOURCE"
echo "days: $DAYS"
echo "stores: ${STORES[*]}"
echo ""

echo "== fetch-slorepo (per store keep-going mode, days=${DAYS}, source=${SOURCE}) =="
for index in "${!STORES[@]}"; do
  store_id="${STORES[$index]}"
  store_name="$(display_name "$store_id")"
  log_path="$TMP_DIR/fetch_${store_id}.log"
  raw_dir="$ROOT_DIR/data/raw/slorepo/$store_id"
  raw_count=0
  fetch_status=""
  fetch_note=""
  failed_machine_pages="0"

  if [ -d "$raw_dir" ]; then
    raw_count="$(find "$raw_dir" -maxdepth 1 -type f | wc -l | tr -d ' ')"
  fi

  if python3 -m src.cli fetch-slorepo --store "$store_id" --days "$DAYS" --sleep "$SLEEP_SECONDS" >"$log_path" 2>&1; then
    summary_line="$(grep "^${store_id}: status=" "$log_path" | tail -n 1 || true)"
    if [ -n "$summary_line" ]; then
      fetch_status="$(printf '%s\n' "$summary_line" | sed -E 's/.*status=([^ ]+).*/\1/')"
      failed_machine_pages="$(printf '%s\n' "$summary_line" | sed -E 's/.*failed_machine_pages=([0-9]+).*/\1/')"
    else
      fetch_status="success"
    fi
    if [ "$fetch_status" = "partial_success" ]; then
      fetch_note="一部機種ページ取得失敗: ${failed_machine_pages}件"
    else
      fetch_note="最新取得に成功"
    fi
  else
    fetch_status="failed"
    if [ "$raw_count" -gt 0 ]; then
      fetch_note="fetch失敗のため既存rawを継続利用"
    else
      fetch_note="fetch失敗で利用可能なrawなし"
    fi
    tail -n 10 "$log_path" || true
  fi

  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$store_id" "$store_name" "$fetch_status" "$failed_machine_pages" "$fetch_note" \
    >>"$FETCH_STATUS_TSV"
  echo "${store_id}: ${fetch_status} (${fetch_note})"

  if [ "$index" -lt $((${#STORES[@]} - 1)) ]; then
    sleep "$SLEEP_SECONDS"
  fi
done

echo ""
echo "== parse-slorepo (per store keep-going mode, days=${DAYS}, source=${SOURCE}) =="
for store_id in "${STORES[@]}"; do
  store_name="$(display_name "$store_id")"
  log_path="$TMP_DIR/parse_${store_id}.log"
  parse_status="failed"
  daily_count="0"
  machine_count="0"
  unit_count="0"
  parse_note=""

  if python3 -m src.cli parse-slorepo --store "$store_id" --days "$DAYS" >"$log_path" 2>&1; then
    summary_line="$(grep "^${store_id}: daily=" "$log_path" | tail -n 1 || true)"
    if [ -n "$summary_line" ]; then
      parse_status="success"
      daily_count="$(printf '%s\n' "$summary_line" | sed -E 's/.*daily=([0-9]+).*/\1/')"
      machine_count="$(printf '%s\n' "$summary_line" | sed -E 's/.*machine=([0-9]+).*/\1/')"
      unit_count="$(printf '%s\n' "$summary_line" | sed -E 's/.*unit=([0-9]+).*/\1/')"
      parse_note="DB保存まで完了"
    elif grep -q "no slorepo raw HTML files" "$log_path"; then
      parse_status="failed"
      parse_note="parse対象rawなし"
    else
      parse_note="parse出力を要確認"
    fi
  else
    parse_note="parseコマンド失敗"
    tail -n 10 "$log_path" || true
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$store_id" "$store_name" "$parse_status" "$daily_count" "$machine_count" "$unit_count" "$parse_note" \
    >>"$PARSE_STATUS_TSV"
  echo "${store_id}: ${parse_status} daily=${daily_count} machine=${machine_count} unit=${unit_count}"
done

echo ""
echo "== fetch / parse summary =="
while IFS=$'\t' read -r store_id store_name fetch_status failed_machine_pages fetch_note; do
  parse_line="$(grep "^${store_id}" "$PARSE_STATUS_TSV" || true)"
  parse_status="$(printf '%s\n' "$parse_line" | cut -f3)"
  daily_count="$(printf '%s\n' "$parse_line" | cut -f4)"
  machine_count="$(printf '%s\n' "$parse_line" | cut -f5)"
  unit_count="$(printf '%s\n' "$parse_line" | cut -f6)"
  echo "- ${store_name}: fetch=${fetch_status}, failed_machine_pages=${failed_machine_pages}, parse=${parse_status}, daily=${daily_count}, machine=${machine_count}, unit=${unit_count}"
done <"$FETCH_STATUS_TSV"

echo ""
echo "== analyze-targets --date ${TARGET_DATE} --days ${DAYS} --source ${SOURCE} =="
ANALYZE_LOG="$TMP_DIR/analyze_targets.log"
if python3 -m src.cli analyze-targets --date "$TARGET_DATE" --days "$DAYS" --source "$SOURCE" >"$ANALYZE_LOG" 2>&1; then
  cat "$ANALYZE_LOG"
else
  cat "$ANALYZE_LOG"
  echo "analyze-targets failed"
fi

echo ""
echo "== build-site --date ${TARGET_DATE} --days 7 --source ${SOURCE} =="
BUILD_LOG="$TMP_DIR/build_site.log"
if python3 -m src.cli build-site --date "$TARGET_DATE" --days 7 --source "$SOURCE" >"$BUILD_LOG" 2>&1; then
  cat "$BUILD_LOG"
else
  cat "$BUILD_LOG"
  echo "build-site failed"
fi

echo ""
echo "backfill complete"
echo "stdout log: $OUT_LOG"
echo "stderr log: $ERR_LOG"
