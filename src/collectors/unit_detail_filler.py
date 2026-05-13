from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from src.collectors.base_collector import CollectorError
from src.collectors.minrepo_collector import MinrepoCollector
from src.db.database import Database, utc_now_iso
from src.parsers.minrepo_parser import MinrepoParser


@dataclass
class FillSummary:
    candidates: int = 0
    fetched_pages: int = 0
    cached_pages: int = 0
    saved_html_count: int = 0
    updated_rows: int = 0
    parse_failed: int = 0
    fetch_failed: int = 0
    skipped_due_to_limit: int = 0


def unit_detail_raw_path(
    raw_root: Path,
    source: str,
    store_id: str,
    report_date: date,
    unit_number: str,
) -> Path:
    directory = raw_root / "unit_details" / source / store_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{report_date.isoformat()}_{unit_number}.html"


def list_missing_unit_rows(database: Database, store_id: str, days: int, limit: int | None) -> list:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return database.list_missing_unit_results(store_id=store_id, cutoff_date=cutoff, limit=limit)


def fill_missing_unit_details(
    database: Database,
    collector: MinrepoCollector,
    parser: MinrepoParser,
    raw_root: Path,
    store_id: str,
    days: int,
    max_pages: int,
) -> FillSummary:
    candidates = list_missing_unit_rows(database, store_id=store_id, days=days, limit=None)
    summary = FillSummary(candidates=len(candidates))

    for row in candidates:
        report_date = date.fromisoformat(row["report_date"])
        detail_url = MinrepoCollector.build_unit_detail_url(row["source_url"], row["unit_number"])
        raw_path = unit_detail_raw_path(
            raw_root=raw_root,
            source=row["source"],
            store_id=store_id,
            report_date=report_date,
            unit_number=row["unit_number"],
        )

        html: str | None = None
        if raw_path.exists():
            html = raw_path.read_text(encoding="utf-8")
            summary.cached_pages += 1
        else:
            if summary.fetched_pages >= max_pages:
                summary.skipped_due_to_limit += 1
                database.update_unit_result_detail(
                    int(row["id"]),
                    detail_url=detail_url,
                    detail_parse_status="skipped_limit",
                    detail_error="max-pages exceeded",
                )
                continue
            try:
                response = collector.get(detail_url)
                response = collector.ensure_success_response(response, detail_url)
                html = response.text
                raw_path.write_text(html, encoding="utf-8")
                summary.fetched_pages += 1
                summary.saved_html_count += 1
            except CollectorError as exc:
                summary.fetch_failed += 1
                database.update_unit_result_detail(
                    int(row["id"]),
                    detail_url=detail_url,
                    detail_parse_status="fetch_failed",
                    detail_error=str(exc),
                )
                continue

        try:
            parsed = parser.parse_unit_detail_page(html=html, source_url=detail_url)
        except Exception as exc:
            summary.parse_failed += 1
            database.update_unit_result_detail(
                int(row["id"]),
                detail_url=detail_url,
                detail_fetched_at=utc_now_iso(),
                detail_parse_status="parse_failed",
                detail_error=str(exc),
            )
            continue

        before = (
            row["diff"] is None,
            row["games"] is None,
            row["payout_rate"] is None,
        )
        database.update_unit_result_detail(
            int(row["id"]),
            diff=parsed.get("diff"),
            games=parsed.get("games"),
            payout_rate=parsed.get("payout_rate"),
            detail_url=detail_url,
            detail_fetched_at=utc_now_iso(),
            detail_parse_status="parsed",
            detail_error=None,
        )
        after_filled = sum(
            1
            for missing_before, key in zip(
                before,
                ["diff", "games", "payout_rate"],
            )
            if missing_before and parsed.get(key) is not None
        )
        if after_filled:
            summary.updated_rows += 1

    return summary
