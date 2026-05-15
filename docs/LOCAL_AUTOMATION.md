# LOCAL_AUTOMATION

## 1. 自動更新の仕組み

- macOS の `launchd` で毎日 `02:30`、`04:00`、`05:30` に `scripts/daily_update.sh` を実行します。
- 目的は、朝 `06:00` までに dashboard が更新済みの状態に近づけることです。
- 一度で最新日が取れなくても、早朝に複数回リトライして `slorepo` 側の更新待ちを吸収します。
- 作業ディレクトリはこのプロジェクトルートです。
- 標準出力は `logs/daily_update.out.log`、標準エラーは `logs/daily_update.err.log` に保存します。
- `daily_update.sh` は fetch、parse、品質検証、`report-tomorrow`、`build-site` を順番に実行します。
- fetch が一部失敗しても、前回の raw が残っていれば継続してサイトを更新します。
- `public/` には表示用の summary JSON だけを出し、raw HTML や SQLite DB は出しません。
- `report-tomorrow` と dashboard は `analysis_anchor_date` を表示し、`target_date` とズレる場合は注意文を出します。
- `06:00` 時点で最新データが取れていなくても、取得できた最新日を隠さず表示します。
- `daily_update.sh` が途中失敗しても、最後に生成できた dashboard を壊さない方針です。
- Mac がスリープ中やログアウト中は `launchd` の定時実行は動かないため、朝更新を保証したい日はスリープさせない運用が必要です。

## 2. インストール方法

1. プロジェクトルートで `bash scripts/install_launchd.sh` を実行します。
2. `~/Library/LaunchAgents/com.slot-dashboard.daily.plist` が配置されます。
3. `launchctl load` により登録され、以後は毎日 `02:30`、`04:00`、`05:30` に実行されます。

## 3. アンインストール方法

1. プロジェクトルートで `bash scripts/uninstall_launchd.sh` を実行します。
2. `launchctl unload` で登録を解除し、plist を削除します。

## 4. 手動実行方法

- 即時実行: `launchctl kickstart -k gui/$(id -u)/com.slot-dashboard.daily`
- スクリプト直接実行: `bash scripts/daily_update.sh`
- 朝の更新確認時は `logs/daily_update.out.log` に `02:30`、`04:00`、`05:30` 前後の記録があるかを見る。

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
- Mac が夜間にスリープしていなかったか確認する。スリープ中は `02:30`、`04:00`、`05:30` の自動実行は走らない。
- `scripts/daily_update.sh` を手動実行して、fetch 失敗時も `build-site` まで進むか確認する。
- `public/data/latest.json` の `generated_at` が更新されているか確認する。
- dashboard 上で `analysis_anchor_date` と注意文が出ている場合は、データサイト側の最新更新待ちである可能性が高い。
