from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.cli import cmd_analyze_targets, cmd_debug_target_conditions
from src.db.database import Database, utc_now_iso
from src.db.models import DailyStoreResultRecord, MachineResultRecord, UnitResultRecord
from src.normalizers.store_normalizer import StoreNormalizer
from src.reports.targets_report import (
    analyze_targets,
    debug_target_conditions,
    write_targets_outputs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _seed_slorepo_targets_fixture(database: Database) -> None:
    created_at = utc_now_iso()
    dates = [
        date(2026, 5, 10),
        date(2026, 5, 11),
        date(2026, 5, 12),
        date(2026, 5, 13),
        date(2026, 5, 14),
        date(2026, 5, 15),
    ]

    daily_rows = [
        (dates[0], 2200, 220, 2800, 0.52, 8),
        (dates[1], 2600, 260, 2900, 0.53, 8),
        (dates[2], 2800, 280, 3000, 0.54, 8),
        (dates[3], 3200, 320, 3100, 0.56, 8),
        (dates[4], 3600, 360, 3200, 0.58, 8),
        (dates[5], 3900, 390, 3300, 0.6, 8),
    ]
    for report_date, total_diff, avg_diff, avg_game, win_rate, total_units in daily_rows:
        database.upsert_daily_store_result(
            DailyStoreResultRecord(
                source="slorepo",
                store_id="cosmo_obu",
                report_date=report_date,
                total_diff=total_diff,
                avg_diff=avg_diff,
                avg_game=avg_game,
                win_rate=win_rate,
                total_units=total_units,
                source_url="https://example.com/slorepo/daily",
                created_at=created_at,
            )
        )

    machine_rows: list[MachineResultRecord] = []
    unit_rows: list[UnitResultRecord] = []
    machine_a_diffs = [-200, -50, 100, 180, 260, 320]
    machine_b_diffs = [300, 340, 380, 460, 520, 610]
    machine_c_diffs = [1400, 1450, 1500, 1520, 1550, 1600]
    for index, report_date in enumerate(dates):
        machine_rows.extend(
            [
                MachineResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    machine_name_raw="機種A",
                    machine_name_normalized="機種A",
                    machine_category="other",
                    unit_count=3,
                    total_diff=machine_a_diffs[index] * 3,
                    avg_diff=machine_a_diffs[index],
                    avg_game=3000 + index * 100,
                    win_rate=0.45 + index * 0.02,
                    source_url="https://example.com/slorepo/machine-a",
                    created_at=created_at,
                ),
                MachineResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    machine_name_raw="機種B",
                    machine_name_normalized="機種B",
                    machine_category="other",
                    unit_count=3,
                    total_diff=machine_b_diffs[index] * 3,
                    avg_diff=machine_b_diffs[index],
                    avg_game=3100 + index * 80,
                    win_rate=0.52 + index * 0.01,
                    source_url="https://example.com/slorepo/machine-b",
                    created_at=created_at,
                ),
                MachineResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    machine_name_raw="機種C",
                    machine_name_normalized="機種C",
                    machine_category="other",
                    unit_count=2,
                    total_diff=machine_c_diffs[index] * 2,
                    avg_diff=machine_c_diffs[index],
                    avg_game=2500 + index * 60,
                    win_rate=0.7,
                    source_url="https://example.com/slorepo/machine-c",
                    created_at=created_at,
                ),
            ]
        )
        unit_rows.extend(
            [
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="101",
                    machine_name_raw="機種A",
                    machine_name_normalized="機種A",
                    machine_category="other",
                    diff=[-300, -400, -500, -600, -800, -1200][index],
                    games=[2200, 2300, 2400, 2500, 2600, 2500][index],
                    payout_rate=98.0,
                    source_url="https://example.com/slorepo/unit-101",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="102",
                    machine_name_raw="機種A",
                    machine_name_normalized="機種A",
                    machine_category="other",
                    diff=[500, 600, 700, 800, 1200, 1500][index],
                    games=[2500, 2600, 2700, 3000, 4500, 4500][index],
                    payout_rate=103.0,
                    source_url="https://example.com/slorepo/unit-102",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="103",
                    machine_name_raw="機種A",
                    machine_name_normalized="機種A",
                    machine_category="other",
                    diff=[400, 300, 200, -200, 100, 300][index],
                    games=[2400, 2300, 2200, 2100, 1500, 1800][index],
                    payout_rate=101.0,
                    source_url="https://example.com/slorepo/unit-103",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="111",
                    machine_name_raw="機種C",
                    machine_name_normalized="機種C",
                    machine_category="other",
                    diff=[1300, 1350, 1400, 1500, 1550, 1600][index],
                    games=[2100, 2200, 2300, 2400, 2500, 2600][index],
                    payout_rate=108.0,
                    source_url="https://example.com/slorepo/unit-111",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="201",
                    machine_name_raw="機種B",
                    machine_name_normalized="機種B",
                    machine_category="other",
                    diff=[600, 700, 800, 900, 1000, 1300][index],
                    games=[2100, 2200, 2300, 2400, 2900, 3000][index],
                    payout_rate=105.0,
                    source_url="https://example.com/slorepo/unit-201",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="202",
                    machine_name_raw="機種B",
                    machine_name_normalized="機種B",
                    machine_category="other",
                    diff=[500, 650, 750, 850, 900, 1100][index],
                    games=[2200, 2300, 2400, 2500, 2800, 3200][index],
                    payout_rate=104.0,
                    source_url="https://example.com/slorepo/unit-202",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="cosmo_obu",
                    report_date=report_date,
                    unit_number="203",
                    machine_name_raw="機種B",
                    machine_name_normalized="機種B",
                    machine_category="other",
                    diff=[-200, 100, 150, 200, -100, 200][index],
                    games=[1800, 1900, 2000, 2100, 1700, 1800][index],
                    payout_rate=100.0,
                    source_url="https://example.com/slorepo/unit-203",
                    created_at=created_at,
                ),
            ]
        )

    database.upsert_machine_results(machine_rows)
    database.upsert_unit_results(unit_rows)

    for report_date in [date(2026, 5, 14), date(2026, 5, 15)]:
        database.upsert_daily_store_result(
            DailyStoreResultRecord(
                source="slorepo",
                store_id="winglet",
                report_date=report_date,
                total_diff=1800,
                avg_diff=180,
                avg_game=2600,
                win_rate=0.52,
                total_units=2,
                source_url="https://example.com/slorepo/winglet",
                created_at=created_at,
            )
        )
        database.upsert_machine_results(
            [
                MachineResultRecord(
                    source="slorepo",
                    store_id="winglet",
                    report_date=report_date,
                    machine_name_raw="低サンプル機種",
                    machine_name_normalized="低サンプル機種",
                    machine_category="other",
                    unit_count=2,
                    total_diff=2200,
                    avg_diff=1100,
                    avg_game=3200,
                    win_rate=0.8,
                    source_url="https://example.com/slorepo/low-sample",
                    created_at=created_at,
                )
            ]
        )
        database.upsert_unit_results(
            [
                UnitResultRecord(
                    source="slorepo",
                    store_id="winglet",
                    report_date=report_date,
                    unit_number="301",
                    machine_name_raw="低サンプル機種",
                    machine_name_normalized="低サンプル機種",
                    machine_category="other",
                    diff=1100,
                    games=3200,
                    payout_rate=106.0,
                    source_url="https://example.com/slorepo/winglet-301",
                    created_at=created_at,
                ),
                UnitResultRecord(
                    source="slorepo",
                    store_id="winglet",
                    report_date=report_date,
                    unit_number="302",
                    machine_name_raw="低サンプル機種",
                    machine_name_normalized="低サンプル機種",
                    machine_category="other",
                    diff=1200,
                    games=3300,
                    payout_rate=107.0,
                    source_url="https://example.com/slorepo/winglet-302",
                    created_at=created_at,
                ),
            ]
        )

    database.upsert_daily_store_result(
        DailyStoreResultRecord(
            source="minrepo",
            store_id="cosmo_obu",
            report_date=date(2026, 5, 15),
            total_diff=99999,
            avg_diff=9999,
            avg_game=9999,
            win_rate=1.0,
            total_units=1,
            source_url="https://example.com/minrepo/noise",
            created_at=created_at,
        )
    )
    database.upsert_machine_results(
        [
            MachineResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 15),
                machine_name_raw="ノイズ機種",
                machine_name_normalized="ノイズ機種",
                machine_category="other",
                unit_count=1,
                total_diff=99999,
                avg_diff=9999,
                avg_game=9999,
                win_rate=1.0,
                source_url="https://example.com/minrepo/noise-machine",
                created_at=created_at,
            )
        ]
    )
    database.upsert_unit_results(
        [
            UnitResultRecord(
                source="minrepo",
                store_id="cosmo_obu",
                report_date=date(2026, 5, 15),
                unit_number="999",
                machine_name_raw="ノイズ機種",
                machine_name_normalized="ノイズ機種",
                machine_category="other",
                diff=99999,
                games=9999,
                payout_rate=120.0,
                source_url="https://example.com/minrepo/noise-unit",
                created_at=created_at,
            )
        ]
    )


