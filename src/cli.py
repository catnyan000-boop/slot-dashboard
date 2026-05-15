from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from src.analysis.unit_data_quality import summarize_unit_data_quality
from src.collectors.unit_detail_filler import (
    fill_missing_unit_details,
    list_missing_unit_rows,
)
from src.db.database import Database
from src.normalizers.store_normalizer import StoreNormalizer
from src.parsers.minrepo_parser import MinrepoParser
from src.reports.site_builder import build_static_site, load_validation_statuses
from src.reports.targets_report import write_targets_outputs
from src.reports.tomorrow_report import generate_tomorrow_report, run_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DEBUG_RAW_DIR = DATA_DIR / "debug_raw"
DB_PATH = DATA_DIR / "slot.db"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
STORES_PATH = PROJECT_ROOT / "stores.yaml"
REPORTS_DIR = PROJECT_ROOT / "reports"
PUBLIC_DIR = PROJECT_ROOT / "public"


def _database() -> Database:
    return Database(DB_PATH)


def _store_normalizer() -> StoreNormalizer:
    return StoreNormalizer.from_yaml(STORES_PATH)


def _date_cutoff(days: int) -> date:
    return date.today() - timedelta(days=days)


def _raw_store_dir(store_id: str) -> Path:
    return RAW_DIR / "minrepo" / store_id


def _slorepo_raw_store_dir(store_id: str) -> Path:
    return RAW_DIR / "slorepo" / store_id


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


def _list_recent_slorepo_raw_files(store_id: str, days: int) -> list[Path]:
    cutoff = _date_cutoff(days)
    files: list[Path] = []
    for path in sorted(_slorepo_raw_store_dir(store_id).glob("*.html")):
        if path.name.startswith("store_"):
            files.append(path)
            continue
        try:
            report_date = date.fromisoformat(path.name[:10])
        except ValueError:
            continue
        if report_date >= cutoff:
            files.append(path)
    return files


@dataclass
class SourceProbe:
    label: str
    url: str
    status_code: int | None = None
    final_url: str = ""
    response_size_bytes: int = 0
    content_type: str = ""
    title: str = ""
    first_300_chars: str = ""
    table_headers: list[str] = field(default_factory=list)
    has_daiban_text: bool = False
    usable: bool = False
    error_reason: str = ""


def _make_source_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "slot-store-analyzer/0.1 "
                "(+respectful public-data collector; source entrypoint diagnostics)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
    )
    return session


def _probe_source_url(
    session: requests.Session,
    url: str,
    label: str,
    delay_seconds: float,
    last_request_at: list[float],
) -> SourceProbe:
    elapsed = time.monotonic() - last_request_at[0]
    if elapsed < delay_seconds:
        time.sleep(delay_seconds - elapsed)
    probe = SourceProbe(label=label, url=url)
    try:
        response = session.get(url, timeout=20)
    except Exception as exc:
        probe.error_reason = f"{type(exc).__name__}: {exc}"
        last_request_at[0] = time.monotonic()
        return probe

    last_request_at[0] = time.monotonic()
    probe.status_code = response.status_code
    probe.final_url = response.url
    probe.response_size_bytes = len(response.content or b"")
    probe.content_type = response.headers.get("Content-Type", "")
    probe.first_300_chars = re.sub(r"\s+", " ", response.text).strip()[:300]

    soup = BeautifulSoup(response.text, "html.parser")
    probe.title = soup.title.get_text(" ", strip=True) if soup.title else ""
    probe.has_daiban_text = "台番" in soup.get_text(" ", strip=True)
    for table in soup.find_all("table")[:3]:
        first_row = table.find("tr")
        if not first_row:
            continue
        cells = [cell.get_text(" ", strip=True) for cell in first_row.find_all(["th", "td"])]
        probe.table_headers.append(" | ".join(cells[:8]))

    if response.status_code >= 400:
        probe.error_reason = f"HTTP {response.status_code}"
    elif not response.text.strip():
        probe.error_reason = "Empty HTML returned"
    else:
        probe.usable = True
    return probe


def _print_source_probe(probe: SourceProbe) -> None:
    print(f"label: {probe.label}")
    print(f"url: {probe.url}")
    print(f"status: {probe.status_code if probe.status_code is not None else 'n/a'}")
    print(f"final_url: {probe.final_url}")
    print(f"response_size_bytes: {probe.response_size_bytes}")
    print(f"content_type: {probe.content_type}")
    print(f"title: {probe.title}")
    print(f"table_headers: {json.dumps(probe.table_headers, ensure_ascii=False)}")
    print(f"first_300_chars: {probe.first_300_chars}")
    print(f"error_reason: {probe.error_reason}")
    print(f"usable: {'yes' if probe.usable else 'no'}")


def _store_search_terms(store) -> list[str]:
    terms = [store.canonical_name, store.display_name, *store.aliases]
    deduped: list[str] = []
    for term in terms:
        if term and term not in deduped:
            deduped.append(term)
    return deduped


