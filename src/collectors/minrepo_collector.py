from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse

from bs4 import BeautifulSoup

from src.db.models import StoreDefinition

from .base_collector import BaseCollector, CollectedPage


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
