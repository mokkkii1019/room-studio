# 素材タイル（CC0）— 出典と取得手順

`materials/` に置いてある素材タイルは **ambientCG の CC0 素材**。2026-07-20 に**全64種**を
手続き生成から差し替えた。木目14種を先に通して実機で確認し、そのあと残り50種を追加した。

## なぜスクレイピングしないのか

当初「床材メーカーのサイトから収集する」案が出たが**採用しなかった**。大建工業・パナソニック・
サンゲツ等が掲載している木目や石目の画像は各社が費用をかけて撮影した著作物で、収集して
roomstudio.jp の素材パレットに組み込むと複製・公衆送信にあたる。roomstudio.jp は
アフィリエイト収益のある商用サイトなので私的利用の例外は使えず、素材そのものを提供する形
なので引用でも説明できない。楽天の商品画像を扱えているのは公式APIとアフィリエイト規約と
いう明示的な許諾があるからで、性質がまったく違う。

CC0 素材なら**商用利用・改変・再配布すべて自由、クレジット表記も不要**で、結果も良い。

## 出典

- **ambientCG** — https://ambientcg.com/ ／ ライセンス: CC0 1.0（パブリックドメイン）
- 公式APIから取得している（スクレイピングではない）:
  `https://ambientcg.com/api/v2/full_json?type=Material&category=Wood&limit=100&sort=Popular`
- 平らでタイル可能なカラーマップの実体:
  `https://f003.backblazeb2.com/file/ambientCG-Web/media/surface-preview/<id>/<id>_SQ_Color.jpg`

### ⚠️ `/media/thumbnail/` は使ってはいけない
そちらは**球体のレンダリング画像**で、タイルではない。一度これを使って「シームレス性を検証
した（端の不連続 0.00）」と誤って報告した。実際は球の周りの**白背景と白背景**を比較して
いただけだった。必ず `_SQ_Color.jpg` を使うこと。

## 採用している素材（全64種）

すべて ambientCG（CC0）。長辺512pxへ縮小（**アスペクト比は維持**）、JPEG品質84。
タイル64枚＋96pxサムネイル64枚で合計約3.4MB。

| キー | 表示名 | ambientCG | 選び方 |
|---|---|---|---|
| oak | オーク | Wood095 | 目視 |
| natoak | ナチュラルオーク | Wood050 | 目視 |
| ash | アッシュ | Wood058 | 目視 |
| walnut | ウォルナット | Wood027 | 目視 |
| teak | チーク | Wood092 | 目視 |
| ebony | エボニー | Wood028 | 目視 |
| maple | メープル | Wood048 | 目視 |
| cherry | チェリー | Wood026 | 目視 |
| mahogany | マホガニー | Wood066 | 目視 |
| birch | バーチ | Wood021 | 目視 |
| pine | パイン | Wood061 | 目視 |
| rosewood | ローズウッド | Wood067 | 目視 |
| greyoak | グレーオーク | Wood049 | 目視 |
| smokedoak | スモークオーク | Wood060 | 目視 |
| marble | 大理石（白） | Marble021 | 目視 |
| calacatta | カラカッタ | Marble012 | 目視 |
| marblegr | 大理石（灰） | Marble003 | 目視 |
| emperador | エンペラドール（茶） | Marble008 | 目視 |
| nero | 黒大理石 | Marble016 | 目視 |
| greenmarble | グリーン大理石 | Marble009 | 目視 |
| pinkmarble | ピンク大理石 | Marble010 | 目視 |
| travertine | トラバーチン | Marble007 | 目視 |
| limestone | ライムストーン | Marble014 | 目視 |
| blackgranite | 黒御影石 | Marble002 | 目視 |
| beigegranite | ベージュ御影石 | Marble011 | 目視 |
| granite | 御影石 | Rock032 | 目視 |
| slate | スレート（石目） | Rock041 | 目視 |
| sandstone | 砂岩 | Rock029 | 目視 |
| basalt | 玄武岩 | Rock035 | 目視 |
| shikkui | 漆喰（白） | Plaster007 | 色一致 28 |
| nurigy | 塗り壁（グレージュ） | Plaster002 | 色一致 5 |
| nurigray | 塗り壁（グレー） | Plaster005 | 色一致 2 |
| plasterwarm | 漆喰（生成り） | Plaster001 | 色一致 28 |
| mochaplaster | 塗り壁（モカ） | Plaster004 | 色一致 21 |
| terraplaster | 塗り壁（テラ） | Plaster006 | 色一致 30 |
| concrete | コンクリート | Concrete003 | 色一致 3 |
| mortar | モルタル | Concrete037 | 色一致 2 |
| concretedk | コンクリート（濃） | Concrete042A | 色一致 3 |
| mortarwarm | モルタル（暖） | Concrete047A | 色一致 5 |
| linen | リネン | Fabric062 | 色一致 6 |
| fabricbg | 織物（ベージュ） | Fabric045 | 色一致 7 |
| fabricgr | 織物（グレー） | Fabric034 | 色一致 2 |
| wool | ウール | Fabric031 | 目視で差し替え |
| denim | デニム | Fabric015 | 色一致 12 |
| greenvelvet | ベルベット（緑） | Fabric078 | 目視で差し替え（Fabric052はタータン柄だった） |
| terrafabric | 織物（テラコッタ） | Fabric026 | 目視で差し替え |
| navyfabric | 織物（ネイビー） | Fabric049 | 色一致 14 |
| subway | サブウェイタイル | Tiles107 | 目視で差し替え |
| mosaic | モザイクタイル | Tiles133A | 目視で差し替え |
| stonetile | 石目タイル（大判） | Tiles143 | 目視で差し替え |
| greensubway | グリーンタイル | Tiles032 | 目視で差し替え |
| blacktile | 黒タイル | Tiles075 | 色一致 8 |
| navytile | ネイビータイル | Tiles035 | 目視で差し替え |
| brick | レンガ | Bricks088 | 色一致 7 |
| terr | テラコッタ | Bricks071 | 色一致 8 |
| whitebrick | 白レンガ | Bricks048 | 色一致 4 |
| darkbrick | 黒レンガ | Bricks058 | 色一致 8 |
| leathercamel | レザー（キャメル） | Leather016 | 色一致 5 |
| leatherbrown | レザー（ブラウン） | Leather019 | 色一致 7 |
| leatherblack | レザー（ブラック） | Leather013 | 色一致 3 |
| leathergreige | レザー（グレージュ） | Leather017 | 実写を目標色に着色 |
| leathergreen | レザー（グリーン） | Leather017 | 実写を目標色に着色 |
| washi | 和紙（生成り） | Plaster003 | 色一致 33 |
| washigray | 和紙（グレー） | Plaster003 | 実写を目標色に着色 |

