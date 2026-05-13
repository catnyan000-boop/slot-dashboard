from __future__ import annotations

from datetime import date
from pathlib import Path

from src.collectors.minrepo_collector import MinrepoCollector
from src.collectors.unit_detail_filler import (
    fill_missing_unit_details,
    unit_detail_raw_path,
)
from src.db.database import Database, utc_now_iso
from src.db.models import UnitResultRecord
from src.parsers.minrepo_parser import MinrepoParser

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, text: str, url: str, status_code: int = 200):
        self.text = text
        self.url = url
        self.status_code = status_code


class _FakeCollector:
    source_name = "minrepo"

    def __init__(self, html_by_url: dict[str, str] | None = None):
        self.html_by_url = html_by_url or {}
        self.requested_urls: list[str] = []

    def get(self, url: str):
        self.requested_urls.append(url)
        html = self.html_by_url[url]
        return _FakeResponse(html, url)

    @staticmethod
    def ensure_success_response(response, url: str, allow_redirect: bool = True):
        return response


def _init_db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    return database


def _insert_missing_row(database: Database, *, diff=None, games=None, payout_rate=None) -> None:
    database.upsert_unit_results(
        [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 13),
                unit_number="1373",
                machine_name_raw="Lパチスロ革命機ヴァルヴレイヴ2",
                machine_name_normalized="Lパチスロ革命機ヴァルヴレイヴ2",
                machine_category="smart_slot_at",
                diff=diff,
                games=games,
                payout_rate=payout_rate,
                diff_source="unit_list_page" if diff is not None else None,
                games_source="unit_list_page" if games is not None else None,
                payout_rate_source="unit_list_page" if payout_rate is not None else None,
                source_url="https://min-repo.com/3099785/?kishu=all",
                created_at=utc_now_iso(),
            )
        ]
    )


def test_detail_url_is_generated_correctly() -> None:
    assert (
        MinrepoCollector.build_unit_detail_url("https://min-repo.com/3099785/?kishu=all", "1373")
        == "https://min-repo.com/3099785/?num=1373"
    )


def test_parser_extracts_unit_detail_values() -> None:
    parser = MinrepoParser()
    html = """
    <html><body>
      <h1>2026/5/13(水) コスモジャパン大府店</h1>
      <div>2026年5月14日</div>
      <table>
        <tr><th>機種</th><th>差枚</th><th>G数</th><th>出率</th></tr>
        <tr><td>機種A</td><td>▲1,500</td><td>6,626</td><td>98.6%</td></tr>
      </table>
    </body></html>
    """
    parsed = parser.parse_unit_detail_page(html=html, source_url="https://example.com/?num=1")
    assert parsed["diff"] == -1500
    assert parsed["games"] == 6626
    assert parsed["payout_rate"] == 98.6


def test_max_pages_is_not_exceeded(tmp_path: Path) -> None:
    database = _init_db(tmp_path)
    for unit_number in ["101", "102", "103"]:
        database.upsert_unit_results(
            [
                UnitResultRecord(
                    source="minrepo",
                    store_id="cosmo_obu",
                    report_date=date(2026, 5, 13),
                    unit_number=unit_number,
                    machine_name_raw="機種A",
                    machine_name_normalized=f"機種A-{unit_number}",
                    machine_category="other",
                    diff=None,
                    games=1000.0,
                    payout_rate=None,
                    source_url="https://min-repo.com/3099785/?kishu=all",
                    created_at=utc_now_iso(),
                )
            ]
        )
    html = """
    <html><body><h1>2026/5/13(水) コスモジャパン大府店</h1><div>2026年5月14日</div>
    <table><tr><th>機種</th><th>差枚</th><th>G数</th><th>出率</th></tr>
    <tr><td>機種A</td><td>1,000</td><td>2,000</td><td>110.0%</td></tr></table></body></html>
    """
    collector = _FakeCollector(
        {
            "https://min-repo.com/3099785/?num=101": html,
            "https://min-repo.com/3099785/?num=102": html,
            "https://min-repo.com/3099785/?num=103": html,
        }
    )
    summary = fill_missing_unit_details(
        database=database,
        collector=collector,  # type: ignore[arg-type]
        parser=MinrepoParser(),
        raw_root=tmp_path / "raw",
        store_id="cosmo_obu",
        days=7,
        max_pages=2,
    )
    assert summary.fetched_pages == 2
    assert summary.skipped_due_to_limit == 1
    assert len(collector.requested_urls) == 2


