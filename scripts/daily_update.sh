#!/usr/bin/env bash

set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

REPORTS_DIR="$ROOT_DIR/reports"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/slot-daily-update.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$REPORTS_DIR"

TOMORROW="$(
  python3 - <<'PY'
from datetime import date, timedelta
print((date.today() + timedelta(days=1)).isoformat())
PY
)"

export PYTHONWARNINGS="ignore:urllib3 v2 only supports OpenSSL 1.1.1+"

STORES_TSV="$TMP_DIR/stores.tsv"
python3 - >"$STORES_TSV" <<'PY'
from pathlib import Path
from src.normalizers.store_normalizer import StoreNormalizer

catalog = StoreNormalizer.from_yaml(Path("stores.yaml"))
for store in catalog.list_stores():
    print(f"{store.store_id}\t{store.display_name}")
PY

FETCH_STATUS_TSV="$TMP_DIR/fetch_statuses.tsv"

echo "== fetch-minrepo (per store keep-going mode, days=7) =="
>"$FETCH_STATUS_TSV"
while IFS=$'\t' read -r store_id display_name; do
  log_path="$TMP_DIR/fetch_${store_id}.log"
  raw_dir="$ROOT_DIR/data/raw/minrepo/$store_id"
  raw_count=0
  fetch_status=""
  fetch_note=""
  if [ -d "$raw_dir" ]; then
    raw_count="$(find "$raw_dir" -maxdepth 1 -type f | wc -l | tr -d ' ')"
  fi

  if python3 -m src.cli fetch-minrepo --store "$store_id" --days 7 >"$log_path" 2>&1; then
    fetch_status="成功"
    fetch_note="最新取得に成功"
  else
    if [ "$raw_count" -gt 0 ]; then
      fetch_status="失敗（前回データ使用）"
      fetch_note="fetch失敗のため既存rawを継続利用"
    else
      fetch_status="失敗"
      fetch_note="fetch失敗で利用可能なrawなし"
    fi
  fi

  printf '%s\t%s\t%s\t%s\n' "$store_id" "$display_name" "$fetch_status" "$fetch_note" >>"$FETCH_STATUS_TSV"
  echo "${store_id}: ${fetch_status}"
done <"$STORES_TSV"

echo ""
echo "== parse-minrepo --all =="
PARSE_ALL_LOG="$TMP_DIR/parse_all.log"
PARSE_ALL_STATUS="成功"
if ! python3 -m src.cli parse-minrepo --all >"$PARSE_ALL_LOG" 2>&1; then
  PARSE_ALL_STATUS="失敗"
fi
echo "parse_all: $PARSE_ALL_STATUS"

echo ""
echo "== unit-coverage --all --days 7 =="
python3 -m src.cli unit-coverage --all --days 7 >"$TMP_DIR/unit_coverage_all_7days.txt" 2>&1 || true

echo ""
echo "== summarize validation report =="
python3 - "$REPORTS_DIR/unit_coverage_9stores_7days.md" "$FETCH_STATUS_TSV" <<'PY'
from datetime import date
from pathlib import Path
import sys

from src.analysis.unit_data_quality import summarize_unit_data_quality
from src.cli import DB_PATH
from src.db.database import Database

output_path = Path(sys.argv[1])
status_tsv_path = Path(sys.argv[2])
database = Database(DB_PATH)
stores: list[tuple[str, str, str, str]] = []
for line in status_tsv_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    store_id, display_name, fetch_status, fetch_note = line.split("\t", 3)
    stores.append((store_id, display_name, fetch_status, fetch_note))

cutoff = (date.today()).fromordinal(date.today().toordinal() - 7).isoformat()
today_text = date.today().isoformat()
lines = [
    "# Unit Coverage Validation (9 stores / 7 days)",
    "",
    f"最終更新日: {today_text}",
    "対象期間は直近7日です。",
    "",
]

for store_id, display_name, fetch_status, fetch_note in stores:
    unit_df = database.query_dataframe(
        "SELECT * FROM unit_results WHERE store_id = ? AND report_date >= ?",
        [store_id, cutoff],
    )
    quality = summarize_unit_data_quality(unit_df, store_id)
    parse_status = "成功" if int(quality["total_rows"]) > 0 else "失敗"

    notes = []
    if fetch_note:
        notes.append(fetch_note)
    if parse_status != "成功":
        notes.append("parse済み unit_results が不足")
    if int(quality["total_rows"]) == 0:
        notes.append("unit_results が 0 でデータ不足")
    if float(quality["diff_missing_rate"]) >= 0.5:
        notes.append("diff欠損率50%以上のため台番・末尾・並び分析は信頼不可")
    if not notes:
        notes.append("大きな追加注意なし")

    excluded = quality["excluded_machines"][:10]
    excluded_text = "なし"
    if excluded:
        excluded_text = "; ".join(
            f"{row['machine_name']} ({row['reason']})"
            for row in excluded
        )

    lines.extend(
        [
            f"## {display_name}",
            "",
            f"- 取得: {fetch_status}",
            f"- parse: {parse_status}",
            f"- unit_results_total: {quality['total_rows']}",
            f"- diff_null_count: {quality['diff_null_count']}",
            f"- unit_diff_missing_rate: {quality['diff_missing_rate']}",
            f"- 台番分析ステータス: {quality['pattern_analysis_status']}",
            f"- 末尾分析ステータス: {quality['tail_analysis_status']}",
            f"- 並び分析ステータス: {quality['cluster_analysis_status']}",
            f"- 有効分析範囲: {', '.join(quality['effective_analyses'])}",
            f"- 除外対象機種: {excluded_text}",
            f"- 注意点: {' / '.join(notes)}",
            "",
        ]
    )

output_path.write_text("\n".join(lines), encoding="utf-8")
print(output_path)
PY

echo ""
echo "== report-tomorrow --date ${TOMORROW} --days 7 =="
if ! python3 -m src.cli report-tomorrow --date "$TOMORROW" --days 7 >"$TMP_DIR/report_tomorrow.log" 2>&1; then
  cat "$TMP_DIR/report_tomorrow.log"
fi

echo ""
echo "== build-site --date ${TOMORROW} --days 7 =="
if ! python3 -m src.cli build-site --date "$TOMORROW" --days 7 >"$TMP_DIR/build_site.log" 2>&1; then
  cat "$TMP_DIR/build_site.log"
  exit 1
fi
cat "$TMP_DIR/build_site.log"

echo ""
echo "daily update complete"