def test_analyze_targets_extracts_candidates_and_respects_source(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    payload = analyze_targets(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 16),
        lookback_days=30,
        source="slorepo",
        status_overrides={
            "cosmo_obu": {
                "fetch_status": "partial_success",
                "failed_machine_pages": "1",
            }
        },
    )

    target_types = {row["target_type"] for row in payload["candidates"]}
    assert "raise_candidate" in target_types
    assert "tail_candidate" in target_types
    assert "cluster_candidate" in target_types
    assert "machine_candidate" in target_types
    assert "keep_candidate" not in target_types

    raise_candidate = next(
        row for row in payload["candidates"] if row["target_type"] == "raise_candidate"
    )
    assert raise_candidate["priority_group"] == "main"
    assert raise_candidate["unit_number"] == "101"
    assert raise_candidate["evidence"]["previous_day_diff"] == -1200.0
    assert raise_candidate["evidence"]["previous_day_games"] == 2500.0
    assert raise_candidate["evidence"]["negative_streak_days"] >= 2
    assert "理由あり" not in raise_candidate["reason_text"]
    assert "前回" in raise_candidate["reason_text"]
    assert "同機種平均" in raise_candidate["reason_text"]

    tail_candidate = next(
        row for row in payload["candidates"] if row["target_type"] == "tail_candidate"
    )
    assert tail_candidate["unit_number"].startswith("末尾")
    assert tail_candidate["evidence"]["sample_count"] >= 5

    cluster_candidate = next(
        row for row in payload["candidates"] if row["target_type"] == "cluster_candidate"
    )
    assert cluster_candidate["unit_number"] == "201-202"
    assert cluster_candidate["evidence"]["sample_count"] >= 1

    assert payload["source"] == "slorepo"
    assert payload["requested_days"] == 30
    assert payload["analysis_anchor_date"] == "2026-05-15"
    assert payload["analysis_anchor_notice"] == ""
    assert payload["target_store_count"] == 4
    assert payload["target_store_ids"] == [
        "cosmo_obu",
        "marushin_777",
        "apan_kobo",
        "keiz_galerie_apita",
    ]
    assert payload["priority_groups"]["main"] == ["コスモジャパン大府", "マルシン777"]
    assert payload["priority_groups"]["sub"] == ["APANCLUB弘法通り", "KEIZギャラリエアピタ"]
    coverage = {row["store_id"]: row for row in payload["store_coverage"]}
    assert coverage["cosmo_obu"]["oldest_date"] == "2026-05-10"
    assert coverage["cosmo_obu"]["latest_date"] == "2026-05-15"
    assert coverage["cosmo_obu"]["available_days"] == 6
    assert coverage["cosmo_obu"]["requested_days"] == 30
    assert coverage["cosmo_obu"]["coverage_rate"] == 0.2
    assert coverage["cosmo_obu"]["daily_count"] == 6
    assert coverage["cosmo_obu"]["machine_count"] >= 1
    assert coverage["cosmo_obu"]["unit_count"] >= 1
    assert coverage["cosmo_obu"]["failed_machine_pages"] == 1
    assert coverage["cosmo_obu"]["coverage_state"] == "warning"
    assert coverage["cosmo_obu"]["coverage_state_label"] == "不足"
    assert payload["summary"]["priority_candidate_counts"]["main"] >= 1
    assert payload["summary"]["highlight_counts"]["top_candidates"] <= 5
    assert payload["summary"]["highlight_counts"]["main_candidates"] >= 1
    assert payload["candidates"][0]["priority_group"] == "main"
    assert all(row["machine_name"] != "ノイズ機種" for row in payload["candidates"])
    assert all(row["priority_group"] in {"main", "sub"} for row in payload["candidates"])
    assert len(payload["highlights"]["top_candidates"]) <= 5
    top_candidates = payload["highlights"]["top_candidates"]
    top_type_counts: dict[str, int] = {}
    for row in top_candidates:
        top_type_counts[row["target_type"]] = top_type_counts.get(row["target_type"], 0) + 1
        assert row["confidence"] in {"A", "B"}
        assert "adjusted_score" in row
    assert top_type_counts.get("tail_candidate", 0) <= 1
    assert top_type_counts.get("cluster_candidate", 0) <= 2
    assert top_type_counts.get("machine_candidate", 0) <= 2
    assert any(row["target_type"] == "raise_candidate" for row in top_candidates)
    assert all(
        row["priority_group"] in {"main", "sub", "watch"}
        for row in top_candidates
    )
    main_store_sections = payload["main_store_sections"]
    assert set(main_store_sections) == {"cosmo_obu", "marushin_777"}
    assert set(payload["sub_store_sections"]) == {"apan_kobo", "keiz_galerie_apita"}
    assert len(main_store_sections["cosmo_obu"]["candidates"]) <= 10
    assert len(main_store_sections["marushin_777"]["candidates"]) <= 10
    assert len(main_store_sections["cosmo_obu"]["tail_candidates"]) <= 2
    assert len(main_store_sections["marushin_777"]["tail_candidates"]) <= 2
    assert any(
        row["target_type"] == "raise_candidate"
        for row in main_store_sections["cosmo_obu"]["candidates"]
    )
    per_main_store: dict[str, int] = {}
    for row in payload["highlights"]["main_candidates"]:
        per_main_store[row["store_id"]] = per_main_store.get(row["store_id"], 0) + 1
    assert per_main_store
    assert all(count <= 5 for count in per_main_store.values())
    per_sub_store: dict[str, int] = {}
    for row in payload["highlights"]["sub_candidates"]:
        per_sub_store[row["store_id"]] = per_sub_store.get(row["store_id"], 0) + 1
    assert all(count <= 3 for count in per_sub_store.values())

    store_scores = {row["store_id"]: row for row in payload["store_scores"]}
    assert store_scores["cosmo_obu"]["priority_group"] == "main"
    assert store_scores["cosmo_obu"]["priority_multiplier"] == 1.2
    assert "winglet" not in store_scores


