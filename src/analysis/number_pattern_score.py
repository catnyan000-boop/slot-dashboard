from __future__ import annotations

import re

import pandas as pd

from .cluster_score import detect_positive_clusters


def _tail_number(value: str) -> str | None:
    match = re.search(r"(\d+)", str(value))
    if not match:
        return None
    return str(int(match.group(1)) % 10)


def score_number_patterns(unit_df: pd.DataFrame, store_id: str) -> list[dict[str, object]]:
    frame = unit_df[unit_df["store_id"] == store_id].copy()
    if frame.empty:
        return []

    frame["diff"] = pd.to_numeric(frame["diff"], errors="coerce")
    frame["games"] = pd.to_numeric(frame["games"], errors="coerce").fillna(0.0)
    frame["tail"] = frame["unit_number"].map(_tail_number)
    frame = frame[frame["tail"].notna() & frame["diff"].notna()]
    if frame.empty:
        return []

    patterns: list[dict[str, object]] = []
    for tail, group in frame.groupby("tail"):
        patterns.append(
            {
                "pattern": f"末尾{tail}",
                "score": round(
                    group["diff"].mean() * 0.01
                    + group["games"].mean() * 0.002
                    + (group["diff"] > 0).mean() * 15.0
                    + min(len(group), 50) * 0.2,
                    2,
                ),
                "avg_diff": round(float(group["diff"].mean()), 2),
                "avg_game": round(float(group["games"].mean()), 2),
                "win_rate": round(float((group["diff"] > 0).mean()), 4),
                "sample_size": int(len(group)),
            }
        )

    clusters = detect_positive_clusters(frame)
    for cluster in clusters:
        patterns.append(
            {
                "pattern": f"並び{cluster['pattern']}",
                "score": round(float(cluster["count"]) * 3.0, 2),
                "avg_diff": None,
                "avg_game": None,
                "win_rate": None,
                "sample_size": int(cluster["count"]),
            }
        )

    return sorted(patterns, key=lambda item: float(item["score"]), reverse=True)
