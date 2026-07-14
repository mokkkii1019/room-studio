# Room Studio 現状仕様書（公開版）

> 対象読者: プロジェクト外のプランナー／開発者。
> 本書は **実際のコード（`room-studio.html` / `api/*.py` / `server.py`）に基づく現状**を記述する。ロードマップ上の未実装機能は「未実装」と明記する。
> 最終更新: 2026-07-12（対象コミット `edc476c` 時点）

---

## 0. 一行サマリー

**「買う前に試す」模様替えシミュレーター。** 部屋の写真をブラウザに読み込み、①壁・床の色/素材を変える ②家具・家電・雑貨を切り抜いて配置する ③不要物を消す、をすべてブラウザ内で行う。写真は原則として端末外に送信されない。マネタイズは**楽天アフィリエイトのみ**。

- 公開URL: `https://room-studio-fawn.vercel.app/`
- ホスティング: Vercel（FastAPI プリセット、単一 Serverless Function）
- 料金: 無料（課金機能は未実装）

---

## 1. 技術スタック

### 1.1 フロントエンド
- **単一自己完結型 HTML**: `room-studio.html`（約 276KB）。**ビルドステップ・npm・フレームワークなし**の素の JavaScript（Vanilla JS）＋ HTML ＋ CSS。1ファイルで全機能が完結する設計。
- **描画**: HTML5 Canvas 2D（合成・マスク・素材投影・ワープすべて自前実装）。
- **Web Worker**: PatchMatch（消しゴム補完）を worker 化して UI ブロッキングを回避。worker ソースは既存の純粋関数を `.toString()` で束ねて動的生成（アルゴリズムの二重管理なし）。
- **ブラウザ内AI（CDNから動的import）**:
  - AI選択 = **SlimSAM**（`Xenova/slimsam-77-uniform`）を `@huggingface/transformers`（transformers.js）経由で実行。**WebGPU優先・WASMフォールバック**。
  - 背景除去（任意背景）= **`@imgly/background-removal`**（U²-Net系）。
  - いずれも画像は端末内で処理し、取得するのはモデルの重みのみ（初回のみネット接続が必要、以降ブラウザキャッシュ）。
- **フォント**: Google Fonts（`Zen Kaku Gothic New` / `JetBrains Mono`）を CDN から読み込み。
- **永続化**: IndexedDB ＋ localStorage（詳細は §3）。File System Access API で保存先フォルダ/ファイル名を指定（非対応ブラウザは通常ダウンロードにフォールバック）。

### 1.2 バックエンド（公開版 = Vercel）
- **`api/index.py`**: FastAPI アプリ（`app`）。Vercel が**単一の Serverless Function**としてデプロイし全リクエストを処理。
- 提供エンドポイント（公開版）:
  - `GET /`・`GET /room-studio.html` … アプリHTML配信（`Cache-Control: no-cache`＝常に最新）
  - `GET /health` … `{ ok, inpaint:false, collect:true, provider, mode, configured }`
  - `GET /collect` … 家具/家電/雑貨の商品検索（楽天API経由）
  - `GET /shops` … 楽天全ショップからメーカー/店舗を検索
  - `GET /item` … itemCode で1件再取得（参照のみ保存の再ハイドレーション用）
  - `GET /imgproxy` … 外部画像の同一オリジン中継（キャンバス汚染防止・許可ホストのみ）
  - `GET /track` … アフィリンク/購入クリック計測（204、stdout ログのみ）
  - `GET /about`・`/privacy`・`/tokushoho` … 法務ページ（静的生成）
  - `GET /og.png`・`/apple-touch-icon.png` … 画像アセット
- **依存**: `requirements.txt` は `fastapi` のみ（Vercel の Python ランタイム有効化に必須）。収集ロジックは**標準ライブラリのみ**で実装（`urllib` 等）。`vercel.json` は不要（ゼロ設定）。
- **重い AI 補完（LaMa `/inpaint`）は公開版に載せない**。公開では消しゴムはブラウザ内 PatchMatch に自動フォールバック。

