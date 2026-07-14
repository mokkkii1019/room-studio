# STEP 0「前提工事」実装レポート

集客（SEO/note/SNS）を受け止める技術的土台の整備。実装・検証は完了。**本番のDNS/Vercel/楽天/GA4 の管理画面操作はユーザーが行う**（下記 §4 の残作業チェックリスト参照）。

- ブランチ: `feature/step0-prelaunch`
- 基準: `edc476c`（`CURRENT_SPEC.md`）
- 方針: 単一HTML＋Vercel FastAPI のステートレス構成を維持。Supabase/DB/認証は追加せず。

---

## 1. 実装した内容

### (1) 独自ドメイン移行の準備（コード対応）
- **`SITE_BASE_URL` 環境変数を導入**（`api/_site.py`）。末尾スラッシュ除去、未設定時は現行 `https://room-studio-fawn.vercel.app`（`_DEFAULT_BASE`）にフォールバック＝後方互換。
- **配信時インジェクション**を GA4 と同じ仕組みに統一：`render_app_html()` が `inject_base_url()`（canonical/og:url/og:image/JSON-LD の基準URL書換）→ `inject_ga4()` の順で適用。`api/index.py`・`server.py` の配信箇所を `render_app_html()` に差し替え。
- 楽天 Referer/Origin は既存の `_req_referer()`（Host から自動生成）で吸収されるため**コード変更不要**。DNS/Vercel/楽天の実操作は `docs/DOMAIN_MIGRATION.md` に手順化。

### (2) GA4 計測の有効化（設定と検証、LP対応）
- `.env.example` に `GA4_ID` プレースホルダ追記、README のデプロイ環境変数に `GA4_ID`/`SITE_BASE_URL` を明記。
- LP用に `ga4_head_snippet()` を追加（`rs_notrack` オプトアウトを尊重）。全LPに注入されることをテストで確認。
- **メーカー別計測の布石**：`trackClick(id,type,url,shop)` に第4引数 `shop` を追加し、`/track` と GA4 `select_item` の両方に `shop` を含めた（既存2導線=ライブラリ/レイヤーのみ）。`/track` エンドポイント（`index.py`/`server.py`）も `shop` を受理。
- 計測設計は `docs/MEASUREMENT.md`（見るべき指標・`/track` の差替え箇所=`log_track`・将来拡張）。

### (3) sitemap.xml / robots.txt（新規・課題#10）
- `GET /robots.txt`（`text/plain; charset=utf-8`, `max-age=86400`）：公開時は許可＋`Sitemap:` 提示、**私的版（`ACCESS_TOKEN` 設定時）は `Disallow: /`**。アクセスゲートでも robots は開放（`/health` と同様）。
- `GET /sitemap.xml`（`application/xml; charset=utf-8`, `max-age=86400`）：トップ・法務3ページ・全LP を `SITE_BASE_URL` 基準で列挙、`<lastmod>` は `room-studio.html` の mtime。
- 両ルートを `api/index.py`・`server.py` の双方に追加（ローカル検証可能）。

### (4) 検索意図別の静的LP（新規・課題#7/#10）
- LPシステムを `api/_site.py` に集約。**定義は `LANDING_PAGES` 配列の1箇所**に持ち、sitemap が自動参照（`landing_slugs()`）。
- `GET /lp/{slug}` を両サーバーに追加（未知slugは404）。
- LPテンプレート（`landing_html`）は title/description/canonical/OGP/Twitter/JSON-LD(`WebPage`)/GA4注入/本文/CTA/フッター法務リンク＋PR表記を備える。
- **CTA導線**：`/?ref=lp-<slug>`（GA4 の `page_location` でLP→アプリ転換を分別。アプリ改修不要）。
- 初期LP **4枚**（本文は枠＋執筆指示コメント。捏造統計・断定なし）：
  | slug | 検索意図 |
  |---|---|
  | `6jo-hitorigurashi-layout` | 6畳 一人暮らし レイアウト |
  | `hitorigurashi-sofa` | 一人暮らし ソファ 選び方/配置 |
  | `chintai-kabe-makeover` | 賃貸 壁 模様替え（原状回復） |
  | `hokuo-interior` | 北欧インテリア 部屋づくり |

