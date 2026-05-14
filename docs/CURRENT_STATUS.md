# CURRENT_STATUS

- Git 管理化済み。
- 初回コミット済み。
- `ruff` pass。
- `pytest` は `23 passed`。
- コスモジャパン大府は直近7日で `unit_diff_missing_rate` が約59.7%。
- `?num=` 個別台ページでも `"-"` の台が多く、みんレポ単独で完全補完は困難。
- みんレポの live fetch は現時点で不可。
  - `tag` / `detail` / `?kishu=all` / `?num=` / 都道府県ページ / 日付archiveページはいずれも `HTTP 200 / 0 bytes`。
  - headers変更・`requests.Session` 利用でも改善なし。
  - 既存DB / 既存raw は historical data としては利用可能。
- 現時点では店舗別・機種別・カテゴリ別分析を主軸にする。
- 台番・末尾・並び分析は欠損率で制御する。
