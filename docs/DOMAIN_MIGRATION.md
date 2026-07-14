# 独自ドメイン移行 手順書

現行 `https://room-studio-fawn.vercel.app` から独自ドメイン（例 `https://roomstudio.jp`）へ移行するための手順。
**コード側の対応は STEP0 で完了済み**（`SITE_BASE_URL` 環境変数で canonical/OGP/JSON-LD/sitemap のURLを一括切替）。本書に残るのは**ユーザーが管理画面で行う実操作**。

> ⚠️ Claude Code はコード対応と本手順書の作成まで。**DNS・Vercel・楽天の管理画面操作はユーザーが実施**する。

---

## 前提：コード側の仕組み（対応済み）

- `SITE_BASE_URL`（環境変数・末尾スラッシュ不要）を設定すると、`api/_site.py` の `render_app_html()` が配信時に `room-studio.html` 内の `https://room-studio-fawn.vercel.app` を全て `SITE_BASE_URL` に書き換える（canonical / og:url / og:image / JSON-LD）。
- 未設定なら現行の vercel.app にフォールバック（後方互換・既存デプロイは無変更）。
- sitemap.xml / robots.txt / 各LP の URL も `SITE_BASE_URL` を基準に生成される。
- 楽天API向けの Referer/Origin は `_req_referer()` が**リクエストの Host ヘッダから自動生成**するため、ドメインが変わってもコード変更は不要（新ドメインを楽天の許可サイトに登録するだけ）。

---

## 手順（ユーザー実施・推奨順）

### 1. ドメイン取得
- レジストラ（お名前.com / Cloudflare / Google Domains 等）で希望ドメインを取得。

### 2. Vercel に独自ドメインを追加
1. Vercel の対象プロジェクト → **Settings → Domains → Add**。
2. 取得したドメイン（例 `roomstudio.jp`、および `www.roomstudio.jp`）を追加。
3. Vercel が表示する DNS レコードを控える。

### 3. DNS 設定（レジストラ側）
- **Apex（`roomstudio.jp`）**: Vercel 指定の A レコード（例 `76.76.21.21`）を設定。ALIAS/ANAME 対応レジストラなら Vercel 指定のターゲットでも可。
- **www（`www.roomstudio.jp`）**: `cname.vercel-dns.com` への CNAME を設定。
- 反映まで数分〜最大48時間。Vercel の Domains 画面が「Valid Configuration」になれば完了。
- Apex か www のどちらを正とするか決め、もう一方はリダイレクト設定（Vercel の Redirect 機能）にすると canonical が一本化されて望ましい。

### 4. 環境変数 `SITE_BASE_URL` を設定
1. Vercel → **Settings → Environment Variables**。
2. `SITE_BASE_URL = https://roomstudio.jp`（**末尾スラッシュなし**、正となるホスト名）を **Production（必要なら Preview も）** に追加。
3. **再デプロイ**（環境変数は再デプロイで反映）。

### 5. 楽天「許可されたWebサイト」に新ドメインを追加
1. [楽天ウェブサービス](https://webservice.rakuten.co.jp/) の管理画面 → 該当アプリ → **許可されたWebサイト**。
2. 新ドメインを `http(s)://` を付けずに追加（例 `roomstudio.jp`）。www も使うなら `www.roomstudio.jp` も追加。
3. 旧 `room-studio-fawn.vercel.app` は移行完了まで残しておく（切替直後の疎通確認のため）。
4. 反映は登録後すぐ・再デプロイ不要。

### 6. OGP画像の確認（任意）
- `og:image` は `SITE_BASE_URL/og.png` を指す（`/og.png` ルートが配信）。新ドメインで `https://roomstudio.jp/og.png` が開けることを確認。

---

## 移行後の疎通確認（チェックリスト）

新ドメイン `https://roomstudio.jp` で以下を確認：

- [ ] `GET /health` が `{"provider":"official","mode":"public", ...}` を返す
- [ ] `GET /collect?type=sofa&count=3` が商品を返す（＝楽天API疎通OK。空/502なら §トラブル参照）
- [ ] 収集した商品の「詳細/購入」リンクが `affiliateUrl`（`hb.afl.rakuten.co.jp` 経由）になっている（＝アフィリエイト報酬が発生する形）
- [ ] トップページの `<head>` の `canonical` / `og:url` / `og:image` が新ドメインになっている（ブラウザの「ページのソースを表示」で確認）
- [ ] `GET /robots.txt` の `Sitemap:` 行が新ドメインを指す
- [ ] `GET /sitemap.xml` の各 `<loc>` が新ドメインになっている
- [ ] 各LP（`/lp/...`）の canonical が新ドメイン
- [ ] `GET /imgproxy?url=<楽天画像URL>` が画像を返す（許可ホストは楽天CDNのまま）

---

## トラブルシューティング

| 症状 | 原因/対処 |
|---|---|
| `/collect` が 502（Referer不一致系） | 新ドメインが楽天の許可サイトに未登録。§5 を実施。反映は即時。 |
| canonical/OGP が旧ドメインのまま | `SITE_BASE_URL` 未設定 or 再デプロイ未実施。§4 の再デプロイを実施。 |
| `404: NOT_FOUND`（全パス） | Vercel の Framework Preset が「Other」。**FastAPI** に変更して再デプロイ。 |
| 画像が出ない（canvas汚染エラー） | `/imgproxy` の許可ホストは楽天CDNのみ。楽天以外の画像は公開版では扱わない仕様。 |
| DNS が「Invalid Configuration」 | A/CNAME の値・伝播待ち。Vercel Domains 画面の指示値と一致するか再確認。 |

---

## 補足：ハードコードURLの棚卸し（STEP0時点）

`room-studio-fawn.vercel.app` の出現箇所と扱い（詳細は `STEP0_REPORT.md`）：

- `room-studio.html`（canonical/og:url/og:image/JSON-LD の4箇所）… **配信時に `SITE_BASE_URL` へ自動書換**（`_DEFAULT_BASE` がフォールバック値）。ファイル自体の文字列は既定値として残置。
- `tools/check_makers.py`（開発用CLIの `RAKUTEN_REFERER` 既定値）… **配信物ではない**開発ツール。移行後に楽天疎通を試すなら `RAKUTEN_REFERER` 環境変数で新ドメインを指定すればよい（必須ではない）。
- `docs/CURRENT_SPEC.md`（仕様書内の記述）… ドキュメントのため現状維持。移行完了後にスナップショットとして追記更新すればよい。