def _find_anaslo_store_url(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = anchor.get_text(" ", strip=True)
        if "データ一覧" in text and "ana-slo.com" in href:
            return href
    return ""


def _find_slorepo_store_url(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = re.sub(r"\s+", "", anchor["href"])
        if "/hole/" in href:
            return href
    return ""


def _slorepo_date_urls(store_html: str, store_url: str, limit: int) -> list[str]:
    soup = BeautifulSoup(store_html, "html.parser")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not re.fullmatch(r"\d{8}/?", href):
            continue
        url = urljoin(store_url if store_url.endswith("/") else store_url + "/", href)
        if url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _slorepo_first_machine_url(date_html: str, date_url: str) -> str:
    soup = BeautifulSoup(date_html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if "kishu/?kishu=" in href:
            return urljoin(date_url if date_url.endswith("/") else date_url + "/", href)
    return ""


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


def cmd_debug_fetch_minrepo(args: argparse.Namespace) -> int:
    from src.collectors.minrepo_collector import MinrepoCollector

    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    collector = MinrepoCollector(
        raw_root=RAW_DIR,
        base_url="https://min-repo.com",
        request_delay_seconds=args.sleep,
    )
    result = collector.debug_fetch_store_history(
        store=store,
        days=args.days,
        limit=args.limit,
        debug_raw_root=DEBUG_RAW_DIR,
    )

    print(f"store_id: {result.store_id}")
    print(f"display_name: {result.store_display_name}")
    print(f"canonical_name: {result.canonical_name}")
    print(f"days: {args.days}")
    print(f"limit: {args.limit}")
    print(f"user_agent: {result.user_agent}")
    print(f"request_delay_seconds: {result.request_delay_seconds}")
    print(f"tag_base_url: {result.tag_base_url}")
    print(f"separate_store_page_requested: {result.separate_store_page_requested}")
    for index, entry in enumerate(result.tag_probe_entries, start=1):
        print("")
        print(f"[probe {index}] probe_name: {entry.probe_name}")
        print(f"request_mode: {entry.request_mode}")
        print(f"request_headers: {json.dumps(entry.request_headers, ensure_ascii=False)}")
        print(f"url: {entry.url}")
        print(f"status: {entry.status_code if entry.status_code is not None else 'n/a'}")
        print(f"final_url: {entry.final_url}")
        print(f"redirect: {'yes' if entry.redirected else 'no'}")
        print(f"content_type: {entry.content_type}")
        print(f"response_size_bytes: {entry.response_size_bytes}")
        print(f"first_300_chars: {entry.first_300_chars}")
        print(f"title: {entry.title}")
        print(f"error_reason: {entry.error_reason}")
    print(f"existing_raw_recent_count: {len(result.existing_raw_files)}")
    for path in result.existing_raw_files:
        print(f"existing_raw_recent: {path}")
    print(f"debug_saved_count: {len(result.debug_saved_files)}")
    for path in result.debug_saved_files:
        print(f"debug_saved: {path}")
    if result.first_failure_stage:
        print(f"first_failure_stage: {result.first_failure_stage}")
        print(f"first_failure_reason: {result.first_failure_reason}")
    else:
        print("first_failure_stage: none")
        print("first_failure_reason: none")

    for index, entry in enumerate(result.entries, start=1):
        print("")
        print(f"[{index}] stage: {entry.stage}")
        print(f"url: {entry.url}")
        print(f"status: {entry.status_code if entry.status_code is not None else 'n/a'}")
        print(f"final_url: {entry.final_url}")
        print(f"redirect: {'yes' if entry.redirected else 'no'}")
        print(f"content_type: {entry.content_type}")
        print(f"response_size_bytes: {entry.response_size_bytes}")
        print(f"title: {entry.title}")
        print(f"h1: {entry.h1}")
        print(f"first_300_chars: {entry.first_300_chars}")
        print(f"empty_html_reason: {entry.empty_html_reason}")
        print(f"expected_content_status: {entry.expected_content_status}")
        print(f"error_reason: {entry.error_reason}")
        print(f"saved_raw_path: {entry.saved_raw_path}")
        print(f"fetch_usable: {'yes' if entry.fetch_usable else 'no'}")
    return 0


def _extract_report_id(url: str) -> str:
    match = re.search(r"/(\d+)/?(?:\?|$)", url)
    return match.group(1) if match else ""


def _extract_numeric_urls_from_html(html: str, pattern: str) -> list[str]:
    return sorted(set(re.findall(pattern, html)))


def _raw_report_urls(files: list[Path], limit: int) -> list[str]:
    urls: list[str] = []
    for path in files:
        html = path.read_text(encoding="utf-8")
        matches = _extract_numeric_urls_from_html(html, r"https://min-repo\.com/\d+/")
        for url in matches:
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
    return urls


def _raw_num_urls(files: list[Path], limit: int) -> list[str]:
    urls: list[str] = []
    for path in files:
        if not path.name.endswith("_units.html"):
            continue
        html = path.read_text(encoding="utf-8")
        matches = _extract_numeric_urls_from_html(html, r"https://min-repo\.com/\d+/\?num=\d+")
        for url in matches:
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
    return urls


def _listing_urls_from_raw(files: list[Path], db_rows: list[object]) -> list[tuple[str, str]]:
    prefecture_url = ""
    city_url = ""
    latest_report_date = ""
    for row in db_rows:
        url = row["url"]
        if "?kishu=all" in url:
            continue
        latest_report_date = row["report_date"] or ""
        break

    for path in files:
        html = path.read_text(encoding="utf-8")
        if not prefecture_url:
            match = re.search(r"https://min-repo\.com/category/[^\"'\s<>]+/", html)
            if match:
                prefecture_url = match.group(0)
        if not city_url:
            match = re.search(r"https://min-repo\.com/category/[^\"'\s<>]+/[^\"'\s<>]+/", html)
            if match:
                city_url = match.group(0)
        if prefecture_url and city_url:
            break

    urls: list[tuple[str, str]] = []
    if prefecture_url:
        urls.append(("prefecture_page", prefecture_url))
    if city_url:
        urls.append(("city_page", city_url))
    if latest_report_date:
        report_date = date.fromisoformat(latest_report_date)
        urls.append(
            (
                "date_archive_page",
                f"https://min-repo.com/{report_date.year:04d}/{report_date.month:02d}/{report_date.day:02d}/",
            )
        )
    return urls


def _print_probe_entry(label: str, entry) -> None:
    print(f"label: {label}")
    print(f"url: {entry.url}")
    print(f"status: {entry.status_code if entry.status_code is not None else 'n/a'}")
    print(f"final_url: {entry.final_url}")
    print(f"response_size_bytes: {entry.response_size_bytes}")
    print(f"content_type: {entry.content_type}")
    print(f"first_300_chars: {entry.first_300_chars}")
    print(f"title: {entry.title}")
    print(f"error_reason: {entry.error_reason}")
    print(f"fetch_usable: {'yes' if entry.fetch_usable else 'no'}")


def cmd_debug_minrepo_entrypoints(args: argparse.Namespace) -> int:
    from src.collectors.minrepo_collector import MinrepoCollector

    database = _database()
    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    collector = MinrepoCollector(
        raw_root=RAW_DIR,
        base_url="https://min-repo.com",
        request_delay_seconds=args.sleep,
    )

    db_rows = database.list_source_pages("minrepo", store_ids=[store.store_id])
    db_detail_urls: list[str] = []
    db_units_urls: list[str] = []
    for row in reversed(db_rows):
        url = row["url"]
        if "?kishu=all" in url:
            if url not in db_units_urls:
                db_units_urls.append(url)
        else:
            if url not in db_detail_urls:
                db_detail_urls.append(url)
    db_detail_urls = list(reversed(db_detail_urls))[: args.limit]
    db_units_urls = list(reversed(db_units_urls))[: args.limit]

    raw_files = list(reversed(_list_recent_raw_files(store.store_id, args.days)))
    raw_report_urls = _raw_report_urls(raw_files, args.limit)
    raw_num_urls = _raw_num_urls(raw_files, args.limit)
    listing_urls = _listing_urls_from_raw(raw_files, list(reversed(db_rows)))

    print(f"store_id: {store.store_id}")
    print(f"display_name: {store.display_name}")
    print(f"canonical_name: {store.canonical_name}")
    print(f"days: {args.days}")
    print(f"limit: {args.limit}")
    print("db_report_urls:")
    for url in db_detail_urls:
        print(f"- report_id={_extract_report_id(url)} url={url}")
    print("raw_report_urls:")
    for url in raw_report_urls:
        print(f"- report_id={_extract_report_id(url)} url={url}")

    print("detail_refetch_results:")
    detail_entries = []
    for index, url in enumerate(db_detail_urls[: args.limit], start=1):
        entry = collector.probe_url(url)
        detail_entries.append(entry)
        print(f"[{index}]")
        _print_probe_entry(f"detail_report_id_{_extract_report_id(url)}", entry)

    print("units_refetch_results:")
    units_entries = []
    for index, url in enumerate(db_units_urls[: args.limit], start=1):
        entry = collector.probe_url(url)
        units_entries.append(entry)
        print(f"[{index}]")
        _print_probe_entry(f"units_report_id_{_extract_report_id(url)}", entry)

    print("num_refetch_results:")
    num_entries = []
    for index, url in enumerate(raw_num_urls[: args.limit], start=1):
        entry = collector.probe_url(url)
        num_entries.append(entry)
        print(f"[{index}]")
        _print_probe_entry(f"num_report_id_{_extract_report_id(url)}", entry)

    print("listing_page_results:")
    listing_entries = []
    for index, (label, url) in enumerate(listing_urls, start=1):
        entry = collector.probe_url(url, probe_name=label)
        listing_entries.append(entry)
        print(f"[{index}]")
        _print_probe_entry(label, entry)

    detail_usable = any(entry.fetch_usable for entry in detail_entries)
    units_usable = any(entry.fetch_usable for entry in units_entries)
    num_usable = any(entry.fetch_usable for entry in num_entries)
    listing_usable = any(entry.fetch_usable for entry in listing_entries)

    print("entrypoint_summary:")
    db_entrypoint_status = "usable (historical only)" if db_detail_urls else "unusable"
    raw_entrypoint_status = "usable (historical only)" if raw_report_urls else "unusable"
    print(f"- existing_db_report_urls: {db_entrypoint_status}")
    print(f"- existing_raw_report_urls: {raw_entrypoint_status}")
    print(f"- live_detail_urls: {'usable' if detail_usable else 'unusable'}")
    print(f"- live_units_urls: {'usable' if units_usable else 'unusable'}")
    print(f"- live_num_urls: {'usable' if num_usable else 'unusable'}")
    print(f"- live_listing_pages: {'usable' if listing_usable else 'unusable'}")
    next_entrypoint = "none"
    if detail_usable:
        next_entrypoint = "known detail URL refresh"
    elif units_usable:
        next_entrypoint = "known ?kishu=all refresh"
    elif listing_usable:
        next_entrypoint = "prefecture/city/date listing page"
    elif db_detail_urls or raw_report_urls:
        next_entrypoint = "existing DB/raw only; no live refresh entrypoint confirmed"
    print(f"next_entrypoint: {next_entrypoint}")
    return 0


def _source_search_urls(source: str, query: str) -> list[str]:
    encoded = quote(query)
    if source == "slorepo":
        return [f"https://www.slorepo.com/search/?query={encoded}"]
    if source == "anaslo":
        return [f"https://ana-slo.com/?s={encoded}"]
    raise SystemExit(f"unsupported source: {source}")


def _debug_slorepo_store(
    session,
    store,
    limit: int,
    sleep: float,
    last_request_at: list[float],
) -> None:
    search_probe = None
    store_probe = None
    date_probe = None
    machine_probe = None
    store_url = ""
    search_html = ""

    for term in _store_search_terms(store):
        for search_url in _source_search_urls("slorepo", term):
            search_probe = _probe_source_url(
                session,
                search_url,
                label=f"search:{term}",
                delay_seconds=sleep,
                last_request_at=last_request_at,
            )
            if "/hole/" in search_probe.final_url:
                store_url = (
                    search_probe.final_url
                    if search_probe.final_url.endswith("/")
                    else search_probe.final_url + "/"
                )
                break
            if search_probe.usable:
                elapsed = time.monotonic() - last_request_at[0]
                if elapsed < sleep:
                    time.sleep(sleep - elapsed)
                response = session.get(search_url, timeout=20)
                last_request_at[0] = time.monotonic()
                search_html = response.text
                store_url = _find_slorepo_store_url(search_html)
        if store_url:
            break

    print("search_result:")
    if search_probe is not None:
        _print_source_probe(search_probe)

    if not store_url and search_probe is not None and search_probe.final_url:
        store_url = search_probe.final_url if "/hole/" in search_probe.final_url else ""
    if not store_url:
        print("store_page_result:")
        print("label: store_page")
        print("url: ")
        print("status: n/a")
        print("final_url: ")
        print("response_size_bytes: 0")
        print("content_type: ")
        print("title: ")
        print("table_headers: []")
        print("first_300_chars: ")
        print("error_reason: store page URL not found from search")
        print("usable: no")
        print("source_summary:")
        print("- store_page: unusable")
        print("- daily_data: unusable")
        print("- machine_data: unusable")
        print("- unit_data: unusable")
        return

    store_probe = _probe_source_url(
        session,
        store_url,
        label="store_page",
        delay_seconds=sleep,
        last_request_at=last_request_at,
    )
    print("store_page_result:")
    _print_source_probe(store_probe)

    store_html = ""
    if store_probe.usable:
        elapsed = time.monotonic() - last_request_at[0]
        if elapsed < sleep:
            time.sleep(sleep - elapsed)
        response = session.get(store_url, timeout=20)
        last_request_at[0] = time.monotonic()
        store_html = response.text

    date_urls = _slorepo_date_urls(store_html, store_url, limit) if store_html else []
    if date_urls:
        date_probe = _probe_source_url(
            session,
            date_urls[0],
            label="daily_page",
            delay_seconds=sleep,
            last_request_at=last_request_at,
        )
        print("daily_page_result:")
        _print_source_probe(date_probe)

    machine_url = ""
    if date_probe and date_probe.usable:
        elapsed = time.monotonic() - last_request_at[0]
        if elapsed < sleep:
            time.sleep(sleep - elapsed)
        response = session.get(date_urls[0], timeout=20)
        last_request_at[0] = time.monotonic()
        machine_url = _slorepo_first_machine_url(response.text, date_urls[0])
    if machine_url:
        machine_probe = _probe_source_url(
            session,
            machine_url,
            label="machine_or_unit_page",
            delay_seconds=sleep,
            last_request_at=last_request_at,
        )
        print("machine_or_unit_page_result:")
        _print_source_probe(machine_probe)

    has_machine_data = bool(
        date_probe
        and any("機種" in header and "平均差枚" in header for header in date_probe.table_headers)
    )
    has_unit_data = bool(machine_probe and machine_probe.has_daiban_text)
    print("source_summary:")
    print(f"- store_page: {'usable' if store_probe and store_probe.usable else 'unusable'}")
    print(f"- daily_data: {'usable' if date_probe and date_probe.usable else 'unusable'}")
    print(f"- machine_data: {'usable' if has_machine_data else 'unusable'}")
    print(f"- unit_data: {'usable' if has_unit_data else 'unusable'}")


def _debug_anaslo_store(
    session,
    store,
    limit: int,
    sleep: float,
    last_request_at: list[float],
) -> None:
    del limit
    search_probe = None
    store_probe = None
    store_url = ""

    for term in _store_search_terms(store):
        for search_url in _source_search_urls("anaslo", term):
            search_probe = _probe_source_url(
                session,
                search_url,
                label=f"search:{term}",
                delay_seconds=sleep,
                last_request_at=last_request_at,
            )
            if search_probe.usable:
                elapsed = time.monotonic() - last_request_at[0]
                if elapsed < sleep:
                    time.sleep(sleep - elapsed)
                response = session.get(search_url, timeout=20)
                last_request_at[0] = time.monotonic()
                store_url = _find_anaslo_store_url(response.text)
            if store_url:
                break
        if store_url:
            break

    print("search_result:")
    if search_probe is not None:
        _print_source_probe(search_probe)

    if store_url:
        store_probe = _probe_source_url(
            session,
            store_url,
            label="store_page",
            delay_seconds=sleep,
            last_request_at=last_request_at,
        )
    print("store_page_result:")
    if store_probe is not None:
        _print_source_probe(store_probe)
    else:
        print("label: store_page")
        print(f"url: {store_url}")
        print("status: n/a")
        print("final_url: ")
        print("response_size_bytes: 0")
        print("content_type: ")
        print("title: ")
        print("table_headers: []")
        print("first_300_chars: ")
        print("error_reason: store page URL not found from search")
        print("usable: no")

    print("source_summary:")
    print(f"- store_page: {'usable' if store_probe and store_probe.usable else 'unusable'}")
    print("- daily_data: unusable")
    print("- machine_data: unusable")
    print("- unit_data: unusable")


def cmd_debug_source_entrypoints(args: argparse.Namespace) -> int:
    normalizer = _store_normalizer()
    stores = _resolve_target_stores(args, normalizer)
    session = _make_source_session()
    last_request_at = [0.0]

    print(f"source: {args.source}")
    print(f"limit: {args.limit}")
    print(f"sleep: {args.sleep}")
    for index, store in enumerate(stores, start=1):
        if index > 1:
            print("")
        print(f"store_id: {store.store_id}")
        print(f"display_name: {store.display_name}")
        print(f"canonical_name: {store.canonical_name}")
        if args.source == "slorepo":
            _debug_slorepo_store(session, store, args.limit, args.sleep, last_request_at)
        elif args.source == "anaslo":
            _debug_anaslo_store(session, store, args.limit, args.sleep, last_request_at)
        else:
            raise SystemExit(f"unsupported source: {args.source}")
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


def _slorepo_store_slug(store_id: str) -> str:
    directory = _slorepo_raw_store_dir(store_id)
    for path in sorted(directory.glob("store_*.html")):
        slug = path.stem.removeprefix("store_")
        if slug:
            return slug
    return ""


def _slorepo_url_from_raw_path(store_id: str, path: Path) -> str:
    store_slug = _slorepo_store_slug(store_id) or "unknown"
    if path.name.startswith("store_"):
        return f"https://www.slorepo.com/hole/{store_slug}/"
    if path.name.endswith("_day.html"):
        report_date = date.fromisoformat(path.name[:10])
        return (
            f"https://www.slorepo.com/hole/{store_slug}/"
            f"{report_date.strftime('%Y%m%d')}/"
        )
    if "_machine_" in path.name:
        report_date = date.fromisoformat(path.name[:10])
        machine_slug = path.stem.split("_machine_", 1)[1]
        return (
            f"https://www.slorepo.com/hole/{store_slug}/"
            f"{report_date.strftime('%Y%m%d')}/kishu/?kishu={machine_slug}"
        )
    return ""


def _parse_slorepo_store_raw(
    *,
    store_id: str,
    days: int,
    parser,
    database: Database | None = None,
) -> tuple[int, int, int]:
    files = _list_recent_slorepo_raw_files(store_id, days)
    if not files:
        return 0, 0, 0

    daily_count = 0
    machine_count = 0
    unit_count = 0
    for path in files:
        if path.name.startswith("store_"):
            continue

        html = path.read_text(encoding="utf-8")
        source_url = _slorepo_url_from_raw_path(store_id, path)
        if path.name.endswith("_day.html"):
            daily_record, machine_records = parser.parse_detail_page(
                html=html,
                store_id=store_id,
                source_url=source_url,
            )
            if database is not None:
                database.upsert_daily_store_result(daily_record)
                database.upsert_machine_results(machine_records)
            daily_count += 1
            machine_count += len(machine_records)
        elif "_machine_" in path.name:
            unit_records = parser.parse_unit_page(
                html=html,
                store_id=store_id,
                source_url=source_url,
            )
            if database is not None:
                database.upsert_unit_results(unit_records)
            unit_count += len(unit_records)

    return daily_count, machine_count, unit_count


def cmd_debug_slorepo(args: argparse.Namespace) -> int:
    from src.collectors.slorepo_collector import SlorepoCollector

    normalizer = _store_normalizer()
    store = _resolve_target_stores(args, normalizer)[0]
    collector = SlorepoCollector(
        raw_root=RAW_DIR,
        request_delay_seconds=args.sleep,
    )

    print(f"store_id: {store.store_id}")
    print(f"display_name: {store.display_name}")
    print(f"canonical_name: {store.canonical_name}")
    print(f"days: {args.days}")
    print(f"limit: {args.limit}")

    store_page = collector.fetch_store_page(store)
    store_status = (
        store_page.record.status_code
        if store_page.record.status_code is not None
        else "cached"
    )
    print("store_page:")
    print(f"- url: {store_page.record.url}")
    print(f"- status: {store_status}")
    print(f"- raw_path: {store_page.record.raw_path}")

    day_pages = collector.fetch_day_pages(store=store, days=args.days, store_page=store_page)
    print(f"day_pages_count: {len(day_pages)}")
    for index, page in enumerate(day_pages[: args.limit], start=1):
        status = page.record.status_code if page.record.status_code is not None else "cached"
        daily_record, machine_records = collector.parser.parse_detail_page(
            html=page.raw_html,
            store_id=store.store_id,
            source_url=page.record.url,
        )
        machine_urls = collector.extract_machine_page_urls(
            page.raw_html,
            page.record.url,
            limit=args.limit,
        )
        print(f"day_page[{index}]:")
        print(f"- url: {page.record.url}")
        print(f"- status: {status}")
        print(f"- raw_path: {page.record.raw_path}")
        print(f"- report_date: {daily_record.report_date.isoformat()}")
        print(f"- machine_url_count: {len(machine_urls)}")
        print(f"- machine_record_count: {len(machine_records)}")

    machine_pages = collector.fetch_machine_pages(
        store=store,
        day_pages=day_pages[: args.limit],
        max_pages_per_day=args.limit,
    )
    print(f"machine_pages_count: {len(machine_pages)}")
    for index, page in enumerate(machine_pages[: args.limit], start=1):
        status = page.record.status_code if page.record.status_code is not None else "cached"
        unit_records = collector.parser.parse_unit_page(
            html=page.raw_html,
            store_id=store.store_id,
            source_url=page.record.url,
        )
        print(f"machine_page[{index}]:")
        print(f"- url: {page.record.url}")
        print(f"- status: {status}")
        print(f"- raw_path: {page.record.raw_path}")
        print(f"- unit_record_count: {len(unit_records)}")
    return 0


def cmd_fetch_slorepo(args: argparse.Namespace) -> int:
    from src.collectors.slorepo_collector import SlorepoCollector

    normalizer = _store_normalizer()
    collector = SlorepoCollector(
        raw_root=RAW_DIR,
        request_delay_seconds=args.sleep,
    )
    total_pages = 0
    total_saved = 0
    total_cached = 0
    total_machine_pages = 0
    total_saved_machine_pages = 0
    total_failed_machine_pages = 0
    for store in _resolve_target_stores(args, normalizer):
        result = collector.collect_store_days_result(store=store, days=args.days)
        pages = result.pages
        saved = sum(1 for page in pages if page.record.status_code is not None)
        cached = len(pages) - saved
        total_pages += len(pages)
        total_saved += saved
        total_cached += cached
        total_machine_pages += result.total_machine_pages
        total_saved_machine_pages += result.saved_machine_pages
        total_failed_machine_pages += len(result.failed_machine_pages)
        print(
            f"{store.store_id}: status={result.status} pages={len(pages)} saved={saved} "
            f"cached={cached} total_machine_pages={result.total_machine_pages} "
            f"saved_machine_pages={result.saved_machine_pages} "
            f"failed_machine_pages={len(result.failed_machine_pages)} "
            f"raw_dir={_slorepo_raw_store_dir(store.store_id)}"
        )
        if result.failed_machine_pages:
            print("failed_machine_urls:")
            for failed_page in result.failed_machine_pages:
                print(f"- {failed_page.url} ({failed_page.error})")
    print(f"total_pages: {total_pages}")
    print(f"saved_pages: {total_saved}")
    print(f"cached_pages: {total_cached}")
    print(f"total_machine_pages: {total_machine_pages}")
    print(f"saved_machine_pages: {total_saved_machine_pages}")
    print(f"failed_machine_pages: {total_failed_machine_pages}")
    return 0


def cmd_parse_slorepo_raw(args: argparse.Namespace) -> int:
    from src.parsers.slorepo_parser import SlorepoParser

    normalizer = _store_normalizer()
    parser = SlorepoParser()
    total_daily = 0
    total_machine = 0
    total_unit = 0

    for store in _resolve_target_stores(args, normalizer):
        daily_count, machine_count, unit_count = _parse_slorepo_store_raw(
            store_id=store.store_id,
            days=args.days,
            parser=parser,
        )
        if daily_count == 0 and machine_count == 0 and unit_count == 0:
            print(f"{store.store_id}: no slorepo raw HTML files")
            continue

        total_daily += daily_count
        total_machine += machine_count
        total_unit += unit_count
        print(
            f"{store.store_id}: daily={daily_count} machine={machine_count} unit={unit_count}"
        )

    print(f"total_daily: {total_daily}")
    print(f"total_machine: {total_machine}")
    print(f"total_unit: {total_unit}")
    return 0


def cmd_parse_slorepo(args: argparse.Namespace) -> int:
    from src.parsers.slorepo_parser import SlorepoParser

    database = _database()
    database.initialize(SCHEMA_PATH)
    database.seed_stores(_store_normalizer().catalog)

    normalizer = _store_normalizer()
    parser = SlorepoParser()
    total_daily = 0
    total_machine = 0
    total_unit = 0

    for store in _resolve_target_stores(args, normalizer):
        daily_count, machine_count, unit_count = _parse_slorepo_store_raw(
            store_id=store.store_id,
            days=args.days,
            parser=parser,
            database=database,
        )
        if daily_count == 0 and machine_count == 0 and unit_count == 0:
            print(f"{store.store_id}: no slorepo raw HTML files")
            continue

        total_daily += daily_count
        total_machine += machine_count
        total_unit += unit_count
        print(
            f"{store.store_id}: daily={daily_count} machine={machine_count} unit={unit_count}"
        )

    print(f"total_daily: {total_daily}")
    print(f"total_machine: {total_machine}")
    print(f"total_unit: {total_unit}")
    return 0


def cmd_analyze_stores(args: argparse.Namespace) -> int:
    database = _database()
    target_date = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1)
    result = run_analysis(
        database,
        _store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
        source=getattr(args, "source", None),
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
    source = getattr(args, "source", None)
    status_report = (
        REPORTS_DIR / "slorepo_coverage_9stores_7days.md"
        if source == "slorepo"
        else REPORTS_DIR / "unit_coverage_9stores_7days.md"
    )
    status_overrides = load_validation_statuses(status_report)
    report_path = generate_tomorrow_report(
        database=database,
        store_normalizer=_store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
        output_dir=REPORTS_DIR,
        source=source,
        status_overrides=status_overrides,
    )
    print(report_path)
    return 0


def cmd_build_site(args: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    database.seed_stores(_store_normalizer().catalog)
    target_date = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1)
    source = getattr(args, "source", None)
    status_report = (
        REPORTS_DIR / "slorepo_coverage_9stores_7days.md"
        if source == "slorepo"
        else REPORTS_DIR / "unit_coverage_9stores_7days.md"
    )
    status_overrides = load_validation_statuses(status_report)
    outputs = build_static_site(
        database=database,
        store_normalizer=_store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
        output_dir=PUBLIC_DIR,
        source=source,
        status_overrides=status_overrides,
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")
    return 0


def cmd_analyze_targets(args: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    database.seed_stores(_store_normalizer().catalog)
    target_date = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=1)
    source = getattr(args, "source", None)
    status_report = (
        REPORTS_DIR / "slorepo_coverage_9stores_7days.md"
        if source == "slorepo"
        else REPORTS_DIR / "unit_coverage_9stores_7days.md"
    )
    status_overrides = load_validation_statuses(status_report)
    payload, report_path, json_path = write_targets_outputs(
        database=database,
        store_normalizer=_store_normalizer(),
        target_date=target_date,
        lookback_days=args.days,
        reports_dir=REPORTS_DIR,
        public_dir=PUBLIC_DIR,
        source=source,
        status_overrides=status_overrides,
    )
    counts = payload["summary"]["target_counts"]
    print(f"report: {report_path}")
    print(f"json: {json_path}")
    print(
        "S/A/B/見送り: "
        f"{counts['S']} / {counts['A']} / {counts['B']} / {counts['見送り']}"
    )
    print(
        "raise/keep/tail/cluster/machine: "
        f"{counts['raise_candidate']} / {counts['keep_candidate']} / "
        f"{counts['tail_candidate']} / {counts['cluster_candidate']} / "
        f"{counts['machine_candidate']}"
    )
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


def _query_unit_quality(
    database: Database,
    store_id: str,
    days: int,
    source: str | None = None,
) -> dict[str, object]:
    cutoff = _date_cutoff(days).isoformat()
    sql = """
    SELECT *
    FROM unit_results
    WHERE store_id = ?
      AND report_date >= ?
    """
    params: list[str] = [store_id, cutoff]
    if source:
        sql += "\n      AND source = ?"
        params.append(source)
    unit_df = database.query_dataframe(sql, params)
    return summarize_unit_data_quality(unit_df, store_id)


def _print_unit_coverage(
    store,
    quality: dict[str, object],
    days: int,
    source: str | None = None,
) -> None:
    print(f"store_id: {store.store_id}")
    print(f"display_name: {store.display_name}")
    print(f"lookback_days: {days}")
    if source:
        print(f"source: {source}")
    print(f"unit_diff_missing_rate: {quality['diff_missing_rate']}")
    print(f"unit_results_total: {quality['total_rows']}")
    print(f"diff_null_count: {quality['diff_null_count']}")
    print(f"diff_zero_count: {quality['diff_zero_count']}")
    print(f"effective_analyses: {', '.join(quality['effective_analyses'])}")
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


def cmd_unit_coverage(args: argparse.Namespace) -> int:
    database = _database()
    database.initialize(SCHEMA_PATH)
    normalizer = _store_normalizer()
    stores = _resolve_target_stores(args, normalizer)
    source = getattr(args, "source", None)
    for index, store in enumerate(stores):
        quality = _query_unit_quality(database, store.store_id, args.days, source=source)
        _print_unit_coverage(store, quality, args.days, source=source)
        if index < len(stores) - 1:
            print("")
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

    debug_fetch = subparsers.add_parser(
        "debug-fetch-minrepo",
        help="Debug Minrepo fetch flow and raw HTML usability",
    )
    debug_fetch.add_argument("--store")
    debug_fetch.add_argument("--all", action="store_true")
    debug_fetch.add_argument("--days", type=int, default=7)
    debug_fetch.add_argument("--limit", type=int, default=3)
    debug_fetch.add_argument("--sleep", type=float, default=2.0)
    debug_fetch.set_defaults(func=cmd_debug_fetch_minrepo)

    debug_entrypoints = subparsers.add_parser(
        "debug-minrepo-entrypoints",
        help="Debug alternative Minrepo entrypoints using DB and raw history",
    )
    debug_entrypoints.add_argument("--store")
    debug_entrypoints.add_argument("--all", action="store_true")
    debug_entrypoints.add_argument("--days", type=int, default=7)
    debug_entrypoints.add_argument("--limit", type=int, default=5)
    debug_entrypoints.add_argument("--sleep", type=float, default=2.0)
    debug_entrypoints.set_defaults(func=cmd_debug_minrepo_entrypoints)

    debug_source_entrypoints = subparsers.add_parser(
        "debug-source-entrypoints",
        help="Debug Anaslo or Slorepo store/day/machine/unit entrypoints",
    )
    debug_source_entrypoints.add_argument("--source", choices=["anaslo", "slorepo"], required=True)
    debug_source_entrypoints.add_argument("--store")
    debug_source_entrypoints.add_argument("--all", action="store_true")
    debug_source_entrypoints.add_argument("--limit", type=int, default=3)
    debug_source_entrypoints.add_argument("--sleep", type=float, default=2.0)
    debug_source_entrypoints.set_defaults(func=cmd_debug_source_entrypoints)

    debug_slorepo = subparsers.add_parser(
        "debug-slorepo",
        help="Debug Slorepo store/day/machine fetch flow without DB writes",
    )
    debug_slorepo.add_argument("--store")
    debug_slorepo.add_argument("--all", action="store_true")
    debug_slorepo.add_argument("--days", type=int, default=7)
    debug_slorepo.add_argument("--limit", type=int, default=3)
    debug_slorepo.add_argument("--sleep", type=float, default=2.0)
    debug_slorepo.set_defaults(func=cmd_debug_slorepo)

    fetch_slorepo = subparsers.add_parser("fetch-slorepo", help="Fetch Slorepo HTML")
    fetch_slorepo.add_argument("--store")
    fetch_slorepo.add_argument("--all", action="store_true")
    fetch_slorepo.add_argument("--days", type=int, default=7)
    fetch_slorepo.add_argument("--sleep", type=float, default=2.0)
    fetch_slorepo.set_defaults(func=cmd_fetch_slorepo)

    parse_slorepo = subparsers.add_parser(
        "parse-slorepo-raw",
        help="Parse saved Slorepo raw HTML without DB writes",
    )
    parse_slorepo.add_argument("--store")
    parse_slorepo.add_argument("--all", action="store_true")
    parse_slorepo.add_argument("--days", type=int, default=7)
    parse_slorepo.set_defaults(func=cmd_parse_slorepo_raw)

    parse_slorepo_db = subparsers.add_parser(
        "parse-slorepo",
        help="Parse saved Slorepo HTML and persist results to DB",
    )
    parse_slorepo_db.add_argument("--store")
    parse_slorepo_db.add_argument("--all", action="store_true")
    parse_slorepo_db.add_argument("--days", type=int, default=7)
    parse_slorepo_db.set_defaults(func=cmd_parse_slorepo)

    parse = subparsers.add_parser("parse-minrepo", help="Parse saved Minrepo HTML")
    parse.add_argument("--store")
    parse.add_argument("--all", action="store_true")
    parse.set_defaults(func=cmd_parse_minrepo)

    analyze = subparsers.add_parser("analyze-stores", help="Analyze stores")
    analyze.add_argument("--days", type=int, default=180)
    analyze.add_argument("--date")
    analyze.add_argument("--source", choices=["minrepo", "slorepo", "anaslo"])
    analyze.set_defaults(func=cmd_analyze_stores)

    report = subparsers.add_parser("report-tomorrow", help="Generate tomorrow report")
    report.add_argument("--date")
    report.add_argument("--days", type=int, default=180)
    report.add_argument("--source", choices=["minrepo", "slorepo", "anaslo"])
    report.set_defaults(func=cmd_report_tomorrow)

    build_site = subparsers.add_parser("build-site", help="Build static dashboard site")
    build_site.add_argument("--date")
    build_site.add_argument("--days", type=int, default=7)
    build_site.add_argument("--source", choices=["minrepo", "slorepo", "anaslo"])
    build_site.set_defaults(func=cmd_build_site)

    analyze_targets = subparsers.add_parser(
        "analyze-targets",
        help="Extract practical store/machine/unit target candidates",
    )
    analyze_targets.add_argument("--date")
    analyze_targets.add_argument("--days", type=int, default=30)
    analyze_targets.add_argument("--source", choices=["minrepo", "slorepo", "anaslo"])
    analyze_targets.set_defaults(func=cmd_analyze_targets)

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
    unit_coverage.add_argument("--source", choices=["minrepo", "slorepo", "anaslo"])
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
