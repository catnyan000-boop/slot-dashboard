from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.db.models import StoreDefinition

from .base_collector import BaseCollector, CollectedPage


@dataclass
class FetchDebugEntry:
    stage: str
    url: str
    probe_name: str = ""
    request_mode: str = ""
    request_headers: dict[str, str] = field(default_factory=dict)
    status_code: Optional[int] = None
    final_url: str = ""
    redirected: bool = False
    content_type: str = ""
    response_size_bytes: int = 0
    title: str = ""
    h1: str = ""
    first_300_chars: str = ""
    empty_html_reason: str = ""
    expected_content_status: str = ""
    error_reason: str = ""
    saved_raw_path: str = ""
    fetch_usable: bool = False


@dataclass
class StoreFetchDebugResult:
    store_id: str
    store_display_name: str
    canonical_name: str
    tag_base_url: str
    user_agent: str
    request_delay_seconds: float
    existing_raw_files: list[str] = field(default_factory=list)
    debug_saved_files: list[str] = field(default_factory=list)
    tag_probe_entries: list[FetchDebugEntry] = field(default_factory=list)
    entries: list[FetchDebugEntry] = field(default_factory=list)
    first_failure_stage: str = ""
    first_failure_reason: str = ""
    separate_store_page_requested: bool = False


