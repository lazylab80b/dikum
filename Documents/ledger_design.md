# Ledger Management Tool — 設計ドキュメント

## 概要
### 目的
- ChatGPTで複数の画像ファイルを生成・加工する作業を補佐する。
- 作業が長期間に渡ると、せっかく作成したファイルがタイムアウトで消えてしまう。そこで、これらの作業ファイルを **台帳 (ledger)** で管理し、復元・監査・エクスポートを可能にする。
- `/mnt/data/<proj>/` 配下の短命ファイル（サンドボックス内のPythonで生成・加工・コピーしたもの）と、`/mnt/data/` 直下の長命ファイル（DALL·E生成結果やユーザがアップロードしたUUID付きファイル）など寿命の異なるファイルを一元管理し、必要に応じて復元できるようにする。

---

### 全体像

- **台帳の正本**(唯一の基準): `/mnt/data/ledger.jsonl`
  - 1行＝1レコードの**JSONL**形式(フォーマット詳細は後述。文字コードはUTF-8)
  - 専用の台帳管理スクリプトにより生成・追記される(**追記型**。既存レコードは書き換えない)。
  - 重複 `p` がある場合は **最後の行が有効**（最新が勝ち）。
  - 必要に応じて冗長レコードをマージした正規化を行い、総サイズをシュリンクする(後述)。

- **ZIP用台帳スナップショット**: `/mnt/data/<proj>/ledger_zip.jsonl`
  - `export` 時は `/mnt/data/<proj>/` **を丸ごとZIP** に入れる（この中に `ledger_zip.jsonl` が含まれる）。
  - スナップショットは正本と同じスキーマだが、`org` の取り扱いのみ一部異なる（後述）。

- **Blobフォルダ**: `/mnt/data/`
  - **DALL・E生成物** (A_ や An_ などで始まるファイル名)や、**ユーザが明示的にアップした画像**(UUIDファイル名)が置かれる長命ファイル領域。
  - アシスタント側からインライン表示される画像はこれに含まれないことに注意。ユーザがそれをコピペやD&Dして、明示的に再アップロードすることで、はじめてBlob内の長命ファイルとして実体化される。

- **プロジェクトフォルダ**: `/mnt/data/<proj>/`
  - アシスタントがサンドボックス内のPythonで生成したり加工したりした結果の短命ファイルを集約する場所。
  - 例: `panels/`, `references/`, `materials/`, `finals/` など。
  - DALL・E生成物であっても、アシスタントにコピーや移動を指示して作成した場合はこれに当てはまり、短命となることに注意。
  - セッションタイムアウトなどで削除されても、再開時には別の記憶域から自動的にコピーされてくるらしい(ファイルのタイムスタンプが更新されている)
  - Blobフォルダという名前は、本ツール内で勝手に呼称しているもので、公式ではない。
  
* **エキスポートZipファイル**: `<proj>.zip`
  - プロジェクトの成果を保存したり、別スレッドで作業を再開するために作成するアーカイブファイル。
  - プロジェクトフォルダ内の全ファイル(台帳スナップショットを含む)をzipで圧縮したもの。
  
- `t` は ISO8601 UTC（例: `"2025-08-23T12:34:56Z"`）。
- 画像ファイル識別は、ファイルサイズで簡易チェック後に、`md5`での比較が主軸。必要に応じ `raw`（RAW RGBAハッシュ）も併記。
  - ブラウザからのアップロードであれば、PNGのraw情報は維持されることを確認済(PNGメタは削られる)
  - モバイルアプリからアップロードすると、解像度も変わってJPEGで再エンコードされるためMD5などで識別不能となることを確認済み。よって、アプリからのアップロードは避けるべきである。

---
## 用語（日本語／英語対応）

- 復元（recovery）
  - 上位の包括概念。失われた状態を元に戻す一連の作業全体を指す。

- 再構築（rebuild）
  - 台帳 `ledger.jsonl` を **checkpoint + その後の差分（stdout の `LEDGER>>` 行）**から再構成すること。

