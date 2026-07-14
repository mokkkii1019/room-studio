# LP ビジュアル刷新 実行計画

作業指示書「LP4枚のビジュアル刷新 —「落ち着いた上質」デザインへ」の実行計画。曖昧点は本書・`CURRENT_SPEC.md`・既存本文に沿う合理的判断で進め、判断は `LP_REDESIGN_REPORT.md` に記録。

- ブランチ: `feature/lp-redesign`（main から分岐）
- 対象: `api/_site.py` の `landing_html`/`LANDING_PAGES` ＋ 画像配信ルート（`index.py`/`server.py`）
- 方針: 本文・FAQ・内部リンク・メタ・構造化データは不変。見た目と画像配置のみ刷新。

## 0. 絶対ルール
- [x] 本文/FAQ/内部リンク/メタ/JSON-LD/アプリ導線/楽天リンクを壊さない
- [x] 画像ライセンス厳守（人物NG・ブランドNG・API経由NG・帰属不要素材のみ）→ `LP_IMAGE_GUIDE.md`
- [x] UGC/公開/共有を訴求しない
- [x] アプリ本体（room-studio.html）のデザインは変えない（対象はLPのみ）
- [x] 重いJSフレームワークを入れない・画像はlazy/サイズ/alt対応
- [x] `feature/lp-redesign` で作業・main直コミットなし

## 1–2. デザイン方向・トークン
- [x] 配色を§2トークンで実装（bg #FBF9F6 / panel #F3EEE8 / text #3A2E2A / muted #6B615C / acc① テラコッタ #B85042・hover #8F3D32 / acc② セージ #6E8E7D / line #E5DDD4）
- [x] タイポ: 見出し=Zen Old Mincho（誌面感）+本文=Zen Kaku Gothic New（既存方式のGoogle Fonts）
- [x] 余白たっぷり（各セクション上下56px・モバイル40px）、最大幅860px、角丸12px、淡い影
- [x] 署名要素=before/after対比（静止画の横並び・軽量・モーションなし）

## 3. 画像（役割分担・プレースホルダ）
- [x] A=フリー素材ヒーロー枠、B=アプリbefore/after枠を実装（役割分担）
- [x] 未配置でも崩れないプレースホルダ（グレージュ地＋指示テキスト、`onload`で隠し`onerror`で撤去）
- [x] `/lp-assets/{name}` 配信ルート（拡張子自動判別・パス安全）＋ `lp-assets/` ディレクトリ
- [x] alt/loading=lazy/アスペクト比指定
- [x] `LP_IMAGE_GUIDE.md` に画像一覧・サイズ・ライセンス注意を明記

## 4. テンプレート構成
- [x] ヒーロー（H1+リード+CTA+写真A）→ 導入①→ before/after(B) → 本文②③ → FAQ → 関連(カード) → フッターCTA
- [x] CTAはテラコッタ、ヒーローとフッターの2箇所

## 5. 進め方・完了条件
- [x] 北欧LPをリファレンスに（テンプレートは共有＝4枚に同時適用）。北欧を確認用に提示
- [x] 品質ゲート: トークン準拠／画像枠が崩れない／モバイル対応／focus可視・reduced-motion尊重／本文・FAQ・内部リンク・メタ・JSON-LD・楽天・アプリ導線不変／lazy+alt+サイズ／`LP_IMAGE_GUIDE.md` 整備
- [x] `LP_REDESIGN_REPORT.md` に変更点・構成・ユーザーが用意する画像一覧をまとめ

## 6. 受け入れチェックリスト → REPORT で報告