class MinrepoCollector(BaseCollector):
    source_name = "minrepo"

    @staticmethod
    def build_unit_detail_url(source_url: str, unit_number: str) -> str:
        parsed = urlparse(source_url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        query = parse_qs(parsed.query)
        if "num" in query and query["num"]:
            return f"{base}?num={query['num'][0]}"
        return f"{base}?num={unit_number}"

    def fetch_store_history(self, store: StoreDefinition, days: int) -> list[CollectedPage]:
        cutoff = date.today() - timedelta(days=days)
        tag_base_url = f"{self.base_url}/tag/{quote(store.canonical_name)}/"
        seen_urls: set[str] = set()
        collected: list[CollectedPage] = []
        stop_due_to_cutoff = False

        for page_number in range(1, 51):
            tag_url = (
                tag_base_url
                if page_number == 1
                else urljoin(tag_base_url, f"page/{page_number}/")
            )
            response = self.get(tag_url)
            if response is None:
                break
            response = self.ensure_success_response(response, tag_url, allow_redirect=False)
            detail_urls = self._extract_report_urls(response.text)
            if not detail_urls:
                break

            for detail_url in detail_urls:
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                detail_response = self.get(detail_url)
                if detail_response is None:
                    continue
                detail_response = self.ensure_success_response(detail_response, detail_url)
                report_date = self._extract_report_date(detail_response.text)
                if report_date is None:
                    continue
                if report_date < cutoff:
                    stop_due_to_cutoff = True
                    break

                detail_path = self.save_raw_html(
                    store.store_id,
                    report_date,
                    "detail",
                    detail_response.text,
                )
                detail_record = self.build_source_page_record(
                    source=self.source_name,
                    store_id=store.store_id,
                    url=detail_url,
                    report_date=report_date,
                    raw_path=detail_path,
                    status_code=detail_response.status_code,
                    html=detail_response.text,
                )
                collected.append(CollectedPage(record=detail_record, raw_html=detail_response.text))

                unit_url = f"{detail_url}?kishu=all"
                unit_response = self.get(unit_url)
                if unit_response is None:
                    continue
                unit_response = self.ensure_success_response(unit_response, unit_url)
                unit_path = self.save_raw_html(
                    store.store_id,
                    report_date,
                    "units",
                    unit_response.text,
                )
                unit_record = self.build_source_page_record(
                    source=self.source_name,
                    store_id=store.store_id,
                    url=unit_url,
                    report_date=report_date,
                    raw_path=unit_path,
                    status_code=unit_response.status_code,
                    html=unit_response.text,
                )
                collected.append(CollectedPage(record=unit_record, raw_html=unit_response.text))

            if stop_due_to_cutoff:
                break

        return collected

    def debug_fetch_store_history(
        self,
        store: StoreDefinition,
        days: int,
        limit: int = 3,
        debug_raw_root: Optional[Path] = None,
    ) -> StoreFetchDebugResult:
        cutoff = date.today() - timedelta(days=days)
        tag_base_url = f"{self.base_url}/tag/{quote(store.canonical_name)}/"
        result = StoreFetchDebugResult(
            store_id=store.store_id,
            store_display_name=store.display_name,
            canonical_name=store.canonical_name,
            tag_base_url=tag_base_url,
            user_agent=self.session.headers.get("User-Agent", ""),
            request_delay_seconds=self.request_delay_seconds,
            existing_raw_files=self._existing_recent_raw_files(store.store_id, cutoff),
        )
        result.tag_probe_entries = self._probe_tag_fetch_patterns(tag_base_url)
        seen_urls: set[str] = set()
        fetched_details = 0
        stop = False

        for page_number in range(1, 51):
            tag_url = (
                tag_base_url
                if page_number == 1
                else urljoin(tag_base_url, f"page/{page_number}/")
            )
            tag_entry, tag_response = self._debug_request(
                stage="tag_page",
                url=tag_url,
                expected_content_status="pending",
                allow_redirect=False,
                debug_raw_root=debug_raw_root,
                store_id=store.store_id,
                debug_label=f"tag_page_{page_number}",
            )
            result.entries.append(tag_entry)
            if not tag_response:
                self._mark_failure(result, "tag_page", tag_entry.error_reason)
                break

            detail_urls = self._extract_report_urls(tag_response.text)
            if not detail_urls:
                tag_entry.expected_content_status = "report detail links not found"
                tag_entry.error_reason = "No report detail URLs found on tag page"
                self._mark_failure(result, "tag_page", tag_entry.error_reason)
                break
            tag_entry.fetch_usable = True
            tag_entry.expected_content_status = f"report detail links found={len(detail_urls)}"

            for detail_index, detail_url in enumerate(detail_urls, start=1):
                if fetched_details >= limit:
                    stop = True
                    break
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                detail_entry, detail_response = self._debug_request(
                    stage="detail_page",
                    url=detail_url,
                    expected_content_status="pending",
                    allow_redirect=True,
                    debug_raw_root=debug_raw_root,
                    store_id=store.store_id,
                    debug_label=f"detail_{page_number}_{detail_index}",
                )
                result.entries.append(detail_entry)
                if not detail_response:
                    self._mark_failure(result, "detail_page", detail_entry.error_reason)
                    continue

                report_date = self._extract_report_date(detail_response.text)
                if report_date is None:
                    detail_entry.expected_content_status = "report_date not found"
                    detail_entry.error_reason = "Could not extract report_date from detail page"
                    self._mark_failure(result, "detail_page", detail_entry.error_reason)
                    continue

                has_machine_table = self._has_heading_table(detail_response.text, "機種別データ")
                has_variety_table = self._has_heading_table(detail_response.text, "バラエティ")
                detail_entry.fetch_usable = True
                detail_entry.expected_content_status = (
                    f"report_date={report_date.isoformat()} "
                    f"machine_table={has_machine_table} variety_table={has_variety_table}"
                )

                if report_date < cutoff:
                    detail_entry.error_reason = (
                        "Reached cutoff: "
                        f"report_date={report_date.isoformat()} < {cutoff.isoformat()}"
                    )
                    stop = True
                    break

                fetched_details += 1
                unit_url = f"{detail_url}?kishu=all"
                units_entry, units_response = self._debug_request(
                    stage="units_page",
                    url=unit_url,
                    expected_content_status="pending",
                    allow_redirect=True,
                    debug_raw_root=debug_raw_root,
                    store_id=store.store_id,
                    debug_label=f"units_{page_number}_{detail_index}",
                )
                result.entries.append(units_entry)
                if not units_response:
                    self._mark_failure(result, "units_page", units_entry.error_reason)
                    continue

                units_table = self._find_units_table(units_response.text)
                if units_table is None:
                    units_entry.fetch_usable = True
                    units_entry.expected_content_status = "expected 全台 table not found"
                    units_entry.error_reason = (
                        "Units page HTML exists but expected 全台 table is missing"
                    )
                    self._mark_failure(result, "units_page", units_entry.error_reason)
                    continue

                header = self._table_header_text(units_table)
                units_entry.fetch_usable = True
                units_entry.expected_content_status = f"units table found header={header}"

            if stop:
                break

        if debug_raw_root is not None:
            result.debug_saved_files = self._list_debug_saved_files(debug_raw_root, store.store_id)
        return result

    def probe_url(
        self,
        url: str,
        probe_name: str = "",
        request_mode: str = "session",
        headers: Optional[dict[str, str]] = None,
    ) -> FetchDebugEntry:
        return self._probe_single_request(
            url=url,
            probe_name=probe_name,
            request_mode=request_mode,
            headers=headers or self._sanitized_headers(dict(self.session.headers)),
        )

    def _extract_report_urls(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True)
            href = anchor["href"]
            if not re.match(r"^(?:\d{4}/)?\d{1,2}/\d{1,2}\(", label):
                continue
            if not re.match(r"^https?://min-repo\.com/\d+/?$", href):
                href = urljoin(self.base_url + "/", href)
            if re.match(r"^https?://min-repo\.com/\d+/?$", href):
                urls.append(href.rstrip("/") + "/")
        return urls

    def _extract_report_date(self, html: str) -> Optional[date]:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        h1_text = h1.get_text(" ", strip=True) if h1 else ""
        header_match = re.search(r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})\(", h1_text)
        publish_match = re.search(
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            soup.get_text("\n", strip=True),
        )
        publish_year = int(publish_match.group(1)) if publish_match else date.today().year

        if not header_match:
            return None
        year = int(header_match.group(1) or publish_year)
        month = int(header_match.group(2))
        day_value = int(header_match.group(3))
        if publish_match and not header_match.group(1):
            publish_month = int(publish_match.group(2))
            if publish_month == 1 and month == 12:
                year -= 1
        return date(year, month, day_value)

    def _debug_request(
        self,
        stage: str,
        url: str,
        expected_content_status: str,
        allow_redirect: bool,
        debug_raw_root: Optional[Path],
        store_id: str,
        debug_label: str,
    ) -> tuple[FetchDebugEntry, Optional[object]]:
        entry = FetchDebugEntry(
            stage=stage,
            url=url,
            expected_content_status=expected_content_status,
        )
        try:
            response = self.get(url)
        except Exception as exc:
            entry.error_reason = f"{type(exc).__name__}: {exc}"
            entry.empty_html_reason = "no response object available"
            return entry, None

        if response is None:
            entry.error_reason = "Blocked by robots.txt or no response"
            entry.empty_html_reason = "request returned None"
            return entry, None

        entry.status_code = response.status_code
        entry.final_url = response.url
        entry.redirected = response.url.rstrip("/") != url.rstrip("/")
        entry.content_type = response.headers.get("Content-Type", "")
        entry.response_size_bytes = len(response.content or b"")
        entry.title, entry.h1 = self._extract_title_h1(response.text)
        entry.first_300_chars = self._snippet(response.text)
        entry.empty_html_reason = self._empty_html_reason(response.text)

        if response.text.strip() and debug_raw_root is not None:
            saved_path = self._save_debug_html(
                debug_raw_root=debug_raw_root,
                store_id=store_id,
                label=debug_label,
                html=response.text,
            )
            entry.saved_raw_path = str(saved_path)

        if response.status_code >= 400:
            entry.error_reason = f"HTTP {response.status_code}"
            return entry, None
        if not allow_redirect and entry.redirected:
            entry.error_reason = f"Unexpected redirect to {response.url}"
            return entry, None
        if not response.text.strip():
            entry.error_reason = "Empty HTML returned"
            return entry, None
        return entry, response

    def _probe_tag_fetch_patterns(self, tag_url: str) -> list[FetchDebugEntry]:
        profiles = [
            {
                "probe_name": "current_session",
                "request_mode": "session",
                "headers": self._sanitized_headers(dict(self.session.headers)),
            },
            {
                "probe_name": "browser_accept_session",
                "request_mode": "session",
                "headers": self._browser_like_headers(),
            },
            {
                "probe_name": "browser_accept_plain",
                "request_mode": "plain_requests_get",
                "headers": self._browser_like_headers(),
            },
        ]

        entries: list[FetchDebugEntry] = []
        for profile in profiles:
            entry = self._probe_single_request(
                url=tag_url,
                probe_name=profile["probe_name"],
                request_mode=profile["request_mode"],
                headers=profile["headers"],
            )
            entries.append(entry)
        return entries

    def _probe_single_request(
        self,
        url: str,
        probe_name: str,
        request_mode: str,
        headers: dict[str, str],
    ) -> FetchDebugEntry:
        entry = FetchDebugEntry(
            stage="tag_probe",
            url=url,
            probe_name=probe_name,
            request_mode=request_mode,
            request_headers=headers,
        )
        if not self.can_fetch(url):
            entry.error_reason = "Blocked by robots.txt"
            entry.empty_html_reason = "request blocked before send"
            return entry

        try:
            if request_mode == "session":
                response = self._session_request(url, headers)
            else:
                response = self._plain_request(url, headers)
        except Exception as exc:
            entry.error_reason = f"{type(exc).__name__}: {exc}"
            entry.empty_html_reason = "no response object available"
            return entry

        entry.status_code = response.status_code
        entry.final_url = response.url
        entry.redirected = response.url.rstrip("/") != url.rstrip("/")
        entry.content_type = response.headers.get("Content-Type", "")
        entry.response_size_bytes = len(response.content or b"")
        entry.title, entry.h1 = self._extract_title_h1(response.text)
        entry.first_300_chars = self._snippet(response.text)
        entry.empty_html_reason = self._empty_html_reason(response.text)
        if response.status_code >= 400:
            entry.error_reason = f"HTTP {response.status_code}"
        elif not response.text.strip():
            entry.error_reason = "Empty HTML returned"
        else:
            entry.fetch_usable = True
        return entry

    def _session_request(self, url: str, headers: dict[str, str]) -> requests.Response:
        original_headers = dict(self.session.headers)
        self.session.headers.clear()
        self.session.headers.update(headers)
        try:
            return self.get(url)  # type: ignore[return-value]
        finally:
            self.session.headers.clear()
            self.session.headers.update(original_headers)

    def _plain_request(self, url: str, headers: dict[str, str]) -> requests.Response:
        self._sleep_if_needed()
        response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        return response

    def _existing_recent_raw_files(self, store_id: str, cutoff: date) -> list[str]:
        raw_dir = self.raw_root / self.source_name / store_id
        if not raw_dir.exists():
            return []
        files: list[str] = []
        for path in sorted(raw_dir.glob("*.html")):
            try:
                report_date = date.fromisoformat(path.name[:10])
            except ValueError:
                continue
            if report_date >= cutoff:
                files.append(str(path))
        return files

    def _list_debug_saved_files(self, debug_raw_root: Path, store_id: str) -> list[str]:
        debug_dir = debug_raw_root / self.source_name / store_id
        if not debug_dir.exists():
            return []
        return [str(path) for path in sorted(debug_dir.glob("*.html"))]

    @staticmethod
    def _mark_failure(result: StoreFetchDebugResult, stage: str, reason: str) -> None:
        if not result.first_failure_stage:
            result.first_failure_stage = stage
            result.first_failure_reason = reason

    @staticmethod
    def _extract_title_h1(html: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        h1 = soup.find("h1")
        return title, h1.get_text(" ", strip=True) if h1 else ""

    @staticmethod
    def _snippet(html: str) -> str:
        return re.sub(r"\s+", " ", html).strip()[:300]

    def _sleep_if_needed(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_delay_seconds:
            time.sleep(self.request_delay_seconds - elapsed)

    @staticmethod
    def _sanitized_headers(headers: dict[str, str]) -> dict[str, str]:
        keep_keys = {"User-Agent", "Accept", "Accept-Language"}
        return {key: value for key, value in headers.items() if key in keep_keys}

    @staticmethod
    def _browser_like_headers() -> dict[str, str]:
        return {
            "User-Agent": (
                "slot-store-analyzer/0.1 "
                "(+respectful public-data collector; browser-like accept diagnostics)"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }

    @staticmethod
    def _empty_html_reason(html: str) -> str:
        return "response.text.strip() is empty" if not html.strip() else "non-empty HTML"

    @staticmethod
    def _has_heading_table(html: str, keyword: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            if keyword in heading.get_text(" ", strip=True) and heading.find_next("table"):
                return True
        return False

    @staticmethod
    def _find_units_table(html: str):
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            if "全台" in heading.get_text(" ", strip=True):
                table = heading.find_next("table")
                if table is not None:
                    return table
        return None

    @staticmethod
    def _table_header_text(table) -> str:
        first_row = table.find("tr") if table is not None else None
        if first_row is None:
            return ""
        cells = [cell.get_text(" ", strip=True) for cell in first_row.find_all(["td", "th"])]
        return " | ".join(cells[:8])

    @staticmethod
    def _save_debug_html(
        debug_raw_root: Path,
        store_id: str,
        label: str,
        html: str,
    ) -> Path:
        directory = debug_raw_root / MinrepoCollector.source_name / store_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{label}.html"
        path.write_text(html, encoding="utf-8")
        return path
