from __future__ import annotations

import math

import pandas as pd


def _safe_std(series: pd.Series) -> float:
    value = float(series.std(ddof=0)) if len(series) else 0.0
    return 0.0 if math.isnan(value) else value


def _recent_trend(data: pd.DataFrame, value_column: str) -> float:
    if data.empty:
        return 0.0
    frame = data.sort_values("report_date").copy()
    frame["report_date"] = pd.to_datetime(frame["report_date"])
    last_date = frame["report_date"].max()
    recent = pd.to_numeric(
        frame.loc[frame["report_date"] >= (last_date - pd.Timedelta(days=30)), value_column],
        errors="coerce",
    ).fillna(0.0)
    older = pd.to_numeric(
        frame.loc[frame["report_date"] < (last_date - pd.Timedelta(days=30)), value_column],
        errors="coerce",
    ).fillna(0.0)
    return float(recent.mean() - older.mean()) if not recent.empty else 0.0


def score_machine_categories(machine_df: pd.DataFrame, store_id: str) -> list[dict[str, object]]:
    frame = machine_df[machine_df["store_id"] == store_id].copy()
    if frame.empty:
        return []
    frame["avg_diff"] = pd.to_numeric(frame["avg_diff"], errors="coerce").fillna(0.0)
    frame["avg_game"] = pd.to_numeric(frame["avg_game"], errors="coerce").fillna(0.0)
    frame["win_rate"] = pd.to_numeric(frame["win_rate"], errors="coerce").fillna(0.0)

    results: list[dict[str, object]] = []
    for category, group in frame.groupby("machine_category"):
        volatility = _safe_std(group["avg_diff"])
        trend = _recent_trend(group, "avg_diff")
        score = (
            group["avg_diff"].mean() * 0.01
            + group["avg_game"].mean() * 0.003
            + group["win_rate"].mean() * 18.0
            + trend * 0.01
            - volatility * 0.004
            + min(len(group), 30) * 0.5
        )
        results.append(
            {
                "category": category,
                "score": round(score, 2),
                "avg_diff": round(float(group["avg_diff"].mean()), 2),
                "median_diff": round(float(group["avg_diff"].median()), 2),
                "avg_game": round(float(group["avg_game"].mean()), 2),
                "win_rate": round(float(group["win_rate"].mean()), 4),
                "sample_size": int(len(group)),
                "volatility": round(volatility, 2),
                "recent_trend": round(trend, 2),
            }
        )
    return sorted(results, key=lambda item: float(item["score"]), reverse=True)


def score_machines(machine_df: pd.DataFrame, store_id: str) -> list[dict[str, object]]:
    frame = machine_df[machine_df["store_id"] == store_id].copy()
    if frame.empty:
        return []
    frame["avg_diff"] = pd.to_numeric(frame["avg_diff"], errors="coerce").fillna(0.0)
    frame["avg_game"] = pd.to_numeric(frame["avg_game"], errors="coerce").fillna(0.0)
    frame["win_rate"] = pd.to_numeric(frame["win_rate"], errors="coerce").fillna(0.0)
    frame["unit_count"] = pd.to_numeric(frame["unit_count"], errors="coerce").fillna(0.0)

    results: list[dict[str, object]] = []
    for machine_name, group in frame.groupby("machine_name_normalized"):
        category = str(group["machine_category"].mode().iloc[0])
        volatility = _safe_std(group["avg_diff"])
        trend = _recent_trend(group, "avg_diff")
        install = float(group["unit_count"].mean())

        stability_bonus = 0.0
        if category in {"normal_a_type", "jug_hana"}:
            stability_bonus = group["avg_game"].mean() * 0.002 + group["win_rate"].mean() * 16.0
            stability_bonus -= volatility * 0.006
        elif category == "smart_slot_at":
            stability_bonus = group["avg_game"].mean() * 0.0025 + install * 1.2
            stability_bonus -= volatility * 0.0035
        else:
            stability_bonus = group["avg_game"].mean() * 0.0018 + group["win_rate"].mean() * 12.0
            stability_bonus -= volatility * 0.0045

        score = (
            group["avg_diff"].mean() * 0.01
            + trend * 0.012
            + stability_bonus
            + min(len(group), 20) * 0.4
        )
        results.append(
            {
                "machine_name": machine_name,
                "category": category,
                "score": round(score, 2),
                "avg_diff": round(float(group["avg_diff"].mean()), 2),
                "avg_game": round(float(group["avg_game"].mean()), 2),
                "win_rate": round(float(group["win_rate"].mean()), 4),
                "sample_size": int(len(group)),
                "volatility": round(volatility, 2),
                "recent_trend": round(trend, 2),
                "avg_units": round(install, 2),
            }
        )
    return sorted(results, key=lambda item: float(item["score"]), reverse=True)
