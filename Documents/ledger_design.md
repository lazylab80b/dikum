# Ledger Management Tool — 設計ドキュメント

## 目的
- ChatGPTで複数の画像ファイルを生成・加工する作業を補佐する。
- この作業が長期間に渡ると、せっかく作成したファイルがタイムアウトで消えてしまう。そこで、これらの作業ファイルを **台帳 (ledger)** で管理し、復元・監査・エクスポートを可能にする。
- /mnt/data/<proj>/配下の短命ファイル(サンドボックス内のPythonで生成・加工・コピーしたもの)と、/mnt/data/配下の長寿命ファイル(DALL-E生成結果やユーザがアップロードしたUUID付きファイル)など寿命の異なるファイルを一元管理し、必要に応じて復元できるようにする。

---

## 台帳仕様（JSONL）

- 各レコードは JSON オブジェクト、1行＝1レコード。
- 代表的フィールド:
  - `op`: 操作種別
    - `"proj"`: プロジェクト定義（pr と dirs を持つ）
    - `"index"`: 新規ファイル登録
    - `"audit"`: 監査結果
    - `"export"`, `"import"`: 出力・入力操作
  - `pr`: プロジェクト名（`op=proj` のみ必須）
  - `dst`: プロジェクト内での相対パス（例: `panels/4.png`）
  - `org`: オリジン（由来ファイル）
    - `uuid://<id>`: アップロードファイル
    - `dalle://<id>`: DALL·E出力ファイル
    - `pack://<zipname>/<path>`: zip 内のファイル
    - `path://...`: ローカルパス（将来の拡張）
  - `md5`: ファイルMD5（ファイル単位）
  - `raw`: 画像RAWハッシュ（PNG再圧縮等の差異を吸収する場合に利用）
  - `sz`: ファイルサイズ
  - `t`: タイムスタンプ
  - `g`: 生成元（`dalle` / `gpt` / `upload`）

---

## 用語
- **迷子ファイル (lost)**  
  - プロジェクト下に存在するが、台帳に記録が無いファイル。そのままだとタイムアウトでファイルが消えたときに、仮に本体データが残っていたとしても、そこに紐づけられていないので正しく復活できない可能性が濃厚な状態。
- **孤児ファイル (orphan)**  
  - プロジェクト下に存在するが、オリジン (org) と紐づけられないファイル。そのままだとタイムアウトでファイルが消えたときに、どこにも本体データが残っていないので完全に失われてしまう危険な状態。

---

## サブコマンド仕様

### index
- 指定ディレクトリ配下の画像ファイルを走査し、台帳に `index` レコードを追記する。
- org は生成元に応じて付与（uuid://, dalle:// 等）。

### audit
1. `<proj>` 以下を再帰的に探索。
2. ファイルごとに台帳を確認。
3. org が存在し、サイズ/MD5 が一致 → OK。
4. 不一致や紐づけなし → lost/orphan として処理。
   - lost: 台帳に未登録 → indexを追加。
   - orphan: org 不明 → 画像をインライン提示して再アップを促す。
5. 危険ファイルが多い場合（>8）、リストのみ提示し、再 audit を促す。

### export
- `<proj>/` 以下を zip 化。
- 同時に `ledger_zip.jsonl` を生成し、org を `pack://` に書き換えて zip に含める。
- `ledger.jsonl` 正本は /mnt/data/ 直下に保存。

### import
- `zip` を展開し、含まれる `ledger_zip.jsonl` を読み込み。
- `org=pack://` を保持したまま台帳に反映。

---

## ディレクトリ構成（例）

```
/mnt/data/
  ledger.jsonl        ← 台帳の正本
  <proj>/             ← 作業プロジェクトルート(作品名など、そのプロジェクト固有の名前に置き換える)
    panels/           ← コマ画像
    references/       ← 参照画像
    materials/        ← 作品固有素材
    common/           ← 全作品共通素材
    finals/           ← 完成原稿
    ledger_zip.jsonl  ← zipに含めるための台帳のスナップショット
```

---

## 運用フロー（例）

1. **生成**: DALL·E出力 → `<proj>/panels/4.png` にコピー → index追記。
2. **監査**: 「ファイル確認！」 → audit 実行 → lost/orphan 検出 → インライン表示 or 再アップ。
3. **保存**: 「保存！」 → export 実行 → `<proj>.zip` と `ledger_zip.jsonl` を生成。
4. **復元**: 新スレッドで zip を import → 台帳復元 → lost/orphan があれば audit。

---

## 現在の実装状況
- `ledgertool/ledger_core.py`: CSVベースのPoC版。
- `ledgertool/ledger.py`: CLIラッパー。
- `scripts/bundle.py`: 単一ファイル化ツール。
- `tests/test_ledger_core.py`: ユニットテスト雛形。
- 今後: JSONL版の実装と audit 機能強化。

---

## TODO
- [ ] JSONL 台帳実装への移行
- [ ] audit による lost/orphan 処理
- [ ] export/import 実装の完成
- [ ] GPTs との統合運用（インライン表示や再アップ促し）
