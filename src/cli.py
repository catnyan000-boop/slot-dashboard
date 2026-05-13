from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from src.analysis.unit_data_quality import summarize_unit_data_quality
from src.collectors.unit_detail_filler import (
    fill_missing_unit_details,
    list_missing_unit_rows,
)
from src.db.database import Database
from src.normalizers.store_normalizer import StoreNormalizer
from src.parsers.minrepo_parser import MinrepoParser
from src.reports.tomorrow_report import generate_tomorrow_report, run_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "slot.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
STORES_PATH = PROJECT_ROOT / "stores.yaml"
REPORTS_DIR = PROJECT_ROOT / "reports"


def _database() -> Database:
    return Database(DB_PATH)


def _store_normalizer() -> StoreNormalizer:
    return StoreNormalizer.from_yaml(STORES_PATH)


def _date_cutoff(days: int) -> date:
    return date.today() - timedelta(days=days)


def _raw_store_dir(store_id: str) -> Path:
    return RAW_DIR / "minrepo" / store_id


def _list_recent_raw_files(store_id: str, days: int) -> list[Path]:
    cutoff = _date_cutoff(days)
    files: list[Path] = []
    for path in sorted(_raw_store_dir(store_id).glob("*.html")):
        try:
            report_date = date.fromisoformat(path.name[:10])
        except ValueError:
            continue
        if report_date >= cutoff:
            files.append(path)
    return files


def cmd_init_db(_: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    database.seed_stores(_store_normalizer().catalog)
    print(f"initialized db: {DB_PATH}")
    return 0


def cmd_stores(_: argparse.Namespace) -> int:
    normalizer = _store_normalizer()
    for store in normalizer.list_stores():
        event_days = ",".join(store.event_days)
        print(f"{store.store_id}\t{store.display_name}\t{store.canonical_name}\t{event_days}")
    return 0


def _resolve_target_stores(args: argparse.Namespace, normalizer: StoreNormalizer):
    if args.all:
        return normalizer.list_stores()
    store = normalizer.get_by_store_id(args.store) if args.store else None
    if store is None and args.store:
        store = normalizer.resolve(args.store)
    if store is None:
        raise SystemExit("--store か --all を指定してください")
    return [store]


def cmd_fetch_minrepo(args: argparse.Namespace) -> int:
    from src.collectors.minrepo_collector import MinrepoCollector

    database = _database()
    database.initialize(SCHEMA_PATH)
    database.seed_stores(_store_normalizer().catalog)

    normalizer = _store_normalizer()
    collector = MinrepoCollector(
        raw_root=RAW_DIR,
        base_url="https://min-repo.com",
    )
    total_pages = 0
    for store in _resolve_target_stores(args, normalizer):
        pages = collector.fetch_store_history(store, days=args.days)
        for page in pages:
            database.upsert_source_page(page.record)
        total_pages += len(pages)
        print(f"{store.store_id}: fetched {len(pages)} pages")
    print(f"total fetched pages: {total_pages}")
    return 0


def cmd_parse_minrepo(args: argparse.Namespace) -> int:
    database = _database()
    parser = MinrepoParser()
    normalizer = _store_normalizer()
    store_ids = [store.store_id for store in _resolve_target_stores(args, normalizer)]
    pages = database.list_source_pages("minrepo", store_ids=store_ids)
    if not pages:
        print("no source_pages found for minrepo")
        return 0

    parsed_count = 0
    warnings_count = 0
    for page in pages:
        raw_path = Path(page["raw_path"])
        if not raw_path.exists():
            continue
        html = raw_path.read_text(encoding="utf-8")
        url = page["url"]
        store_id = page["store_id"]
        if url.endswith("?kishu=all") or raw_path.name.endswith("_units.html"):
            unit_records = parser.parse_unit_page(html=html, store_id=store_id, source_url=url)
            database.upsert_unit_results(unit_records)
            parsed_count += len(unit_records)
            if not unit_records:
                warnings_count += 1
                print(f"warning: unit_results=0 for {store_id} {url}")
        else:
            daily_record, machine_records = parser.parse_detail_page(
                html=html,
                store_id=store_id,
                source_url=url,
            )
            database.upsert_daily_store_result(daily_record)
            database.upsert_machine_results(machine_records)
            parsed_count += 1 + len(machine_records)
    print(f"parsed records: {parsed_count}")
    print(f"warnings: {warnings_count}")
    return 0


def cmd_analyze_stores(args: argparse.Namespace) -> int:
    database = _database()
    target_date = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1)
    result = run_analysis(
        database,
        _store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
    )
    print(f"analysis run_id: {result['run_id']}")
    for row in result["rows"][:9]:
        print(
            f"{row['rank']}\t{row['display_name']}\tscore={row['score']}\t"
            f"confidence={row['confidence']}\tsamples={row['sample_size']}"
        )
    return 0