### 1.3 バックエンド（ローカル版 = `server.py`）
- 公開版の全機能に加えて **LaMa 補完 `POST /inpaint`** を提供（`simple-lama-inpainting` ＋ PyTorch、GPU不要でCPU動作）。
- ローカルでは IKEA/Shopify クローラ収集も選択可能（`APP_MODE=private` 設定時）。
- `uvicorn` で `http://127.0.0.1:7865` に配信。

### 1.4 収集モジュール構成（公開/私的の二重分離）
```
api/
├── index.py               … Vercel エントリ（FastAPI app）
├── _collect_core.py       … 収集の facade（プロバイダ選択＋整形＋imgproxy・stdlib）
├── _provider_base.py      … プロバイダ共通（CollectError・env切替・カテゴリフィルタ）
├── _provider_official.py  … 【公開用】楽天正規APIのみ（常にimport可・公開安全）
├── _provider_crawler.py   … 【私的用】IKEA/Shopifyクローラ（.vercelignoreで配信除外＋実行時403）
└── _site.py               … 法務ページ・GA4注入・クリック計測・アクセスゲート
```
- `APP_MODE=public`（既定）では**クローラを import すらせず**、要求されても `403`。加えて `.vercelignore` でファイル自体を配信対象から除外する**二重防御**。
- `/health` が `{"provider":"official","mode":"public"}` を返すことで、公開URL上でクローラ無効を目視確認できる。

---

## 2. 主要機能

すべてクライアント側（またはローカルサーバー）で完結。写真は原則外部送信されない。

### 2.1 部屋の読み込み
- 「画像を開く」or「デモの部屋」。長辺 **1100px** に自動縮小。

### 2.2 表面（壁/床/天井）の色・素材変更
- 範囲指定4方式: **面（ポリゴン）選択** / 選択ブラシ（ソフト） / 自動選択（近似色フラッド・**壁の角＝Sobelエッジで停止**オプション付き） / **AI選択（SlimSAM）**。
- **色**: スポイト（周辺色採取）対応。既定で不透明に上塗りしつつ質感・陰影は保持。
- **素材**: 全**25種**（木目/大理石/石/御影石/タイル/レンガ/漆喰/コンクリート/布 等）をシームレス生成。
- **画像から素材抽出**: 写真から継ぎ目なしタイルを生成して一覧に追加（localStorage 保存＋プロジェクトにも含む）。
- **遠近投影**: 「遠近に合わせる」トグル＋4隅ハンドルで素材を床/壁平面にパース投影（ホモグラフィ）。

### 2.3 家具・家電・雑貨の配置
- 取得元: ドラッグ＆ドロップ / 「画像を追加」 / **ネットから収集**（§2.6）→ **家具ライブラリ**に格納 → クリック/ドラッグで部屋に配置。
- 編集: ドラッグ移動・角ハンドル拡縮・**回転（面内）**・**Z軸回転（yaw、台形パース投影）**・**台形補正（キーストーン、4隅自由ドラッグ）**・不透明度・反転・複製・前面/背面。
- 背景切り抜き: **自動（フラッド・単色背景向け）** / **AIで切り抜く（@imgly・任意背景）** / **手動ブラシ**。
- 色・素材変更も配置後に適用可。

### 2.4 消しゴム（不要物の削除・補完）
- 範囲指定: ブラシ／削る／**AI選択（SlimSAM）**。AIの過不足はドラッグで補正可。
- 補完エンジンは**自動切替**:
  - **LaMa**（ローカル `server.py` 起動時のみ・高品質）
  - **PatchMatch**（ブラウザ内・**公開版はこれが常用**・設定ゼロ）

### 2.5 保存・書き出し・その他
- **PNG書き出し** / **プロジェクト保存・読込（.json）** / **マイプロジェクト（IndexedDB）** / **編集中の自動保存＆復元**（IndexedDB session） / **before/after比較スライダー** / **全操作対応 Undo/Redo（Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y）**。
- レスポンシブ（モバイルは2本指ピンチズーム＋パン）。初回チュートリアル（4ステップ）。

