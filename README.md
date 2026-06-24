# Room Studio — 部屋を買う前に「塗って・置いて・消して」試すアプリ

部屋の写真に対して、**色/素材をアイテム単位で変更**・**家具を切り抜いて配置**・**不要物を消して補完**を、ブラウザ内で行えます（写真は外部送信されません）。

消しゴム（補完）は2つのエンジンを自動で切り替えます。

- **LaMa（ローカルAI・推奨）** … `server.py` を起動すると有効化。**GPU不要・CPUで動作**。Photoshopの「コンテンツに応じた塗りつぶし」相当の品質。
- **PatchMatch（ブラウザ内・設定ゼロ）** … サーバー未起動時の自動フォールバック。周囲のテクスチャを合成して埋めます（拡散ぼかしより大幅に高品質）。

---

## クイックスタート

### A. まず触る（設定ゼロ）
`room-studio.html` をブラウザで開くだけ。消しゴムは PatchMatch で動きます。
ヘッダーの「デモの部屋」で全機能を試せます。

### B. 消しゴムを最高品質にする（LaMa・CPUでOK）
```bash
# 1) 依存をインストール
pip install -r requirements.txt
# GPUが無いPCは、軽量なCPU版torchを先に入れると快適:
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2) サーバー起動（アプリ本体も同時に配信します）
python server.py
```
ブラウザで **http://127.0.0.1:7865** を開く → 「消しゴム」タブに
**『AI補完エンジン（LaMa）に接続済み — 高品質』** と出れば成功です。
（`room-studio.html` を直接開いても、サーバーが起動していれば自動検出します。「接続を再確認」ボタンあり。）

> 初回の補完だけモデルのダウンロード＆ロードで少し待ちます。2回目以降は速いです。
> CPUでは画像サイズに応じて数秒かかることがあります（GPUがあれば自動で使います）。

---

## 機能の使い方

1. **部屋を読み込む** … 「画像を開く」or「デモの部屋」。長辺1100pxに自動縮小。
2. **表面（壁/床/天井）** … 「表面を追加」→ 範囲を指定 → **色** / **素材** を変更。質感・陰影は保ったまま色だけ置換。範囲指定は3通り:
   - *選択ブラシ*（縁が柔らかいソフトブラシ）
   - *自動選択*（近い色をまとめて）
   - **AI選択（SlimSAM）** … 壁・床・家具などを**クリック**すると物体の範囲を自動推定。追加クリックで精度を上げ、**Alt/右クリック**で不要部分を除外。「選択に追加」で確定。初回はモデルのダウンロード（数十MB・ネット接続が必要）に少し時間がかかります（2回目以降はブラウザキャッシュ）。**画像は端末内のみで処理され外部送信されません**（取得するのはモデルの重みファイルのみ）。WebGPU対応ブラウザでは高速、未対応時はCPU(WASM)で動作。
3. **家具** … 画像を追加 → ドラッグ移動・角ハンドルで拡縮。切り抜きは2通り: *背景を自動で消す*（白/単色背景向け。エロード＋フェザー＋地色逆合成でハロー低減）か **AIで背景を切り抜く**（任意背景・U²-Net）。さらに色・素材・回転・不透明度・反転・複製・前面/背面。
4. **消しゴム** … 消したい物を赤ブラシで塗る →「この範囲を消す」。LaMa接続時はAIで、未接続時はPatchMatchで補完。
5. **書き出す（PNG）** / **取り消す**（消しゴム操作の巻き戻し）。

---

## 補完エンジンの実装メモ（検証済み）

- **PatchMatch**（Barnes et al. 2009 のNNF + 伝播 + ランダム探索、多重解像度EMで再構成）。Photoshopの「コンテンツに応じた塗りつぶし」と同系統のテクスチャ合成。重ねパッチの平均化に由来する微小なボケは古典手法の宿命で、これを超えるにはAI（LaMa）が要ります。
  - 検証: 高コントラストの周期テクスチャでも拡散方式より誤差が小さく、**構造そのものを復元**できることを確認済み（拡散方式はぼかすだけ）。実際の壁・床はより素直で差は更に明確。
  - 速度のためブラウザ側は領域を最大360pxに縮小して処理→拡大。フル解像度の高品質が必要な場合はLaMa（サーバー）が担当。
- **LaMa**（`simple-lama-inpainting`）… フルサイズで推論。大きな物・複雑な背景に強い。

