from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from src.analysis.machine_score import score_machine_categories, score_machines
from src.analysis.number_pattern_score import score_number_patterns
from src.analysis.store_score import score_stores
from src.analysis.unit_data_quality import summarize_unit_data_quality
from src.db.models import StoreScoreRecord, TargetRecommendationRecord
from src.normalizers.store_normalizer import StoreNormalizer
from src.reports.daily_report import confidence_to_letter


def _quality_value_text(value: object) -> str:
    if value is None:
        return "データ不足"
    return str(value)


def _quality_section_lines(row: dict[str, object]) -> list[str]:
    quality = row["unit_quality"]
    display_name = row["display_name"]
    total_rows = int(quality["total_rows"])
    fetch_status = str(row.get("fetch_status", "不明"))
    parse_status = str(row.get("parse_status", "不明"))
    failed_machine_pages = int(row.get("failed_machine_pages", 0) or 0)
    status_note = str(row.get("status_note", "") or "")

    lines = [f"### {display_name}"]
    lines.extend(
        [
            f"- fetch_status: {fetch_status}",
            f"- parse_status: {parse_status}",
            f"- failed_machine_pages: {failed_machine_pages}",
        ]
    )
    if status_note:
        lines.append(f"- 注意点: {status_note}")
    if total_rows == 0:
        lines.extend(
            [
                "- unit_diff_missing_rate: データ不足",
                "- unit_results_total: 0",
                "- diff_null_count: 0",
                "- 台番分析ステータス: データ不足",
                "- 末尾分析ステータス: データ不足",
                "- 並び分析ステータス: データ不足",
                "- 有効分析範囲: データ不足",
                "- データ不足",
            ]
        )
        return lines

    lines.extend(
        [
            f"- unit_diff_missing_rate: {quality['diff_missing_rate']}",
            f"- unit_results_total: {quality['total_rows']}",
            f"- diff_null_count: {quality['diff_null_count']}",
            f"- 台番分析ステータス: {quality['pattern_analysis_status']}",
            f"- 末尾分析ステータス: {quality['tail_analysis_status']}",
            f"- 並び分析ステータス: {quality['cluster_analysis_status']}",
            f"- 有効分析範囲: {', '.join(quality['effective_analyses'])}",
        ]
    )

    if quality["excluded_machines"]:
        lines.append("- 除外対象機種:")
        for machine in quality["excluded_machines"]:
            lines.append(f"  - {machine['machine_name']}: {machine['reason']}")
    else:
        lines.append("- 除外対象機種: なし")

    if float(quality["diff_missing_rate"]) >= 0.5:
        lines.extend(
            [
                "- 台番分析は信頼不可",
                "- 末尾分析は信頼不可",
                "- 並び分析は信頼不可",
                "- 現時点では店舗別・機種別・カテゴリ別分析のみ有効",
            ]
        )

    return lines


def _coverage_window_text(target_date: date, lookback_days: int) -> str:
    start_date = target_date - timedelta(days=lookback_days)
    end_date = target_date - timedelta(days=1)
    return f"{start_date.isoformat()} 〜 {end_date.isoformat()}"


def _resolved_coverage_window_text(unit_df, target_date: date, lookback_days: int) -> str:
    if unit_df.empty or "report_date" not in unit_df.columns:
        return _coverage_window_text(target_date, lookback_days)
    report_dates = unit_df["report_date"].dropna()
    if report_dates.empty:
        return _coverage_window_text(target_date, lookback_days)
    return f"{str(report_dates.min())} 〜 {str(report_dates.max())}"


