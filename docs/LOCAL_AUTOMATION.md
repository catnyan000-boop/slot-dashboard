# LOCAL_AUTOMATION

## 1. 自動更新の仕組み

- macOS の `launchd` で毎日 `09:30` に `scripts/daily_update.sh` を実行します。
- 作業ディレクトリはこのプロジェクトルートです。
- 標準出力は `logs/daily_update.out.log`、標準エラーは `logs/daily_update.err.log` に保存します。
- `daily_update.sh` は fetch、parse、品質検証、`report-tomorrow`、`build-site` を順番に実行します。
- fetch が一部失敗しても、前回の raw が残っていれば継続してサイトを更新します。
- `public/` には表示用の summary JSON だけを出し、raw HTML や SQLite DB は出しません。

## 2. インストール方法

1. プロジェクトルートで `bash scripts/install_launchd.sh` を実行します。
2. `~/Library/LaunchAgents/com.slot-dashboard.daily.plist` が配置されます。
3. `launchctl load` により登録され、以後は毎日 `09:30` に実行されます。

## 3. アンインストール方法

1. プロジェクトルートで `bash scripts/uninstall_launchd.sh` を実行します。
2. `launchctl unload` で登録を解除し、plist を削除します。

## 4. 手動実行方法

- 即時実行: `launchctl kickstart -k gui/$(id -u)/com.slot-dashboard.daily`
- スクリプト直接実行: `bash scripts/daily_update.sh`

## 5. ログ確認方法

- 標準出力: `tail -f logs/daily_update.out.log`
- 標準エラー: `tail -f logs/daily_update.err.log`
- launchd の登録確認: `launchctl list | rg com.slot-dashboard.daily`

## 6. サイトの見方

- 更新結果は `public/index.html` と `public/data/latest.json` に反映されます。
- `取得失敗` や `失敗（前回データ使用）` はサイト上の fetch ステータスで確認できます。
- `parse失敗` は `parse_status` と `データ不足` 表示で確認できます。

## 7. 更新されない時の確認項目

- `bash scripts/install_launchd.sh` を実行したユーザーでログインしているか確認する。
- `~/Library/LaunchAgents/com.slot-dashboard.daily.plist` が存在するか確認する。
- `launchctl list | rg com.slot-dashboard.daily` で登録状態を確認する。
- `logs/daily_update.out.log` と `logs/daily_update.err.log` を確認する。
- `scripts/daily_update.sh` を手動実行して、fetch 失敗時も `build-site` まで進むか確認する。
- `public/data/latest.json` の `generated_at` が更新されているか確認する。