### コードの地図（`room-studio.html` の `<script>` 内）
| 役割 | 主な関数 |
|---|---|
| 色変換/輝度 | `rgb2hsl/hsl2rgb/lpOf` |
| 素材生成 | `MATERIALS`, `woodTile/tileTile/...`, `buildMaterialBuffer` |
| 選択 | `stampDisc`, `stampDiscSoft`(ソフト), `floodFill`, `boxBlurMask` |
| AI選択(SAM) | `ensureSamLoaded`/`ensureSamEmbeddings`(モデル&埋め込み), `samDecode`(クリック→マスク), `samTensorToMask`, `handleSamClick`, `samCommit`/`samResetPoints`, `invalidateSam` |
| 表面の色・素材 | `applyRecolorToImageData`, `rebuildSurface` |
| 家具 | `removeBg`(改良マット・単色), `aiCutFurniture`(@imgly任意背景), `rebuildFurniture`, `furnitureHit` ほか |
| 消しゴム統括 | `runEraseNow`（LaMa→PatchMatchの切替）, `probeServer`, `updateEraseBadge` |
| LaMa連携 | `serverInpaintRegion`, `dataURLToCanvas` |
| PatchMatch | `patchMatchRegion`→`patchMatchComplete`→`pmComplete`（`pmDownRGB/pmValidSrc/pmDist`） |
| 描画/入力/レイヤー/UI | `render/renderOverlay`, ポインタ系, `addSurfaceLayer/addFurnitureLayer`, `setMode/syncPanels` |

---

## まだ弱いところ → Claude Code での次の一手

### 1. 選択を「賢く」する ✅ 実装済み（2026-06）
**SAM (Segment Anything)** をブラウザ実行。`@huggingface/transformers`（transformers.js）をCDNから動的import し、**SlimSAM**（`Xenova/slimsam-77-uniform`）を **WebGPU優先・WASMフォールバック**で実行。クリック1つで「壁だけ」「ソファだけ」を選択→`samDecode` が得たマスクを既存の `mask`(Uint8) に流し込む。
- 表面ツールに「AI選択」を追加（ステージ下のドックにも）。クリックで物体推定、追加クリック（正例）/Alt・右クリック（負例）で精度調整、「選択に追加」で確定。
- 画像の埋め込みは初回クリック時に1度だけ計算してキャッシュ（消しゴム/取り消し/リセット/画像読込で自動失効）。
- 画像は端末内のみで処理。取得するのはモデル重みのみ（初回はネット接続必要、以降キャッシュ）。

> 次の発展候補: 室内特化の ADE20K セグメンテーションで壁/床/家具を**自動レイヤー化**（クリック不要の一括分割）。

### 2. 家具の任意背景の切り抜き ✅ 実装済み（2026-06）
単色背景は従来の `removeBg`（フラッド）、**複雑な背景は「AIで背景を切り抜く」ボタン**で **@imgly/background-removal**（U²-Net系・ブラウザ完結）を実行。結果（アルファ付き）を `layer.aiCutCanvas` に保持し、`rebuildFurniture` がこれをベースに使う（色・素材変更もそのまま適用）。「AI切り抜きを解除」で元に戻せる。初回のみモデルDL（ネット接続必要）、画像は端末内で処理。

### 3. 床/壁の遠近対応
床の四隅を指定 → ホモグラフィで素材タイルと家具を**床平面に正しく投影**（今は正対貼り）。

### 4. 速度
重い画素処理（PatchMatch・recolor）を **Web Worker + OffscreenCanvas** へ。UIは縮小プレビュー即時→確定時フル解像度。

### 5. 仕上げ（順次実装中）
- **before/afterスライダー** ✅ 実装済み（2026-06）… ヘッダー「比較」ボタン。編集前（元写真）と編集後（合成結果）をドラッグで比較。`State.compare` + `renderOverlay` のクリップ描画。
- **プロジェクト保存/読込** ✅ 実装済み（2026-06）… ヘッダー「保存」「読込」。部屋（元写真＋編集後）と全レイヤー（表面マスク・家具画像・各パラメータ）を1つの `.json` に直列化。`saveProject`/`loadProject`。
- 汎用Undo/Redo（今は消しゴムのみ）… 予定

### LaMa をさらに強化したい場合
- `server.py` は `simple-lama-inpainting` を使用。より多機能にするなら **IOPaint（旧 lama-cleaner）** に置換可能（モデル選択・各種インペイント手法）。
- テキスト指示で埋めたい（=Fireflyの生成塗りつぶし的）なら **Stable Diffusion inpainting**。重いのでGPU推奨。
- 完全クライアント化したい場合は LaMa の **ONNX** を `onnxruntime-web`(WebGPU) で実行し、`serverInpaintRegion` をローカル推論に差し替え。

---

## ファイル
- `room-studio.html` … アプリ本体（単一ファイル）
- `server.py` … ローカル LaMa 補完サーバー（アプリ配信も兼任）
- `requirements.txt` … サーバーの依存

*すべての処理はクライアント側、またはあなたのPC上のローカルサーバーで完結します。写真は外部に送信されません。*
