from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.analysis.store_score import score_stores
from src.analysis.unit_data_quality import summarize_unit_data_quality
from src.normalizers.store_normalizer import StoreNormalizer

PRIORITY_MULTIPLIERS = {
    "main": 1.20,
    "sub": 1.05,
    "watch": 0.85,
}

PRIORITY_ORDER = {
    "main": 0,
    "sub": 1,
    "watch": 2,
}


def _safe_float(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and math.isnan(value):
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(numeric) else numeric


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _tail_number(value: object) -> str | None:
    match = re.search(r"(\d+)", str(value))
    if not match:
        return None
    return str(int(match.group(1)) % 10)


def _unit_number_int(value: object) -> int | None:
    match = re.search(r"(\d+)", str(value))
    if not match:
        return None
    return int(match.group(1))


def _normalize_fetch_status(status: str) -> str:
    value = str(status or "").strip()
    if value in {"success", "partial_success", "failed"}:
        return value
    if value == "成功":
        return "success"
    if value == "一部成功":
        return "partial_success"
    if value == "失敗（前回データ使用）":
        return "failed"
    if value == "失敗":
        return "failed"
    return value or "failed"


def _priority_group(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in PRIORITY_ORDER:
        return normalized
    return "watch"


def _priority_multiplier(priority_group: str, quality_good: bool) -> float:
    multiplier = PRIORITY_MULTIPLIERS.get(_priority_group(priority_group), 1.0)
    if quality_good:
        return multiplier
    return min(multiplier, 1.0)


def _apply_priority_score(score: float, priority_group: str, quality_good: bool) -> float:
    return round(float(score) * _priority_multiplier(priority_group, quality_good), 2)


def _candidate_sort_key(candidate: dict[str, object]) -> tuple[int, float, str]:
    return (
        PRIORITY_ORDER.get(str(candidate.get("priority_group", "watch")), 9),
        -float(candidate.get("score", 0.0)),
        str(candidate.get("store_id", "")),
    )


def _query_lookback_frames(
    database,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start_date = target_date - timedelta(days=lookback_days)
    end_date = target_date
    params = [start_date.isoformat(), end_date.isoformat()]
    source_clause = ""
    if source:
        source_clause = " AND source = ?"
        params.append(source)
    daily_df = database.query_dataframe(
        f"""
        SELECT *
        FROM daily_store_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    machine_df = database.query_dataframe(
        f"""
        SELECT *
        FROM machine_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    unit_df = database.query_dataframe(
        f"""
        SELECT *
        FROM unit_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    return daily_df, machine_df, unit_df


def _prepare_frames(
    daily_df: pd.DataFrame,
    machine_df: pd.DataFrame,
    unit_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not daily_df.empty:
        daily_df = daily_df.copy()
        daily_df["report_date"] = pd.to_datetime(daily_df["report_date"]).dt.date
        for column in ["total_diff", "avg_diff", "avg_game", "win_rate", "total_units"]:
            daily_df[column] = pd.to_numeric(daily_df[column], errors="coerce")
    if not machine_df.empty:
        machine_df = machine_df.copy()
        machine_df["report_date"] = pd.to_datetime(machine_df["report_date"]).dt.date
        for column in ["unit_count", "total_diff", "avg_diff", "avg_game", "win_rate"]:
            machine_df[column] = pd.to_numeric(machine_df[column], errors="coerce")
    if not unit_df.empty:
        unit_df = unit_df.copy()
        unit_df["report_date"] = pd.to_datetime(unit_df["report_date"]).dt.date
        for column in ["diff", "games", "payout_rate"]:
            unit_df[column] = pd.to_numeric(unit_df[column], errors="coerce")
        unit_df["unit_int"] = unit_df["unit_number"].map(_unit_number_int)
        unit_df["tail"] = unit_df["unit_number"].map(_tail_number)
    return daily_df, machine_df, unit_df


def _coverage_window_text(unit_df: pd.DataFrame, target_date: date, lookback_days: int) -> str:
    fallback = (
        f"{(target_date - timedelta(days=lookback_days)).isoformat()} 〜 "
        f"{(target_date - timedelta(days=1)).isoformat()}"
    )
    if unit_df.empty or "report_date" not in unit_df.columns:
        return fallback
    report_dates = unit_df["report_date"].dropna()
    if report_dates.empty:
        return fallback
    return f"{str(report_dates.min())} 〜 {str(report_dates.max())}"


def _latest_available_unit_date(unit_df: pd.DataFrame, target_date: date) -> date | None:
    if unit_df.empty or "report_date" not in unit_df.columns:
        return None
    report_dates = unit_df["report_date"].dropna()
    if report_dates.empty:
        return None
    eligible = report_dates[report_dates < target_date]
    if eligible.empty:
        return None
    return eligible.max()


def _recent_machine_stats(machine_frame: pd.DataFrame) -> dict[str, object]:
    if machine_frame.empty:
        return {
            "avg_diff": 0.0,
            "avg_game": 0.0,
            "win_rate": 0.0,
            "sample_count": 0,
            "recent_trend": 0.0,
        }
    frame = machine_frame.sort_values("report_date").copy()
    last_date = frame["report_date"].max()
    recent_cutoff = last_date - timedelta(days=7)
    recent = frame[frame["report_date"] >= recent_cutoff]
    older = frame[frame["report_date"] < recent_cutoff]
    recent_avg = _safe_float(recent["avg_diff"].mean())
    older_avg = _safe_float(older["avg_diff"].mean()) if not older.empty else recent_avg
    return {
        "avg_diff": round(_safe_float(frame["avg_diff"].mean()), 2),
        "avg_game": round(_safe_float(frame["avg_game"].mean()), 2),
        "win_rate": round(_safe_float(frame["win_rate"].mean()), 4),
        "sample_count": int(frame["report_date"].nunique()),
        "recent_trend": round(recent_avg - older_avg, 2),
    }


def _confidence_letter(
    *,
    score: float,
    sample_count: int,
    quality_good: bool,
    caution_penalty: int = 0,
) -> str:
    if sample_count >= 10 and score >= 80 and quality_good and caution_penalty == 0:
        return "A"
    if sample_count >= 5 and score >= 65 and caution_penalty <= 1:
        return "B"
    return "C"


def _tier_label(score: float, confidence: str) -> str:
    if score >= 85 and confidence == "A":
        return "S"
    if score >= 75 and confidence in {"A", "B"}:
        return "A"
    if score >= 60:
        return "B"
    return "見送り"


def _candidate_dict(
    *,
    store_id: str,
    store_name: str,
    priority_group: str,
    machine_name: str,
    unit_number: str,
    target_type: str,
    score: float,
    confidence: str,
    reason: str,
    evidence: dict[str, object],
    caution: str,
) -> dict[str, object]:
    return {
        "rank": 0,
        "store_id": store_id,
        "store_name": store_name,
        "priority_group": priority_group,
        "machine_name": machine_name,
        "unit_number": unit_number,
        "target_type": target_type,
        "score": round(float(score), 2),
        "confidence": confidence,
        "tier": _tier_label(float(score), confidence),
        "reason": reason,
        "evidence": evidence,
        "caution": caution,
    }


def _cluster_ranges_filtered(
    day_frame: pd.DataFrame,
    *,
    require_positive_diff: bool,
    min_games: int | None,
) -> list[dict[str, object]]:
    frame = day_frame.copy()
    frame = frame[frame["unit_int"].notna()]
    if require_positive_diff:
        frame = frame[frame["diff"].notna() & (frame["diff"] > 0)]
    if min_games is not None:
        frame = frame[frame["games"].notna() & (frame["games"] >= min_games)]
    frame = frame.sort_values("unit_int")
    if frame.empty:
        return []
    rows = frame.to_dict(orient="records")
    clusters: list[list[dict[str, object]]] = []
    current = [rows[0]]
    for row in rows[1:]:
        if int(row["unit_int"]) == int(current[-1]["unit_int"]) + 1:
            current.append(row)
            continue
        if len(current) >= 2:
            clusters.append(current)
        current = [row]
    if len(current) >= 2:
        clusters.append(current)
    results: list[dict[str, object]] = []
    for cluster in clusters:
        start = int(cluster[0]["unit_int"])
        end = int(cluster[-1]["unit_int"])
        results.append(
            {
                "pattern": f"{start}-{end}",
                "length": len(cluster),
                "avg_diff": round(
                    sum(_safe_float(row["diff"]) for row in cluster) / len(cluster),
                    2,
                ),
                "avg_games": round(
                    sum(_safe_float(row["games"]) for row in cluster) / len(cluster),
                    2,
                ),
            }
        )
    return results


def _cluster_ranges(day_frame: pd.DataFrame, min_games: int = 2000) -> list[dict[str, object]]:
    return _cluster_ranges_filtered(
        day_frame,
        require_positive_diff=True,
        min_games=min_games,
    )


def _cluster_history_days(machine_units: pd.DataFrame, min_games: int = 2000) -> int:
    if machine_units.empty:
        return 0
    count = 0
    for _, day_frame in machine_units.groupby("report_date"):
        if _cluster_ranges(day_frame, min_games=min_games):
            count += 1
    return count


def _unit_negative_streak(unit_history: pd.DataFrame) -> int:
    if unit_history.empty:
        return 0
    streak = 0
    for _, row in unit_history.sort_values("report_date", ascending=False).iterrows():
        diff = row["diff"]
        if pd.isna(diff) or diff > 0:
            break
        streak += 1
    return streak


def _build_store_payloads(
    *,
    stores,
    daily_df: pd.DataFrame,
    unit_df: pd.DataFrame,
    target_date: date,
    status_overrides: dict[str, dict[str, str]] | None,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    scored = {
        row.store_id: row for row in score_stores(daily_df, stores, target_date)
    }
    store_rows: list[dict[str, object]] = []
    quality_map: dict[str, dict[str, object]] = {}
    overrides = status_overrides or {}
    for store in stores:
        store_daily = daily_df[daily_df["store_id"] == store.store_id].copy()
        store_units = unit_df[unit_df["store_id"] == store.store_id].copy()
        quality = summarize_unit_data_quality(unit_df, store.store_id)
        quality_map[store.store_id] = quality
        priority_group = _priority_group(getattr(store, "priority_group", "watch"))
        quality_good = float(quality["diff_missing_rate"]) < 0.1
        score_row = scored[store.store_id]
        override = overrides.get(store.store_id, overrides.get(store.display_name, {}))
        fetch_status = _normalize_fetch_status(
            override.get(
                "fetch_status",
                "success" if not store_units.empty or not store_daily.empty else "failed",
            )
        )
        failed_machine_pages = _safe_int(override.get("failed_machine_pages", 0))
        unit_row_count = int(len(store_units))
        store_rows.append(
            {
                "store_id": store.store_id,
                "store_name": store.display_name,
                "priority_group": priority_group,
                "days": int(store_daily["report_date"].nunique()) if not store_daily.empty else 0,
                "total_diff": round(_safe_float(store_daily["total_diff"].sum()), 2),
                "avg_diff": round(_safe_float(store_daily["avg_diff"].mean()), 2),
                "avg_game": round(_safe_float(store_daily["avg_game"].mean()), 2),
                "win_rate": round(_safe_float(store_daily["win_rate"].mean()), 4),
                "unit_results_total": unit_row_count,
                "unit_diff_missing_rate": quality["diff_missing_rate"],
                "fetch_status": fetch_status,
                "failed_machine_pages": failed_machine_pages,
                "base_store_score": score_row.score,
                "priority_multiplier": _priority_multiplier(priority_group, quality_good),
                "store_score": _apply_priority_score(score_row.score, priority_group, quality_good),
                "confidence": score_row.confidence,
                "confidence_letter": _confidence_letter(
                    score=_apply_priority_score(score_row.score, priority_group, quality_good),
                    sample_count=score_row.sample_size,
                    quality_good=quality_good,
                    caution_penalty=1 if fetch_status == "partial_success" else 0,
                ),
                "reason": score_row.reason,
            }
        )
    return sorted(store_rows, key=lambda row: float(row["store_score"]), reverse=True), quality_map


def _build_machine_payloads(
    *,
    stores,
    machine_df: pd.DataFrame,
    store_payloads: list[dict[str, object]],
    quality_map: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    store_score_map = {row["store_id"]: row for row in store_payloads}
    machine_rows: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for store in stores:
        store_frame = machine_df[machine_df["store_id"] == store.store_id].copy()
        if store_frame.empty:
            continue
        for machine_name, group in store_frame.groupby("machine_name_normalized"):
            stats = _recent_machine_stats(group)
            unit_count = round(_safe_float(group["unit_count"].mean()), 2)
            store_score = float(store_score_map[store.store_id]["store_score"])
            priority_group = _priority_group(getattr(store, "priority_group", "watch"))
            quality_good = float(quality_map[store.store_id]["diff_missing_rate"]) < 0.1
            base_score = round(
                max(
                    0.0,
                    45.0
                    + stats["avg_diff"] * 0.01
                    + stats["avg_game"] * 0.002
                    + stats["win_rate"] * 18.0
                    + stats["recent_trend"] * 0.01
                    + min(unit_count, 20.0) * 0.8
                    + min(store_score / 8.0, 10.0),
                ),
                2,
            )
            score = _apply_priority_score(base_score, priority_group, quality_good)
            row = {
                "store_id": store.store_id,
                "store_name": store.display_name,
                "priority_group": priority_group,
                "machine_name": machine_name,
                "active_days": int(group["report_date"].nunique()),
                "unit_count": unit_count,
                "avg_diff": stats["avg_diff"],
                "avg_game": stats["avg_game"],
                "win_rate": stats["win_rate"],
                "recent_trend": stats["recent_trend"],
                "base_machine_score": base_score,
                "machine_score": score,
            }
            machine_rows.append(row)
            if row["active_days"] < 2 or stats["avg_game"] < 1000:
                continue
            confidence = _confidence_letter(
                score=score,
                sample_count=row["active_days"],
                quality_good=quality_good,
                caution_penalty=0,
            )
            caution = ""
            if row["active_days"] < 5:
                caution = "sample_count少なめのため参考程度"
            candidates.append(
                _candidate_dict(
                    store_id=store.store_id,
                    store_name=store.display_name,
                    priority_group=priority_group,
                    machine_name=machine_name,
                    unit_number="",
                    target_type="machine_candidate",
                    score=score,
                    confidence=confidence,
                    reason=(
                        f"同機種の平均差枚 {stats['avg_diff']}、平均G数 {stats['avg_game']}。"
                        f" 直近傾向 {stats['recent_trend']}。"
                    ),
                    evidence={
                        "previous_day_diff": None,
                        "previous_day_games": None,
                        "recent_avg_diff": stats["avg_diff"],
                        "recent_avg_games": stats["avg_game"],
                        "win_rate": stats["win_rate"],
                        "sample_count": row["active_days"],
                    },
                    caution=caution,
                )
            )
    machine_rows = sorted(machine_rows, key=lambda row: float(row["machine_score"]), reverse=True)
    filtered_candidates: list[dict[str, object]] = []
    per_store_count: dict[str, int] = {}
    for candidate in sorted(candidates, key=lambda row: float(row["score"]), reverse=True):
        count = per_store_count.get(candidate["store_id"], 0)
        if count >= 2:
            continue
        filtered_candidates.append(candidate)
        per_store_count[candidate["store_id"]] = count + 1
    return machine_rows, filtered_candidates


def _build_unit_candidates(
    *,
    stores,
    target_date: date,
    daily_df: pd.DataFrame,
    machine_df: pd.DataFrame,
    unit_df: pd.DataFrame,
    quality_map: dict[str, dict[str, object]],
    analysis_anchor_date: date | None,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    raise_candidates: list[dict[str, object]] = []
    tail_candidates: list[dict[str, object]] = []
    cluster_candidates: list[dict[str, object]] = []

    if analysis_anchor_date is None:
        return raise_candidates, tail_candidates, cluster_candidates

    for store in stores:
        store_units = unit_df[unit_df["store_id"] == store.store_id].copy()
        store_daily = daily_df[daily_df["store_id"] == store.store_id].copy()
        store_machines = machine_df[machine_df["store_id"] == store.store_id].copy()
        priority_group = _priority_group(getattr(store, "priority_group", "watch"))
        quality = quality_map[store.store_id]
        quality_good = (
            float(quality["diff_missing_rate"]) < 0.1
            and str(quality["pattern_analysis_status"]) == "台番分析可能"
        )
        if store_units.empty:
            continue

        recent_store_avg_diff = round(_safe_float(store_daily["avg_diff"].tail(7).mean()), 2)
        anchor_units = store_units[store_units["report_date"] == analysis_anchor_date].copy()
        anchor_units = anchor_units[anchor_units["diff"].notna() & anchor_units["games"].notna()]

        for _, anchor_row in anchor_units.iterrows():
            machine_name = str(anchor_row["machine_name_normalized"])
            machine_history = store_machines[
                store_machines["machine_name_normalized"] == machine_name
            ].copy()
            machine_stats = _recent_machine_stats(machine_history)
            unit_history = store_units[
                (store_units["unit_number"] == anchor_row["unit_number"])
                & (store_units["report_date"] <= analysis_anchor_date)
                & store_units["diff"].notna()
            ].copy()
            streak = _unit_negative_streak(unit_history)
            base_evidence = {
                "previous_day_diff": round(_safe_float(anchor_row["diff"]), 2),
                "previous_day_games": round(_safe_float(anchor_row["games"]), 2),
                "recent_avg_diff": machine_stats["avg_diff"],
                "recent_avg_games": machine_stats["avg_game"],
                "win_rate": machine_stats["win_rate"],
                "sample_count": int(machine_stats["sample_count"]),
            }

            if (
                quality_good
                and _safe_float(anchor_row["diff"]) <= -1000
                and _safe_float(anchor_row["games"]) >= 2000
                and _safe_float(machine_stats["avg_game"]) >= 1500
            ):
                score = (
                    48.0
                    + min(abs(_safe_float(anchor_row["diff"])) / 150.0, 14.0)
                    + min(_safe_float(anchor_row["games"]) / 450.0, 12.0)
                    + (8.0 if streak >= 2 else 0.0)
                    + (10.0 if streak >= 3 else 0.0)
                    + min(max(_safe_float(machine_stats["avg_diff"]), 0.0) / 300.0, 10.0)
                    + min(max(recent_store_avg_diff, 0.0) / 500.0, 8.0)
                )
                score = _apply_priority_score(score, priority_group, quality_good)
                confidence = _confidence_letter(
                    score=score,
                    sample_count=int(machine_stats["sample_count"]),
                    quality_good=quality_good,
                    caution_penalty=0,
                )
                caution = ""
                if int(machine_stats["sample_count"]) < 5:
                    caution = "sample_count少なめのため参考程度"
                raise_candidates.append(
                    _candidate_dict(
                        store_id=store.store_id,
                        store_name=store.display_name,
                        priority_group=priority_group,
                        machine_name=machine_name,
                        unit_number=str(anchor_row["unit_number"]),
                        target_type="raise_candidate",
                        score=score,
                        confidence=confidence,
                        reason=(
                            f"基準日マイナス差枚 {round(_safe_float(anchor_row['diff']), 2)}、"
                            f" {round(_safe_float(anchor_row['games']), 2)}G。"
                            f" {streak}日連続凹み。"
                        ),
                        evidence=base_evidence,
                        caution=caution,
                    )
                )

        if quality_good:
            tail_frame = store_units[
                store_units["diff"].notna()
                & store_units["games"].notna()
                & store_units["tail"].notna()
            ].copy()
            if not tail_frame.empty:
                last_date = tail_frame["report_date"].max()
                recent_cutoff = last_date - timedelta(days=7)
                for tail, group in tail_frame.groupby("tail"):
                    sample_count = int(len(group))
                    if sample_count < 5:
                        continue
                    recent_group = group[group["report_date"] >= recent_cutoff]
                    avg_diff = _safe_float(group["diff"].mean())
                    avg_games = _safe_float(group["games"].mean())
                    recent_avg_diff = _safe_float(recent_group["diff"].mean())
                    recent_avg_games = _safe_float(recent_group["games"].mean())
                    win_rate = _safe_float((group["diff"] > 0).mean())
                    if recent_avg_diff <= 0:
                        continue
                    score = (
                        45.0
                        + avg_diff * 0.01
                        + recent_avg_diff * 0.012
                        + avg_games * 0.002
                        + win_rate * 16.0
                        + min(sample_count, 30) * 0.5
                    )
                    score = _apply_priority_score(score, priority_group, quality_good)
                    confidence = _confidence_letter(
                        score=score,
                        sample_count=sample_count,
                        quality_good=quality_good,
                        caution_penalty=0,
                    )
                    caution = ""
                    if sample_count < 10:
                        caution = "sample_count少なめのため参考程度"
                    tail_candidates.append(
                        _candidate_dict(
                            store_id=store.store_id,
                            store_name=store.display_name,
                            priority_group=priority_group,
                            machine_name="",
                            unit_number=f"末尾{tail}",
                            target_type="tail_candidate",
                            score=score,
                            confidence=confidence,
                            reason=(
                                f"末尾{tail} が直近でプラス傾向。"
                                f" 平均差枚 {round(avg_diff, 2)} / 平均G数 {round(avg_games, 2)}。"
                            ),
                            evidence={
                                "previous_day_diff": None,
                                "previous_day_games": None,
                                "recent_avg_diff": round(recent_avg_diff, 2),
                                "recent_avg_games": round(recent_avg_games, 2),
                                "win_rate": round(win_rate, 4),
                                "sample_count": sample_count,
                            },
                            caution=caution,
                        )
                    )

        anchor_machine_units = anchor_units[anchor_units["unit_int"].notna()].copy()
        for machine_name, group in anchor_machine_units.groupby("machine_name_normalized"):
            machine_history_units = store_units[
                store_units["machine_name_normalized"] == machine_name
            ].copy()
            history_days = _cluster_history_days(machine_history_units)
            machine_history = store_machines[
                store_machines["machine_name_normalized"] == machine_name
            ].copy()
            machine_stats = _recent_machine_stats(machine_history)
            for cluster in _cluster_ranges(group, min_games=2000):
                score = (
                    52.0
                    + cluster["length"] * 8.0
                    + min(cluster["avg_diff"] / 250.0, 14.0)
                    + min(cluster["avg_games"] / 800.0, 10.0)
                    + min(history_days * 4.0, 12.0)
                    + min(max(_safe_float(machine_stats["avg_diff"]), 0.0) / 350.0, 8.0)
                )
                score = _apply_priority_score(score, priority_group, quality_good)
                confidence = _confidence_letter(
                    score=score,
                    sample_count=max(history_days, cluster["length"]),
                    quality_good=quality_good,
                    caution_penalty=0,
                )
                caution = ""
                if history_days < 2:
                    caution = "sample_count少なめのため参考程度"
                cluster_candidates.append(
                    _candidate_dict(
                        store_id=store.store_id,
                        store_name=store.display_name,
                        priority_group=priority_group,
                        machine_name=str(machine_name),
                        unit_number=str(cluster["pattern"]),
                        target_type="cluster_candidate",
                        score=score,
                        confidence=confidence,
                        reason=(
                            f"基準日に {cluster['pattern']} の並びで"
                            f" {cluster['length']}台プラス。高G数を伴う。"
                        ),
                        evidence={
                            "previous_day_diff": cluster["avg_diff"],
                            "previous_day_games": cluster["avg_games"],
                            "recent_avg_diff": machine_stats["avg_diff"],
                            "recent_avg_games": machine_stats["avg_game"],
                            "win_rate": machine_stats["win_rate"],
                            "sample_count": history_days,
                        },
                        caution=caution,
                    )
                )

    def _trim(candidates: list[dict[str, object]], per_store_limit: int) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        counts: dict[str, int] = {}
        for candidate in sorted(candidates, key=_candidate_sort_key):
            count = counts.get(candidate["store_id"], 0)
            if count >= per_store_limit:
                continue
            result.append(candidate)
            counts[candidate["store_id"]] = count + 1
        return result

    return (
        _trim(raise_candidates, 3),
        _trim(tail_candidates, 2),
        _trim(cluster_candidates, 2),
    )


def _count_cluster_matches(
    frame: pd.DataFrame,
    *,
    require_positive_diff: bool,
    min_games: int | None,
    min_length: int,
) -> int:
    if frame.empty:
        return 0
    total = 0
    for _, group in frame.groupby("machine_name_normalized"):
        clusters = _cluster_ranges_filtered(
            group,
            require_positive_diff=require_positive_diff,
            min_games=min_games,
        )
        total += sum(1 for cluster in clusters if int(cluster["length"]) >= min_length)
    return total


def debug_target_conditions(
    *,
    database,
    store_normalizer: StoreNormalizer,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
) -> dict[str, object]:
    stores = store_normalizer.list_stores()
    daily_df, machine_df, unit_df = _query_lookback_frames(
        database,
        target_date,
        lookback_days,
        source=source,
    )
    daily_df, machine_df, unit_df = _prepare_frames(daily_df, machine_df, unit_df)
    _, quality_map = _build_store_payloads(
        stores=stores,
        daily_df=daily_df,
        unit_df=unit_df,
        target_date=target_date,
        status_overrides=None,
    )

    previous_day = target_date - timedelta(days=1)
    latest_unit_date = None if unit_df.empty else unit_df["report_date"].dropna().max()

    def _snapshot_for_day(snapshot_date: date | None) -> dict[str, object]:
        if snapshot_date is None:
            return {
                "date": None,
                "unit_rows": 0,
                "unit_rows_complete": 0,
                "store_rows": 0,
                "raise": {
                    "diff_le_neg500": 0,
                    "diff_le_neg1000": 0,
                    "games_ge_1000": 0,
                    "games_ge_2000": 0,
                    "diff_le_neg500_and_games_ge_1000": 0,
                    "diff_le_neg1000_and_games_ge_2000": 0,
                    "negative_streak_ge_2": 0,
                    "negative_streak_ge_3": 0,
                    "machine_avg_games_ge_1500": 0,
                    "quality_good": 0,
                    "final_candidates": 0,
                },
                "cluster": {
                    "consecutive2plus_same_day_machine": 0,
                    "positive_diff_consecutive2plus": 0,
                    "positive_diff_games_ge_1000_consecutive2plus": 0,
                    "positive_diff_games_ge_2000_consecutive2plus": 0,
                    "positive_diff_games_ge_2000_consecutive3plus": 0,
                    "final_candidates": 0,
                },
            }

        day_units = unit_df[unit_df["report_date"] == snapshot_date].copy()
        day_complete = day_units[day_units["diff"].notna() & day_units["games"].notna()].copy()
        raise_counts = {
            "diff_le_neg500": 0,
            "diff_le_neg1000": 0,
            "games_ge_1000": 0,
            "games_ge_2000": 0,
            "diff_le_neg500_and_games_ge_1000": 0,
            "diff_le_neg1000_and_games_ge_2000": 0,
            "negative_streak_ge_2": 0,
            "negative_streak_ge_3": 0,
            "machine_avg_games_ge_1500": 0,
            "quality_good": 0,
            "final_candidates": 0,
        }
        cluster_counts = {
            "consecutive2plus_same_day_machine": 0,
            "positive_diff_consecutive2plus": 0,
            "positive_diff_games_ge_1000_consecutive2plus": 0,
            "positive_diff_games_ge_2000_consecutive2plus": 0,
            "positive_diff_games_ge_2000_consecutive3plus": 0,
            "final_candidates": 0,
        }

        for store in stores:
            store_day_units = day_units[day_units["store_id"] == store.store_id].copy()
            store_complete = day_complete[day_complete["store_id"] == store.store_id].copy()
            if store_day_units.empty:
                continue

            quality = quality_map[store.store_id]
            quality_good = (
                float(quality["diff_missing_rate"]) < 0.1
                and str(quality["pattern_analysis_status"]) == "台番分析可能"
            )
            store_machines = machine_df[machine_df["store_id"] == store.store_id].copy()

            cluster_counts["consecutive2plus_same_day_machine"] += _count_cluster_matches(
                store_day_units,
                require_positive_diff=False,
                min_games=None,
                min_length=2,
            )
            cluster_counts["positive_diff_consecutive2plus"] += _count_cluster_matches(
                store_day_units,
                require_positive_diff=True,
                min_games=None,
                min_length=2,
            )
            cluster_counts["positive_diff_games_ge_1000_consecutive2plus"] += (
                _count_cluster_matches(
                    store_day_units,
                    require_positive_diff=True,
                    min_games=1000,
                    min_length=2,
                )
            )
            cluster_counts["positive_diff_games_ge_2000_consecutive2plus"] += (
                _count_cluster_matches(
                    store_day_units,
                    require_positive_diff=True,
                    min_games=2000,
                    min_length=2,
                )
            )
            cluster_counts["positive_diff_games_ge_2000_consecutive3plus"] += (
                _count_cluster_matches(
                    store_day_units,
                    require_positive_diff=True,
                    min_games=2000,
                    min_length=3,
                )
            )
            cluster_counts["final_candidates"] += _count_cluster_matches(
                store_day_units,
                require_positive_diff=True,
                min_games=2000,
                min_length=2,
            )

            for _, prev_row in store_complete.iterrows():
                diff = _safe_float(prev_row["diff"])
                games = _safe_float(prev_row["games"])
                machine_name = str(prev_row["machine_name_normalized"])
                machine_history = store_machines[
                    store_machines["machine_name_normalized"] == machine_name
                ].copy()
                machine_stats = _recent_machine_stats(machine_history)
                unit_history = unit_df[
                    (unit_df["store_id"] == store.store_id)
                    & (unit_df["unit_number"] == prev_row["unit_number"])
                    & (unit_df["report_date"] < target_date)
                    & unit_df["diff"].notna()
                ].copy()
                streak = _unit_negative_streak(unit_history)

                if diff <= -500:
                    raise_counts["diff_le_neg500"] += 1
                if diff <= -1000:
                    raise_counts["diff_le_neg1000"] += 1
                if games >= 1000:
                    raise_counts["games_ge_1000"] += 1
                if games >= 2000:
                    raise_counts["games_ge_2000"] += 1
                if diff <= -500 and games >= 1000:
                    raise_counts["diff_le_neg500_and_games_ge_1000"] += 1
                if diff <= -1000 and games >= 2000:
                    raise_counts["diff_le_neg1000_and_games_ge_2000"] += 1
                if streak >= 2:
                    raise_counts["negative_streak_ge_2"] += 1
                if streak >= 3:
                    raise_counts["negative_streak_ge_3"] += 1
                if _safe_float(machine_stats["avg_game"]) >= 1500:
                    raise_counts["machine_avg_games_ge_1500"] += 1
                if quality_good:
                    raise_counts["quality_good"] += 1
                if (
                    quality_good
                    and diff <= -1000
                    and games >= 2000
                    and _safe_float(machine_stats["avg_game"]) >= 1500
                ):
                    raise_counts["final_candidates"] += 1

        return {
            "date": snapshot_date.isoformat(),
            "unit_rows": int(len(day_units)),
            "unit_rows_complete": int(len(day_complete)),
            "store_rows": int(day_units["store_id"].nunique()) if not day_units.empty else 0,
            "raise": raise_counts,
            "cluster": cluster_counts,
        }

    previous_day_snapshot = _snapshot_for_day(previous_day)
    analysis_anchor_snapshot = _snapshot_for_day(latest_unit_date)
    anchor_notice = ""
    if latest_unit_date and latest_unit_date != previous_day:
        anchor_notice = (
            f"最新取得データは {latest_unit_date.isoformat()} のため、"
            "この日を基準に候補抽出しています。"
        )
    raise_reason = (
        "前日 unit データが 0 件のため、上げ狙い候補は条件判定まで進んでいません。"
        if previous_day_snapshot["unit_rows"] == 0
        else (
            "前日 unit データは存在します。"
            "最終ゲートは quality / diff / games / machine_avg_games です。"
        )
    )
    cluster_reason = (
        "前日 unit データが 0 件のため、並び候補は同日・同機種・連番判定まで進んでいません。"
        if previous_day_snapshot["unit_rows"] == 0
        else "前日 unit データは存在します。最終ゲートは diff > 0 と games >= 2000 の連番です。"
    )
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_date": target_date.isoformat(),
        "source": source or "all",
        "lookback_days": lookback_days,
        "coverage_window": _coverage_window_text(unit_df, target_date, lookback_days),
        "calendar_previous_day": previous_day.isoformat(),
        "latest_available_unit_date": latest_unit_date.isoformat() if latest_unit_date else None,
        "analysis_anchor_date": latest_unit_date.isoformat() if latest_unit_date else None,
        "analysis_anchor_notice": anchor_notice,
        "previous_day_snapshot": previous_day_snapshot,
        "analysis_anchor_snapshot": analysis_anchor_snapshot,
        "raise_reason": raise_reason,
        "cluster_reason": cluster_reason,
    }


def _rank_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for index, candidate in enumerate(
        sorted(candidates, key=_candidate_sort_key),
        start=1,
    ):
        updated = dict(candidate)
        updated["rank"] = index
        ranked.append(updated)
    return ranked


def _candidate_counts(candidates: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "S": 0,
        "A": 0,
        "B": 0,
        "見送り": 0,
        "raise_candidate": 0,
        "tail_candidate": 0,
        "cluster_candidate": 0,
        "machine_candidate": 0,
    }
    for candidate in candidates:
        counts[str(candidate["tier"])] += 1
        counts[str(candidate["target_type"])] += 1
    return counts


def analyze_targets(
    *,
    database,
    store_normalizer: StoreNormalizer,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
    status_overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, object]:
    stores = store_normalizer.list_stores()
    daily_df, machine_df, unit_df = _query_lookback_frames(
        database,
        target_date,
        lookback_days,
        source=source,
    )
    daily_df, machine_df, unit_df = _prepare_frames(daily_df, machine_df, unit_df)
    analysis_anchor_date = _latest_available_unit_date(unit_df, target_date)
    store_scores, quality_map = _build_store_payloads(
        stores=stores,
        daily_df=daily_df,
        unit_df=unit_df,
        target_date=target_date,
        status_overrides=status_overrides,
    )
    machine_scores, machine_candidates = _build_machine_payloads(
        stores=stores,
        machine_df=machine_df,
        store_payloads=store_scores,
        quality_map=quality_map,
    )
    raise_candidates, tail_candidates, cluster_candidates = _build_unit_candidates(
        stores=stores,
        target_date=target_date,
        daily_df=daily_df,
        machine_df=machine_df,
        unit_df=unit_df,
        quality_map=quality_map,
        analysis_anchor_date=analysis_anchor_date,
    )
    all_candidates = _rank_candidates(
        machine_candidates
        + raise_candidates
        + tail_candidates
        + cluster_candidates
    )
    counts = _candidate_counts(all_candidates)
    coverage_window = _coverage_window_text(unit_df, target_date, lookback_days)
    priority_groups = {
        key: [
            store.display_name
            for store in stores
            if _priority_group(store.priority_group) == key
        ]
        for key in ("main", "sub", "watch")
    }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_date": target_date.isoformat(),
        "source": source or "all",
        "lookback_days": lookback_days,
        "coverage_window": coverage_window,
        "analysis_anchor_date": (
            analysis_anchor_date.isoformat() if analysis_anchor_date else None
        ),
        "analysis_anchor_notice": (
            ""
            if (
                analysis_anchor_date is None
                or analysis_anchor_date == target_date - timedelta(days=1)
            )
            else (
                f"最新取得データは {analysis_anchor_date.isoformat()} のため、"
                "この日を基準に候補抽出しています。"
            )
        ),
        "summary": {
            "store_count": len(stores),
            "available_store_count": sum(
                1 for row in store_scores if float(row["unit_diff_missing_rate"]) < 0.1
            ),
            "partial_success_stores": sum(
                1 for row in store_scores if row["fetch_status"] == "partial_success"
            ),
            "priority_candidate_counts": {
                "main": sum(1 for row in all_candidates if row["priority_group"] == "main"),
                "sub": sum(1 for row in all_candidates if row["priority_group"] == "sub"),
                "watch": sum(1 for row in all_candidates if row["priority_group"] == "watch"),
            },
            "target_counts": counts,
        },
        "priority_groups": priority_groups,
        "store_scores": store_scores,
        "machine_scores": machine_scores[:50],
        "candidates": all_candidates,
        "sections": {
            "machine_candidates": [
                row for row in all_candidates if row["target_type"] == "machine_candidate"
            ][:12],
            "raise_candidates": [
                row for row in all_candidates if row["target_type"] == "raise_candidate"
            ][:20],
            "tail_candidates": [
                row for row in all_candidates if row["target_type"] == "tail_candidate"
            ][:20],
            "cluster_candidates": [
                row for row in all_candidates if row["target_type"] == "cluster_candidate"
            ][:20],
        },
    }


def _markdown_candidate_lines(
    title: str,
    candidates: list[dict[str, object]],
) -> list[str]:
    lines = [f"## {title}"]
    if not candidates:
        lines.append("- なし")
        return lines
    for row in candidates:
        evidence = row["evidence"]
        label = row["machine_name"] or row["unit_number"] or "-"
        lines.append(
            f"- {row['rank']}. {row['store_name']} | {label} | "
            f"type={row['target_type']} | priority_group={row['priority_group']} | "
            f"score={row['score']} | confidence={row['confidence']}"
        )
        lines.append(f"  - reason: {row['reason']}")
        lines.append(
            "  - evidence: "
            f"prev_diff={evidence['previous_day_diff']} / "
            f"prev_games={evidence['previous_day_games']} / "
            f"recent_avg_diff={evidence['recent_avg_diff']} / "
            f"recent_avg_games={evidence['recent_avg_games']} / "
            f"win_rate={evidence['win_rate']} / "
            f"sample_count={evidence['sample_count']}"
        )
        lines.append(f"  - caution: {row['caution'] or 'なし'}")
    return lines


def write_targets_outputs(
    *,
    database,
    store_normalizer: StoreNormalizer,
    target_date: date,
    lookback_days: int,
    reports_dir: Path,
    public_dir: Path,
    source: str | None = None,
    status_overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, object], Path, Path]:
    payload = analyze_targets(
        database=database,
        store_normalizer=store_normalizer,
        target_date=target_date,
        lookback_days=lookback_days,
        source=source,
        status_overrides=status_overrides,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "data").mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"targets_{target_date.isoformat()}.md"
    json_path = public_dir / "data" / "targets.json"

    counts = payload["summary"]["target_counts"]
    lines = [
        f"# Targets {target_date.isoformat()}",
        "",
        f"- source: {payload['source']}",
        f"- coverage_window: {payload['coverage_window']}",
        f"- lookback_days: {payload['lookback_days']}",
        f"- analysis_anchor_date: {payload['analysis_anchor_date']}",
        f"- generated_at: {payload['generated_at']}",
        f"- S/A/B/見送り: {counts['S']} / {counts['A']} / {counts['B']} / {counts['見送り']}",
        (
            f"- raise/tail/cluster/machine: "
            f"{counts['raise_candidate']} / "
            f"{counts['tail_candidate']} / {counts['cluster_candidate']} / "
            f"{counts['machine_candidate']}"
        ),
        f"- main: {', '.join(payload['priority_groups']['main'])}",
        f"- sub: {', '.join(payload['priority_groups']['sub'])}",
        f"- watch: {', '.join(payload['priority_groups']['watch'])}",
        "",
        "## 店舗スコア",
    ]
    if payload["analysis_anchor_notice"]:
        lines.insert(7, f"- note: {payload['analysis_anchor_notice']}")
    for row in payload["store_scores"]:
        lines.append(
            f"- {row['store_name']} | priority_group={row['priority_group']} | "
            f"days={row['days']} | total_diff={row['total_diff']} | "
            f"avg_diff={row['avg_diff']} | avg_game={row['avg_game']} | "
            f"win_rate={row['win_rate']} | unit_rows={row['unit_results_total']} | "
            f"fetch_status={row['fetch_status']} | "
            f"failed_machine_pages={row['failed_machine_pages']} | "
            f"store_score={row['store_score']}"
        )
    lines.append("")
    lines.append("## 機種スコア")
    for row in payload["machine_scores"][:20]:
        lines.append(
            f"- {row['store_name']} | {row['machine_name']} | days={row['active_days']} | "
            f"unit_count={row['unit_count']} | avg_diff={row['avg_diff']} | "
            f"avg_game={row['avg_game']} | win_rate={row['win_rate']} | "
            f"recent_trend={row['recent_trend']} | score={row['machine_score']}"
        )
    lines.append("")
    for section_title, key in (
        ("狙い機種", "machine_candidates"),
        ("上げ狙い候補", "raise_candidates"),
        ("末尾候補", "tail_candidates"),
        ("並び候補", "cluster_candidates"),
    ):
        lines.extend(_markdown_candidate_lines(section_title, payload["sections"][key]))
        lines.append("")

    report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, report_path, json_path