### 2.6 ネットからの家具収集（公開版 = 楽天のみ）
- UIで **ジャンル → 品目 → テイスト（自由記述）→ 枚数（最大90・既定50）** を指定。
- **カテゴリ体系**（`COLLECT_TAXONOMY`／フロントとサーバーで一致）:
  - **家具**: ソファ / ダイニングテーブル / ローテーブル / 椅子 / ベッド / デスク / サイドボード / シェルフ
  - **家電**: テレビ / 冷蔵庫 / 洗濯機 / エアコン / 電子レンジ / 炊飯器 / 空気清浄機 / 扇風機 / 加湿器 / 掃除機
  - **日用品・インテリア雑貨**: カーペット/ラグ / カーテン / テーブルランプ / フロアランプ / ランプシェード / 観葉植物 / アート/ポスター / 鏡 / クッション / 時計 / 収納ボックス / ゴミ箱
- **メーカー絞り込み（任意・複数選択）**: ジャンルごとにプリセット15社（家具＝ニトリ/LOWYA/タンスのゲン/カリモク家具/無印良品…、家電＝パナソニック/ソニー/シャープ…、日用品＝山崎実業/アイリスオーヤマ…）。検索窓で任意メーカーも追加可（`/shops` が楽天全ショップから候補を返す）。複数選択時は枚数をメーカー数で按分。
- **画像品質担保**: 楽天は先頭3枚＋連番URL補完で最大10候補を取得し、クライアントが「最も単体・正面・無地背景らしい1枚」を自動選択（`scoreSingleItem`）。収集後にバックグラウンドで背景自動除去（高速/AI/しない を選択）。
- 各アイテムに**商品ページリンク・価格・店舗名**が付く。ライブラリは `.json` で保存/読込可。

---

## 3. データモデル

> ⚠️ **重要（推測ではなく実コードに基づく事実）**: **Supabase・外部データベースは現時点で一切使われていない。** `supabase` の文字列はコードベースで `README.md`（ロードマップ記述）にのみ出現し、`api/` や `room-studio.html` には実装が存在しない。**認証・ユーザーアカウント・クラウド同期・Stripe課金も未実装。** 現状のデータモデルは **100% クライアント側（ブラウザ内）で完結**する。サーバーは状態を持たない（ステートレス）。

### 3.1 クライアント側の永続化

#### IndexedDB（DB名 `roomstudio`, version 2）
| オブジェクトストア | keyPath | 用途 |
|---|---|---|
| `projects` | `id` | **マイプロジェクト**（お気に入り保存）。画像込みのフルプロジェクトをオフライン保存。 |
| `session` | `id` | **編集中セッションの自動保存**。`id:'current'` に 2.5 秒デバウンスで書き込み、リロード後に自動復元。 |

- `projects` エントリの形: `{ id, name, savedAt, thumb(JPEG dataURL), project(下記JSON) }`（実装は `idbPut`/`idbGetAll`/`idbGet`/`idbDel`）。

#### localStorage キー
| キー | 内容 |
|---|---|
| `roomstudio_usermats`（`USERMAT_LS`） | ユーザー抽出素材（シームレス素材）の配列 |
| `rs_notrack` | クリック計測オプトアウト（自己クリック除外） |
| `roomstudio_firstSeen` | 初回起動日（`YYYY-MM-DD`）。フリーミアムの grandfather 判定に使用 |
| `roomstudio_tut_done` | チュートリアル完了フラグ |
| パネル幅キー | 詳細パネル/レイヤー列の幅（UI状態） |