def test_write_targets_outputs_writes_safe_json(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    payload, report_path, json_path = write_targets_outputs(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 16),
        lookback_days=30,
        reports_dir=tmp_path / "reports",
        public_dir=tmp_path / "public",
        source="slorepo",
    )

    assert report_path.exists()
    assert json_path.exists()
    text = json_path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["source"] == "slorepo"
    assert data["requested_days"] == 30
    assert "raw_path" not in text
    assert "db_path" not in text
    assert "data/raw" not in text
    assert "priority_group" in text
    assert "keep_candidate" not in text
    assert "理由あり" not in text
    assert data["analysis_anchor_date"] == "2026-05-15"
    assert data["target_store_count"] == 4
    assert len(data["highlights"]["top_candidates"]) <= 5
    assert len(data["main_store_sections"]["cosmo_obu"]["candidates"]) <= 10
    assert len(data["main_store_sections"]["marushin_777"]["candidates"]) <= 10
    assert sum(
        1
        for row in data["highlights"]["top_candidates"]
        if row["target_type"] == "tail_candidate"
    ) <= 1
    assert any(row["target_type"] == "raise_candidate" for row in data["candidates"])
    assert payload["summary"]["target_counts"]["raise_candidate"] >= 1
    report_text = report_path.read_text(encoding="utf-8")
    assert "## データ充足状況" in report_text
    assert "コスモジャパン大府 | 6/30日" in report_text
    assert "- main: コスモジャパン大府, マルシン777" in report_text
    assert "- analysis_anchor_date: 2026-05-15" in report_text
    assert "priority_group=main" in report_text
    assert "据え置き候補" not in report_text


