from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from src.db.database import utc_now_iso
from src.db.models import SourcePageRecord, StoreDefinition


@dataclass
class CollectedPage:
    record: SourcePageRecord
    raw_html: str


class CollectorError(RuntimeError):
    pass


class BaseCollector(ABC):
    source_name = "base"

    def __init__(
        self,
        raw_root: Path,
        base_url: str,
        request_delay_seconds: float = 1.5,
        timeout_seconds: int = 20,
        user_agent: str = "slot-store-analyzer/0.1 (+respectful public-data collector)",
    ) -> None:
        self.raw_root = raw_root
        self.base_url = base_url.rstrip("/")
        self.request_delay_seconds = request_delay_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._robots_text = self._load_robots_text()

    def _load_robots_text(self) -> Optional[str]:
        parsed = urlparse(self.base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            response = self.session.get(robots_url, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                return None
            return response.text
        except Exception:
            return None

    def can_fetch(self, url: str) -> bool:
        if not self._robots_text:
            return True
        path = urlparse(url).path or "/"
        explicit_disallow_rules: list[str] = []
        agent_tokens = {
            self.session.headers.get("User-Agent", "").lower(),
            "slot-store-analyzer",
            "*",
        }

        current_agent = None
        for raw_line in self._robots_text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, value = [part.strip() for part in line.split(":", 1)]
            field_lower = field.lower()
            value_lower = value.lower()

            if field_lower == "user-agent":
                current_agent = value_lower
                continue
            if field_lower == "disallow" and current_agent in agent_tokens and value:
                explicit_disallow_rules.append(value)

        return not any(path.startswith(rule) for rule in explicit_disallow_rules)

    def get(self, url: str) -> Optional[requests.Response]:
        if not self.can_fetch(url):
            return None
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_delay_seconds:
            time.sleep(self.request_delay_seconds - elapsed)
        response = self.session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        return response

    @staticmethod
    def ensure_success_response(
        response: Optional[requests.Response],
        url: str,
        allow_redirect: bool = True,
    ) -> requests.Response:
        if response is None:
            raise CollectorError(f"Blocked by robots.txt or no response for {url}")
        if response.status_code >= 400:
            raise CollectorError(f"HTTP {response.status_code} for {url}")
        if not allow_redirect and response.url.rstrip("/") != url.rstrip("/"):
            raise CollectorError(f"Unexpected redirect: {url} -> {response.url}")
        if not response.text.strip():
            raise CollectorError(f"Empty HTML returned for {url}")
        return response

    def save_raw_html(
        self,
        store_id: str,
        report_date: date,
        page_kind: str,
        html: str,
    ) -> Path:
        if not html.strip():
            raise CollectorError(
                f"Refusing to save empty HTML for {store_id} {report_date} {page_kind}"
            )
        directory = self.raw_root / self.source_name / store_id
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{report_date.isoformat()}_{page_kind}.html"
        path = directory / filename
        path.write_text(html, encoding="utf-8")
        return path

    @staticmethod
    def build_source_page_record(
        source: str,
        store_id: str,
        url: str,
        report_date: Optional[date],
        raw_path: Path,
        status_code: Optional[int],
        html: str,
    ) -> SourcePageRecord:
        return SourcePageRecord(
            source=source,
            store_id=store_id,
            url=url,
            report_date=report_date,
            raw_path=str(raw_path),
            fetched_at=utc_now_iso(),
            status_code=status_code,
            content_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        )

    @abstractmethod
    def fetch_store_history(self, store: StoreDefinition, days: int) -> list[CollectedPage]:
        raise NotImplementedError
