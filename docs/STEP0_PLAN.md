# STEP 0「前提工事」実行計画（チェックリスト）

作業指示書を実行可能なチェックリストに落としたもの。進捗は本ファイルで管理し、確定結果は `STEP0_REPORT.md` に記録する。

- 対象コミット基準: `edc476c`（`CURRENT_SPEC.md`）
- 作業ブランチ: `feature/step0-prelaunch`
- 構成前提: 単一HTML（`room-studio.html`）＋ Vercel FastAPI（`api/index.py`）のステートレス構成。Supabase/DB/認証は**追加しない**。

---

## 0. 絶対ルール（遵守事項）
- [x] コア機能（canvas編集・収集・AI選択）に触れない（触れるのは `<head>` メタ＋ルーティング/配信＋明示許可された軽微追加のみ）
- [x] アフィリエイト導線（`_provider_official.py`・`affiliateUrl`・`/imgproxy` 許可ホスト・`RAKUTEN_*`）を変更しない
- [x] 秘密情報をコミットしない（`.env.example` はプレースホルダのみ）
- [x] 公開/私的の分離（`APP_MODE=public` でクローラ非import＋`.vercelignore`）を維持
- [x] `feature/step0-prelaunch` で作業し意味単位でコミット
- [x] 破壊的操作（force push・リモート/DNS/Vercel/楽天の管理画面操作）をしない

## 1. ドメイン移行（準備とコード対応のみ）
- [x] `SITE_BASE_URL` を導入（未設定時は現行 vercel.app にフォールバック）
- [x] 配信時インジェクションで canonical・og:url・og:image・JSON-LD を `SITE_BASE_URL` ベースに書換（`_site.render_app_html` / `inject_base_url`）
- [x] ハードコードURLの洗い出しと置換方針を `STEP0_REPORT.md` に記録
- [x] 楽天許可サイト/DNS/Vercel の手順を `docs/DOMAIN_MIGRATION.md` に明記
- [x] 実DNS・実デプロイ・楽天管理画面操作はユーザーに委ねる（手順書のみ）

## 2. GA4 計測の有効化（コード実装済み・設定と検証）
- [x] `.env.example` に `GA4_ID` プレースホルダ追記＋READMEに「本番はVercel環境変数」明記
- [x] 新設LPでもGA4注入が効くことを確認（`ga4_head_snippet` を各LPに埋込）
- [x] `docs/MEASUREMENT.md` を作成（見るべき指標・メーカー別計測・`/track` 差替え箇所）
- [x] メーカー別計測に向け `/track` と `select_item` に `shop` を軽微追加（過剰実装せず）
- [x] GA4プロパティ作成/測定ID発行の手順を `MEASUREMENT.md` に併記（実操作はユーザー）

## 3. sitemap.xml / robots.txt（新規）
- [x] `GET /robots.txt` を追加（許可＋Sitemap提示、私的版/ゲート配下は除外）
- [x] `GET /sitemap.xml` を追加（トップ・法務・全LP・`lastmod`）
- [x] 正しい Content-Type（`application/xml` / `text/plain`）とキャッシュヘッダ
- [x] LP定義を1箇所（`LANDING_PAGES`）に集約し sitemap が自動参照

## 4. 検索意図別の静的LP（新規）
- [x] LPテンプレートを設計（title/description/canonical/OGP/JSON-LD/GA4/導線/フッター法務＋PR表記）
- [x] 初期LPを3〜5枚作成（6畳一人暮らし/一人暮らしソファ/賃貸壁模様替え/北欧インテリア＝4枚）
- [x] 本文は枠＋執筆指示コメント（捏造統計・不確かな断定なし）
- [x] LP群を1箇所に集約し sitemap が自動で拾う

## 5. 進め方・完了条件
- [x] `STEP0_PLAN.md` 作成（本ファイル）
- [x] 曖昧点は合理的仮定で前進し `STEP0_REPORT.md`「仮定と判断」に記録
- [x] 品質ゲート（robots/sitemap のContent-Type、LP表示、URL/GA4差替え、既存機能不変、クローラ非import）を検証
- [x] `STEP0_REPORT.md` に実装内容・変更ファイル・ユーザー残作業・確認結果・既知の制限をまとめ

## 6. 受け入れチェックリスト（`STEP0_REPORT.md` で報告）
- [x] ブランチ作業・リグレッションなし
- [x] `SITE_BASE_URL` で一括切替＋フォールバック
- [x] robots/sitemap が正しく配信・sitemapが全URL列挙
- [x] LP 3〜5枚・アプリ導線・GA4注入
- [x] `GA4_ID` 設定でgtag.js注入・既存イベント有効
- [x] 楽天連携不変
- [x] 秘密情報ハードコードなし
- [x] `docs/` 一式（PLAN/REPORT/DOMAIN_MIGRATION/MEASUREMENT）が揃う
