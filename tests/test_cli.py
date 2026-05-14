from argparse import Namespace
from datetime import date
from pathlib import Path

from src.cli import (
    SourceProbe,
    cmd_debug_fetch_minrepo,
    cmd_debug_minrepo_entrypoints,
    cmd_debug_source_entrypoints,
    cmd_parse_minrepo,
    cmd_unit_coverage,
    cmd_validate_unit_data,
)
from src.collectors.base_collector import CollectorError
from src.collectors.minrepo_collector import (
    FetchDebugEntry,
    MinrepoCollector,
    StoreFetchDebugResult,
)
from src.db.database import Database, utc_now_iso
from src.db.models import SourcePageRecord, UnitResultRecord
from src.normalizers.store_normalizer import StoreNormalizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_empty_html_save_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MinrepoCollector, "_load_robots_text", lambda self: None)
    collector = MinrepoCollector(raw_root=tmp_path, base_url="https://min-repo.com")
    try:
        collector.save_raw_html("cosmo_obu", date(2026, 5, 10), "detail", "")
    except CollectorError as exc:
        assert "empty HTML" in str(exc)
    else:
        raise AssertionError("Expected CollectorError for empty HTML")


def test_parse_minrepo_warns_when_unit_results_are_zero(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    raw_path = tmp_path / "2026-05-10_units.html"
    raw_path.write_text(
        (
            "<html><body><h1>2026/5/10(土) コスモジャパン大府店</h1>"
            "<div>2026年5月11日</div></body></html>"
        ),
        encoding="utf-8",
    )
    database.upsert_source_page(
        SourcePageRecord(
            source="minrepo",
            store_id="cosmo_obu",
            url="https://example.com/detail?kishu=all",
            report_date=date(2026, 5, 10),
            raw_path=str(raw_path),
            fetched_at=utc_now_iso(),
            status_code=200,
            content_hash="hash",
        )
    )

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    result = cmd_parse_minrepo(Namespace(store="cosmo_obu", all=False))
    captured = capsys.readouterr()

    assert result == 0
    assert "warning: unit_results=0" in captured.out


def test_validate_unit_data_warns_when_diff_missing_rate_is_high(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    rows = [
        UnitResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 10),
            unit_number=str(i),
            machine_name_raw="機種A",
            machine_name_normalized="機種A",
            machine_category="other",
            diff=None if i < 8 else 100.0,
            games=1000.0,
            payout_rate=100.0,
            bb=None,
            rb=None,
            source_url="https://example.com",
            created_at=utc_now_iso(),
        )
        for i in range(10)
    ]
    database.upsert_unit_results(rows)

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    result = cmd_validate_unit_data(Namespace(store="cosmo_obu", all=False, days=7))
    captured = capsys.readouterr()
    assert result == 0
    assert "WARNING:" in captured.out


def test_unit_coverage_supports_all_stores(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    database.upsert_unit_results(
        [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 10),
                unit_number="1",
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=100.0,
                games=1000.0,
                payout_rate=100.0,
                bb=None,
                rb=None,
                source_url="https://example.com",
                created_at=utc_now_iso(),
            ),
            UnitResultRecord(
                source="minrepo",
                store_id="kyoraku_tokai",
                report_date=date(2026, 5, 10),
                unit_number="1",
                machine_name_raw="機種B",
                machine_name_normalized="機種B",
                machine_category="smart_slot_at",
                diff=None,
                games=1000.0,
                payout_rate=100.0,
                bb=None,
                rb=None,
                source_url="https://example.com",
                created_at=utc_now_iso(),
            ),
        ]
    )

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    result = cmd_unit_coverage(Namespace(store=None, all=True, days=7))
    captured = capsys.readouterr()

    assert result == 0
    assert "store_id: cosmo_obu" in captured.out
    assert "store_id: kyoraku_tokai" in captured.out
    assert "display_name: コスモジャパン大府" in captured.out
    assert "display_name: KYORAKU東海" in captured.out