- 再展開（restore）
  - 台帳の `index` と `org` を解決し、**blob／pack** から実ファイルを `/mnt/data/<proj>/` に **再展開**して、プロジェクトフォルダ構成を再現すること。
  - 宛先が既存で `md5` 一致の場合はコピーをスキップ。

- 迷子（lost）
  - プロジェクト下に存在するが、台帳に記録が無い／`org` が未設定・不整合なファイル。  
  - **blob** 内に同一 `md5` が見つかれば自動ひも付け可能。
  - ひも付け前にタイムアウトで消えてしまうと、仮に**blob**に本体データが残っていても復活できない危険があり。

- 孤児（orphan）
  - プロジェクト下に存在し、`org` が未解決のまま **blob** に同一 `md5` が無いファイル。
  - タイムアウトで消えた場合、完全に失われる危険あり→ ユーザの再アップが必要。

---

## 台帳のレコード仕様

### 1)　`proj`（プロジェクト定義：台帳の先頭に1回）

```json
{"op":"proj","t":"2025-08-23T12:00:00Z",
 "pr":"nigami-amami",
 "dirs":["characters","references","panels","finals","materials","common"],
 "packs":["common"]}
```

- `pr`: プロジェクト名(必須)
- `dirs`: 初期ディレクトリ
- `packs`: 利用可能な共有素材パックIDリスト
- `t`: タイムスタンプ。ISO8601 UTC（例: `"2025-08-23T12:34:56Z"`）。

### 2) `pack`（共有素材パックの登録：必要なだけ）

```json
{"op":"pack","t":"2025-08-23T12:10:00Z",
 "id":"common",
 "org":"blob://common_assets_2025-08.zip",
 "root":""}
```

- `id`: パック名
- `org`: 参照元ZIP（Blob内）
- `root`: ZIP内のルートディレクトリ（空ならZIP直下）。

### 3) `index`（実ファイルの出所と宛先を1行で定義：何度でも）

```json
{"op":"index","t":"2025-08-23T12:34:56Z",
 "p":"references/クロキ先輩-元画像.jpg",
 "org":"blob://8a51be19-69a9-45a3-84ae-20baea55045a.jpg",
 "md5":"0959376d5f94f332a5290be1906a5624",
 "sz":11373,"w":87,"h":400,"g":"dalle"}
```

- **必須**:  
  - `p`: プロジェクト内の相対パス
  - `md5`: ファイルMD5  
- **任意**:  
  - `org`: 由来（`blob://`, `pack://` 等）  
  - `raw`: RAW画像のMD5ハッシュ（PNG再圧縮等の差異を吸収する場合に利用） 
  - `sz`: ファイルサイズ  
  - `w`,`h`: 画像解像度  
  - `g`: 生成元（`dalle` / `gpt` / `upload`）  
  - `note`: 任意メモ  

- **`org` スキーマ**詳細仕様:
  - `blob://<name>` → `/mnt/data/<name>` の長命ファイル  
  - `pack://<id>/<path>` → 共有素材パック内のファイル (`id`は`pack` で登録済)
  - `path://...` → 将来拡張用  
  - `zip://` →現状は未使用（export/importには不要）

- **登録ルール**:  
  - 宛先(`p`)が無い or `md5` 不一致 → コピー（`--no-copy` で禁止可）  
  - 宛先があり `md5` 一致 → スキップ  


---
## 台帳管理スクリプト(ledger.py)のサブコマンド動作仕様

### 復元（restore）

1. `proj` レコードから `<proj>` を決定し、必要な `dirs` を mkdir。  
2. 各 `index` の 由来(`org`) を解決して、宛先(`p`)にコピー。
3. 宛先存在 & `md5`一致ならスキップ。不一致は `--force` 時のみ上書き。

### 監査（audit）

* 目的: `/mnt/data/<proj>/` を再帰走査し、**迷子を自動ひも付け**、**孤児**を最大8件まで報告し、ユーザの再アップロードによるblob化を促す。

1. `<proj>/` 以下を再帰探索。  
2. 各ファイルを台帳と照合。  
   - **OK**: `org` 実体あり、`sz` と `md5` が一致 → 何もしない。
   - **迷子 (lost)**: `org` が未設定/不整合 → Blob 内に同一 `md5` があれば即ひも付け＆ index 追記。  
   - **孤児 (orphan)**: `org` が未解決かつ Blob に一致が無い → 標準出力に`ORPHAN {"p":..., "md5":..., "sz":..., "reason":"no_match|org_gone|mismatch"}`を出力。
