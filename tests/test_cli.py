from argparse import Namespace
from datetime import date
from pathlib import Path

from src.cli import cmd_parse_minrepo, cmd_unit_coverage, cmd_validate_unit_data
from src.collectors.base_collector import CollectorError
from src.collectors.minrepo_collector import MinrepoCollector
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
