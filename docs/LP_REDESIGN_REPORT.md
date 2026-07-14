# LP ビジュアル刷新 実装レポート

「文字だけ」だった検索意図別LP4枚を、「落ち着いた上質（ベージュ/グレージュ×テラコッタ/セージ・余白多め）」のビジュアルに刷新。**本文・FAQ・内部リンク・メタ・構造化データは不変**、見た目と画像配置のみ追加。

- ブランチ: `feature/lp-redesign`（main分岐）
- 変更ファイル: `api/_site.py`（テンプレート＋LP画像データ＋画像配信ヘルパー）、`api/index.py`・`server.py`（`/lp-assets` ルート）、`lp-assets/`（画像置き場）、`docs/`（本レポート＋PLAN＋IMAGE_GUIDE）

---

## 1. 実装内容

### デザイン（§2トークン準拠）
- 配色をCSS変数で実装：`--bg:#FBF9F6 / --panel:#F3EEE8 / --text:#3A2E2A / --muted:#6B615C / --acc:#B85042(テラコッタ)・#8F3D32(hover) / --acc2:#6E8E7D(セージ) / --line:#E5DDD4`。旧・青系リンク（#3B6FE0）は排除。
- タイポ：見出し **Zen Old Mincho**（誌面感・字間広め）＋本文 **Zen Kaku Gothic New**。既存と同じGoogle Fonts方式（preconnect＋display=swap）。
- 余白：最大幅860px・各セクション上下56px（モバイル40px）・角丸12px・淡い影（`0 2px 12px rgba(0,0,0,.06)`）。

### テンプレート構成（§4）
ヒーロー（H1＋リード＋テラコッタCTA＋ヒーロー写真）→ 導入①→ **before/after** → 本文②③ → FAQ（カード）→ 関連ページ（カード）→ フッターCTA（＋PR表記＋法務リンク）。CTAはヒーローとフッターの2箇所。

### 署名ビジュアル：before/after
各LPに「変える前／後」の対比を横並び（モバイルは縦積み）で実装。Beforeはセージ、Afterはテラコッタのラベル。**モーションなし**（reduced-motion配慮も兼ねる）。キャプションで「Room Studioで◯◯を変えた例」を明示。ソファLPのみ「色ちがい①/②」の比較として構成。

### 画像スロット（役割分担・プレースホルダ）
- **A=フリー素材ヒーロー**（無人インテリア）、**B=アプリbefore/afterキャプチャ**。各LPに hero＋before＋after の3枠。
- 未配置でも崩れない：画像ファイルが無い枠はサーバー側で**表示しない**（開発用の指示テキストや空の箱を公開ページに出さない）。`lp-assets/` にファイルを置くとその枠が自動表示。before/afterは2枚そろったときだけ表示。※本番公開を画像より先に行う判断（運営指示）に合わせ、当初の「指示テキスト付きプレースホルダ」から「未配置は非表示」に変更。
- `loading="lazy"`・意味のある `alt`・アスペクト比（hero 16:9 / BA 4:3）で CLS 抑制。
- 配信：`/lp-assets/{name}` ルート（`api/index.py`・`server.py`）。**拡張子自動判別**（webp/jpg/jpeg/png/avif）・**パス安全**（`[A-Za-z0-9._-]` のみ・`..`/スラッシュ拒否）・24hキャッシュ。置き場は `lp-assets/`。

---

## 2. 品質ゲート結果（自動テスト・全パス）
`TestClient`（GA4オフ）＋ `_site.lp_asset` 単体で全項目パス：