def test_debug_fetch_minrepo_prints_failure_details(
    monkeypatch,
    capsys,
) -> None:
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    debug_result = StoreFetchDebugResult(
        store_id="cosmo_obu",
        store_display_name="コスモジャパン大府",
        canonical_name="コスモジャパン大府店",
        tag_base_url="https://min-repo.com/tag/%E3%82%B3%E3%82%B9%E3%83%A2/",
        user_agent="slot-store-analyzer/0.1 (+respectful public-data collector)",
        request_delay_seconds=2.0,
        existing_raw_files=["data/raw/minrepo/cosmo_obu/2026-05-13_detail.html"],
        debug_saved_files=["data/debug_raw/minrepo/cosmo_obu/tag_page_1.html"],
        tag_probe_entries=[
            FetchDebugEntry(
                stage="tag_probe",
                url="https://min-repo.com/tag/%E3%82%B3%E3%82%B9%E3%83%A2/",
                probe_name="current_session",
                request_mode="session",
                request_headers={"User-Agent": "slot-store-analyzer/0.1"},
                status_code=200,
                final_url="https://min-repo.com/tag/%E3%82%B3%E3%82%B9%E3%83%A2/",
                redirected=False,
                content_type="text/html; charset=UTF-8",
                response_size_bytes=0,
                first_300_chars="",
                title="",
                error_reason="Empty HTML returned",
            )
        ],
        entries=[
            FetchDebugEntry(
                stage="tag_page",
                url="https://min-repo.com/tag/%E3%82%B3%E3%82%B9%E3%83%A2/",
                status_code=403,
                final_url="https://min-repo.com/tag/%E3%82%B3%E3%82%B9%E3%83%A2/",
                redirected=False,
                content_type="text/html; charset=UTF-8",
                response_size_bytes=1234,
                title="Forbidden",
                h1="Access denied",
                first_300_chars="<html>forbidden</html>",
                empty_html_reason="non-empty HTML",
                expected_content_status="report detail links not found",
                error_reason="HTTP 403",
                saved_raw_path="data/debug_raw/minrepo/cosmo_obu/tag_page_1.html",
                fetch_usable=False,
            )
        ],
        first_failure_stage="tag_page",
        first_failure_reason="HTTP 403",
        separate_store_page_requested=False,
    )

    monkeypatch.setattr(
        MinrepoCollector,
        "debug_fetch_store_history",
        lambda self, store, days, limit, debug_raw_root: debug_result,
    )

    result = cmd_debug_fetch_minrepo(
        Namespace(store="cosmo_obu", all=False, days=7, limit=3, sleep=2.0)
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "canonical_name: コスモジャパン大府店" in captured.out
    assert "probe_name: current_session" in captured.out
    assert "first_failure_stage: tag_page" in captured.out
    assert "status: 403" in captured.out
    assert "fetch_usable: no" in captured.out


def test_debug_minrepo_entrypoints_prints_sources_and_summary(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    database.upsert_source_page(
        SourcePageRecord(
            source="minrepo",
            store_id="cosmo_obu",
            url="https://min-repo.com/3099785/",
            report_date=date(2026, 5, 13),
            raw_path=str(tmp_path / "2026-05-13_detail.html"),
            fetched_at=utc_now_iso(),
            status_code=200,
            content_hash="hash1",
        )
    )
    database.upsert_source_page(
        SourcePageRecord(
            source="minrepo",
            store_id="cosmo_obu",
            url="https://min-repo.com/3099785/?kishu=all",
            report_date=date(2026, 5, 13),
            raw_path=str(tmp_path / "2026-05-13_units.html"),
            fetched_at=utc_now_iso(),
            status_code=200,
            content_hash="hash2",
        )
    )

    raw_path = tmp_path / "2026-05-13_units.html"
    raw_path.write_text(
        (
            '<html><body>'
            '<a href="https://min-repo.com/3099785/">detail</a>'
            '<a href="https://min-repo.com/3099785/?num=1373">1373</a>'
            '<a href="https://min-repo.com/category/%e6%84%9b%e7%9f%a5%e7%9c%8c/">pref</a>'
            '<a href="https://min-repo.com/category/%e6%84%9b%e7%9f%a5%e7%9c%8c/%e5%a4%a7%e5%ba%9c%e5%b8%82/">city</a>'
            '</body></html>'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)
    monkeypatch.setattr("src.cli._list_recent_raw_files", lambda store_id, days: [raw_path])
    monkeypatch.setattr(
        MinrepoCollector,
        "probe_url",
        lambda self, url, probe_name="", request_mode="session", headers=None: FetchDebugEntry(
            stage="probe",
            url=url,
            probe_name=probe_name,
            status_code=200,
            final_url=url,
            response_size_bytes=123,
            content_type="text/html; charset=UTF-8",
            title="ok",
            first_300_chars="<html>",
            fetch_usable=False,
            error_reason="Empty HTML returned",
        ),
    )

    result = cmd_debug_minrepo_entrypoints(
        Namespace(store="cosmo_obu", all=False, days=7, limit=5, sleep=2.0)
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "db_report_urls:" in captured.out
    assert "raw_report_urls:" in captured.out
    assert "detail_refetch_results:" in captured.out
    assert "units_refetch_results:" in captured.out
    assert "num_refetch_results:" in captured.out
    assert "listing_page_results:" in captured.out
    assert "entrypoint_summary:" in captured.out
    assert "next_entrypoint:" in captured.out


    def test_debug_source_entrypoints_slorepo_prints_summary(
        monkeypatch,
        capsys,
    ) -> None:
        store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
        monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)
        monkeypatch.setattr("src.cli._store_search_terms", lambda store: [store.canonical_name])

    def fake_probe(session, url, label, delay_seconds, last_request_at):
        del session, delay_seconds, last_request_at
        if "search" in url:
            return SourceProbe(
                label=label,
                url=url,
                status_code=200,
                final_url="https://www.slorepo.com/hole/test/",
                response_size_bytes=100,
                content_type="text/html",
                title="search",
                first_300_chars="<html>",
                usable=True,
            )
        if "kishu/?kishu=" in url:
            return SourceProbe(
                label=label,
                url=url,
                status_code=200,
                final_url=url,
                response_size_bytes=100,
                content_type="text/html",
                title="machine",
                table_headers=["台番 | 5/13(水) | 5/12(火)"],
                has_daiban_text=True,
                first_300_chars="<html>",
                usable=True,
            )
        if "20260513" in url:
            return SourceProbe(
                label=label,
                url=url,
                status_code=200,
                final_url=url,
                response_size_bytes=100,
                content_type="text/html",
                title="daily",
                table_headers=["機種 | 平均差枚 | 平均G数 | 勝率"],
                first_300_chars="<html>",
                usable=True,
            )
        return SourceProbe(
            label=label,
            url=url,
            status_code=200,
            final_url=url,
            response_size_bytes=100,
            content_type="text/html",
            title="store",
            first_300_chars="<html>",
            usable=True,
        )

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

    class FakeSession:
        def get(self, url, timeout):
            del timeout
            if "20260513" in url and "kishu" not in url:
                return FakeResponse('<a href="kishu/?kishu=test">機種</a>')
            return FakeResponse('<a href="20260513">5/13</a>')

    monkeypatch.setattr("src.cli._probe_source_url", fake_probe)
    monkeypatch.setattr("src.cli._make_source_session", lambda: FakeSession())

    result = cmd_debug_source_entrypoints(
        Namespace(source="slorepo", store="cosmo_obu", all=False, limit=3, sleep=0.0)
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "source_summary:" in captured.out
    assert "- store_page: usable" in captured.out
    assert "- daily_data: usable" in captured.out
    assert "- machine_data: usable" in captured.out
    assert "- unit_data: usable" in captured.out


def test_debug_source_entrypoints_anaslo_marks_blocked_store_page(
    monkeypatch,
    capsys,
) -> None:
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

    class FakeSession:
        def get(self, url, timeout):
            del url, timeout
            return FakeResponse('<a href="https://ana-slo.com/hall-page/">データ一覧</a>')

    def fake_probe(session, url, label, delay_seconds, last_request_at):
        del session, delay_seconds, last_request_at
        if "?s=" in url:
            return SourceProbe(
                label=label,
                url=url,
                status_code=200,
                final_url=url,
                response_size_bytes=100,
                content_type="text/html",
                title="search",
                first_300_chars="<html>",
                usable=True,
            )
        return SourceProbe(
            label=label,
            url=url,
            status_code=403,
            final_url=url,
            response_size_bytes=100,
            content_type="text/html",
            title="Just a moment...",
            first_300_chars="<html>",
            usable=False,
            error_reason="HTTP 403",
        )

    monkeypatch.setattr("src.cli._probe_source_url", fake_probe)
    monkeypatch.setattr("src.cli._store_search_terms", lambda store: [store.canonical_name])
    monkeypatch.setattr("src.cli._make_source_session", lambda: FakeSession())

    result = cmd_debug_source_entrypoints(
        Namespace(source="anaslo", store="cosmo_obu", all=False, limit=3, sleep=0.0)
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "- store_page: unusable" in captured.out
    assert "- daily_data: unusable" in captured.out