3. orphan が **8件に達した時点で探索を打ち切り**、スクリプトを終了する。  
   - 残りのファイルは次のターンで再チェックされる前提。
4. orphan が0件のまま再起探索が完了した場合は、`INFO {"resolved":true}` を返して完了宣言。(orphanが1件でもあれば出力しない)

> ポイント:  
> - orphan報告を受けたアシスタントは、当該画像をインライン表示(フル解像度)し、ユーザが簡単にコピペやD&Dによるアップロードできるようにする。
> - 最終的に orphan=0 になるまで、ユーザ、アシスタント、およびスクリプトが連携してターンを繰り返して`audit` を実行していく。
> - orphan報告したものと異なる画像がアップされたとしても問題ない。いつかorphan=0に収束することが期待される。
> - **サイズ一致のみではリンクしない**（誤マッチ防止）。  
> - 台帳は **追記のみ**で、既存行の書換えは行わない。

---

### 保存（export）／取込（import）

- **export**  
  - `<proj>/` をZIP化。  
  - `ledger_zip.jsonl` を生成し、`org` は `pack://` のみ保持。他は破棄。  
  - 正本 `/mnt/data/ledger.jsonl` は更新しない。  

- **import**  
  - ZIPを展開。  
  - `ledger_zip.jsonl` を読み込み台帳に追記。  
  - `org=pack://` はそのまま保持。  

---
## チェックポイント（checkpoint）

### 目的と前提
- **課題**: `/mnt/data/ledger.jsonl` 自体が短命で消える可能性がある。
- **対策**:
  1) レコードを追加するたび **そのJSON行を stdout に出力**（会話履歴へ残す）。  
  2) 一定間隔で **checkpoint（cp）を自動生成**し、**正規化（コンパクション）**した台帳で置き換える。  
  3) checkpoint 時は **スナップショット全文を stdout に出力**（履歴からの再構築を容易にする）。

---

### 自動発火トリガ
- 直近の cp 以降に追加された **`index` レコードが N 件（既定: 32）** に達したら自動発火。  
  - CLI オプション例: `--cp-threshold N`  
- 任意で **時間閾値**（例: 最終 cp から30分）も実装可（`--cp-max-age`）。

---

### cp レコード（台帳に追記するメタ行）
```json
{"op":"cp","t":"2025-08-24T12:00:00Z",
 "seq":3,                      // CPの連番
 "lines":123,                  // この時点の台帳行数（cp自体含む想定でもOK）
 "sha256":"<compact_ledger_sha256>",  // 正規化後ledger全文のSHA-256
 "total_index":210,            // CP時点の累計 index 件数
 "note":"auto"}                // "auto" / "manual"
```
- **判定は O(1)**: `since = current_total_index - last_cp.total_index` が `>= 閾値` なら発火。

---

### 正規化（コンパクション）ルール
- `proj` …… **最後の1行**のみ保持。  
- `pack` …… **同一 `id` の最後勝ち**。  
- `index` …… **同一 `p` の最後勝ち**。  
- `export` / `import` …… **保持**（イベント境界の記録）。  
- `audit` …… **省略**（台帳肥大防止。自動ひも付けで生じる `index` は保持される）。

> 出力順は推奨で安定化：`proj` → `pack*` → `index*` → `export/import*`

---

### アトミック更新フロー
1) 正規化済み全文を `/mnt/data/ledger.jsonl.tmp` に書き出し（UTF-8 / LF）。  
2) 任意で旧版を `/mnt/data/ledger.jsonl.bak` に退避。  
3) `rename(tmp, ledger.jsonl)` で **アトミック置換**。  
4) 直後に **cp レコードを1行追記**（append-only を維持）。

---

### stdout 出力フォーマット（履歴保存）
- 平時（各追記時）:  
  ```
  LEDGER>> { ...JSON1行... }
  ```
