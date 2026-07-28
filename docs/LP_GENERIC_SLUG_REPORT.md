# LP汎用化レポート — URL・メタ情報・本文の整合（2026-07-28）

## 0. 背景

LPを1枚に集約し、内容を北欧特化から汎用（Room Studio全般）に変更した結果、
URLが `/lp/hokuo-interior` のままで中身と不一致になっていた。この不整合を解消する。

---

## 🔴 GA4を見る人への記録：2026-07-28 に ref が変わりました

アプリ導線の計測パラメータが、この日を境に変わっています。**GA4でLP経由の流入を
見るときは、日付をまたぐと別の値になる**ため注意してください。

| | 値 |
|---|---|
| 2026-07-28 **より前** | `?ref=lp-hokuo-interior` |
| 2026-07-28 **以降** | `?ref=lp-moyougae-simulation` |

**なぜ変えたか**: `ref` は `/?ref=lp-<slug>` という既存規約でslugに追従する。
LPの流入データがまだほとんど蓄積されていない時期であり、連続性が切れる損失より
規約の一貫性を保つ利益のほうが大きいと判断した（運営判断）。

過去分と合算したい場合は、GA4 で `lp-hokuo-interior` と `lp-moyougae-simulation`
の両方を対象にすること。なお **URLの301は連続性が保たれる**（下記）ので、
検索評価への影響とこの計測キーの断絶は別物である点に注意。

---

## 1. URLの変更

```
旧: /lp/hokuo-interior
新: /lp/moyougae-simulation
```

**選定理由**: 「模様替え シミュレーション」という高インテントな検索語に直接一致し、
既存slug（`chintai-kabe-makeover` 等）のローマ字慣習とも揃う。家具・床壁・雑貨を
すべて含むアプリの価値を一語で表せ、本文を将来変えても陳腐化しにくい。

canonical / og:url / WebPage JSON-LD の url はいずれもslug由来なので自動追従。

## 2. 301リダイレクト（連鎖なしの1段に統一）

旧4URLすべてを**新URLへ直接**向けた。旧3LPの行き先も `hokuo-interior` から
張り替えているため、`301 → 301 → 200` の連鎖は発生しない。

```
/lp/hokuo-interior           → 301 → /lp/moyougae-simulation → 200
/lp/6jo-hitorigurashi-layout → 301 → /lp/moyougae-simulation → 200
/lp/hitorigurashi-sofa       → 301 → /lp/moyougae-simulation → 200
/lp/chintai-kabe-makeover    → 301 → /lp/moyougae-simulation → 200
/lp/（未知のslug）           → 404
```

`LP_REDIRECTS` に「次にリネームするときも全エントリを張り替える（hopを足さない）」
方針をコメントで明記した。

## 3. 本文の汎用化（北欧は例の一つとして残す）

**情報量は減らしていない。むしろ増えている。**

| 箇所 | 変更前 | 変更後 |
|---|---|---|
| title | 北欧インテリアの部屋づくりを、色と質感で試す | 模様替えシミュレーション：自分の部屋の写真で試す |
| description | 北欧インテリアは色と素材の…北欧らしい雰囲気に | 模様替えは、やってみるまで仕上がりが分からないもの…登録もインストールも不要 |
| lead | …**北欧テイスト**のような憧れの雰囲気も | …憧れの雰囲気に近づけるかどうかも |
| 本文セクション03 | 見出し「たとえば、北欧インテリアを目指すなら」 | 見出し「目指したいテイストを決めて、寄せていく」 |
| FAQ Q2 | 「北欧インテリアはどんな色でまとめれば…」 | 「好きなテイストに合わせて、色はどうまとめれば…」 |
| hero alt / 画像指示 | 北欧テイストの明るいリビング | 木の質感のある明るいリビング |

北欧は**ナチュラル・インダストリアルと並列の一例**として本文・FAQ内に残した（計3回）。
具体例が消えないため情報量が落ちず、北欧の検索意図も弱く受け続けられる。

| 指標 | 変更前 | 変更後 |
|---|---|---|
| 本文セクション数 | 3 | **3** |
| 本文の総字数 | 496 | **542** |
| FAQ設問数 | 3 | **3** |
| FAQ回答の総字数 | 376 | **422** |

## 4. アセット

`lp-assets/` はファイル名がslug依存（`<slug>-hero` 等）のため改名した。
実在するのはヒーロー写真1枚のみで、before/after と動画は未配置。

```
lp-assets/hokuo-interior-hero.webp → lp-assets/moyougae-simulation-hero.webp   (git mv)
```

以後の想定ファイル名は `moyougae-simulation-{hero,hero.mp4,hero.webm,before,after}`。
`docs/LP_IMAGE_GUIDE.md` も新slugに更新済み。

## 5. sitemap

`landing_slugs()` 由来なので自動追従。掲載は5URL（トップ＋法務3＋LP1）で、
`/lp/moyougae-simulation` に差し替わり、旧URLは載らない。

---

## 6. 検証結果（すべてパス）

**URL/メタ** — canonical・og:url・WebPage JSON-LD の url がいずれも新URL。
JSON-LD の name が新titleと一致。

**301** — 旧4URLすべて、実HTTPで **リダイレクト回数=1・最終200**。
新slug自身は `landing_redirect()` が `None`（ループなし）。未知slugは404。

**厳守事項（削除・簡略化していないこと）** — 本文3セクション／FAQ3問／
FAQPage設問3／WebPage・FAQPage JSON-LD／アプリ導線 `?ref=lp-moyougae-simulation` 5箇所／
アフィリエイト（PR）表記／楽天クレジット／運営者・プライバシー・特商法リンク／h1は1つ、
すべて健在。本文・FAQの総字数は変更前を上回る。

**汎用化** — title・description・lead・セクション03見出し・FAQ Q2設問・hero alt から
「北欧」が消え、本文中には例として3回残存。ナチュラル／インダストリアルの並列例も存在。

**禁止事項** — UGC・投稿・共有・公開・SNSの訴求語ゼロ。賃貸の断定表現なし
（賃貸の記述自体が現行LPに存在しない＝賃貸LPごと削除済みのため、今回の維持対象は無し）。

**アセット** — 新名で200・`image/webp`、HTMLが新名を参照。旧名は404（参照元が無いため問題なし）。

**表示** — headless Edge で全体をレンダリングし、書き換えた見出し
「目指したいテイストを決めて、寄せていく」「好きなテイストに合わせて、色は…」が
`_phrase()` の読点分割で自然に改行されることを確認。

---

## 7. 未反映・注意点

- 本作業は `feature/lp-generic-slug` ブランチ。**main へは未マージ・未push**。
  本番 roomstudio.jp はまだ旧UI・旧URLのまま。
- 旧URLの301は**デプロイして初めて効く**。デプロイ前に `/lp/hokuo-interior` を
  消してしまうと404になるため、必ずこの変更ごと反映すること。
- デプロイ後、Google Search Console で旧URLのインデックスが新URLへ移るまで数日〜数週かかる。
  sitemap 再送信をしておくと早い。
