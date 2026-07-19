# /bgcut（サーバ側AI背景切り抜き）— 再開手順書

> 2026-07-17 に実装。PCシャットダウンをまたいで再開するためのメモ。
> コードは**すべて実装・ローカル検証済み**。残るのは「モデルのGitHub Releaseアップロード」と「コミット/デプロイ」の判断だけ。

## いまの状態

### 実装完了（working tree に未コミットで存在。ディスク上に保存済み＝再起動後も残る）
- `api/_bgcut_core.py`（新規）— ISNet/onnxruntime 推論コア。遅延import・モデル/tmpキャッシュ・Semaphore(2)。
- `api/index.py` / `server.py` — `GET /bgcut` ルート、`_GATE_API` に `/bgcut`、`/health` に `bgcut` フラグ。
- `requirements.txt` — fastapi + onnxruntime/numpy/pillow。`requirements-local.txt` — onnxruntime 追加。
- `room-studio.html` — SERVER.bgcut / applyCutAlpha / serverCutCanvas / 自動キュー(cutQueue) / pickBestCandidate の {canvas,url} 化 / addToFurniLib の imgUrl+自動キュー / makeFurniEl のサムネ・スピナー / placeFromLib の優先処理+フォールバック / 永続化(buildProjectObject・loadProject・exportLib・importLib)。
- `tools/quantize_isnet.py`（新規）— fp32→quint8 量子化スクリプト。
- `.env.example` / `README.md` / `docs/CURRENT_SPEC.md` — /bgcut 追記。`.gitignore` に `*.onnx`。

`git status --short`：M = .env.example, README.md, api/index.py, docs/CURRENT_SPEC.md, requirements.txt, requirements-local.txt, room-studio.html, server.py, .gitignore / ?? = api/_bgcut_core.py, tools/quantize_isnet.py, docs/BGCUT_RESUME.md

### 検証済み（ローカル・headless Edge E2E）
- 収集→自動キュー→全10件切り抜き完了、srcCanvas 温存、配置で layer.aiCutCanvas に反映、解除で復帰。
- 永続化ラウンドトリップ（cut/imgUrl 往復）、forCloud で切り抜き除外（楽天規約）。
- ゲート：ACCESS_TOKEN 時 /bgcut は key 無しで 401。モデル欠損時 503→ブラウザAI（@imgly）へフォールバック（1回・結果再利用）。
- 品質：quint8 vs fp32 のマスク IoU 0.98〜0.999。推論 CPU 約2〜3秒/枚。

### 量子化モデル（恒久保存済み）
- **場所**: `C:\Users\ldttm\room-studio-bgcut-model\isnet-general-use.quint8.onnx`（約44MB）
- SHA256: `F1B1C6F7656E532627697AFC989D953BE1E7EF8F55A718F3611E8C9FD50CDEF7`
- 由来: rembg 配布の `isnet-general-use.onnx`（Apache-2.0 / 原作 xuebinqin/DIS）を `tools/quantize_isnet.py` で quint8 化。
- 再生成する場合: `python tools/quantize_isnet.py`（onnxruntime/onnx/numpy が必要。fp32 を自動DLして量子化）。

## 残タスク（再開時にやること）

### A. モデルを GitHub Release にアップロード
公開リポジトリ `mokkkii1019/room-studio` にタグ `bgcut-model-v1` でリリースを作り、
`isnet-general-use.quint8.onnx` を**公開アセット**として添付する。
- URL は既定値と一致させる：
  `https://github.com/mokkkii1019/room-studio/releases/download/bgcut-model-v1/isnet-general-use.quint8.onnx`
  （`api/_bgcut_core.py` の `MODEL_URL` 既定値。別URLにするなら Vercel 環境変数 `BGCUT_MODEL_URL` で上書き）
- 手段：GitHub の Releases 画面から手動、または `gh release create bgcut-model-v1 "C:\Users\ldttm\room-studio-bgcut-model\isnet-general-use.quint8.onnx" --title ... --notes ...`（gh CLI 未インストール）。

### B. コミット & デプロイ
- `git add -A && git commit`（新規2ファイル＋変更）。**main への push = Vercel 本番（roomstudio.jp）へ自動デプロイ**。
- モデル未アップロードでも /bgcut は 503→ブラウザAIに自動フォールバックするので、A より先に push しても壊れない。ただし A を済ませてからの方がサーバ切り抜きが即有効。
- デプロイ後の確認：
  1. `curl https://roomstudio.jp/health` → `"bgcut":true`
  2. `curl -o out.png "https://roomstudio.jp/bgcut?url=<楽天画像URL(enc)>&v=1"` の1回目（コールド＋モデルDL）と2回目（ウォーム）、3回目 `x-vercel-cache: HIT`
  3. Vercel Project Settings → Functions で maxDuration 60s（初回コールドの余裕）
  4. `/collect` 等 他ルートのコールドスタート悪化がないか

## ローカルで再度動かす場合
```
# 依存（別venv 推奨）
pip install fastapi "uvicorn[standard]" onnxruntime pillow numpy
# モデルをローカルパス指定で起動（DL不要）
set BGCUT_MODEL_PATH=C:\Users\ldttm\room-studio-bgcut-model\isnet-general-use.quint8.onnx
set RAKUTEN_REFERER=https://roomstudio.jp/   # /collect を試すなら（.env に RAKUTEN_APP_ID/ACCESS_KEY 必要）
python server.py   # http://127.0.0.1:7865
```
`/health` に `"bgcut":true` が出ればOK。