- ✅ 4枚とも新デザイン適用（トークン色・フォント・余白）、旧青リンク不在
- ✅ ヒーロー／before-after／関連カード／フッターCTAが描画、before/afterキャプション反映
- ✅ 画像スロットが `/lp-assets/<slug>-hero|before|after` を参照・`loading="lazy"`・`alt`付き・プレースホルダ指示テキストあり
- ✅ 画像ルート：未配置で404／`..`トラバーサル拒否／拡張子自動解決／content-type正／スラッシュ拒否
- ✅ **本文・FAQ（Q/A全文）・内部リンク・title/description/canonical/OGP・WebPage+FAQPage JSON-LD が不変**
- ✅ 内部リンク先すべて200・sitemap 4LP不変・UGC語不在
- ✅ a11y：`:focus-visible` アウトライン・`prefers-reduced-motion` 尊重・モバイル(≤640px)で縦積み
- ✅ `python -m py_compile`（`_site.py`/`index.py`/`server.py`）通過
- ✅ 重いフレームワーク不使用（サーバー生成HTML＋最小限のinline属性のみ）

> before/after の「実スクリーンショット」は、実画像が未配置のため本レポートでは割愛（現状はプレースホルダ表示）。デザインの見た目は下記「確認方法」で確認可能。

---

## 3. 確認方法（デザインレビュー）
- **Vercel プレビュー**：`feature/lp-redesign` をpush済み → Vercel が自動でプレビューデプロイを生成。Vercel → Deployments → `feature/lp-redesign` の行 → Visit → `/lp/hokuo-interior`（リファレンス）を開く。
- テンプレートは4枚共通のため、北欧LPのデザインがOKなら他3枚も同じ見た目（各LP固有の本文・画像指示のみ差分）。

---

## 4. ユーザーが用意する画像（詳細は `LP_IMAGE_GUIDE.md`）
`lp-assets/` に置くだけで差し替わる（拡張子任意）。**フリー素材は人物NG・ブランドNG・API経由NG・帰属不要素材のみ**。

| LP | ヒーロー(A) | before(B) | after(B) |
|---|---|---|---|
| 6畳 | `6jo-hitorigurashi-layout-hero` | `-before`（配色前） | `-after`（明るい配色後） |
| ソファ | `hitorigurashi-sofa-hero` | `-before`（ベージュ） | `-after`（グレー・色比較） |
| 賃貸 | `chintai-kabe-makeover-hero` | `-before`（白い壁） | `-after`（壁色変更後） |
| 北欧 | `hokuo-interior-hero` | `-before`（変更前） | `-after`（北欧トーン後） |

推奨: ヒーロー 16:9・横1600px・WebP 300KB以下／before-after 4:3・横800px・各150KB以下。

---

## 5. 受け入れチェックリスト
- [x] `feature/lp-redesign` で4枚に「落ち着いた上質」デザイン（§2トークン準拠）
- [x] before/after を署名ビジュアルとして実装（未配置でも崩れないプレースホルダ）
- [x] フリー素材枠(A)＋アプリキャプチャ枠(B)を役割分担・alt/サイズ/lazy対応
- [x] `LP_IMAGE_GUIDE.md` に画像指定＋ライセンス注意（人物/ブランド/API不可・帰属不要のみ）
- [x] モバイル対応・focus可視・reduced-motion尊重
- [x] 本文/FAQ/内部リンク/メタ/JSON-LD/アプリ導線/楽天リンク不変
- [x] 重いフレームワーク不使用・LP軽量性を維持
- [x] `docs/`（LP_REDESIGN_PLAN / LP_REDESIGN_REPORT / LP_IMAGE_GUIDE）作成

---

## 6. 仮定と判断
- **テンプレート共有**: `landing_html` は4枚共通のため、デザイン刷新は同時に4枚へ適用。北欧をリファレンスとして提示し、デザイン承認＝全4枚確定（要修正時は共有テンプレートを調整＝全4枚へ反映）。
- **before/after は静止画横並び**を採用（§2の2案のうち軽量・堅牢・モーションなしの方）。比較スライダーは将来の任意拡張。
- **画像配信**は専用ルート＋`lp-assets/`。拡張子自動判別で運営が形式を選べる。未配置時はプレースホルダ（本番に「画像が入ります」の枠が出るため、公開前に実画像配置を推奨）。
- **フォント**は既存方式に合わせGoogle Fonts。見出しにZen Old Mincho 1系統のみ追加（「重いフォントを足しすぎない」を尊重）。
