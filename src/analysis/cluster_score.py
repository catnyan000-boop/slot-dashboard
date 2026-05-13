from __future__ import annotations

import re

import pandas as pd


def _extract_unit_numeric(value: str) -> int | None:
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else None


def detect_positive_clusters(
    frame: pd.DataFrame,
    min_games: int = 1000,
    min_cluster_length: int = 2,
) -> list[dict[str, object]]:
    if frame.empty:
        return []

    data = frame.copy()
    data["unit_int"] = data["unit_number"].map(_extract_unit_numeric)
    data["games"] = pd.to_numeric(data["games"], errors="coerce").fillna(0.0)
    data["diff"] = pd.to_numeric(data["diff"], errors="coerce")
    data = data[
        (data["unit_int"].notna())
        & (data["games"] >= min_games)
        & (data["diff"].notna())
        & (data["diff"] > 0)
    ]
    if data.empty:
        return []

    patterns: dict[str, dict[str, object]] = {}
    for report_date, day_frame in data.groupby("report_date"):
        units = sorted(int(value) for value in day_frame["unit_int"].tolist())
        if not units:
            continue
        current = [units[0]]
        for unit in units[1:]:
            if unit == current[-1] + 1:
                current.append(unit)
                continue
            if len(current) >= min_cluster_length:
                key = f"{current[0]}-{current[-1]}"
                patterns.setdefault(key, {"pattern": key, "count": 0, "dates": []})
                patterns[key]["count"] = int(patterns[key]["count"]) + 1
                patterns[key]["dates"].append(str(report_date))
            current = [unit]
        if len(current) >= min_cluster_length:
            key = f"{current[0]}-{current[-1]}"
            patterns.setdefault(key, {"pattern": key, "count": 0, "dates": []})
            patterns[key]["count"] = int(patterns[key]["count"]) + 1
            patterns[key]["dates"].append(str(report_date))

    return sorted(patterns.values(), key=lambda item: int(item["count"]), reverse=True)[:5]
