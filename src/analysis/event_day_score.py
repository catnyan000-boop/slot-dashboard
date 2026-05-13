from __future__ import annotations

from datetime import date

import pandas as pd


def _matches_event_day(day_value: int, token: str) -> bool:
    if token == "0":
        return day_value % 10 == 0
    try:
        return day_value == int(token)
    except ValueError:
        return False


def compute_event_day_edge(
    frame: pd.DataFrame,
    event_days: list[str],
    target_date: date,
) -> float:
    if frame.empty or not event_days:
        return 0.0
    data = frame.copy()
    data["report_date"] = pd.to_datetime(data["report_date"])
    event_mask = data["report_date"].dt.day.apply(
        lambda value: any(_matches_event_day(int(value), token) for token in event_days)
    )
    target_tokens = [str(target_date.day), str(target_date.day % 10)]
    target_mask = data["report_date"].dt.day.apply(
        lambda value: any(_matches_event_day(int(value), token) for token in target_tokens)
    )
    baseline = pd.to_numeric(data["avg_diff"], errors="coerce").fillna(0.0)
    event_mean = baseline[event_mask].mean() if event_mask.any() else 0.0
    target_mean = baseline[target_mask].mean() if target_mask.any() else 0.0
    overall_mean = baseline.mean() if not baseline.empty else 0.0
    return ((event_mean - overall_mean) * 0.6 + (target_mean - overall_mean) * 0.4) / 1000.0
