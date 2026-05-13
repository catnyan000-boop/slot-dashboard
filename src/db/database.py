from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import pandas as pd

from .models import (
    DailyStoreResultRecord,
    MachineResultRecord,
    SourcePageRecord,
    StoreCatalog,
    StoreScoreRecord,
    TargetRecommendationRecord,
    UnitResultRecord,
)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self, schema_path: Path) -> None:
        schema = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
            self._migrate_schema(conn)

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(unit_results)").fetchall()
        }
        additions = {
            "diff_source": "TEXT",
            "games_source": "TEXT",
            "payout_rate_source": "TEXT",
            "detail_url": "TEXT",
            "detail_fetched_at": "TEXT",
            "detail_parse_status": "TEXT",
            "detail_error": "TEXT",
        }
        for column, column_type in additions.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE unit_results ADD COLUMN {column} {column_type}")

    def seed_stores(self, catalog: StoreCatalog) -> None:
        now = utc_now_iso()
        sql = """
        INSERT INTO stores (
            store_id, display_name, canonical_name, prefecture, city,
            aliases, event_days, memo, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(store_id) DO UPDATE SET
            display_name=excluded.display_name,
            canonical_name=excluded.canonical_name,
            prefecture=excluded.prefecture,
            city=excluded.city,
            aliases=excluded.aliases,
            event_days=excluded.event_days,
            memo=excluded.memo,
            updated_at=excluded.updated_at
        """
        with self.connect() as conn:
            for store in catalog.stores:
                conn.execute(
                    sql,
                    (
                        store.store_id,
                        store.display_name,
                        store.canonical_name,
                        store.prefecture,
                        store.city,
                        json.dumps(store.aliases, ensure_ascii=False),
                        json.dumps(store.event_days, ensure_ascii=False),
                        store.memo,
                        now,
                        now,
                    ),
                )

    def list_stores(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT store_id, display_name, canonical_name, aliases, event_days
                FROM stores
                ORDER BY store_id
                """
            ).fetchall()
        return rows

    def upsert_source_page(self, record: SourcePageRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_pages (
                    source, store_id, url, report_date, raw_path,
                    fetched_at, status_code, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, store_id, url) DO UPDATE SET
                    report_date=excluded.report_date,
                    raw_path=excluded.raw_path,
                    fetched_at=excluded.fetched_at,
                    status_code=excluded.status_code,
                    content_hash=excluded.content_hash
                """,
                (
                    record.source,
                    record.store_id,
                    record.url,
                    record.report_date.isoformat() if record.report_date else None,
                    record.raw_path,
                    record.fetched_at,
                    record.status_code,
                    record.content_hash,
                ),
            )

    def list_source_pages(
        self,
        source: str,
        store_ids: Optional[Iterable[str]] = None,
    ) -> list[sqlite3.Row]:
        params: list[Any] = [source]
        sql = """
        SELECT source, store_id, url, report_date, raw_path, fetched_at, status_code, content_hash
        FROM source_pages
        WHERE source = ?
        """
        if store_ids:
            placeholders = ",".join("?" for _ in store_ids)
            sql += f" AND store_id IN ({placeholders})"
            params.extend(store_ids)
        sql += " ORDER BY store_id, report_date, url"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return rows

    def upsert_daily_store_result(self, record: DailyStoreResultRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_store_results (
                    source, store_id, report_date, total_diff, avg_diff,
                    avg_game, win_rate, total_units, source_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, store_id, report_date) DO UPDATE SET
                    total_diff=excluded.total_diff,
                    avg_diff=excluded.avg_diff,
                    avg_game=excluded.avg_game,
                    win_rate=excluded.win_rate,
                    total_units=excluded.total_units,
                    source_url=excluded.source_url
                """,
                (
                    record.source,
                    record.store_id,
                    record.report_date.isoformat(),
                    record.total_diff,
                    record.avg_diff,
                    record.avg_game,
                    record.win_rate,
                    record.total_units,
                    record.source_url,
                    record.created_at,
                ),
            )

    def upsert_machine_results(self, records: Iterable[MachineResultRecord]) -> None:
        sql = """
        INSERT INTO machine_results (
            source, store_id, report_date, machine_name_raw, machine_name_normalized,
            machine_category, unit_count, total_diff, avg_diff, avg_game,
            win_rate, source_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(
            source, store_id, report_date, machine_name_normalized, unit_count
        ) DO UPDATE SET
            machine_name_raw=excluded.machine_name_raw,
            machine_category=excluded.machine_category,
            total_diff=excluded.total_diff,
            avg_diff=excluded.avg_diff,
            avg_game=excluded.avg_game,
            win_rate=excluded.win_rate,
            source_url=excluded.source_url
        """
        with self.connect() as conn:
            conn.executemany(
                sql,
                [
                    (
                        record.source,
                        record.store_id,
                        record.report_date.isoformat(),
                        record.machine_name_raw,
                        record.machine_name_normalized,
                        record.machine_category,
                        record.unit_count,
                        record.total_diff,
                        record.avg_diff,
                        record.avg_game,
                        record.win_rate,
                        record.source_url,
                        record.created_at,
                    )
                    for record in records
                ],
            )

    def upsert_unit_results(self, records: Iterable[UnitResultRecord]) -> None:
        sql = """
        INSERT INTO unit_results (
            source, store_id, report_date, unit_number, machine_name_raw,
            machine_name_normalized, machine_category, diff, games,
            payout_rate, bb, rb, diff_source, games_source, payout_rate_source,
            detail_url, detail_fetched_at, detail_parse_status, detail_error,
            source_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(
            source, store_id, report_date, unit_number, machine_name_normalized
        ) DO UPDATE SET
            machine_name_raw=excluded.machine_name_raw,
            machine_category=excluded.machine_category,
            diff=CASE
                WHEN unit_results.diff_source = 'unit_detail_page' THEN unit_results.diff
                ELSE COALESCE(excluded.diff, unit_results.diff)
            END,
            games=CASE
                WHEN unit_results.games_source = 'unit_detail_page' THEN unit_results.games
                ELSE COALESCE(excluded.games, unit_results.games)
            END,
            payout_rate=CASE
                WHEN unit_results.payout_rate_source = 'unit_detail_page'
                    THEN unit_results.payout_rate
                ELSE COALESCE(excluded.payout_rate, unit_results.payout_rate)
            END,
            bb=excluded.bb,
            rb=excluded.rb,
            diff_source=CASE
                WHEN unit_results.diff_source = 'unit_detail_page'
                    THEN unit_results.diff_source
                WHEN excluded.diff IS NOT NULL
                    THEN COALESCE(excluded.diff_source, unit_results.diff_source)
                ELSE unit_results.diff_source
            END,
            games_source=CASE
                WHEN unit_results.games_source = 'unit_detail_page'
                    THEN unit_results.games_source
                WHEN excluded.games IS NOT NULL
                    THEN COALESCE(excluded.games_source, unit_results.games_source)
                ELSE unit_results.games_source
            END,
            payout_rate_source=CASE
                WHEN unit_results.payout_rate_source = 'unit_detail_page'
                    THEN unit_results.payout_rate_source
                WHEN excluded.payout_rate IS NOT NULL
                    THEN COALESCE(
                        excluded.payout_rate_source,
                        unit_results.payout_rate_source
                    )
                ELSE unit_results.payout_rate_source
            END,
            detail_url=COALESCE(excluded.detail_url, unit_results.detail_url),
            detail_fetched_at=COALESCE(
                excluded.detail_fetched_at, unit_results.detail_fetched_at
            ),
            detail_parse_status=COALESCE(
                excluded.detail_parse_status, unit_results.detail_parse_status
            ),
            detail_error=COALESCE(excluded.detail_error, unit_results.detail_error),
            source_url=excluded.source_url
        """
        with self.connect() as conn:
            conn.executemany(
                sql,
                [
                    (
                        record.source,
                        record.store_id,
                        record.report_date.isoformat(),
                        record.unit_number,
                        record.machine_name_raw,
                        record.machine_name_normalized,
                        record.machine_category,
                        record.diff,
                        record.games,
                        record.payout_rate,
                        record.bb,
                        record.rb,
                        record.diff_source,
                        record.games_source,
                        record.payout_rate_source,
                        record.detail_url,
                        record.detail_fetched_at,
                        record.detail_parse_status,
                        record.detail_error,
                        record.source_url,
                        record.created_at,
                    )
                    for record in records
                ],
            )

    def list_missing_unit_results(
        self,
        store_id: str,
        cutoff_date: str,
        limit: Optional[int] = None,
    ) -> list[sqlite3.Row]:
        sql = """
        SELECT *
        FROM unit_results
        WHERE store_id = ?
          AND report_date >= ?
          AND (diff IS NULL OR payout_rate IS NULL)
        ORDER BY report_date DESC, COALESCE(games, 0) DESC, unit_number
        """
        params: list[Any] = [store_id, cutoff_date]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def update_unit_result_detail(
        self,
        row_id: int,
        *,
        diff: Optional[float] = None,
        games: Optional[float] = None,
        payout_rate: Optional[float] = None,
        detail_url: Optional[str] = None,
        detail_fetched_at: Optional[str] = None,
        detail_parse_status: Optional[str] = None,
        detail_error: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            current = conn.execute("SELECT * FROM unit_results WHERE id = ?", (row_id,)).fetchone()
            if current is None:
                return

            next_diff = current["diff"] if current["diff"] is not None else diff
            next_games = current["games"] if current["games"] is not None else games
            next_payout = (
                current["payout_rate"] if current["payout_rate"] is not None else payout_rate
            )

            next_diff_source = current["diff_source"]
            next_games_source = current["games_source"]
            next_payout_source = current["payout_rate_source"]
            if current["diff"] is None and diff is not None:
                next_diff_source = "unit_detail_page"
            if current["games"] is None and games is not None:
                next_games_source = "unit_detail_page"
            if current["payout_rate"] is None and payout_rate is not None:
                next_payout_source = "unit_detail_page"

            conn.execute(
                """
                UPDATE unit_results
                SET diff = ?,
                    games = ?,
                    payout_rate = ?,
                    diff_source = ?,
                    games_source = ?,
                    payout_rate_source = ?,
                    detail_url = COALESCE(?, detail_url),
                    detail_fetched_at = COALESCE(?, detail_fetched_at),
                    detail_parse_status = COALESCE(?, detail_parse_status),
                    detail_error = ?
                WHERE id = ?
                """,
                (
                    next_diff,
                    next_games,
                    next_payout,
                    next_diff_source,
                    next_games_source,
                    next_payout_source,
                    detail_url,
                    detail_fetched_at,
                    detail_parse_status,
                    detail_error,
                    row_id,
                ),
            )

    def create_analysis_run(self, target_date: str, memo: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO analysis_runs (target_date, created_at, memo) VALUES (?, ?, ?)",
                (target_date, utc_now_iso(), memo),
            )
            return int(cursor.lastrowid)

    def save_store_scores(self, records: Iterable[StoreScoreRecord]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO store_scores (
                    run_id, store_id, target_date, score, confidence, sample_size, reason_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, store_id) DO UPDATE SET
                    score=excluded.score,
                    confidence=excluded.confidence,
                    sample_size=excluded.sample_size,
                    reason_json=excluded.reason_json
                """,
                [
                    (
                        record.run_id,
                        record.store_id,
                        record.target_date.isoformat(),
                        record.score,
                        record.confidence,
                        record.sample_size,
                        record.reason_json,
                    )
                    for record in records
                ],
            )

    def save_target_recommendations(
        self, records: Iterable[TargetRecommendationRecord]
    ) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO target_recommendations (
                    run_id, target_date, store_id, rank, recommended_categories,
                    recommended_machines, recommended_number_patterns, avoid_reason,
                    confidence, reason_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, store_id) DO UPDATE SET
                    rank=excluded.rank,
                    recommended_categories=excluded.recommended_categories,
                    recommended_machines=excluded.recommended_machines,
                    recommended_number_patterns=excluded.recommended_number_patterns,
                    avoid_reason=excluded.avoid_reason,
                    confidence=excluded.confidence,
                    reason_text=excluded.reason_text
                """,
                [
                    (
                        record.run_id,
                        record.target_date.isoformat(),
                        record.store_id,
                        record.rank,
                        record.recommended_categories,
                        record.recommended_machines,
                        record.recommended_number_patterns,
                        record.avoid_reason,
                        record.confidence,
                        record.reason_text,
                    )
                    for record in records
                ],
            )

    def query_dataframe(self, sql: str, params: Optional[Iterable[Any]] = None) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(sql, conn, params=list(params or []))

    def table_counts(self) -> dict[str, int]:
        tables = [
            "source_pages",
            "daily_store_results",
            "machine_results",
            "unit_results",
        ]
        with self.connect() as conn:
            result = {}
            for table in tables:
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                result[table] = int(row["count"])
        return result
