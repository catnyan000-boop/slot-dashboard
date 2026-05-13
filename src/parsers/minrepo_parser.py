from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional

from bs4 import BeautifulSoup, Tag

from src.collectors.minrepo_collector import MinrepoCollector
from src.db.database import utc_now_iso
from src.db.models import DailyStoreResultRecord, MachineResultRecord, UnitResultRecord
from src.normalizers.machine_normalizer import MachineNormalizer
from src.parsers.base_parser import BaseParser

MISSING_TOKENS = {"", "-", "--", "---", "----", "N/A", "n/a", "NA", "－", "ー"}


def _clean_number(value: str) -> Optional[float]:
    text = (value or "").strip()
    if text in MISSING_TOKENS:
        return None
    text = text.replace(",", "")
    text = text.replace("＋", "+").replace("+", "")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-").replace("－", "-")
    text = text.replace("▲", "-").replace("△", "-")
    if text in MISSING_TOKENS or re.fullmatch(r"-+", text or ""):
        return None
    if text.endswith("%"):
        text = text[:-1]
    if not re.search(r"\d", text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_int(value: str) -> Optional[int]:
    number = _clean_number(value)
    return int(number) if number is not None else None


def _parse_ratio(value: str) -> tuple[Optional[float], Optional[int]]:
    match = re.search(r"(\d+)\s*/\s*(\d+)", value or "")
    if not match:
        return None, None
    numerator = int(match.group(1))
    denominator = int(match.group(2))
    if denominator == 0:
        return None, 0
    return numerator / denominator, denominator


class MinrepoParser(BaseParser):
    source_name = "minrepo"

    def peek_report_date(self, html: str) -> Optional[date]:
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.find("h1")
        if not h1:
            return None
        h1_text = h1.get_text(" ", strip=True)
        h1_match = re.search(r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})\(", h1_text)
        if not h1_match:
            return None

        all_text = soup.get_text("\n", strip=True)
        publish_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", all_text)
        year = int(h1_match.group(1)) if h1_match.group(1) else None
        month = int(h1_match.group(2))
        day_value = int(h1_match.group(3))
        if year is None:
            year = int(publish_match.group(1)) if publish_match else date.today().year
            if publish_match:
                publish_month = int(publish_match.group(2))
                if publish_month == 1 and month == 12:
                    year -= 1
        return date(year, month, day_value)

    def parse_detail_page(
        self,
        html: str,
        store_id: str,
        source_url: str,
    ) -> tuple[DailyStoreResultRecord, list[MachineResultRecord]]:
        self._ensure_non_empty_html(html, source_url)
        soup = BeautifulSoup(html, "html.parser")
        report_date = self.peek_report_date(html)
        if report_date is None:
            raise ValueError("Could not extract report_date from Minrepo detail page.")

        text = soup.get_text("\n", strip=True)
        total_diff = self._extract_stat(text, r"総差枚\s*([+\-−]?\d[\d,]*)", as_int=True)
        avg_diff = self._extract_stat(text, r"平均差枚\s*([+\-−]?\d[\d,]*)")
        avg_game = self._extract_stat(text, r"平均G数\s*([\d,]+)")
        win_rate_value = self._extract_raw(text, r"勝率\s*([0-9]+\s*/\s*[0-9]+)")
        win_rate, total_units = _parse_ratio(win_rate_value or "")

        daily_record = DailyStoreResultRecord(
            source=self.source_name,
            store_id=store_id,
            report_date=report_date,
            total_diff=total_diff,
            avg_diff=avg_diff,
            avg_game=avg_game,
            win_rate=win_rate,
            total_units=total_units,
            source_url=source_url,
            created_at=utc_now_iso(),
        )

        machine_records: list[MachineResultRecord] = []
        machine_records.extend(
            self._parse_machine_section(
                soup=soup,
                store_id=store_id,
                report_date=report_date,
                source_url=source_url,
                heading_keyword="機種別データ",
                variety_mode=False,
            )
        )
        machine_records.extend(
            self._parse_machine_section(
                soup=soup,
                store_id=store_id,
                report_date=report_date,
                source_url=source_url,
                heading_keyword="バラエティ",
                variety_mode=True,
            )
        )
        return daily_record, machine_records

    def parse_unit_page(
        self,
        html: str,
        store_id: str,
        source_url: str,
    ) -> list[UnitResultRecord]:
        self._ensure_non_empty_html(html, source_url)
        soup = BeautifulSoup(html, "html.parser")
        report_date = self.peek_report_date(html)
        if report_date is None:
            raise ValueError("Could not extract report_date from Minrepo unit page.")

        table = self._find_table_after_heading(soup, "全台")
        if table is None:
            return []

        records: list[UnitResultRecord] = []
        for row in self._iter_table_rows(table):
            if len(row) < 5 or row[0] == "機種":
                continue
            name, unit_number, diff, games, payout = row[:5]
            normalized_name = MachineNormalizer.normalize_name(name)
            machine_category = MachineNormalizer.categorize_machine(normalized_name)
            diff_value = _clean_number(diff)
            games_value = _clean_number(games)
            payout_value = _clean_number(payout)
            records.append(
                UnitResultRecord(
                    source=self.source_name,
                    store_id=store_id,
                    report_date=report_date,
                    unit_number=unit_number.strip(),
                    machine_name_raw=name,
                    machine_name_normalized=normalized_name,
                    machine_category=machine_category,
                    diff=diff_value,
                    games=games_value,
                    payout_rate=payout_value,
                    bb=None,
                    rb=None,
                    diff_source="unit_list_page" if diff_value is not None else None,
                    games_source="unit_list_page" if games_value is not None else None,
                    payout_rate_source="unit_list_page" if payout_value is not None else None,
                    detail_url=MinrepoCollector.build_unit_detail_url(
                        source_url,
                        unit_number.strip(),
                    ),
                    source_url=source_url,
                    created_at=utc_now_iso(),
                )
            )
        return records

    def parse_unit_detail_page(self, html: str, source_url: str) -> dict[str, object]:
        self._ensure_non_empty_html(html, source_url)
        soup = BeautifulSoup(html, "html.parser")
        report_date = self.peek_report_date(html)
        if report_date is None:
            raise ValueError(f"Could not extract report_date from unit detail page: {source_url}")
        h1 = soup.find("h1")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        first_table = soup.find("table")
        if first_table is None:
            raise ValueError(f"Could not find detail table in unit detail page: {source_url}")
        rows = list(self._iter_table_rows(first_table)) if first_table else []

        machine_name = ""
        diff = None
        games = None
        payout_rate = None
        if len(rows) >= 2 and len(rows[1]) >= 4:
            machine_name, diff_raw, games_raw, payout_raw = rows[1][:4]
            diff = _clean_number(diff_raw)
            games = _clean_number(games_raw)
            payout_rate = _clean_number(payout_raw)
        if not machine_name and diff is None and games is None and payout_rate is None:
            raise ValueError(f"Could not parse unit detail values from {source_url}")

        return {
            "report_date": report_date.isoformat() if report_date else None,
            "title": title,
            "h1": h1.get_text(" ", strip=True) if h1 else "",
            "machine_name": machine_name,
            "diff": diff,
            "games": games,
            "payout_rate": payout_rate,
            "table_count": len(soup.find_all("table")),
        }

    @staticmethod
    def _ensure_non_empty_html(html: str, source_url: str) -> None:
        if not html.strip():
            raise ValueError(f"Empty HTML for {source_url}")

    def _parse_machine_section(
        self,
        soup: BeautifulSoup,
        store_id: str,
        report_date: date,
        source_url: str,
        heading_keyword: str,
        variety_mode: bool,
    ) -> list[MachineResultRecord]:
        table = self._find_table_after_heading(soup, heading_keyword)
        if table is None:
            return []

        records: list[MachineResultRecord] = []
        for row in self._iter_table_rows(table):
            if not row or row[0] == "機種":
                continue
            if variety_mode:
                if len(row) < 5:
                    continue
                name, unit_number, diff, games, _ = row[:5]
                normalized_name = MachineNormalizer.normalize_name(name)
                records.append(
                    MachineResultRecord(
                        source=self.source_name,
                        store_id=store_id,
                        report_date=report_date,
                        machine_name_raw=name,
                        machine_name_normalized=normalized_name,
                        machine_category=MachineNormalizer.categorize_machine(
                            normalized_name, unit_count=1
                        ),
                        unit_count=1,
                        total_diff=_clean_number(diff),
                        avg_diff=_clean_number(diff),
                        avg_game=_clean_number(games),
                        win_rate=1.0 if (_clean_number(diff) or 0) > 0 else 0.0,
                        source_url=source_url,
                        created_at=utc_now_iso(),
                    )
                )
            else:
                if len(row) < 5:
                    continue
                name, avg_diff, avg_game, win_rate_raw, _ = row[:5]
                win_rate, unit_count = _parse_ratio(win_rate_raw)
                normalized_name = MachineNormalizer.normalize_name(name)
                avg_diff_value = _clean_number(avg_diff)
                records.append(
                    MachineResultRecord(
                        source=self.source_name,
                        store_id=store_id,
                        report_date=report_date,
                        machine_name_raw=name,
                        machine_name_normalized=normalized_name,
                        machine_category=MachineNormalizer.categorize_machine(
                            normalized_name, unit_count=unit_count
                        ),
                        unit_count=unit_count or 0,
                        total_diff=(avg_diff_value or 0.0) * (unit_count or 0),
                        avg_diff=avg_diff_value,
                        avg_game=_clean_number(avg_game),
                        win_rate=win_rate,
                        source_url=source_url,
                        created_at=utc_now_iso(),
                    )
                )
        return records

    @staticmethod
    def _extract_raw(text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    @classmethod
    def _extract_stat(cls, text: str, pattern: str, as_int: bool = False) -> Optional[float]:
        raw = cls._extract_raw(text, pattern)
        if raw is None:
            return None
        return _clean_int(raw) if as_int else _clean_number(raw)

    @staticmethod
    def _find_table_after_heading(soup: BeautifulSoup, keyword: str) -> Optional[Tag]:
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            if keyword in heading.get_text(" ", strip=True):
                table = heading.find_next("table")
                if table:
                    return table
        return None

    @staticmethod
    def _iter_table_rows(table: Tag) -> Iterable[list[str]]:
        for row in table.find_all("tr"):
            columns = row.find_all(["td", "th"])
            yield [column.get_text(" ", strip=True) for column in columns]
