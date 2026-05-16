# DASHBOARD_ACCESS

## 1. 初回セットアップ方法

1. Finder でこのプロジェクトフォルダを開きます。
2. `install_dashboard.command` をダブルクリックします。
3. 初回だけ macOS の確認が出た場合は実行を許可します。
4. インストール完了後は、Mac にログインしている間 `launchd` がダッシュボード配信と毎朝の自動更新を管理します。

## 2. ダブルクリックだけで使えること

- 初回セットアップは `install_dashboard.command` をダブルクリックするだけで完了します。
- このファイルは `daily update` と `dashboard server` の両方をまとめてインストールします。

## 3. サイト URL

- ダッシュボード URL は `http://localhost:8765` です。
- 配信対象は `public/` だけです。`data/raw`、`data/processed`、`*.db`、raw HTML は公開しません。

## 4. 開き方

- `open_dashboard.command` をダブルクリックすると、ブラウザで `http://localhost:8765` が開きます。
- ブラウザのブックマークに `http://localhost:8765` を保存しても使えます。

## 5. 自動更新

- データ更新は既存の `daily update` により毎日 `02:30`、`04:00`、`05:30` に自動実行されます。
- 目的は、朝 `06:00` までに dashboard を更新済みの状態に近づけることです。
- データサイト側の更新が遅い日は、取得できた最新日を基準に dashboard を再生成します。
- 更新結果は `public/` に反映され、ローカルサーバーはその内容を表示します。
- Mac ログイン時には dashboard server が自動起動します。
- dashboard には `analysis_anchor_date` が表示され、`target_date` とズレる場合は注意文が出ます。
- Mac がスリープ中は `launchd` の定時実行が走らないため、朝更新を期待する日はスリープさせない運用が必要です。
- `DEPLOY_PAGES=1` で daily update を実行した時だけ、同じ静的成果物を GitHub Pages にも反映できます。

## 5.5 外出先スマホで見る

- GitHub Pages を有効化すると、外出先では `https://<owner>.github.io/<repo>/` 形式の URL から見られます。
- project Pages の URL は repository owner と repository 名で決まります。custom domain を設定している場合はその URL を使います。
- 公開されるのは `public/` の静的成果物だけです。raw HTML、SQLite DB、logs、reports、Python ソースは公開しません。
- 初回だけ GitHub repository settings の Pages で、source を `gh-pages` branch の `/ (root)` に設定します。
- private repository で Pages を使えるかは GitHub の契約プランに依存します。public repository は GitHub Free で使えますが、private repository は GitHub Pro / Team / Enterprise 系が必要です。

## 6. 更新されない時の確認方法

- Mac にログインした状態で使っているか確認します。
- `install_dashboard.command` をもう一度ダブルクリックして、`daily update` と `dashboard server` が入っていることを確認します。
- ブラウザで `http://localhost:8765` を再読み込みします。
- GitHub Pages を使う場合は `DEPLOY_PAGES=1 bash scripts/daily_update.sh` または `bash scripts/deploy_pages.sh` を実行したか確認します。
- Finder で `logs/daily_update.out.log` と `logs/daily_update.err.log` を開き、`02:30`、`04:00`、`05:30` 前後の更新記録を確認します。
- Finder で `logs/dashboard_server.out.log` と `logs/dashboard_server.err.log` を開き、server の起動エラーが出ていないか確認します。
- `scripts/deploy_pages.sh` が `forbidden path detected` または `forbidden content detected` で止まった場合は、公開禁止ファイルやローカル path が `public/` に混ざっていないか確認します。
- `http://localhost:8765` が開かず、`dashboard_server.err.log` に `port 8765 is already in use` と出ている場合は、同じポートを使っている別アプリを止めてから `install_dashboard.command` を再実行します。

## 7. サーバー停止・削除方法

- `uninstall_dashboard.command` をダブルクリックすると、`daily update` と `dashboard server` の両方を解除します。
- dashboard server だけを外したい場合は `scripts/uninstall_dashboard_server_launchd.sh` を使います。
- dashboard server を一度止めたいだけの場合は `scripts/stop_dashboard_server.sh` を使います。

## 8. ログの場所

- dashboard server 標準出力: `logs/dashboard_server.out.log`
- dashboard server 標準エラー: `logs/dashboard_server.err.log`
- daily update 標準出力: `logs/daily_update.out.log`
- daily update 標準エラー: `logs/daily_update.err.log`
