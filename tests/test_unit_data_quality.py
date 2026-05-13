from datetime import date

import pandas as pd

from src.analysis.unit_data_quality import summarize_unit_data_quality


def _frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_missing_rate_and_zero_null_are_distinct() -> None:
    quality = summarize_unit_data_quality(
        _frame(
            [
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "1001",
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": 0.0,
                    "games": 1000.0,
                    "payout_rate": 100.0,
                },
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "1002",
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": None,
                    "games": 900.0,
                    "payout_rate": 99.0,
                },
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "1003",
                    "machine_name_normalized": "機種B",
                    "machine_category": "other",
                    "diff": 120.0,
                    "games": 1200.0,
                    "payout_rate": 101.0,
                },
            ]
        ),
        "cosmo_obu",
    )

    assert quality["total_rows"] == 3
    assert quality["diff_null_count"] == 1
    assert quality["diff_zero_count"] == 1
    assert quality["diff_missing_rate"] == 0.3333


def test_missing_rate_over_fifty_percent_is_unreliable() -> None:
    quality = summarize_unit_data_quality(
        _frame(
            [
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": str(index),
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": None if index < 6 else 100.0,
                    "games": 1000.0,
                    "payout_rate": 100.0,
                }
                for index in range(10)
            ]
        ),
        "cosmo_obu",
    )

    assert quality["diff_missing_rate"] == 0.6
    assert quality["pattern_analysis_ready"] is False
    assert quality["pattern_analysis_status"] == "台番分析は信頼不可"
    assert quality["tail_analysis_status"] == "台番分析は信頼不可"
    assert quality["cluster_analysis_status"] == "台番分析は信頼不可"


def test_machine_date_and_category_grouping_do_not_fail() -> None:
    quality = summarize_unit_data_quality(
        _frame(
            [
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "1001",
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": None,
                    "games": 1000.0,
                    "payout_rate": 100.0,
                },
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "1002",
                    "machine_name_normalized": "機種B",
                    "machine_category": "other",
                    "diff": 50.0,
                    "games": 1100.0,
                    "payout_rate": 101.0,
                },
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 11),
                    "unit_number": "1003",
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": 70.0,
                    "games": 1200.0,
                    "payout_rate": 102.0,
                },
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 11),
                    "unit_number": "1004",
                    "machine_name_normalized": "機種C",
                    "machine_category": "other",
                    "diff": None,
                    "games": 1300.0,
                    "payout_rate": 103.0,
                },
            ]
        ),
        "cosmo_obu",
    )

    machine_names = {row["machine_name_normalized"] for row in quality["machine_missing"]}
    category_names = {row["machine_category"] for row in quality["category_missing"]}
    report_dates = {str(row["report_date"]) for row in quality["date_missing"]}

    assert machine_names == {"機種A", "機種B", "機種C"}
    assert category_names == {"smart", "other"}
    assert report_dates == {"2026-05-10", "2026-05-11"}


def test_excluded_machine_contains_reason_when_machine_missing_rate_is_high() -> None:
    quality = summarize_unit_data_quality(
        _frame(
            [
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": f"200{index}",
                    "machine_name_normalized": "機種A",
                    "machine_category": "smart",
                    "diff": None if index < 3 else 10.0,
                    "games": 1000.0,
                    "payout_rate": 100.0,
                }
                for index in range(4)
            ]
            + [
                {
                    "store_id": "cosmo_obu",
                    "report_date": date(2026, 5, 10),
                    "unit_number": "3001",
                    "machine_name_normalized": "機種B",
                    "machine_category": "other",
                    "diff": 20.0,
                    "games": 1000.0,
                    "payout_rate": 100.0,
                }
            ]
        ),
        "cosmo_obu",
    )

    assert quality["excluded_machines"]
    assert quality["excluded_machines"][0]["machine_name"] == "機種A"
    assert "除外" in quality["excluded_machines"][0]["reason"]