def test_saved_html_is_not_refetched(tmp_path: Path) -> None:
    database = _init_db(tmp_path)
    _insert_missing_row(database, diff=None, games=None, payout_rate=None)
    raw_path = unit_detail_raw_path(
        raw_root=tmp_path / "raw",
        source="minrepo",
        store_id="cosmo_obu",
        report_date=date(2026, 5, 13),
        unit_number="1373",
    )
    raw_path.write_text(
        """
        <html><body><h1>2026/5/13(水) コスモジャパン大府店</h1><div>2026年5月14日</div>
        <table><tr><th>機種</th><th>差枚</th><th>G数</th><th>出率</th></tr>
        <tr><td>機種A</td><td>18,372</td><td>6,626</td><td>192.4%</td></tr></table></body></html>
        """,
        encoding="utf-8",
    )
    collector = _FakeCollector({})
    summary = fill_missing_unit_details(
        database=database,
        collector=collector,  # type: ignore[arg-type]
        parser=MinrepoParser(),
        raw_root=tmp_path / "raw",
        store_id="cosmo_obu",
        days=7,
        max_pages=5,
    )
    assert summary.cached_pages == 1
    assert summary.fetched_pages == 0
    assert collector.requested_urls == []


def test_parse_failed_sets_status(tmp_path: Path) -> None:
    database = _init_db(tmp_path)
    _insert_missing_row(database, diff=None, games=None, payout_rate=None)
    collector = _FakeCollector({"https://min-repo.com/3099785/?num=1373": "<html></html>"})
    summary = fill_missing_unit_details(
        database=database,
        collector=collector,  # type: ignore[arg-type]
        parser=MinrepoParser(),
        raw_root=tmp_path / "raw",
        store_id="cosmo_obu",
        days=7,
        max_pages=5,
    )
    row = database.query_dataframe(
        "SELECT detail_parse_status, detail_error FROM unit_results WHERE unit_number = '1373'"
    ).iloc[0]
    assert summary.parse_failed == 1
    assert row["detail_parse_status"] == "parse_failed"


def test_fill_sets_diff_source_to_unit_detail_page(tmp_path: Path) -> None:
    database = _init_db(tmp_path)
    _insert_missing_row(database, diff=None, games=None, payout_rate=None)
    html = """
    <html><body><h1>2026/5/13(水) コスモジャパン大府店</h1><div>2026年5月14日</div>
    <table><tr><th>機種</th><th>差枚</th><th>G数</th><th>出率</th></tr>
    <tr><td>機種A</td><td>18,372</td><td>6,626</td><td>192.4%</td></tr></table></body></html>
    """
    collector = _FakeCollector({"https://min-repo.com/3099785/?num=1373": html})
    fill_missing_unit_details(
        database=database,
        collector=collector,  # type: ignore[arg-type]
        parser=MinrepoParser(),
        raw_root=tmp_path / "raw",
        store_id="cosmo_obu",
        days=7,
        max_pages=5,
    )
    row = database.query_dataframe(
        "SELECT diff, games, payout_rate, diff_source FROM unit_results WHERE unit_number = '1373'"
    ).iloc[0]
    assert row["diff"] == 18372.0
    assert row["games"] == 6626.0
    assert row["payout_rate"] == 192.4
    assert row["diff_source"] == "unit_detail_page"


def test_existing_actual_value_is_not_overwritten(tmp_path: Path) -> None:
    database = _init_db(tmp_path)
    _insert_missing_row(database, diff=999.0, games=1111.0, payout_rate=None)
    html = """
    <html><body><h1>2026/5/13(水) コスモジャパン大府店</h1><div>2026年5月14日</div>
    <table><tr><th>機種</th><th>差枚</th><th>G数</th><th>出率</th></tr>
    <tr><td>機種A</td><td>18,372</td><td>6,626</td><td>192.4%</td></tr></table></body></html>
    """
    collector = _FakeCollector({"https://min-repo.com/3099785/?num=1373": html})
    fill_missing_unit_details(
        database=database,
        collector=collector,  # type: ignore[arg-type]
        parser=MinrepoParser(),
        raw_root=tmp_path / "raw",
        store_id="cosmo_obu",
        days=7,
        max_pages=5,
    )
    row = database.query_dataframe(
        """
        SELECT diff, games, payout_rate, diff_source, games_source, payout_rate_source
        FROM unit_results WHERE unit_number = '1373'
        """
    ).iloc[0]
    assert row["diff"] == 999.0
    assert row["games"] == 1111.0
    assert row["payout_rate"] == 192.4
    assert row["diff_source"] == "unit_list_page"
    assert row["games_source"] == "unit_list_page"
    assert row["payout_rate_source"] == "unit_detail_page"
