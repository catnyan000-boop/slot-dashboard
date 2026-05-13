from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseParser(ABC):
    source_name = "base"

    @abstractmethod
    def peek_report_date(self, html: str) -> Optional[object]:
        raise NotImplementedError

    @abstractmethod
    def parse_detail_page(self, html: str, store_id: str, source_url: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def parse_unit_page(self, html: str, store_id: str, source_url: str) -> Any:
        raise NotImplementedError

    def parse_unit_detail_page(self, html: str, source_url: str) -> Any:
        raise NotImplementedError
