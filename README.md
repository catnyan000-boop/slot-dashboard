# slot-store-analyzer

公開されているスロット店舗データを収集、保存、正規化、分析し、翌日の狙い店舗と狙い方を Markdown レポートとして出力する Python 製の MVP です。現時点では `みんレポ` のみ対応し、将来的に `アナスロ` と `スロレポ` を足しやすいように `collector` と `parser` を分離しています。

## 目的

- 対象 9 店舗の公開データを継続的に蓄積する
- 店舗名の表記ゆれを吸収し、一貫した store_id で扱う
- 店舗、ジャンル、機種、台番末尾、並び傾向を横断分析する
- 「勝てる台の断定」ではなく「打つべき店・避けるべき店の選別」に寄せる
- 平均差枚だけではなく、G数、勝率、中央値、標準偏差、サンプル数、直近傾向を含めて評価する

## セットアップ方法

1. Python 3.11 以上を推奨します。
2. 仮想環境を作成して依存関係を入れます。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

3. 必要に応じて `.env.example` を参考に環境変数を設定します。
4. DB を初期化します。

```bash
python -m src.cli init-db
```

## CLI の使い方

店舗一覧の確認:

```bash
python -m src.cli stores
```

みんレポ HTML 取得:

```bash
python -m src.cli fetch-minrepo --store cosmo_obu --days 180
python -m src.cli fetch-minrepo --all --days 180
```

保存済み HTML の解析:

```bash
python -m src.cli parse-minrepo --all
```

店舗分析:

```bash
python -m src.cli analyze-stores --days 180
```

明日の狙いレポート生成:

```bash
python -m src.cli report-tomorrow --date 2026-05-15
```

DB 件数確認:

```bash
python -m src.cli db-stats
```

店舗別の日次データ確認:

```bash
python -m src.cli show-store-data --store cosmo_obu --days 7
```

台番サンプル確認:

```bash
python -m src.cli sample-units --store cosmo_obu --limit 20
```

raw HTML 構造確認:

```bash
python -m src.cli inspect-raw --store cosmo_obu --days 7
```

台番データ欠損確認:

```bash
python -m src.cli validate-unit-data --store cosmo_obu --days 7
```

欠損台番候補の確認:

```bash
python -m src.cli list-missing-units --store cosmo_obu --days 7 --limit 20
```

個別台ページからの補完:

```bash
python -m src.cli fill-unit-details --store cosmo_obu --days 7 --max-pages 50 --sleep 2.0
```

## データ取得時の注意

- `robots.txt` と利用規約、アクセス負荷に配慮してください
- ログイン突破、CAPTCHA 回避、制限回避は実装していません
- 取得した HTML は必ず `data/raw/` に保存し、解析は保存済み HTML を対象にします
- `collector` と `parser` は責務分離されています
- 連続アクセスを避けるため、HTTP リクエスト間に待機を入れています

## 分析レポートの見方

- `score` は店舗全体の期待度を表す相対指標です
- `confidence` は A/B/C/D で表し、サンプル量、直近傾向、G数、一致指標数をもとに判定します
- `recommended_categories` はジャンル別の強みを示します
- `recommended_machines` は機種単位の再現性を重視した候補です
- `recommended_number_patterns` は末尾や並びの傾向を要約します
- `avoid_reason` がある店舗は見送り候補です

## 免責事項

- 本ツールは公開情報をもとに仮説を整理するための補助ツールです
- 実際の設定や営業意図を断定するものではありません
- 収集元サイトの数値と差異がある可能性があります
- 利用によって発生した損失について責任を負いません

## 今後の拡張予定

- `アナスロ` 対応 collector/parser の追加
- `スロレポ` 対応 collector/parser の追加
- スケジュール実行と日次自動レポート
- 機種名辞書とイベント日辞書の強化
- 店舗別の曜日相性と並び検出精度の向上
