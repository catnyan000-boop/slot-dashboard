# DATA_POLICY

- raw HTML と正規化済み DB は分けて管理する。
- `data/raw`、`data/processed`、`*.db` は Git 管理しない。
- 推定値と actual 値を混ぜない。
- 取得できないデータは欠損として扱う。
- 無理な補完をしない。
- 過剰アクセスを避ける。