def _query_lookback_frames(
    database,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
) -> tuple:
    start_date = target_date - timedelta(days=lookback_days)
    end_date = target_date
    params = [start_date.isoformat(), end_date.isoformat()]
    source_clause = ""
    if source:
        source_clause = " AND source = ?"
        params.append(source)
    daily_df = database.query_dataframe(
        f"""
        SELECT * FROM daily_store_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    machine_df = database.query_dataframe(
        f"""
        SELECT * FROM machine_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    unit_df = database.query_dataframe(
        f"""
        SELECT * FROM unit_results
        WHERE report_date >= ? AND report_date < ?{source_clause}
        """,
        params,
    )
    return daily_df, machine_df, unit_df


def run_analysis(
    database,
    store_normalizer: StoreNormalizer,
    target_date: date,
    lookback_days: int,
    source: str | None = None,
) -> dict:
    stores = store_normalizer.list_stores()
    daily_df, machine_df, unit_df = _query_lookback_frames(
        database,
        target_date,
        lookback_days,
        source=source,
    )
    scored_stores = score_stores(daily_df, stores, target_date)
    coverage_window = _resolved_coverage_window_text(unit_df, target_date, lookback_days)

    run_id = database.create_analysis_run(
        target_date=target_date.isoformat(),
        memo=f"lookback_days={lookback_days},source={source or 'all'}",
    )

    score_records: list[StoreScoreRecord] = []
    recommendation_records: list[TargetRecommendationRecord] = []
    report_rows: list[dict[str, object]] = []

    for rank, scored in enumerate(scored_stores, start=1):
        category_scores = score_machine_categories(machine_df, scored.store_id)[:3]
        machine_scores = score_machines(machine_df, scored.store_id)
        recommended_machines = [
            item for item in machine_scores if float(item.get("avg_diff", 0) or 0) > 0
        ][:5]
        if not recommended_machines:
            recommended_machines = machine_scores[:5]
        unit_quality = summarize_unit_data_quality(unit_df, scored.store_id)
        if unit_quality["pattern_analysis_ready"]:
            number_patterns = score_number_patterns(unit_df, scored.store_id)[:5]
        else:
            number_patterns = []
        confidence_letter = confidence_to_letter(scored.confidence)

        reason_text = (
            f"平均差枚 {scored.reason.get('avg_diff', 0)} / "
            f"中央値 {scored.reason.get('median_diff', 0)} / "
            f"平均G数 {scored.reason.get('avg_game', 0)} / "
            f"勝率 {round(float(scored.reason.get('win_rate', 0)) * 100, 1)}%"
        )
        avoid_reason = ""
        if confidence_letter == "D":
            avoid_reason = "サンプル不足または傾向不安定"

        score_records.append(
            StoreScoreRecord(
                run_id=run_id,
                store_id=scored.store_id,
                target_date=target_date,
                score=scored.score,
                confidence=scored.confidence,
                sample_size=scored.sample_size,
                reason_json=json.dumps(scored.reason, ensure_ascii=False),
            )
        )
        recommendation_records.append(
            TargetRecommendationRecord(
                run_id=run_id,
                target_date=target_date,
                store_id=scored.store_id,
                rank=rank,
                recommended_categories=json.dumps(category_scores, ensure_ascii=False),
                recommended_machines=json.dumps(recommended_machines, ensure_ascii=False),
                recommended_number_patterns=json.dumps(number_patterns, ensure_ascii=False),
                avoid_reason=avoid_reason,
                confidence=confidence_letter,
                reason_text=reason_text,
            )
        )
        report_rows.append(
            {
                "rank": rank,
                "store_id": scored.store_id,
                "display_name": scored.display_name,
                "score": scored.score,
                "confidence_numeric": scored.confidence,
                "confidence": confidence_letter,
                "sample_size": scored.sample_size,
                "reason": scored.reason,
                "reason_text": reason_text,
                "categories": category_scores,
                "machines": recommended_machines,
                "patterns": number_patterns,
                "avoid_reason": avoid_reason,
                "unit_quality": unit_quality,
            }
        )

    database.save_store_scores(score_records)
    database.save_target_recommendations(recommendation_records)
    return {
        "run_id": run_id,
        "rows": report_rows,
        "coverage_window": coverage_window,
        "source": source or "all",
    }


def generate_tomorrow_report(
    database,
    store_normalizer: StoreNormalizer,
    target_date: date,
    lookback_days: int,
    output_dir: Path,
    source: str | None = None,
    status_overrides: dict[str, dict[str, str]] | None = None,
) -> Path:
    analysis = run_analysis(
        database,
        store_normalizer,
        target_date,
        lookback_days,
        source=source,
    )
    rows = analysis["rows"]
    coverage_window = analysis["coverage_window"]
    source_label = analysis["source"]

    ranking_lines = []
    basis_lines = []
    genre_lines = []
    machine_lines = []
    pattern_lines = []
    alternative_lines = []
    skip_lines = []
    confidence_lines = []
    note_lines = []
    quality_lines = []

    for row in rows[:5]:
        ranking_text = (
            f"{row['rank']}. {row['display_name']} | "
            f"score {row['score']} | 信頼度 {row['confidence']} | sample {row['sample_size']}"
        )
        if row["sample_size"] == 0:
            ranking_text += " | データ不足"
        ranking_lines.append(ranking_text)

        if row["sample_size"] == 0:
            basis_lines.append(f"- {row['display_name']}: データ不足")
        else:
            basis_lines.append(f"- {row['display_name']}: {row['reason_text']}")

        top_categories = (
            ", ".join(item["category"] for item in row["categories"][:3]) or "データ不足"
        )
        genre_lines.append(f"- {row['display_name']}: {top_categories}")

        if row["machines"]:
            top_machines = ", ".join(
                (
                    f"{item['machine_name']} "
                    f"(avg_diff={item['avg_diff']}, "
                    f"avg_game={item['avg_game']}, "
                    f"sample={item['sample_size']})"
                )
                for item in row["machines"][:5]
            )
        else:
            top_machines = "データ不足"
        machine_lines.append(f"- {row['display_name']}: {top_machines}")

        if row["unit_quality"]["pattern_analysis_ready"] and row["patterns"]:
            top_patterns = ", ".join(
                (
                    f"{item['pattern']} "
                    f"(score={item['score']}, sample={item['sample_size']})"
                )
                for item in row["patterns"][:5]
            )
        else:
            top_patterns = (
                "台番分析は信頼不可 / 末尾分析は信頼不可 / "
                "並び分析は信頼不可 / 現時点では店舗別・機種別・カテゴリ別分析のみ有効"
            )
        pattern_lines.append(f"- {row['display_name']}: {top_patterns}")

    for row in rows[5:8]:
        alternative_lines.append(
            f"- {row['display_name']}: score {row['score']} / 信頼度 {row['confidence']}"
        )
    overrides = status_overrides or {}
    for row in rows:
        override = overrides.get(row["store_id"], overrides.get(row["display_name"], {}))
        row["fetch_status"] = override.get(
            "fetch_status",
            (
                "成功"
                if row["sample_size"] > 0 or int(row["unit_quality"]["total_rows"]) > 0
                else "失敗"
            ),
        )
        row["parse_status"] = override.get(
            "parse_status",
            "成功" if int(row["unit_quality"]["total_rows"]) > 0 else "失敗",
        )
        row["failed_machine_pages"] = int(override.get("failed_machine_pages", "0") or "0")
        row["status_note"] = override.get("status_note", "")

    for row in rows:
        if row["confidence"] == "D":
            skip_lines.append(
                f"- {row['display_name']}: {row['avoid_reason'] or '明確な根拠不足'}"
            )
        confidence_lines.append(
            f"- {row['display_name']}: {row['confidence']} (sample={row['sample_size']})"
        )
        note_lines.append(
            f"- {row['display_name']}: "
            f"取得 {row['fetch_status']} / "
            f"parse {row['parse_status']} / "
            f"machine失敗 {row['failed_machine_pages']}件 / "
            f"直近傾向 {row['reason'].get('recent_trend', 0)} / "
            f"標準偏差 {row['reason'].get('volatility', 0)} / "
            f"平均差枚 {row['reason'].get('avg_diff', 0)} / "
            f"平均G数 {row['reason'].get('avg_game', 0)} / "
            f"{row['unit_quality']['pattern_analysis_status']} / "
            f"unit_diff_missing_rate={_quality_value_text(row['unit_quality']['diff_missing_rate'])}"
        )
        quality_lines.extend(_quality_section_lines(row))
        quality_lines.append("")

    markdown = "\n".join(
        [
            f"# {target_date.isoformat()} Tomorrow Report",
            "",
            f"- source: {source_label}",
            "",
            "## 1. 明日の狙い店舗ランキング",
            *ranking_lines,
            "",
            "## 2. 店舗別の根拠",
            *basis_lines,
            "",
            "## 3. 狙いジャンル",
            *genre_lines,
            "",
            "## 4. 狙い機種候補",
            *machine_lines,
            "",
            "## 5. 台番・末尾・並び傾向",
            *pattern_lines,
            "",
            "## 6. 抽選負け時の代替候補",
            *(alternative_lines or ["- 代替候補なし"]),
            "",
            "## 7. 見送り推奨店舗",
            *(skip_lines or ["- 該当なし"]),
            "",
            "## 8. 信頼度 A/B/C/D",
            *confidence_lines,
            "",
            "## 9. サンプル数",
            *[f"- {row['display_name']}: {row['sample_size']}日" for row in rows],
            "",
            "## 10. Unit Data Quality",
            f"集計対象期間: {coverage_window}",
            "",
            *quality_lines,
            "## 11. 注意点",
            *note_lines,
            "",
            "高設定を断定せず、公開データ上の再現性と傾向を優先して評価しています。",
        ]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{target_date.isoformat()}_tomorrow.md"
    path.write_text(markdown, encoding="utf-8")
    return path