### 色違いバリエーションは着色している
`leathergreige` / `leathergreen` / `washigray` の3件は、ambientCG に該当色の実物が無い。
実写テクスチャの明暗（＝質感）を保ったまま目標色へ着色している:

    result = target_rgb * (L / mean(L))

粒立ちや皺はそのまま残り、平均色だけが目標色に一致する。CC0なので改変は自由。
着色元は `leathergreige`/`leathergreen` が Leather017、`washigray` が Plaster003。

### 継ぎ目の数値について
「継ぎ目比 = 端の不連続 ÷ 内部の平均差」。2.5未満なら確実に見えない。細かい織り目や
革のシボは内部の平均差が小さいため比が3〜4に出るが、2×2で並べて目視した限り継ぎ目は
見えない。**数値だけで判断せず必ず並べて見ること。**

## 選定は目視でやること（自動化は2回失敗している）

1. **タグで選ぶ** → 色が合わない。ambientCGのタグは色を正しく持たず、「グリーン大理石」に
   クリーム色、「ネイビータイル」に水色、「玄武岩」に明るい灰色が当たった（60件中16件が不適）
2. **色で選ぶ**（アプリ内の `base` を正解にする）→ 色は合う（平均色差8.8/255）が**素材の
   同一性が壊れる**。「ウォルナット」が編み込み模様、「ウール」がピンクの方眼紙、「メープル」が
   節穴だらけの合板、「石目タイル」が市松模様（継ぎ目比13.04）になった

木材カテゴリには寄木・合板・編み込みパネルが混在しているため、機械的な選別では樹種の
見た目を担保できない。**候補シートを見て決めること。**

## 追加・差し替えの手順

1. 候補一覧を作る（球体プレビューでよい。選ぶだけなら十分）
2. 対応表を決めて `_SQ_Color.jpg` を取得 → 長辺512pxへ縮小（**アスペクト比を維持**）
   → `materials/<key>.jpg`、96px正方形を `materials/<key>_t.jpg`
3. 継ぎ目比を測る（端の不連続 ÷ 内部の平均差 が 2.5 未満なら実用上見えない）
4. 2×2に並べた検証シートを作って**目視**する
5. `room-studio.html` の `MATERIALS` を `photo:true` にし、`base` を実タイルの平均色にする

## 実装メモ

- 配信は `/materials/{name}`（`api/index.py` と `server.py`）。`_site.lp_asset` の
  パス検証をそのまま使っているのでディレクトリ外は 404 になる。
- 読み込みは非同期（`ensureMatTile`）。`matTile()`/`matThumb()` は同期呼び出しなので、
  未読込のあいだは `base` 色のベタ塗りを返す。素材を選んだ時点で `await ensureMatTile()`
  してから適用するため、実際の描画にベタ塗りは出ない。作品を開くときは
  `ensureMatTiles()` で使用中のタイルを先に揃える。
- **非正方形タイルに対応済み。** 写真素材には 512×256 がある（板目）。`buildMaterialBuffer`
  と `rebuildFurniture` は tw/th を別々に扱う。正方形に潰すと板幅が倍に見える。
  遠近パス（`buildPerspectiveMaterialBuffer`）は元から tw/th 別扱いなので変更不要。
