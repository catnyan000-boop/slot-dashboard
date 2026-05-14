from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse

from bs4 import BeautifulSoup

from src.db.models import StoreDefinition
from src.parsers.slorepo_parser import SlorepoParser

from .base_collector import BaseCollector, CollectedPage, CollectorError


class SlorepoCollector(BaseCollector):
    source_name = "slorepo"

    def __init__(
        self,
        raw_root: Path,
        base_url: str = "https://www.slorepo.com",
        request_delay_seconds: float = 1.5,
        timeout_seconds: int = 20,
        user_agent: str = "slot-store-analyzer/0.1 (+respectful public-data collector)",
        parser: Optional[SlorepoParser] = None,
    ) -> None:
        super().__init__(
            raw_root=raw_root,
            base_url=base_url,
            request_delay_seconds=request_delay_seconds,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
        )
        self.parser = parser or SlorepoParser()

    def fetch_store_history(self, store: StoreDefinition, days: int) -> list[CollectedPage]:
        return self.collect_store_days(store=store, days=days)

    def collect_store_days(
        self,
        store: StoreDefinition,
        days: int,
        max_machine_pages_per_day: Optional[int] = None,
    ) -> list[CollectedPage]:
        store_page = self.fetch_store_page(store)
        day_pages = self.fetch_day_pages(store=store, days=days, store_page=store_page)
        machine_pages = self.fetch_machine_pages(
            store=store,
            day_pages=day_pages,
            max_pages_per_day=max_machine_pages_per_day,
        )
        return [store_page, *day_pages, *machine_pages]

    def fetch_store_page(self, store: StoreDefinition) -> CollectedPage:
        cached_store = self._load_cached_store_page(store.store_id)
        if cached_store is not None:
            return cached_store

        search_url = self.build_store_search_url(store)
        search_response = self.ensure_success_response(self.get(search_url), search_url)
        store_url = self.extract_store_page_url(search_response.text, search_response.url)
        if not store_url:
            raise CollectorError(f"Could not find slorepo store page URL for {store.store_id}")

        store_response = search_response
        if search_response.url.rstrip("/") != store_url.rstrip("/"):
            store_response = self.ensure_success_response(self.get(store_url), store_url)

        raw_path = self.save_raw_html(
            store_id=store.store_id,
            report_date=None,
            page_kind="store",
            html=store_response.text,
            source_url=store_url,
        )
        record = self.build_source_page_record(
            source=self.source_name,
            store_id=store.store_id,
            url=store_url,
            report_date=None,
            raw_path=raw_path,
            status_code=store_response.status_code,
            html=store_response.text,
        )
        return CollectedPage(record=record, raw_html=store_response.text)

    def fetch_day_pages(
        self,
        store: StoreDefinition,
        days: int,
        store_page: Optional[CollectedPage] = None,
    ) -> list[CollectedPage]:
        store_page = store_page or self.fetch_store_page(store)
        day_urls = self.extract_day_page_urls(
            store_page.raw_html,
            store_page.record.url,
            limit=days,
        )

        collected: list[CollectedPage] = []
        for day_url in day_urls:
            report_date = self._extract_date_from_url(day_url)
            if report_date is None:
                continue
            raw_path = self.raw_path_for(
                store_id=store.store_id,
                page_kind="day",
                report_date=report_date,
            )
            if raw_path.exists():
                html = raw_path.read_text(encoding="utf-8")
                collected.append(
                    self._build_cached_page(
                        store_id=store.store_id,
                        url=day_url,
                        report_date=report_date,
                        raw_path=raw_path,
                        html=html,
                    )
                )
                continue

            response = self.ensure_success_response(self.get(day_url), day_url)
            parsed_date = self.parser.peek_report_date(response.text) or report_date
            raw_path = self.save_raw_html(
                store_id=store.store_id,
                report_date=parsed_date,
                page_kind="day",
                html=response.text,
            )
            record = self.build_source_page_record(
                source=self.source_name,
                store_id=store.store_id,
                url=day_url,
                report_date=parsed_date,
                raw_path=raw_path,
                status_code=response.status_code,
                html=response.text,
            )
            collected.append(CollectedPage(record=record, raw_html=response.text))

        return collected

    def fetch_machine_pages(
        self,
        store: StoreDefinition,
        day_pages: list[CollectedPage],
        max_pages_per_day: Optional[int] = None,
    ) -> list[CollectedPage]:
        collected: list[CollectedPage] = []
        for day_page in day_pages:
            report_date = day_page.record.report_date or self._extract_date_from_url(
                day_page.record.url
            )
            if report_date is None:
                report_date = self.parser.peek_report_date(day_page.raw_html)
            if report_date is None:
                continue

            machine_urls = self.extract_machine_page_urls(
                day_page.raw_html,
                day_page.record.url,
                limit=max_pages_per_day,
            )
            for machine_url in machine_urls:
                machine_slug = self._machine_slug_from_url(machine_url)
                raw_path = self.raw_path_for(
                    store_id=store.store_id,
                    page_kind="machine",
                    report_date=report_date,
                    source_url=machine_url,
                    machine_slug=machine_slug,
                )
                if raw_path.exists():
                    html = raw_path.read_text(encoding="utf-8")
                    collected.append(
                        self._build_cached_page(
                            store_id=store.store_id,
                            url=machine_url,
                            report_date=report_date,
                            raw_path=raw_path,
                            html=html,
                        )
                    )
                    continue

                response = self.ensure_success_response(self.get(machine_url), machine_url)
                raw_path = self.save_raw_html(
                    store_id=store.store_id,
                    report_date=report_date,
                    page_kind="machine",
                    html=response.text,
                    source_url=machine_url,
                    machine_slug=machine_slug,
                )
                record = self.build_source_page_record(
                    source=self.source_name,
                    store_id=store.store_id,
                    url=machine_url,
                    report_date=report_date,
                    raw_path=raw_path,
                    status_code=response.status_code,
                    html=response.text,
                )
                collected.append(CollectedPage(record=record, raw_html=response.text))

        return collected

    def save_raw_html(
        self,
        store_id: str,
        report_date: Optional[date],
        page_kind: str,
        html: str,
        source_url: str = "",
        machine_slug: str = "",
    ) -> Path:
        if not html.strip():
            raise CollectorError(f"Refusing to save empty HTML for {store_id} {page_kind}")
        path = self.raw_path_for(
            store_id=store_id,
            page_kind=page_kind,
            report_date=report_date,
            source_url=source_url,
            machine_slug=machine_slug,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    def raw_path_for(
        self,
        store_id: str,
        page_kind: str,
        report_date: Optional[date] = None,
        source_url: str = "",
        machine_slug: str = "",
    ) -> Path:
        directory = self.raw_root / self.source_name / store_id
        if page_kind == "store":
            store_slug = self._store_slug_from_url(source_url)
            if not store_slug:
                raise CollectorError(f"Could not derive store slug for {store_id}")
            return directory / f"store_{self._safe_token(store_slug)}.html"
        if report_date is None:
            raise CollectorError(f"report_date is required for {page_kind} page")
        if page_kind == "day":
            return directory / f"{report_date.isoformat()}_day.html"
        if page_kind == "machine":
            slug = machine_slug or self._machine_slug_from_url(source_url) or "unknown"
            return directory / f"{report_date.isoformat()}_machine_{self._safe_token(slug)}.html"
        raise CollectorError(f"Unsupported page_kind: {page_kind}")

    def build_store_search_url(self, store: StoreDefinition) -> str:
        return f"{self.base_url}/search/?query={quote(store.canonical_name)}"

    @staticmethod
    def extract_store_page_url(html: str, fallback_url: str = "") -> str:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = re.sub(r"\s+", "", anchor["href"])
            if "/hole/" in href:
                return urljoin("https://www.slorepo.com/", href).rstrip("/") + "/"
        if "/hole/" in fallback_url:
            return fallback_url.rstrip("/") + "/"
        return ""

    @staticmethod
    def extract_day_page_urls(html: str, store_url: str, limit: int) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not re.fullmatch(r"\d{8}/?", href):
                continue
            url = urljoin(store_url if store_url.endswith("/") else store_url + "/", href)
            url = url.rstrip("/") + "/"
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
        return urls

    @staticmethod
    def extract_machine_page_urls(
        html: str,
        day_url: str,
        limit: Optional[int] = None,
    ) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if "kishu/?kishu=" not in href:
                continue
            url = urljoin(day_url if day_url.endswith("/") else day_url + "/", href)
            if url not in urls:
                urls.append(url)
            if limit is not None and len(urls) >= limit:
                break
        return urls

    def _load_cached_store_page(self, store_id: str) -> Optional[CollectedPage]:
        directory = self.raw_root / self.source_name / store_id
        matches = sorted(directory.glob("store_*.html"))
        if not matches:
            return None
        raw_path = matches[0]
        html = raw_path.read_text(encoding="utf-8")
        store_slug = raw_path.stem.removeprefix("store_")
        url = f"{self.base_url}/hole/{store_slug}/"
        return self._build_cached_page(
            store_id=store_id,
            url=url,
            report_date=None,
            raw_path=raw_path,
            html=html,
        )

    def _build_cached_page(
        self,
        store_id: str,
        url: str,
        report_date: Optional[date],
        raw_path: Path,
        html: str,
    ) -> CollectedPage:
        record = self.build_source_page_record(
            source=self.source_name,
            store_id=store_id,
            url=url,
            report_date=report_date,
            raw_path=raw_path,
            status_code=None,
            html=html,
        )
        return CollectedPage(record=record, raw_html=html)

    @staticmethod
    def _extract_date_from_url(url: str) -> Optional[date]:
        match = re.search(r"(20\d{2})(\d{2})(\d{2})", url or "")
        if not match:
            return None
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    @staticmethod
    def _store_slug_from_url(url: str) -> str:
        match = re.search(r"/hole/([^/]+)/?", url or "")
        return match.group(1) if match else ""

    @staticmethod
    def _machine_slug_from_url(url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        values = query.get("kishu")
        return values[0] if values else ""

    @staticmethod
    def _safe_token(value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        text = text.strip("._-")
        return text or "unknown"
