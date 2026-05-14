from __future__ import annotations

import re
from datetime import date
from typing import Iterable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

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


class SlorepoParser(BaseParser):
    source_name = "slorepo"

    def peek_report_date(self, html: str) -> Optional[date]:
        soup = BeautifulSoup(html, "html.parser")
        candidate_texts = []
        if soup.title:
            candidate_texts.append(soup.title.get_text(" ", strip=True))
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            candidate_texts.append(heading.get_text(" ", strip=True))
        candidate_texts.append(soup.get_text("\n", strip=True))

        for text in candidate_texts:
            full_date = self._extract_full_date(text)
            if full_date is not None:
                return full_date

        all_text = soup.get_text("\n", strip=True)
        month_day_match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*(?:\(|（)", all_text)
        if not month_day_match:
            return None
        year = self._extract_year(all_text)
        if year is None:
            return None
        return date(year, int(month_day_match.group(1)), int(month_day_match.group(2)))

    def parse_detail_page(
        self,
        html: str,
        store_id: str,
        source_url: str,
    ) -> tuple[DailyStoreResultRecord, list[MachineResultRecord]]:
        self._ensure_non_empty_html(html, source_url)
        soup = BeautifulSoup(html, "html.parser")
        report_date = self.peek_report_date(html) or self._extract_date_from_url(source_url)
        if report_date is None:
            raise ValueError(
                f"Could not extract report_date from Slorepo detail page: {source_url}"
            )

        text = soup.get_text("\n", strip=True)
        total_diff = self._extract_stat(text, [r"総差枚\s*([+\-−▲△]?\d[\d,]*)"], as_int=True)
        avg_diff = self._extract_stat(text, [r"平均差枚\s*([+\-−▲△]?\d[\d,]*)"])
        avg_game = self._extract_stat(text, [r"平均G数\s*([\d,]+)", r"平均ゲーム数\s*([\d,]+)"])
        win_rate, total_units = self._extract_win_rate_and_units(text)
        if total_units is None:
            total_units = self._extract_stat(
                text,
                [r"総台数\s*([\d,]+)", r"設置台数\s*([\d,]+)", r"台数\s*([\d,]+)"],
                as_int=True,
            )

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
        table = self._find_machine_table(soup)
        if table is not None:
            for row in self._iter_table_rows_with_cells(table):
                headers = row["headers"]
                values = row["values"]
                cells = row["cells"]
                if not headers or len(values) != len(headers):
                    continue
                column_map = self._build_column_map(headers)
                name_index = column_map.get("machine_name")
                if name_index is None or name_index >= len(values):
                    continue

                machine_name = values[name_index].strip()
                if not machine_name or machine_name == "機種":
                    continue

                normalized_name = MachineNormalizer.normalize_name(machine_name)
                total_diff_value = self._value_by_key(values, column_map, "total_diff")
                avg_diff_value = self._value_by_key(values, column_map, "avg_diff")
                avg_game_value = self._value_by_key(values, column_map, "avg_game")
                unit_count = self._unit_count_from_row(values, column_map)
                win_rate_value = self._win_rate_from_row(values, column_map)
                machine_url = self._machine_url_from_cell(cells[name_index], source_url)

                machine_records.append(
                    MachineResultRecord(
                        source=self.source_name,
                        store_id=store_id,
                        report_date=report_date,
                        machine_name_raw=machine_name,
                        machine_name_normalized=normalized_name,
                        machine_category=MachineNormalizer.categorize_machine(
                            normalized_name,
                            unit_count=unit_count if unit_count > 0 else None,
                        ),
                        unit_count=unit_count,
                        total_diff=total_diff_value,
                        avg_diff=avg_diff_value,
                        avg_game=avg_game_value,
                        win_rate=win_rate_value,
                        source_url=machine_url or source_url,
                        created_at=utc_now_iso(),
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
        report_date = self.peek_report_date(html) or self._extract_date_from_url(source_url)
        if report_date is None:
            raise ValueError(f"Could not extract report_date from Slorepo unit page: {source_url}")

        machine_name_raw = self._extract_machine_name(soup, report_date)
        machine_name_normalized = MachineNormalizer.normalize_name(machine_name_raw)

        table = self._find_unit_table(soup)
        if table is None:
            return []

        records: list[UnitResultRecord] = []
        for row in self._iter_table_rows_with_cells(table):
            headers = row["headers"]
            values = row["values"]
            if not headers or len(values) != len(headers):
                continue
            column_map = self._build_column_map(headers)
            unit_index = column_map.get("unit_number")
            if unit_index is None or unit_index >= len(values):
                continue

            unit_number = values[unit_index].strip()
            if not unit_number or unit_number == "台番":
                continue

            records.append(
                UnitResultRecord(
                    source=self.source_name,
                    store_id=store_id,
                    report_date=report_date,
                    unit_number=unit_number,
                    machine_name_raw=machine_name_raw,
                    machine_name_normalized=machine_name_normalized,
                    machine_category=MachineNormalizer.categorize_machine(machine_name_normalized),
                    diff=self._value_by_key(values, column_map, "diff"),
                    games=self._value_by_key(values, column_map, "games"),
                    payout_rate=self._value_by_key(values, column_map, "payout_rate"),
                    bb=self._int_by_key(values, column_map, "bb"),
                    rb=self._int_by_key(values, column_map, "rb"),
                    source_url=source_url,
                    created_at=utc_now_iso(),
                )
            )

        return records

    @staticmethod
    def _ensure_non_empty_html(html: str, source_url: str) -> None:
        if not html.strip():
            raise ValueError(f"Empty HTML for {source_url}")

    @staticmethod
    def _extract_full_date(text: str) -> Optional[date]:
        patterns = [
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None

    @staticmethod
    def _extract_year(text: str) -> Optional[int]:
        match = re.search(r"(20\d{2})年", text)
        if match:
            return int(match.group(1))
        match = re.search(r"(20\d{2})[/-]\d{1,2}[/-]\d{1,2}", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_date_from_url(source_url: str) -> Optional[date]:
        match = re.search(r"(20\d{2})(\d{2})(\d{2})", source_url or "")
        if not match:
            return None
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    @classmethod
    def _extract_raw(cls, text: str, patterns: list[str]) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    @classmethod
    def _extract_stat(cls, text: str, patterns: list[str], as_int: bool = False) -> Optional[float]:
        raw = cls._extract_raw(text, patterns)
        if raw is None:
            return None
        return _clean_int(raw) if as_int else _clean_number(raw)

    @classmethod
    def _extract_win_rate_and_units(cls, text: str) -> tuple[Optional[float], Optional[int]]:
        raw = cls._extract_raw(text, [r"勝率\s*([0-9]+\s*/\s*[0-9]+)", r"勝率\s*([\d.]+%)"])
        if raw is None:
            return None, None
        ratio_value, total_units = _parse_ratio(raw)
        if ratio_value is not None:
            return ratio_value, total_units
        percent_value = _clean_number(raw)
        if percent_value is None:
            return None, None
        return percent_value / 100.0, None

    @staticmethod
    def _find_machine_table(soup: BeautifulSoup) -> Optional[Tag]:
        for table in soup.find_all("table"):
            headers = SlorepoParser._table_headers(table)
            joined = " ".join(headers)
            if "機種" in joined and any(
                token in joined for token in ["平均差枚", "平均G数", "勝率", "台数"]
            ):
                return table
            if table.find("a", href=re.compile(r"kishu/\?kishu=")):
                return table
        return None

    @staticmethod
    def _find_unit_table(soup: BeautifulSoup) -> Optional[Tag]:
        for table in soup.find_all("table"):
            headers = SlorepoParser._table_headers(table)
            joined = " ".join(headers)
            if "台番" not in joined:
                continue
            if any(token in joined for token in ["差枚", "G数", "出率", "BB", "RB", "合成"]):
                return table
        return None

    @staticmethod
    def _table_headers(table: Tag) -> list[str]:
        header_row = table.find("tr")
        if header_row is None:
            return []
        return [cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"])]

    @staticmethod
    def _iter_table_rows_with_cells(table: Tag) -> Iterable[dict[str, list]]:
        header_row = table.find("tr")
        if header_row is None:
            return
        headers = [cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"])]
        for row in header_row.find_next_siblings("tr"):
            cells = row.find_all(["td", "th"])
            values = [cell.get_text(" ", strip=True) for cell in cells]
            yield {"headers": headers, "values": values, "cells": cells}

    @staticmethod
    def _normalize_header(header: str) -> str:
        text = MachineNormalizer.normalize_name(header)
        return text.replace(" ", "")

    @classmethod
    def _build_column_map(cls, headers: list[str]) -> dict[str, int]:
        column_map: dict[str, int] = {}
        for index, header in enumerate(headers):
            normalized = cls._normalize_header(header)
            if normalized in {"機種", "機種名"}:
                column_map["machine_name"] = index
            elif normalized in {"台番", "台番号"}:
                column_map["unit_number"] = index
            elif normalized in {"差枚", "平均差枚"}:
                column_map["avg_diff" if "平均" in normalized else "diff"] = index
            elif normalized in {"総差枚"}:
                column_map["total_diff"] = index
            elif normalized in {"G数", "ゲーム数", "回転数", "総回転数"}:
                column_map["games"] = index
            elif normalized in {"平均G数", "平均ゲーム数", "平均回転数"}:
                column_map["avg_game"] = index
            elif normalized in {"出率", "機械割"}:
                column_map["payout_rate"] = index
            elif normalized in {"勝率"}:
                column_map["win_rate"] = index
            elif normalized in {"台数", "設置台数"}:
                column_map["unit_count"] = index
            elif normalized in {"BB", "BIG"}:
                column_map["bb"] = index
            elif normalized in {"RB", "REG"}:
                column_map["rb"] = index
            elif normalized in {"合成", "合算"}:
                column_map["combined"] = index
        return column_map

    @staticmethod
    def _machine_url_from_cell(cell: Tag, source_url: str) -> str:
        anchor = cell.find("a", href=True)
        if not anchor:
            return ""
        href = anchor["href"].strip()
        if not href:
            return ""
        return urljoin(source_url if source_url.endswith("/") else source_url + "/", href)

    @staticmethod
    def _value_by_key(values: list[str], column_map: dict[str, int], key: str) -> Optional[float]:
        index = column_map.get(key)
        if index is None or index >= len(values):
            return None
        return _clean_number(values[index])

    @staticmethod
    def _int_by_key(values: list[str], column_map: dict[str, int], key: str) -> Optional[int]:
        index = column_map.get(key)
        if index is None or index >= len(values):
            return None
        return _clean_int(values[index])

    @classmethod
    def _unit_count_from_row(cls, values: list[str], column_map: dict[str, int]) -> int:
        explicit = cls._int_by_key(values, column_map, "unit_count")
        if explicit is not None:
            return explicit
        index = column_map.get("win_rate")
        if index is None or index >= len(values):
            return 0
        _, denominator = _parse_ratio(values[index])
        return denominator or 0

    @classmethod
    def _win_rate_from_row(cls, values: list[str], column_map: dict[str, int]) -> Optional[float]:
        index = column_map.get("win_rate")
        if index is None or index >= len(values):
            return None
        raw = values[index]
        ratio_value, _ = _parse_ratio(raw)
        if ratio_value is not None:
            return ratio_value
        percent_value = _clean_number(raw)
        if percent_value is None:
            return None
        return percent_value / 100.0

    @classmethod
    def _extract_machine_name(cls, soup: BeautifulSoup, report_date: date) -> str:
        for tag_name in ["h1", "h2", "title"]:
            tag = soup.find(tag_name)
            if tag is None:
                continue
            text = cls._strip_machine_name_noise(tag.get_text(" ", strip=True), report_date)
            if text:
                return text
        return ""

    @staticmethod
    def _strip_machine_name_noise(text: str, report_date: date) -> str:
        cleaned = MachineNormalizer.normalize_name(text)
        patterns = [
            report_date.strftime("%Y/%m/%d"),
            report_date.strftime("%Y/%-m/%-d"),
            report_date.strftime("%Y-%m-%d"),
            report_date.strftime("%Y年%-m月%-d日"),
        ]
        for pattern in patterns:
            cleaned = cleaned.replace(pattern, " ")
        cleaned = re.sub(r"\d{4}/\d{1,2}/\d{1,2}\s*[（(][^)）]+[)）]", " ", cleaned)
        cleaned = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日\s*[（(][^)）]+[)）]", " ", cleaned)
        cleaned = re.sub(r"\b(?:台データ|データ一覧|スランプグラフ|差枚情報)\b", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" |-:/")
        return cleaned