def cmd_report_tomorrow(args: argparse.Namespace) -> int:
    database = _database()
    target_date = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1)
    report_path = generate_tomorrow_report(
        database=database,
        store_normalizer=_store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
        output_dir=REPORTS_DIR,
    )
    print(report_path)
    return 0


def cmd_db_stats(_: argparse.Namespace) -> int:
    counts = _database().table_counts()
    for key, value in counts.items():
        print(f"{key}: {value}")
    return 0


def cmd_show_store_data(args: argparse.Namespace) -> int:
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    frame = _database().query_dataframe(
        """
        SELECT
            d.report_date,
            d.total_diff,
            d.avg_diff,
            d.avg_game,
            d.total_units,
            COUNT(DISTINCT m.machine_name_normalized) AS machines
        FROM daily_store_results d
        LEFT JOIN machine_results m
            ON d.source = m.source
           AND d.store_id = m.store_id
           AND d.report_date = m.report_date
        WHERE d.store_id = ?
          AND d.report_date >= date('now', ?)
        GROUP BY d.report_date, d.total_diff, d.avg_diff, d.avg_game, d.total_units
        ORDER BY d.report_date DESC
        """,
        [store.store_id, f"-{args.days} days"],
    )
    if frame.empty:
        print("no rows")
        return 0
    for _, row in frame.iterrows():
        print(
            f"{row['report_date']}\t{row['total_diff']}\t{row['avg_diff']}\t"
            f"{row['avg_game']}\t{row['total_units']}\t{row['machines']}"
        )
    return 0


def cmd_sample_units(args: argparse.Namespace) -> int:
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    frame = _database().query_dataframe(
        """
        SELECT report_date, unit_number, machine_name_normalized, diff, games, payout_rate
        FROM unit_results
        WHERE store_id = ?
        ORDER BY report_date DESC, ABS(COALESCE(diff, 0)) DESC, unit_number
        LIMIT ?
        """,
        [store.store_id, args.limit],
    )
    if frame.empty:
        print("no rows")
        return 0
    for _, row in frame.iterrows():
        print(
            f"{row['report_date']}\t{row['unit_number']}\t{row['machine_name_normalized']}\t"
            f"{row['diff']}\t{row['games']}\t{row['payout_rate']}"
        )
    return 0


def cmd_inspect_raw(args: argparse.Namespace) -> int:
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    files = _list_recent_raw_files(store.store_id, args.days)
    if not files:
        print("no raw HTML files")
        return 0

    print("raw_html_files:")
    parser = MinrepoParser()
    for path in files:
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        h1 = soup.find("h1")
        tables = soup.find_all("table")
        print(f"- file: {path.name}")
        print(f"  title: {title}")
        print(f"  h1: {h1.get_text(' ', strip=True) if h1 else ''}")
        print(f"  table_count: {len(tables)}")
        for index, table in enumerate(tables[:5], start=1):
            rows = list(parser._iter_table_rows(table))
            header = rows[0] if rows else []
            header_text = " | ".join(header)
            joined = " ".join(header)
            print(f"  table_{index}_header: {header_text}")
            print(
                "  table_"
                f"{index}_signals: diff={'差枚' in joined} games={'G数' in joined} "
                f"payout={'出率' in joined} unit={'台番' in joined}"
            )

        unit_links = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "?num=" in href:
                unit_links.append({"text": anchor.get_text(' ', strip=True), "href": href})
        print(f"  unit_link_samples: {json.dumps(unit_links[:5], ensure_ascii=False)}")

        script_numeric_hints = []
        for script in soup.find_all("script"):
            text = script.get_text(" ", strip=True)
            if not text:
                continue
            hint = {
                "has_chart": "Chart(" in text or "datasets" in text,
                "has_large_numeric_array": bool(re.search(r"-?\d+,-?\d+", text)),
                "has_num_query": "?num=" in text,
                "length": len(text),
            }
            if any(hint.values()):
                script_numeric_hints.append(hint)
        print(f"  script_hints: {json.dumps(script_numeric_hints[:5], ensure_ascii=False)}")
    return 0


