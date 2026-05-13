from datetime import date
from pathlib import Path

import pandas as pd

from src.analysis.store_score import score_stores
from src.db.database import Database, utc_now_iso
from src.db.models import DailyStoreResultRecord, StoreDefinition, UnitResultRecord
from src.normalizers.store_normalizer import StoreNormalizer
from src.reports.tomorrow_report import generate_tomorrow_report


def test_scoring_handles_outliers_without_crashing() -> None:
    daily_df = pd.DataFrame(
        [
            {
                "store_id": "test_store",
                "report_date": "2026-05-01",
                "total_diff": 1000,
                "avg_diff": 100,
                "avg_game": 3500,
                "win_rate": 0.55,
                "total_units": 100,
            },
            {
                "store_id": "test_store",
                "report_date": "2026-05-02",
                "total_diff": -100000,
                "avg_diff": -9999,
                "avg_game": 10,
                "win_rate": 0.01,
                "total_units": 100,
            },
            {
                "store_id": "test_store",
                "report_date": "2026-05-03",
                "total_diff": 80000,
                "avg_diff": 5555,
                "avg_game": 8000,
                "win_rate": 0.9,
                "total_units": 100,
            },
        ]
    )
    stores = [
        StoreDefinition(
            store_id="test_store",
            display_name="テスト店",
            canonical_name="テスト店",
            aliases=["テスト店"],
            event_days=["1"],
        )
    ]
    scores = score_stores(daily_df, stores, date(2026, 5, 11))
    assert len(scores) == 1
    assert 0.0 <= scores[0].score <= 100.0
    assert 0.0 <= scores[0].confidence <= 1.0


def test_report_marks_data_shortage_when_sample_size_zero(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    source_root = Path(__file__).resolve().parents[1]
    database.initialize(source_root / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(source_root / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    report_path = generate_tomorrow_report(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 15),
        lookback_days=7,
        output_dir=tmp_path / "reports",
    )
    text = report_path.read_text(encoding="utf-8")
    assert "データ不足" in text


def test_report_marks_number_analysis_unreliable_when_unit_diff_missing_is_high(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "slot.db")
    source_root = Path(__file__).resolve().parents[1]
    database.initialize(source_root / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(source_root / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    database.upsert_daily_store_result(
        DailyStoreResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 14),
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
                report_date=date(2026, 5, 14),
                unit_number=str(i),
                machine_name_raw="機種A",
                machine_name_normalized="機種A",
                machine_category="other",
                diff=None if i < 8 else 100.0,
                games=1000.0,
                payout_rate=100.0,
                bb=None,
                rb=None,
                source_url="https://example.com/detail?kishu=all",
                created_at=utc_now_iso(),
            )
            for i in range(10)
        ]
    )

    report_path = generate_tomorrow_report(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 15),
        lookback_days=7,
        output_dir=tmp_path / "reports",
    )
    text = report_path.read_text(encoding="utf-8")
    assert "unit_diff_missing_rate: 0.8" in text
    assert "diff_null_count: 8" in text
    assert "台番分析ステータス: 台番分析は信頼不可" in text
    assert "末尾分析は信頼不可" in text
    assert "並び分析は信頼不可" in text
    assert "現時点では店舗別・機種別・カテゴリ別分析のみ有効" in text


def test_report_marks_unit_quality_data_shortage_when_unit_samples_are_zero(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "slot.db")
    source_root = Path(__file__).resolve().parents[1]
    database.initialize(source_root / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(source_root / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)

    database.upsert_daily_store_result(
        DailyStoreResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 14),
            total_diff=1000,
            avg_diff=100,
            avg_game=3000,
            win_rate=0.5,
            total_units=10,
            source_url="https://example.com/detail",
            created_at=utc_now_iso(),
        )
    )

    report_path = generate_tomorrow_report(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 15),
        lookback_days=7,
        output_dir=tmp_path / "reports",
    )
    text = report_path.read_text(encoding="utf-8")
    assert "unit_diff_missing_rate: データ不足" in text
    assert "有効分析範囲: データ不足" in text