### 3.2 プロジェクト JSON スキーマ（`buildProjectObject`）
ファイル保存・IndexedDB・自動保存で共通に使うシリアライズ形式。
```jsonc
{
  "app": "room-studio", "version": 1,
  "W": <int>, "H": <int>, "selectedId": <id>, "nextId": <int>,
  "userMaterials": [ { "key", "name", "base", "src" } ],
  "roomOriginal": "<PNG dataURL>",   // 元写真
  "room": "<PNG dataURL>",           // 編集後の下地
  "layers": [
    // 表面レイヤー
    { "type":"surface", "id", "name", "mask":"<base64 Uint8>", "color", "strength",
      "lightShift", "keepTexture", "material", "matStrength", "matScale",
      "perspective", "quad", "visible" },
    // 家具レイヤー
    { "type":"furniture", "id", "name", "x","y","scale","rot","yaw","corners","flip","opacity",
      "bgRemove","bgTol","recolor","color","strength","material","matStrength","visible","category",
      "eraseMask":"<base64|null>", "src":"<PNG dataURL>", "aiCut":"<PNG dataURL>",
      "source","itemCode","productUrl","affiliateUrl","shop" }
  ],
  "libNextId": <int>,
  "furniLib": [ { "id","name","category","source","link","price","shop","itemCode","productUrl","affiliateUrl","src?" } ]
}
```
- **保存モードのバリエーション**:
  - `forFile:true`（ファイル保存）… `furniLib` の画像を除外（`JSON.stringify` の RangeError 回避）。配置済み家具は原寸保持。
  - `forCloud:true`（**将来のクラウド保存を見越した実装だが、保存先は未接続**）… 楽天/IKEA等**由来の商品画像を含めず参照のみ**（`source`/`itemCode`/`productUrl`/配置情報）にする＝楽天規約順守のための下ごしらえ。**呼び出し元のクラウド保存機能自体は未実装。**

### 3.3 サーバー側のデータ保存
- **データベースなし。** `/track`（クリック計測）は `print("TRACK ...")` で **stdout に出力するのみ**（Vercel のファンクションログに残る）。`_site.log_track` のコメントに「No DB in this phase — swap this for a real sink later」と明記。
- 楽天から取得した商品情報は**都度ライブで取得し、運営サーバーには保存しない**（規約順守）。

### 3.4 フリーミアムの足場（実装済みだが課金は未接続）
- `FREE_LIMIT = 3`（無料は3作品まで）。`GRANDFATHER_UNTIL = '2026-12-31'`（この日までに初回起動した端末は保存数無制限）。
- 4作品目以降の保存は「有料会員登録が必要（**近日提供**）」というメッセージのみ。**決済（Stripe等）は未実装**のため、実際の課金・アップグレード導線は存在しない。

---

## 4. アフィリエイト連携

### 4.1 方式
- **楽天ウェブサービス「楽天市場商品検索API」**（新エンドポイント `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401`）を使用（`api/_provider_official.py`）。
- **公開版で許可される唯一の収集プロバイダ**。検索・表示・アフィリエイト購入リンクは全員が無料・ログイン不要で利用可（楽天TOS 10条(10)に基づく）。マネタイズはアフィリエイトのみ、表示データは非保存。

### 4.2 必要な認証情報（環境変数）
| 変数 | 必須 | 用途 |
|---|---|---|
| `RAKUTEN_APP_ID` | ✔ | アプリケーションID（UUID） |
| `RAKUTEN_ACCESS_KEY` | ✔ | アクセスキー（新APIで必須） |
| `RAKUTEN_AFFILIATE_ID` | 任意 | アフィリエイトID。**未指定でもコードに既定値埋め込み**（`553d27b1.3fab40d2.553d27b2.4375e9f6`）。env で上書き可 |
| `RAKUTEN_REFERER` | 任意 | 楽天「許可されたWebサイト」に合わせる。**公開版では不要**（リクエスト元ドメインから自動生成） |

### 4.3 リンクのアフィリエイト化フロー
1. 収集リクエスト時、`affiliateId` パラメータを楽天APIに付与。
2. 楽天が返す `affiliateUrl`（`hb.afl.rakuten.co.jp` 経由のアフィリンク）を各商品の「詳細/購入」リンクに使用（未取得時は `itemUrl` にフォールバック）。
3. `RAKUTEN_AFFILIATE_ID` を送らないと `affiliateUrl` がアフィリンクにならず**報酬が発生しない**ため、既定値を必ず付与する設計。