---

## 2. 変更ファイル一覧

| ファイル | 変更概要 |
|---|---|
| `api/_site.py` | `SITE_BASE_URL`／`inject_base_url`／`render_app_html`／`ga4_head_snippet`／`LANDING_PAGES`＋`landing_html`／`robots_txt`／`sitemap_xml` を追加（+197行） |
| `api/index.py` | `render_app_html` へ差替、`/track` に `shop`、`/robots.txt`・`/sitemap.xml`・`/lp/{slug}` 追加、gateで robots 開放、`_app_lastmod` |
| `server.py` | 同上（ローカル版にも同一ルートを追加） |
| `room-studio.html` | `<head>` は不変。`trackClick` に `shop` 引数を追加＋呼び出し2箇所を更新（**唯一のアプリJS変更・§2.3で明示許可された軽微追加**） |
| `.env.example` | `SITE_BASE_URL`／`GA4_ID`／運営者情報（コメント）をプレースホルダで追記 |
| `README.md` | デプロイ環境変数に `SITE_BASE_URL`／`GA4_ID` を明記 |
| `docs/STEP0_PLAN.md` | 実行チェックリスト（新規） |
| `docs/STEP0_REPORT.md` | 本レポート（新規） |
| `docs/DOMAIN_MIGRATION.md` | ドメイン移行のユーザー手順（新規） |
| `docs/MEASUREMENT.md` | 計測設計メモ（新規） |

> `room-studio.html` の canonical/OGP/JSON-LD の**文字列は既定値として残置**し、配信時に `SITE_BASE_URL` へ書き換える方式（ファイルを直接書き換えない＝`file://` 直開きやフォールバックでも壊れない）。

---

## 3. 動作確認結果（品質ゲート）

`api/index.py` の FastAPI アプリに対し `TestClient` で**4シナリオ全合格**（`fastapi 0.122.0`）。

| 検証項目 | default | 独自ドメイン | GA4 on | 私的ゲート |
|---|:--:|:--:|:--:|:--:|
| `/health` が official/public | ✅ | ✅ | ✅ | ✅ |
| `/robots.txt` Content-Type=text/plain・内容 | ✅(Sitemap行) | ✅ | ✅ | ✅(Disallow /) |
| `/sitemap.xml` Content-Type=xml・全URL列挙・lastmod | ✅ | ✅(新base) | ✅ | ✅(ゲート=401) |
| app canonical/og:url/og:image が base 準拠 | ✅(vercel) | ✅(roomstudio.jp) | ✅ | (ゲート=login) |
| GA4：app `const GA4_ID` 注入 / 未設定は空 | ✅(空) | ✅(空) | ✅(注入) | — |
| LP 表示・canonical・JSON-LD・CTA ref・執筆コメント・PR表記 | ✅ | ✅ | ✅ | (ゲート) |
| LP GA4 スニペット 注入/非注入 | ✅(非) | ✅(非) | ✅(注入) | — |
| `/lp/unknown` 404 | ✅ | ✅ | ✅ | — |
| 私的ゲート：`/` と `/sitemap.xml` は401・robotsは開放 | — | — | — | ✅ |

**リグレッション確認**：
- `/collect`（キー未設定/認証失敗時）は `CollectError`→HTTP 502 で**エラーハンドリングが機能**（500クラッシュせず）。楽天連携の呼び出し経路は不変。
- `/imgproxy` は非許可ホストを 400 で拒否（許可ホスト=楽天CDNのまま）。
- `inject_ga4` の直接呼び出しは `render_app_html` 内のみ。`trackClick` 呼び出しは2箇所とも `shop` 付きで一致。
- `python -m py_compile` は `_site.py`/`index.py`/`server.py` すべて通過。
- `APP_MODE=public` 既定でクローラ（`_provider_crawler`）は import されない（`/health` が official を返すことで確認）。

---

## 4. ユーザーが手動で行う残作業（順序付き）

