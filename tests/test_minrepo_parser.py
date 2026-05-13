from datetime import date
from pathlib import Path

import pytest

from src.collectors.base_collector import CollectorError
from src.collectors.minrepo_collector import MinrepoCollector
from src.db.database import Database, utc_now_iso
from src.db.models import DailyStoreResultRecord, SourcePageRecord
from src.parsers.minrepo_parser import MinrepoParser

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_parser_extracts_data_from_saved_html() -> None:
    parser = MinrepoParser()
    detail_html = (PROJECT_ROOT / "tests" / "fixtures" / "minrepo_detail.html").read_text(
        encoding="utf-8"
    )
    units_html = (PROJECT_ROOT / "tests" / "fixtures" / "minrepo_units.html").read_text(
        encoding="utf-8"
    )

    daily_record, machine_records = parser.parse_detail_page(
        html=detail_html,
        store_id="cosmo_obu",
        source_url="https://example.com/detail",
    )
    unit_records = parser.parse_unit_page(
        html=units_html,
        store_id="cosmo_obu",
        source_url="https://example.com/detail?kishu=all",
    )

    assert daily_record.report_date == date(2026, 5, 10)
    assert daily_record.total_diff == 12345
    assert daily_record.avg_game == 4567
    assert len(machine_records) == 3
    assert len(unit_records) == 3
    assert machine_records[0].machine_category == "smart_slot_at"


def test_parser_parses_negative_and_comma_numbers() -> None:
    parser = MinrepoParser()
    html = """
    <html><body>
      <h1>2026/5/10(土) テスト店</h1>
      <div>2026年5月11日</div>
      <h2>全台 データ一覧</h2>
      <table>
        <tr><th>機種</th><th>台番</th><th>差枚</th><th>G数</th><th>出率</th></tr>
        <tr><td>マイジャグラーV</td><td>101</td><td>-1,234</td><td>6,789</td><td>98.1%</td></tr>
      </table>
    </body></html>
    """
    rows = parser.parse_unit_page(
        html=html,
        store_id="cosmo_obu",
        source_url="https://example.com/test",
    )
    assert rows[0].diff == -1234
    assert rows[0].games == 6789
    assert rows[0].payout_rate == 98.1


def test_parser_supports_unicode_minus_variants() -> None:
    parser = MinrepoParser()
    html = """
    <html><body>
      <h1>2026/5/10(土) テスト店</h1>
      <div>2026年5月11日</div>
      <h2>全台 データ一覧</h2>
      <table>
        <tr><th>機種</th><th>台番</th><th>差枚</th><th>G数</th><th>出率</th></tr>
        <tr><td>機種A</td><td>101</td><td>−1,500</td><td>1,000</td><td>95.0%</td></tr>
        <tr><td>機種B</td><td>102</td><td>▲1,500</td><td>2,000</td><td>94.0%</td></tr>
        <tr><td>機種C</td><td>103</td><td>0</td><td>3,000</td><td>100.0%</td></tr>
        <tr><td>機種D</td><td>104</td><td>-</td><td>4,000</td><td>-</td></tr>
      </table>
    </body></html>
    """
    rows = parser.parse_unit_page(html=html, store_id="cosmo_obu", source_url="https://example.com")
    assert rows[0].diff == -1500
    assert rows[1].diff == -1500
    assert rows[2].diff == 0
    assert rows[3].diff is None
    assert rows[3].payout_rate is None


def test_parser_raises_for_empty_html() -> None:
    parser = MinrepoParser()
    with pytest.raises(ValueError, match="Empty HTML"):
        parser.parse_detail_page("", "cosmo_obu", "https://example.com/detail")


def test_db_does_not_insert_duplicate_daily_rows(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")

    record = DailyStoreResultRecord(
        source="minrepo",
        store_id="cosmo_obu",
        report_date=date(2026, 5, 10),
        total_diff=100,
        avg_diff=10,
        avg_game=2000,
        win_rate=0.5,
        total_units=10,
        source_url="https://example.com/detail",
        created_at=utc_now_iso(),
    )
    database.upsert_daily_store_result(record)
    database.upsert_daily_store_result(record)

    result = database.query_dataframe("SELECT COUNT(*) AS count FROM daily_store_results")
    assert int(result.iloc[0]["count"]) == 1


def test_db_does_not_insert_duplicate_source_pages(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")

    record = SourcePageRecord(
        source="minrepo",
        store_id="cosmo_obu",
        url="https://example.com/detail",
        report_date=date(2026, 5, 10),
        raw_path="/tmp/test.html",
        fetched_at=utc_now_iso(),
        status_code=200,
        content_hash="abc",
    )
    database.upsert_source_page(record)
    database.upsert_source_page(record)

    result = database.query_dataframe("SELECT COUNT(*) AS count FROM source_pages")
    assert int(result.iloc[0]["count"]) == 1


class _FakeResponse:
    def __init__(self, status_code: int, text: str, url: str):
        self.status_code = status_code
        self.text = text
        self.url = url


def test_http_403_404_are_not_treated_as_success() -> None:
    with pytest.raises(CollectorError, match="HTTP 403"):
        MinrepoCollector.ensure_success_response(
            _FakeResponse(403, "forbidden", "https://example.com/403"),
            "https://example.com/403",
        )
    with pytest.raises(CollectorError, match="HTTP 404"):
        MinrepoCollector.ensure_success_response(
            _FakeResponse(404, "missing", "https://example.com/404"),
            "https://example.com/404",
        )