### 4.4 Referer/Origin の自動一致
- 新APIは Referer/Origin が登録済み「許可サイト」と一致することを要求。
- サーバーは**リクエストの `Host` ヘッダから自身のドメインを Referer/Origin として自動生成**（`_req_referer`）。→ Vercel のドメインを楽天の許可サイトに登録するだけで動作（`RAKUTEN_REFERER` 設定不要）。

### 4.5 画像プロキシ（`/imgproxy`）
- 外部の商品画像を**同一オリジンで中継**し、Canvas の tainting（汚染）を回避（→ 背景除去・台形補正・PNG書き出しが可能に）。
- 公開版の許可ホストは**楽天の画像CDNのみ**（`rakuten.co.jp` / `r10s.jp`）。それ以外のホストは 400。14MB上限。24時間キャッシュ。

### 4.6 クリック計測
- 「詳細/購入」クリック時に `GET /track?id&type&url&src=web`（サーバーは 204、stdout ログ）＋ GA4 の `select_item` イベント（GA4有効時）。
- **自己クリックは除外可能**: URL `?notrack=1` で `localStorage.rs_notrack` を立てると計測停止。

### 4.7 規約順守の設計上の配慮
- 表示データは都度ライブ取得し**サーバー非保存**。
- クラウド保存を見越したシリアライズでは**商品画像を含めず参照のみ**（§3.2 `forCloud`）。
- スクレイピング系プロバイダ（IKEA/Shopify）は**公開版から完全に排除**（import されず 403 ＋配信除外）。私的利用のみ。

---

## 5. SEO / OGP の実装状況

`room-studio.html` の `<head>` に実装済み（公開版で配信）。

### 5.1 基本メタ
- `<title>`: 「Room Studio — 買う前に試す」
- `<meta name="description">`: 「部屋の写真に家具を置いて、壁や床の色を替えて、不要な物を消す。買う前の模様替えをブラウザだけで無料で試せます。写真は端末の外に送信されません。」
- `<link rel="canonical" href="https://room-studio-fawn.vercel.app/">`
- `lang="ja"`

### 5.2 OGP / Twitter Card
- `og:type=website`, `og:site_name=Room Studio`, `og:title`, `og:description`, `og:url`, `og:locale=ja_JP`
- `og:image=https://room-studio-fawn.vercel.app/og.png`（**1200×630**、`og.png` を配信）
- `twitter:card=summary_large_image`

### 5.3 構造化データ（JSON-LD）
- `schema.org/WebApplication`（`applicationCategory: DesignApplication`, `operatingSystem: Web`, `inLanguage: ja`, `offers: price 0 JPY`）を1件埋め込み。

### 5.4 アイコン・アセット
- favicon: **インラインSVG**（data URI・ソファのアイコン）。
- `apple-touch-icon.png` を配信。

### 5.5 配信・解析
- HTML は `Cache-Control: no-cache, must-revalidate` で**常に最新**を配信（モバイルの古いキャッシュ表示を防止）。画像アセットは `max-age=86400`。
- **GA4**: `GA4_ID` 環境変数を設定すると、サーバーが配信時に HTML へ測定IDを注入（`inject_ga4`）し gtag.js を読み込む。**未設定が既定 = 解析オフ**。オプトアウト（`rs_notrack`）を尊重。
- **法務ページ**: `/about`（運営者情報）・`/privacy`（プライバシーポリシー）・`/tokushoho`（特商法表記）を静的生成。運営者名・連絡先・住所は環境変数（`OPERATOR_NAME`/`OPERATOR_CONTACT`/`OPERATOR_ADDRESS`）で差し替え可。全ページに「アフィリエイト広告（PR）を含む」旨と「商品情報提供：楽天ウェブサービス」のクレジットを表示。
- **sitemap.xml / robots.txt は未確認（存在しない）。** SPA的な単一ページ構成のため個別URLのインデックス最適化は未実装。

---

## 6. 現在の開発ステータスと既知の課題

