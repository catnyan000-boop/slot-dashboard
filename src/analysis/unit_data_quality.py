from __future__ import annotations

import pandas as pd


def classify_missing_rate(missing_rate: float) -> str:
    if missing_rate < 0.1:
        return "台番分析可能"
    if missing_rate < 0.3:
        return "台番分析は注意付き"
    if missing_rate < 0.5:
        return "台番分析は参考程度"
    return "台番分析は信頼不可"


def _group_missing(frame: pd.DataFrame, group_column: str) -> list[dict[str, object]]:
    if frame.empty:
        return []
    grouped = (
        frame.groupby(group_column)
        .agg(
            total=(group_column, "size"),
            diff_null=("diff", lambda series: int(series.isna().sum())),
        )
        .reset_index()
    )
    grouped["missing_rate"] = grouped["diff_null"] / grouped["total"]
    grouped["status"] = grouped["missing_rate"].map(classify_missing_rate)
    grouped = grouped.sort_values(
        ["missing_rate", "diff_null", "total"],
        ascending=[False, False, False],
    )
    return grouped.to_dict(orient="records")


def summarize_unit_data_quality(
    unit_df: pd.DataFrame,
    store_id: str,
    warning_threshold: float = 0.3,
) -> dict[str, object]:
    frame = unit_df[unit_df["store_id"] == store_id].copy()
    if frame.empty:
        return {
            "total_rows": 0,
            "diff_null_count": 0,
            "diff_zero_count": 0,
            "games_null_count": 0,
            "payout_null_count": 0,
            "diff_missing_rate": 1.0,
            "pattern_analysis_ready": False,
            "pattern_analysis_status": "データ不足",
            "warning": True,
            "machine_missing": [],
            "category_missing": [],
            "date_missing": [],
            "actual_diff_rows": 0,
            "unit_analysis_rows": 0,
            "tail_analysis_rows": 0,
            "cluster_analysis_rows": 0,
            "tail_analysis_status": "データ不足",
            "cluster_analysis_status": "データ不足",
            "excluded_machines": [],
            "excluded_categories": [],
            "effective_analyses": ["店舗別", "機種別", "カテゴリ別"],
        }

    frame["diff"] = pd.to_numeric(frame["diff"], errors="coerce")
    frame["games"] = pd.to_numeric(frame["games"], errors="coerce")
    frame["payout_rate"] = pd.to_numeric(frame["payout_rate"], errors="coerce")

    total_rows = int(len(frame))
    diff_null_count = int(frame["diff"].isna().sum())
    diff_zero_count = int((frame["diff"] == 0).fillna(False).sum())
    games_null_count = int(frame["games"].isna().sum())
    payout_null_count = int(frame["payout_rate"].isna().sum())
    actual_diff_rows = total_rows - diff_null_count
    diff_missing_rate = diff_null_count / total_rows if total_rows else 1.0

    machine_missing = _group_missing(frame, "machine_name_normalized")
    category_missing = _group_missing(frame, "machine_category")

    date_missing = (
        frame.groupby("report_date")
        .agg(
            total=("report_date", "size"),
            diff_null=("diff", lambda series: int(series.isna().sum())),
        )
        .reset_index()
    )
    date_missing["missing_rate"] = date_missing["diff_null"] / date_missing["total"]
    date_missing["status"] = date_missing["missing_rate"].map(classify_missing_rate)
    date_missing = date_missing.sort_values("report_date", ascending=False)

    warning = diff_missing_rate >= warning_threshold
    pattern_analysis_status = classify_missing_rate(diff_missing_rate)
    if actual_diff_rows < 1:
        pattern_analysis_ready = False
        pattern_analysis_status = "データ不足"
    elif diff_missing_rate < 0.5:
        pattern_analysis_ready = True
    else:
        pattern_analysis_ready = False

    excluded_machines = [
        {
            "machine_name": row["machine_name_normalized"],
            "missing_rate": round(float(row["missing_rate"]), 4),
            "reason": f"欠損率 {round(float(row['missing_rate']) * 100, 1)}% のため除外",
            "status": row["status"],
        }
        for row in machine_missing
        if float(row["missing_rate"]) >= 0.5
    ]
    excluded_categories = [
        {
            "category": row["machine_category"],
            "missing_rate": round(float(row["missing_rate"]), 4),
            "reason": f"カテゴリ欠損率 {round(float(row['missing_rate']) * 100, 1)}% のため除外",
            "status": row["status"],
        }
        for row in category_missing
        if float(row["missing_rate"]) >= 0.5
    ]

    excluded_machine_names = {row["machine_name"] for row in excluded_machines}
    excluded_category_names = {row["category"] for row in excluded_categories}
    eligible_frame = frame[
        frame["diff"].notna()
        & ~frame["machine_name_normalized"].isin(excluded_machine_names)
        & ~frame["machine_category"].isin(excluded_category_names)
    ].copy()

    unit_analysis_rows = int(len(eligible_frame))
    tail_analysis_rows = int(eligible_frame["unit_number"].astype(str).str.contains(r"\d").sum())
    cluster_analysis_rows = int((eligible_frame["games"].fillna(0) >= 1000).sum())

    tail_analysis_status = pattern_analysis_status
    cluster_analysis_status = pattern_analysis_status
    if pattern_analysis_ready and unit_analysis_rows == 0:
        tail_analysis_status = "データ不足"
        cluster_analysis_status = "データ不足"

    effective_analyses = ["店舗別", "機種別", "カテゴリ別"]
    if pattern_analysis_ready and unit_analysis_rows > 0:
        effective_analyses.append("台番別")
    if pattern_analysis_ready and tail_analysis_rows > 0:
        effective_analyses.append("末尾別")
    if pattern_analysis_ready and cluster_analysis_rows > 0:
        effective_analyses.append("並び")

    return {
        "total_rows": total_rows,
        "diff_null_count": diff_null_count,
        "diff_zero_count": diff_zero_count,
        "games_null_count": games_null_count,
        "payout_null_count": payout_null_count,
        "diff_missing_rate": round(diff_missing_rate, 4),
        "pattern_analysis_ready": pattern_analysis_ready,
        "pattern_analysis_status": pattern_analysis_status,
        "warning": warning,
        "machine_missing": machine_missing[:20],
        "category_missing": category_missing[:20],
        "date_missing": date_missing.head(20).to_dict(orient="records"),
        "actual_diff_rows": actual_diff_rows,
        "unit_analysis_rows": unit_analysis_rows,
        "tail_analysis_rows": tail_analysis_rows,
        "cluster_analysis_rows": cluster_analysis_rows,
        "tail_analysis_status": tail_analysis_status,
        "cluster_analysis_status": cluster_analysis_status,
        "excluded_machines": excluded_machines[:20],
        "excluded_categories": excluded_categories[:20],
        "effective_analyses": effective_analyses,
        "eligible_machine_names": sorted(
            set(eligible_frame["machine_name_normalized"].dropna().astype(str).tolist())
        ),
        "eligible_categories": sorted(
            set(eligible_frame["machine_category"].dropna().astype(str).tolist())
        ),
    }