def test_cmd_analyze_targets_writes_report_and_json(monkeypatch, tmp_path: Path, capsys) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)
    monkeypatch.setattr("src.cli.REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr("src.cli.PUBLIC_DIR", tmp_path / "public")

    class Args:
        date = "2026-05-16"
        days = 30
        source = "slorepo"

    result = cmd_analyze_targets(Args())
    captured = capsys.readouterr()
    assert result == 0
    assert "report:" in captured.out
    assert "json:" in captured.out
    assert (tmp_path / "reports" / "targets_2026-05-16.md").exists()
    assert (tmp_path / "public" / "data" / "targets.json").exists()


def test_debug_target_conditions_counts_fixture_conditions(tmp_path: Path) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    payload = debug_target_conditions(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 16),
        lookback_days=30,
        source="slorepo",
    )

    assert payload["calendar_previous_day"] == "2026-05-15"
    assert payload["latest_available_unit_date"] == "2026-05-15"
    assert payload["analysis_anchor_date"] == "2026-05-15"
    assert payload["previous_day_snapshot"]["unit_rows"] >= 1
    assert payload["previous_day_snapshot"]["raise"]["diff_le_neg1000"] >= 1
    assert payload["previous_day_snapshot"]["raise"]["games_ge_2000"] >= 1
    assert payload["previous_day_snapshot"]["raise"]["machine_avg_games_ge_1500"] >= 1
    assert payload["previous_day_snapshot"]["raise"]["final_candidates"] >= 1
    assert payload["previous_day_snapshot"]["cluster"]["consecutive2plus_same_day_machine"] >= 1
    assert payload["previous_day_snapshot"]["cluster"]["final_candidates"] >= 1