def cmd_validate_unit_data(args: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    cutoff = _date_cutoff(args.days).isoformat()
    unit_df = database.query_dataframe(
        """
        SELECT *
        FROM unit_results
        WHERE store_id = ?
          AND report_date >= ?
        """,
        [store.store_id, cutoff],
    )
    quality = summarize_unit_data_quality(unit_df, store.store_id)
    print(f"unit_results_total: {quality['total_rows']}")
    print(f"diff_null_count: {quality['diff_null_count']}")
    print(f"diff_zero_count: {quality['diff_zero_count']}")
    print(f"games_null_count: {quality['games_null_count']}")
    print(f"payout_rate_null_count: {quality['payout_null_count']}")
    print(f"diff_missing_rate: {quality['diff_missing_rate']}")
    print(f"pattern_analysis_status: {quality['pattern_analysis_status']}")
    print("machine_missing_rate_top:")
    for row in quality["machine_missing"][:10]:
        print(
            f"- {row['machine_name_normalized']}: "
            f"{row['diff_null']}/{row['total']} ({row['missing_rate']:.3f})"
        )
    print("date_missing_rate:")
    for row in quality["date_missing"]:
        print(
            f"- {row['report_date']}: "
            f"{row['diff_null']}/{row['total']} ({row['missing_rate']:.3f})"
        )
    if quality["warning"]:
        print("WARNING: unit_results の diff 欠損率が高いため、末尾・並び分析は信頼不可です。")
    return 0


def cmd_unit_coverage(args: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    cutoff = _date_cutoff(args.days).isoformat()
    unit_df = database.query_dataframe(
        """
        SELECT *
        FROM unit_results
        WHERE store_id = ?
          AND report_date >= ?
        """,
        [store.store_id, cutoff],
    )
    quality = summarize_unit_data_quality(unit_df, store.store_id)

    print(f"store_id: {store.store_id}")
    print(f"lookback_days: {args.days}")
    print(f"unit_diff_missing_rate: {quality['diff_missing_rate']}")
    print(f"unit_results_total: {quality['total_rows']}")
    print(f"diff_null_count: {quality['diff_null_count']}")
    print(f"diff_zero_count: {quality['diff_zero_count']}")
    print("date_missing_rate:")
    for row in quality["date_missing"]:
        print(
            f"- {row['report_date']}: "
            f"{row['diff_null']}/{row['total']} "
            f"({row['missing_rate']:.3f}) status={row['status']}"
        )
    print("machine_missing_rate:")
    for row in quality["machine_missing"]:
        print(
            f"- {row['machine_name_normalized']}: "
            f"{row['diff_null']}/{row['total']} "
            f"({row['missing_rate']:.3f}) status={row['status']}"
        )
    print("category_missing_rate:")
    for row in quality["category_missing"]:
        print(
            f"- {row['machine_category']}: "
            f"{row['diff_null']}/{row['total']} "
            f"({row['missing_rate']:.3f}) status={row['status']}"
        )
    print(f"pattern_analysis_status: {quality['pattern_analysis_status']}")
    print(f"tail_analysis_status: {quality['tail_analysis_status']}")
    print(f"cluster_analysis_status: {quality['cluster_analysis_status']}")
    print("excluded_machines:")
    for row in quality["excluded_machines"]:
        print(
            f"- {row['machine_name']}: "
            f"{row['reason']} status={row['status']} missing_rate={row['missing_rate']}"
        )
    if not quality["excluded_machines"]:
        print("- none")
    return 0


def cmd_list_missing_units(args: argparse.Namespace) -> int:
    from src.collectors.minrepo_collector import MinrepoCollector

    database = _database()
    database.initialize(SCHEMA_PATH)
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    rows = list_missing_unit_rows(
        database=database,
        store_id=store.store_id,
        days=args.days,
        limit=args.limit,
    )
    if not rows:
        print("no missing units")
        return 0

    for row in rows:
        missing_fields = []
        if row["diff"] is None:
            missing_fields.append("diff")
        if row["games"] is None:
            missing_fields.append("games")
        if row["payout_rate"] is None:
            missing_fields.append("payout_rate")
        detail_url = row["detail_url"] or MinrepoCollector.build_unit_detail_url(
            row["source_url"],
            row["unit_number"],
        )
        print(
            f"{row['report_date']}\t{row['unit_number']}\t{row['machine_name_normalized']}\t"
            f"{','.join(missing_fields)}\t{detail_url}\t{row['detail_parse_status'] or ''}"
        )
    return 0


def cmd_fill_unit_details(args: argparse.Namespace) -> int:
    from src.collectors.minrepo_collector import MinrepoCollector

    database = _database()
    database.initialize(SCHEMA_PATH)
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    collector = MinrepoCollector(
        raw_root=RAW_DIR,
        base_url="https://min-repo.com",
        request_delay_seconds=args.sleep,
    )
    summary = fill_missing_unit_details(
        database=database,
        collector=collector,
        parser=MinrepoParser(),
        raw_root=RAW_DIR,
        store_id=store.store_id,
        days=args.days,
        max_pages=args.max_pages,
    )
    print(f"candidates: {summary.candidates}")
    print(f"fetched_pages: {summary.fetched_pages}")
    print(f"cached_pages: {summary.cached_pages}")
    print(f"saved_html_count: {summary.saved_html_count}")
    print(f"updated_rows: {summary.updated_rows}")
    print(f"parse_failed: {summary.parse_failed}")
    print(f"fetch_failed: {summary.fetch_failed}")
    print(f"skipped_due_to_limit: {summary.skipped_due_to_limit}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="slot-store-analyzer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize SQLite database")
    init_db.set_defaults(func=cmd_init_db)

    stores = subparsers.add_parser("stores", help="List configured stores")
    stores.set_defaults(func=cmd_stores)

    fetch = subparsers.add_parser("fetch-minrepo", help="Fetch Minrepo HTML")
    fetch.add_argument("--store")
    fetch.add_argument("--all", action="store_true")
    fetch.add_argument("--days", type=int, default=180)
    fetch.set_defaults(func=cmd_fetch_minrepo)

    parse = subparsers.add_parser("parse-minrepo", help="Parse saved Minrepo HTML")
    parse.add_argument("--store")
    parse.add_argument("--all", action="store_true")
    parse.set_defaults(func=cmd_parse_minrepo)

    analyze = subparsers.add_parser("analyze-stores", help="Analyze stores")
    analyze.add_argument("--days", type=int, default=180)
    analyze.add_argument("--date")
    analyze.set_defaults(func=cmd_analyze_stores)

    report = subparsers.add_parser("report-tomorrow", help="Generate tomorrow report")
    report.add_argument("--date")
    report.add_argument("--days", type=int, default=180)
    report.set_defaults(func=cmd_report_tomorrow)

    db_stats = subparsers.add_parser("db-stats", help="Show DB row counts")
    db_stats.set_defaults(func=cmd_db_stats)

    show_store_data = subparsers.add_parser("show-store-data", help="Show daily store rows")
    show_store_data.add_argument("--store")
    show_store_data.add_argument("--all", action="store_true")
    show_store_data.add_argument("--days", type=int, default=7)
    show_store_data.set_defaults(func=cmd_show_store_data)

    sample_units = subparsers.add_parser("sample-units", help="Show sample unit rows")
    sample_units.add_argument("--store")
    sample_units.add_argument("--all", action="store_true")
    sample_units.add_argument("--limit", type=int, default=20)
    sample_units.set_defaults(func=cmd_sample_units)

    inspect_raw = subparsers.add_parser("inspect-raw", help="Inspect saved raw HTML structure")
    inspect_raw.add_argument("--store")
    inspect_raw.add_argument("--all", action="store_true")
    inspect_raw.add_argument("--days", type=int, default=7)
    inspect_raw.set_defaults(func=cmd_inspect_raw)

    validate_units = subparsers.add_parser(
        "validate-unit-data",
        help="Validate unit_results missingness and pattern-analysis readiness",
    )
    validate_units.add_argument("--store")
    validate_units.add_argument("--all", action="store_true")
    validate_units.add_argument("--days", type=int, default=7)
    validate_units.set_defaults(func=cmd_validate_unit_data)

    unit_coverage = subparsers.add_parser(
        "unit-coverage",
        help="Summarize unit_results diff missingness for pattern-analysis readiness",
    )
    unit_coverage.add_argument("--store")
    unit_coverage.add_argument("--all", action="store_true")
    unit_coverage.add_argument("--days", type=int, default=7)
    unit_coverage.set_defaults(func=cmd_unit_coverage)

    list_missing = subparsers.add_parser(
        "list-missing-units",
        help="List unit rows missing diff or payout data",
    )
    list_missing.add_argument("--store")
    list_missing.add_argument("--all", action="store_true")
    list_missing.add_argument("--days", type=int, default=7)
    list_missing.add_argument("--limit", type=int, default=20)
    list_missing.set_defaults(func=cmd_list_missing_units)

    fill_details = subparsers.add_parser(
        "fill-unit-details",
        help="Backfill missing unit data from ?num= detail pages",
    )
    fill_details.add_argument("--store")
    fill_details.add_argument("--all", action="store_true")
    fill_details.add_argument("--days", type=int, default=7)
    fill_details.add_argument("--max-pages", type=int, default=50)
    fill_details.add_argument("--sleep", type=float, default=2.0)
    fill_details.set_defaults(func=cmd_fill_unit_details)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
