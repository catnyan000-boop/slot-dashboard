import json
from argparse import Namespace
from datetime import date
from pathlib import Path

from src.cli import cmd_build_site
from src.db.database import Database, utc_now_iso
from src.db.models import DailyStoreResultRecord, UnitResultRecord
from src.normalizers.store_normalizer import StoreNormalizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_site_cli_generates_public_files(monkeypatch, tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    database.upsert_daily_store_result(
        DailyStoreResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 13),
            total_diff=1000,
            avg_diff=100,
            avg_game=3000,
            win_rate=0.5,
            total_units=10,
            source_url="https://example.com/detail",
            created_at=utc_now_iso(),
        )
    )
    database.upsert_unit_results(
        [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 13),
                unit_number=str(index),
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=None if index < 8 else 100.0,
                games=1000.0,
                payout_rate=100.0,
                bb=None,
                rb=None,
                source_url="https://example.com/detail?kishu=all",
                created_at=utc_now_iso(),
            )
            for index in range(10)
        ]
        + [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 13),
                unit_number="100",
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=50.0,
                games=900.0,
                payout_rate=99.0,
                bb=None,
                rb=None,
                source_url="https://example.com/detail?kishu=all",
                created_at=utc_now_iso(),
            )
        ]
    )

    public_dir = tmp_path / "public"
    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)
    monkeypatch.setattr("src.cli.PUBLIC_DIR", public_dir)

    result = cmd_build_site(Namespace(date="2026-05-15", days=7))

    assert result == 0
    assert (public_dir / "index.html").exists()
    assert (public_dir / "data" / "latest.json").exists()
    assert (public_dir / "assets" / "style.css").exists()
    assert (public_dir / "assets" / "app.js").exists()


def test_latest_json_contains_summary_only_and_quality_flags(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    database.upsert_daily_store_result(
        DailyStoreResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 13),
            total_diff=1200,
            avg_diff=120,
            avg_game=3200,
            win_rate=0.55,
            total_units=10,
            source_url="https://example.com/detail",
            created_at=utc_now_iso(),
        )
    )
    database.upsert_unit_results(
        [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 8),
                unit_number=str(index),
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=None if index < 6 else 100.0,
                games=1000.0,
                payout_rate=100.0,
                bb=None,
                rb=None,
                source_url="https://example.com/detail?kishu=all",
                created_at=utc_now_iso(),
            )
            for index in range(10)
        ]
        + [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 13),
                unit_number="100",
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=50.0,
                games=900.0,
                payout_rate=99.0,
                bb=None,
                rb=None,
                source_url="https://example.com/detail?kishu=all",
                created_at=utc_now_iso(),
            )
        ]
    )

    from src.reports.site_builder import build_static_site

    public_dir = tmp_path / "public"
    build_static_site(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 15),
        lookback_days=7,
        output_dir=public_dir,
    )

    index_text = (public_dir / "index.html").read_text(encoding="utf-8")
    latest_path = public_dir / "data" / "latest.json"
    latest_text = latest_path.read_text(encoding="utf-8")
    payload = json.loads(latest_text)

    assert "Slot Analyzer Dashboard" in index_text
    assert "./assets/app.js" in index_text
    assert "window.__SITE_DATA__" not in index_text
    assert "data/raw" not in latest_text
    assert ".db" not in latest_text
    assert "raw_path" not in latest_text
    assert "db_path" not in latest_text
    assert payload["coverage_window"] == "2026-05-08 〜 2026-05-13"
    assert payload["summary_counts"] == {
        "ready": 0,
        "caution": 0,
        "unreliable": 1,
        "shortage": 8,
    }

    stores = {store["store_id"]: store for store in payload["stores"]}
    assert stores["cosmo_obu"]["unit_diff_missing_rate"] == 0.5455
    assert stores["cosmo_obu"]["pattern_analysis_status"] == "台番分析は信頼不可"
    assert stores["cosmo_obu"]["unit_diff_missing_rate_text"] == "0.5455"
    assert stores["kyoraku_tokai"]["pattern_analysis_status"] == "データ不足"
    assert "KYORAKU東海" in payload["data_shortage_stores"]
