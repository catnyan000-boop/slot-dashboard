PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    prefecture TEXT DEFAULT '',
    city TEXT DEFAULT '',
    aliases TEXT NOT NULL,
    event_days TEXT NOT NULL,
    memo TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    store_id TEXT NOT NULL,
    url TEXT NOT NULL,
    report_date TEXT,
    raw_path TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status_code INTEGER,
    content_hash TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_source_pages_unique
ON source_pages(source, store_id, url);

CREATE TABLE IF NOT EXISTS daily_store_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    store_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    total_diff INTEGER,
    avg_diff REAL,
    avg_game REAL,
    win_rate REAL,
    total_units INTEGER,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_store_results_unique
ON daily_store_results(source, store_id, report_date);

CREATE TABLE IF NOT EXISTS machine_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    store_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    machine_name_raw TEXT NOT NULL,
    machine_name_normalized TEXT NOT NULL,
    machine_category TEXT NOT NULL,
    unit_count INTEGER NOT NULL,
    total_diff REAL,
    avg_diff REAL,
    avg_game REAL,
    win_rate REAL,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_machine_results_unique
ON machine_results(source, store_id, report_date, machine_name_normalized, unit_count);

CREATE TABLE IF NOT EXISTS unit_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    store_id TEXT NOT NULL,
    report_date TEXT NOT NULL,
    unit_number TEXT NOT NULL,
    machine_name_raw TEXT NOT NULL,
    machine_name_normalized TEXT NOT NULL,
    machine_category TEXT NOT NULL,
    diff REAL,
    games REAL,
    payout_rate REAL,
    bb INTEGER,
    rb INTEGER,
    diff_source TEXT,
    games_source TEXT,
    payout_rate_source TEXT,
    detail_url TEXT,
    detail_fetched_at TEXT,
    detail_parse_status TEXT,
    detail_error TEXT,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unit_results_unique
ON unit_results(source, store_id, report_date, unit_number, machine_name_normalized);

CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    memo TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS store_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    store_id TEXT NOT NULL,
    target_date TEXT NOT NULL,
    score REAL NOT NULL,
    confidence REAL NOT NULL,
    sample_size INTEGER NOT NULL,
    reason_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_store_scores_unique
ON store_scores(run_id, store_id);

CREATE TABLE IF NOT EXISTS target_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    target_date TEXT NOT NULL,
    store_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    recommended_categories TEXT NOT NULL,
    recommended_machines TEXT NOT NULL,
    recommended_number_patterns TEXT NOT NULL,
    avoid_reason TEXT DEFAULT '',
    confidence TEXT NOT NULL,
    reason_text TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_target_recommendations_unique
ON target_recommendations(run_id, store_id);
