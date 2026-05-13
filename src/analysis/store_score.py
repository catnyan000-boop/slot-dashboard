from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.analysis.event_day_score import compute_event_day_edge
from src.db.models import StoreDefinition


@dataclass
class ScoredStore:
    store_id: str
    display_name: str
    score: float
    confidence: float
    sample_size: int
    reason: dict[str, object]


def _safe_value(value: float) -> float:
    if value is None or math.isnan(value):
        return 0.0
    return float(value)


def _confidence(sample_size: int, avg_game: float, consistency: float, metric_count: int) -> float:
    sample_component = min(sample_size / 60.0, 1.0)
    game_component = min(avg_game / 4000.0, 1.0)
    metric_component = min(metric_count / 8.0, 1.0)
    return round(
        sample_component * 0.45
        + game_component * 0.25
        + consistency * 0.2
        + metric_component * 0.1,
        3,
    )


def score_stores(
    daily_df: pd.DataFrame,
    stores: list[StoreDefinition],
    target_date: date,
) -> list[ScoredStore]:
    frame = daily_df.copy()
    if not frame.empty:
        frame["report_date"] = pd.to_datetime(frame["report_date"])
        for column in ["total_diff", "avg_diff", "avg_game", "win_rate", "total_units"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    results: list[ScoredStore] = []
    for store in stores:
        if frame.empty:
            store_frame = pd.DataFrame()
        else:
            store_frame = frame[frame["store_id"] == store.store_id].copy()
        if store_frame.empty:
            results.append(
                ScoredStore(
                    store_id=store.store_id,
                    display_name=store.display_name,
                    score=0.0,
                    confidence=0.15,
                    sample_size=0,
                    reason={"note": "データ不足"},
                )
            )
            continue

        avg_diff = _safe_value(store_frame["avg_diff"].mean())
        median_diff = _safe_value(store_frame["avg_diff"].median())
        avg_game = _safe_value(store_frame["avg_game"].mean())
        mean_win_rate = _safe_value(store_frame["win_rate"].mean())
        positive_day_rate = float(
            ((store_frame["total_diff"].fillna(store_frame["avg_diff"]) > 0).mean())
        )
        volatility = _safe_value(store_frame["avg_diff"].std(ddof=0))
        recent_cutoff = store_frame["report_date"].max() - pd.Timedelta(days=30)
        recent_avg = _safe_value(
            store_frame.loc[store_frame["report_date"] >= recent_cutoff, "avg_diff"].mean()
        )
        historical_avg = _safe_value(
            store_frame.loc[store_frame["report_date"] < recent_cutoff, "avg_diff"].mean()
        )
        recent_trend = recent_avg - historical_avg
        weekday_avg = _safe_value(
            store_frame.loc[
                store_frame["report_date"].dt.weekday == target_date.weekday(), "avg_diff"
            ].mean()
        )
        tail_avg = _safe_value(
            store_frame.loc[
                store_frame["report_date"].dt.day % 10 == target_date.day % 10, "avg_diff"
            ].mean()
        )
        event_edge = compute_event_day_edge(store_frame, store.event_days, target_date)

        base_score = (
            avg_diff * 0.012
            + median_diff * 0.008
            + avg_game * 0.003
            + mean_win_rate * 20.0
            + positive_day_rate * 18.0
            + recent_trend * 0.01
            + weekday_avg * 0.004
            + tail_avg * 0.004
            + event_edge * 10.0
            - volatility * 0.004
        )
        score = round(max(0.0, min(100.0, 50.0 + base_score)), 2)

        consistency = max(0.0, min(1.0, 1.0 - (volatility / max(abs(avg_diff), 1500.0))))
        metric_count = sum(
            value is not None
            for value in [
                avg_diff,
                median_diff,
                avg_game,
                mean_win_rate,
                positive_day_rate,
                recent_trend,
            ]
        )
        confidence = _confidence(len(store_frame), avg_game, consistency, metric_count)

        reason = {
            "avg_diff": round(avg_diff, 2),
            "median_diff": round(median_diff, 2),
            "avg_game": round(avg_game, 2),
            "win_rate": round(mean_win_rate, 4),
            "positive_day_rate": round(positive_day_rate, 4),
            "volatility": round(volatility, 2),
            "recent_trend": round(recent_trend, 2),
            "weekday_avg": round(weekday_avg, 2),
            "tail_avg": round(tail_avg, 2),
            "event_edge": round(event_edge, 3),
            "event_days": store.event_days,
        }
        results.append(
            ScoredStore(
                store_id=store.store_id,
                display_name=store.display_name,
                score=score,
                confidence=confidence,
                sample_size=int(len(store_frame)),
                reason=json.loads(json.dumps(reason, ensure_ascii=False)),
            )
        )

    return sorted(results, key=lambda item: item.score, reverse=True)