### 6.1 ステータス
- **公開版はVercelでライブしAvailable**（official/public モード、楽天収集＋アフィリエイト導線が稼働）。
- 別系統で**私的クローラ版**（`private-web` ブランチ・`ACCESS_TOKEN` で合言葉ゲート）を運用可能。IKEA/RUGHAUS/KANADEMONO/BAUHAUS を収集元にできるが、**公開版とは完全分離**（`PRIVATE-WEB.md` 参照）。
- コア機能（表面/家具/消しゴム/保存/収集/AI選択/AI背景除去/遠近/Undo-Redo/比較）はすべて実装済み。

### 6.2 既知の課題・制約
| # | 項目 | 内容 |
|---|---|---|
| 1 | **クラウド/認証なし** | Supabase・ログイン・アカウント・複数端末同期は**未実装**。プロジェクトは保存した**そのブラウザ/端末のIndexedDBに紐づく**（端末を変えると消える／共有できない）。 |
| 2 | **課金未接続** | フリーミアムの上限判定（3作品・grandfather）は実装済みだが、**Stripe等の決済・アップグレード導線が無い**。上限到達時は「近日提供」表示のみ。 |
| 3 | **公開版はLaMa非搭載** | 消しゴムはブラウザ内 PatchMatch にフォールバック。古典手法由来の微小なボケがあり、高品質消しゴムはローカル `server.py` 起動時のみ。 |
| 4 | **公開収集は楽天のみ** | IKEA/Shopify等のクローラは規約リスクのため公開版から排除。楽天以外の品揃え・価格帯は公開版では扱えない。 |
| 5 | **収集の安定性** | 楽天APIはサーバーレスの実行時間制約に合わせ最大3ページ・1QPSスロットル。私的版のIKEAはVercel共有IPがブロックされやすい。 |
| 6 | **計測がstdoutのみ** | `/track` はログ出力のみで集計DBなし。GA4も任意。定量分析の基盤は未整備。 |
| 7 | **単一巨大HTML** | `room-studio.html` 約276KB を1ファイルで保守（モジュール分割・テスト・型なし）。機能追加時の見通しに影響。 |
| 8 | **ファイル保存はライブラリ画像を除外** | 巨大化回避のため `.json` ファイル保存では `furniLib` の画像を含めない（配置済み家具は原寸保持されるので作品の見た目は完全再現される）。 |
| 9 | **AI機能はネット必須** | SlimSAM/背景除去/LaMaの初回モデルDLにインターネットが必要。WebGPU非対応環境はCPU(WASM)で低速。 |
| 10 | **SEO最適化は最小限** | 単一ページのため sitemap/robots/個別ランディング等は未整備。 |

### 6.3 ロードマップ（READMEに記載。**いずれも未実装**）
- **マネタイズ土台**: Supabase 認証＋プロジェクト/家具ライブラリのクラウド保存、無料枠制限のサーバー側強制、**Stripe 課金**。
- 家具を床平面の奥行きに合わせて自動スケール/設置。
- 室内特化セグメンテーション（ADE20K）でクリック不要の壁/床/家具自動レイヤー化。
- LaMa の ONNX 化によるブラウザ内完結の高品質補完。
- 楽天以外（Amazon/Yahoo等）の商品API＋公式アフィリエイト追加。

---

## 付録: 主要ファイル早見表
| ファイル | 役割 |
|---|---|
| `room-studio.html` | アプリ本体（単一ファイル・全フロント機能） |
| `api/index.py` | 公開版 Vercel エントリ（FastAPI） |
| `api/_collect_core.py` | 収集facade＋imgproxy（stdlib・公開/私的共有） |
| `api/_provider_official.py` | 楽天正規API（公開用収集プロバイダ） |
| `api/_provider_crawler.py` | IKEA/Shopifyクローラ（私的専用・公開から除外） |
| `api/_provider_base.py` | プロバイダ共通（エラー型・env・カテゴリフィルタ） |
| `api/_site.py` | 法務ページ・GA4注入・クリック計測・アクセスゲート |
| `server.py` | ローカルサーバー（LaMa補完＋全機能＋アプリ配信） |
| `README.md` | 全体ドキュメント（ローカル/公開手順・実装メモ） |
| `PRIVATE-WEB.md` | 私的クローラ版のデプロイ手順 |