- checkpoint 時（**3ブロック**）:  
  1) `CHECKPOINT_BEGIN {"t":"...","seq":N,"lines":L,"sha256":"..."}`
  2) **正規化済み全文**を行ごとに  
     `LEDGER>> { ... }`  
  3) `CHECKPOINT_END {"t":"...","seq":N,"lines":L,"sha256":"..."}`

---

### 再構築手順（台帳消失時）
1) 会話履歴から **最新の `CHECKPOINT_BEGIN ...` ～ `CHECKPOINT_END ...` ブロック**を見つけ、  
   `LEDGER>>` 行を復元して `/mnt/data/ledger.jsonl` を再生成（`sha256`で正規化済み全文と照合）。  
2) その後に続く **追加の `LEDGER>>` 差分行**を順に append するだけで **完全復元**。

---

### 実装メモ（`ledger_core` 側）
- 起動時に ledger.jsonl を走査して  
  - `current_total_index`（累計 index 件数）  
  - `last_cp.total_index` / `last_cp.seq`  
  を取得。  
- `since = current_total_index - last_cp.total_index` が閾値以上で `compact_and_checkpoint()` を呼ぶ。  
- `compact_and_checkpoint()` は  
  - 正規化 → `.tmp` へ書き出し → `rename` → cp 追記 → stdout へ CP ブロック吐き出し  
  の順に実行。

---

## 具体例

### サンプル台帳

```json
{"op":"proj","t":"2025-08-23T12:00:00Z","pr":"nigami-amami",
 "dirs":["characters","references","panels","finals","materials","common"],
 "packs":["common"]}

{"op":"pack","t":"2025-08-23T12:10:00Z",
 "id":"common","org":"blob://common_assets_2025-08.zip","root":""}

{"op":"index","t":"2025-08-23T12:34:56Z",
 "p":"references/クロキ先輩-元画像.jpg",
 "org":"blob://8a51be19-69a9-45a3-84ae-20baea55045a.jpg",
 "md5":"0959376d5f94f332a5290be1906a5624","sz":11373,"w":87,"h":400,"g":"dalle"}

{"op":"index","t":"2025-08-23T12:40:00Z",
 "p":"materials/effects/爆発.png",
 "org":"pack://common/effects/boom.png",
 "md5":"8f1c3a5b...","sz":2210311,"w":1024,"h":1024}
```

### 実行環境のディレクトリ構成例

```
/mnt/data/
  ledger.py           ← 台帳管理スクリプト(bundle版)
  ledger.jsonl        ← 台帳の正本
  nigami-amami/       ← 作業プロジェクトルート(作品名など、そのプロジェクト固有の名前に置き換える)
    panels/           ← コマ画像
    references/       ← 参照画像
    materials/        ← 作品固有素材
    common/           ← 全作品共通素材
    finals/           ← 完成原稿
    ledger_zip.jsonl  ← zipに含めるための台帳のスナップショット
```

### 運用フロー例

1. **生成**: DALL·E出力 → `<proj>/panels/4.png` にコピー → index追記。
2. **監査**: ユーザ指示「ファイル確認！」 → audit 実行 → lost/orphan 検出 → インライン表示 or 再アップ。
3. **保存**: ユーザ指示「保存！」 → export 実行 → `<proj>.zip` と `ledger_zip.jsonl` を生成。
4. **再構築**: ユーザ指示「台帳復活！」 → 会話履歴を遡ってチェックポイントを探し、そこからの差分レコードを追記して台帳正本を再構築。
5. **再展開**: 新スレッドで zip を import → 台帳復元 → lost/orphan があれば audit。


---
## 現在の状況

### 開発済内容
- `ledgertool/ledger_core.py`: CSVベースのPoC版。
- `ledgertool/ledger.py`: CLIラッパー。
- `scripts/bundle.py`: 単一ファイル化ツール。
- `tests/test_ledger_core.py`: ユニットテスト雛形。

### TODO
- [ ] JSONL 台帳実装への移行
- [ ] audit による lost/orphan 処理
- [ ] export/import 実装の完成
- [ ] GPTs との統合運用（インライン表示や再アップ促し）
- [ ] zip://スキーマ要否を再考(別スレへのimport後処理を詳細検討)