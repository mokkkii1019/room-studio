# /bgcut（サーバ側AI背景切り抜き）— 運用メモ

> 2026-07-17 実装 → **2026-07-19 本番（roomstudio.jp）へデプロイ済み**。
> 当初は再開手順書だったが、残タスク A/B が完了したため運用メモに置き換えた。

## 構成

- `api/_bgcut_core.py` — ISNet(quint8)/onnxruntime 推論コア。重い依存は遅延import、
  モデルは `/tmp`（Vercel）にキャッシュ、同時実行は `Semaphore(2)`。
- `api/index.py` / `server.py` — `GET /bgcut`、`_GATE_API` に `/bgcut`、`/health` に `bgcut` フラグ。
- `room-studio.html` — 収集時の自動キュー、サムネのスピナー、配置時の優先適用、
  永続化（project/lib 双方）、`forCloud` では切り抜きを除外（楽天規約）。
- `tools/quantize_isnet.py` — fp32→quint8 量子化スクリプト。

**画像は一切保存しない**（`/imgproxy` と同じ transient 方針）。ディスクに残るのはモデル重みのみ。

## モデル

- **配布元**: <https://github.com/mokkkii1019/room-studio/releases/tag/bgcut-model-v1>
  （アセット `isnet-general-use.quint8.onnx` / 46,360,717 bytes）
  これが `api/_bgcut_core.py` の `MODEL_URL` 既定値。別の場所に置くなら環境変数 `BGCUT_MODEL_URL` で上書き。
- **SHA256**: `f1b1c6f7656e532627697afc989d953be1e7ef8f55a718f3611e8c9fd50cdef7`
- **ローカル原本**: `C:\Users\ldttm\room-studio-bgcut-model\isnet-general-use.quint8.onnx`
- **由来**: rembg 配布の `isnet-general-use.onnx`（Apache-2.0 / 原作 xuebinqin/DIS）を quint8 化。
- **再生成**: `python tools/quantize_isnet.py`（fp32 を自動DLして量子化）。
- **品質**: fp32 比でマスク IoU 0.98〜0.999。

## 本番実測（2026-07-19）

| 項目 | 結果 |
|---|---|
| `/health` | `{"ok":true,"collect":true,"bgcut":true,"mode":"public",...}` |
| 1回目（コールド＋モデル44MB DL＋セッション構築） | 200 / **10.5s** / `x-vercel-cache: MISS` |
| 2回目（ウォーム） | 200 / 0.37s / `HIT` |
| 3回目 | 200 / 0.38s / `HIT` |
| 出力 | RGBA PNG 500x500 / 349KB。alpha=0 が 68.5%、250–254 が 27.9%、中間3.7%（正常な軟エッジ） |

`Cache-Control: public, max-age=86400, s-maxage=2592000` によりエッジで30日保持。
クエリの `v` はモデル更新時にエッジキャッシュを破棄するためのバージョン子。

## フォールバック挙動

`available()` は onnxruntime の有無とモデル取得先の設定のみ見る（`/health` を軽く保つため
onnxruntime を import しない）。実際の失敗は下記の通り 503 になり、クライアントは
ブラウザ内AI（@imgly）へ自動フォールバックする（1回のみ・結果は再利用）。

- onnxruntime 未導入 → 503
- モデルDL失敗／`BGCUT_MODEL_PATH` の実体なし → 503
- デコード不能な入力 → 415、推論失敗 → 500

## ローカルで動かす

```
pip install fastapi "uvicorn[standard]" onnxruntime pillow numpy
set BGCUT_MODEL_PATH=C:\Users\ldttm\room-studio-bgcut-model\isnet-general-use.quint8.onnx
set RAKUTEN_REFERER=https://roomstudio.jp/   # /collect も試す場合（.env に RAKUTEN_APP_ID/ACCESS_KEY 必要）
python server.py   # http://127.0.0.1:7865
```

`/health` に `"bgcut":true` が出ればOK。

## 積み残し

- Vercel Project Settings → Functions の `maxDuration`。コールド10.5sで通っているので
  現行設定でも動くが、モデル配布元が遅い日に備えて 60s へ上げておくと安全（ダッシュボード操作）。
- 他ルート（`/collect` 等）のコールドスタート悪化は未計測。重い依存は遅延importしているため
  理論上は影響しないはずだが、体感で遅くなったら要確認。