def test_cmd_debug_target_conditions_prints_summary(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    monkeypatch.setattr("src.cli._database", lambda: database)
    monkeypatch.setattr("src.cli._store_normalizer", lambda: store_normalizer)

    class Args:
        date = "2026-05-16"
        days = 30
        source = "slorepo"

    result = cmd_debug_target_conditions(Args())
    captured = capsys.readouterr()
    assert result == 0
    assert "calendar_previous_day: 2026-05-15" in captured.out
    assert "analysis_anchor_date: 2026-05-15" in captured.out
    assert "raise_conditions:" in captured.out
    assert "cluster_conditions:" in captured.out
    assert "final raise candidates:" in captured.out
    assert "final cluster candidates:" in captured.out


def test_analyze_targets_uses_latest_available_anchor_when_target_date_is_later(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "slot.db")
    database.initialize(PROJECT_ROOT / "sql" / "schema.sql")
    store_normalizer = StoreNormalizer.from_yaml(PROJECT_ROOT / "stores.yaml")
    database.seed_stores(store_normalizer.catalog)
    _seed_slorepo_targets_fixture(database)

    payload = analyze_targets(
        database=database,
        store_normalizer=store_normalizer,
        target_date=date(2026, 5, 18),
        lookback_days=30,
        source="slorepo",
    )

    assert payload["analysis_anchor_date"] == "2026-05-15"
    assert "2026-05-15" in payload["analysis_anchor_notice"]
    assert payload["summary"]["target_counts"]["raise_candidate"] >= 1
    assert payload["summary"]["target_counts"]["cluster_candidate"] >= 1
