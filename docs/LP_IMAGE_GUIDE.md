# LP 画像ガイド（運営者が用意する画像）

LP刷新で各LPに「画像スロット」を実装済み。**ファイルを `lp-assets/` に置くだけ**で自動的に差し替わります（未配置の間は淡いグレージュのプレースホルダに指示テキストが出て、レイアウトは崩れません）。

- 置き場所: リポジトリ直下の **`lp-assets/`**
- 配信URL: `https://roomstudio.jp/lp-assets/<ファイル名>`（`/lp-assets/{name}` ルートが配信）
- **対応形式**: `.webp`（推奨）/ `.jpg` / `.jpeg` / `.png` / `.avif`。**拡張子は自動判別**（例 `hokuo-interior-hero.jpg` を置けば `hokuo-interior-hero` のスロットに入る）
- 置いたら `git add lp-assets/ && commit && push`（main反映で本番に出る）

---

## ⚠️ フリー素材のライセンス注意（必読・厳守）

ヒーロー写真（下記A）は**フリー素材**を使います。必ず以下を守ってください。

- ✅ **商用利用可・帰属表示不要**の素材のみ（例: Unsplash / Pexels の標準ライセンス）。
- 🚫 **人物が写った写真は使わない**。モデルリリース（肖像の使用許諾）はフリー素材側で保証されません。**無人の室内・インテリアに限定**。
- 🚫 **ブランドロゴ・商標・他社商品が明確に写った写真は使わない**。
- 🚫 **Unsplash等のAPI経由で自動取得しない**。API利用は帰属表示が必須になる等、条件が変わります。**手動でダウンロードした静的ファイル**を置いてください。
- 🚫 フリー素材写真を「Room Studioで加工した実例」であるかのように見せない（それは下記Bの役割）。ヒーローは**あくまでイメージ写真**。

> before/after（下記B）は**あなたがRoom Studioで作成してキャプチャ**するもの＝権利は完全にクリアです。

---

## 画像の役割（2種類）

- **A ＝ ヒーロー写真**（フリー素材の無人インテリア）… ページ最上部の「引き」。世界観づくり。
- **B ＝ before/after キャプチャ**（Room Studioの実画面）… 「実際にこう変えられる」の証明。**各LPの主役**。

---

## 各LPに置くファイル一覧

推奨: ヒーロー=**16:9・横1600px前後・WebPで300KB以下**、before/after=**4:3・横800px前後・各150KB以下**。すべて `loading="lazy"`・alt付きで実装済み。

### 1. 6畳・一人暮らし（`/lp/6jo-hitorigurashi-layout`）
| ファイル名（拡張子任意） | 種別 | 内容の指示 |
|---|---|---|
| `6jo-hitorigurashi-layout-hero` | A | 明るく片付いた**小さめの無人ワンルーム**（横長） |
| `6jo-hitorigurashi-layout-before` | B | Room Studioで**配色を変える前**の6畳 |
| `6jo-hitorigurashi-layout-after` | B | Room Studioで**壁・床・家具を明るい配色にまとめた後**の6畳 |

### 2. 一人暮らしのソファ（`/lp/hitorigurashi-sofa`）
| ファイル名 | 種別 | 内容の指示 |
|---|---|---|
| `hitorigurashi-sofa-hero` | A | **ソファのある明るい無人リビング**（横長） |
| `hitorigurashi-sofa-before` | B | 同じ部屋に**ベージュ系のソファ**を置いた例 |
| `hitorigurashi-sofa-after` | B | 同じ部屋に**グレー系のソファ**を置いた例（色ちがい比較） |

### 3. 賃貸の壁（`/lp/chintai-kabe-makeover`）
| ファイル名 | 種別 | 内容の指示 |
|---|---|---|
| `chintai-kabe-makeover-hero` | A | **白い壁の明るい無人の部屋**（横長） |
| `chintai-kabe-makeover-before` | B | Room Studioで**壁の色を変える前**（もとの白い壁） |
| `chintai-kabe-makeover-after` | B | Room Studioで**壁だけ色を変えた後**のイメージ |

### 4. 北欧インテリア（`/lp/hokuo-interior`）※リファレンス
| ファイル名 | 種別 | 内容の指示 |
|---|---|---|
| `hokuo-interior-hero` | A | **明るい木の質感の北欧テイストな無人リビング**（横長） |
| `hokuo-interior-before` | B | Room Studioで**北欧トーンにする前**のふつうの部屋 |
| `hokuo-interior-after` | B | Room Studioで**床と壁を明るい北欧トーンに変えた後** |

---

## 配置のコツ
- WebP変換とリサイズは [Squooss](https://squoosh.app/) 等で。横1600px・品質75前後で十分きれいかつ軽量。
- before/after は**同じ画角・同じ部屋**で撮ると対比が伝わります（Room Studioの「比較」機能でスクショしてもOK）。
- alt文言はコード側に実装済みなので、ファイルを置くだけで差し替わります（変更したい場合は `api/_site.py` の各LPの `hero`/`ba` の `alt` を編集）。