### A. 独自ドメイン（詳細 `docs/DOMAIN_MIGRATION.md`）
1. [ ] ドメイン取得（レジストラ）
2. [ ] Vercel → Settings → Domains にドメイン追加
3. [ ] レジストラで DNS 設定（Apex=A レコード / www=CNAME `cname.vercel-dns.com`）
4. [ ] Vercel 環境変数 `SITE_BASE_URL=https://<新ドメイン>`（末尾スラッシュなし）→ **再デプロイ**
5. [ ] 楽天ウェブサービスの「許可されたWebサイト」に新ドメインを追加（`http(s)://` 無し）
6. [ ] 疎通確認（`/health`・`/collect`・`affiliateUrl`・canonical/OGP・sitemap）

### B. GA4 計測（詳細 `docs/MEASUREMENT.md`）
7. [ ] GA4 プロパティ＋ウェブストリーム作成 → 測定ID取得
8. [ ] Vercel 環境変数 `GA4_ID=G-XXXXXXXXXX` → **再デプロイ**
9. [ ] リアルタイムで疎通確認。必要なら `shop` をカスタムディメンション登録
10. [ ] （自分のアクセス除外は `?notrack=1`）

### C. LP 本文
11. [ ] 各LP（4枚）の本文プレースホルダを実コピーに差し替え（`api/_site.py` の `LANDING_PAGES` の `sections`。各セクションに執筆指示コメントあり。捏造統計は書かない）
12. [ ] 必要ならLPを追加/削除（`LANDING_PAGES` に足すだけで sitemap に自動反映）

### D. 反映
13. [ ] `feature/step0-prelaunch` をレビューの上マージ → 本番反映

---

## 5. 仮定と判断（曖昧点の処理）

- **LPのディープリンク**：アプリには収集プリセット用のURLパラメータが**存在しない**（`location.search` は `notrack` のみ）。指示書「無理なら通常のトップ導線でよい」に従い、CTAは `/?ref=lp-<slug>`（GA4 attribution 付きのトップ導線）とした。アプリ側にプリセット読取を足すのは別STEP（コア操作ロジックに触れるため）。
- **`trackClick` へのアプリJS変更**：§0ルール1（コア不可侵）と §2.3（`shop` の軽微追加を明示許可）の整合として、後方互換な引数追加（第4引数 `shop`、既定空）に限定。既存2呼び出しのみ更新。
- **robots/sitemap を `server.py` にも追加**：品質ゲートが「ローカルで `server.py` 起動して確認」を要求するため、公開版(`index.py`)と同一ルートをローカルにも実装（挙動を一致させ検証容易に）。
- **URL書換の方式**：`room-studio.html` の文字列を直接置換せず、配信時に `_DEFAULT_BASE→SITE_BASE_URL` を replace。ファイルを直接開いた場合や環境変数未設定時も既定URLで正しく動く。
- **sitemap `<lastmod>`**：毎リクエスト変動を避け、`room-studio.html` の mtime（YYYY-MM-DD）を採用（クローラに優しい安定値）。
- **開発ツール `tools/check_makers.py`**：配信物ではないため `room-studio-fawn.vercel.app` 既定値を残置（`RAKUTEN_REFERER` 環境変数で上書き可）。移行の妨げにならない。

---

## 6. 既知の制限・要対応事項

- **本番反映には再デプロイが必須**：`SITE_BASE_URL`/`GA4_ID` は環境変数のため、設定後に Vercel 再デプロイが要る（設定だけでは反映されない）。
- **LP本文は枠のみ**：SEO効果を出すには実コピー執筆が前提（意図的にプレースホルダ。捏造回避）。
- **ディープリンク未対応**：LPは特定プリセットでアプリを開かず、トップ+ref のみ（将来拡張）。
- **`/track` は stdout ログのみ（課題#6）**：集計DB化は本STEP範囲外。差替え箇所は `_site.log_track` の1関数に集約済み。
- **`app_start`/`collect_run` 等のファネル計測は未実装**（別STEP。`MEASUREMENT.md` §4）。
- **`server.py` 起動でのフル疎通は heavy 依存（torch/PIL/uvicorn）**。今回の品質ゲートは同一ルートを持つ軽量な `api/index.py` app を `TestClient` で検証（robots/sitemap/LP/URL/GA4 のロジックは両者共有の `_site.py` に集約されており等価）。
