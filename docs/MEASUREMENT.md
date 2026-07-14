# 計測設計メモ（GA4 ＋ クリック計測）

集客（SEO/note/SNS）の効果と、収益（アフィリエイト）に最も近い先行指標を継続的に見るための最小計測設計。
**GA4の注入コードは実装済み**（`GA4_ID` 環境変数を設定すると配信時に gtag.js を注入）。本書は「何を見るか」「どう設定するか」「将来どこを差し替えるか」をまとめる。

---

## 1. 有効化の手順（ユーザー実施）

1. [Google Analytics](https://analytics.google.com/) で **GA4 プロパティ**を作成し、**ウェブデータストリーム**を追加。
2. 発行される**測定ID**（`G-XXXXXXXXXX`）を控える。
3. Vercel → **Settings → Environment Variables** に `GA4_ID = G-XXXXXXXXXX` を設定（Production／必要なら Preview）→ **再デプロイ**。
4. トップページを開き、GA4 の「リアルタイム」に自分のアクセスが出れば有効化成功。
   - 自分のクリックを除外したい場合は、URL に `?notrack=1` を付けて一度アクセス（`localStorage` に記録され、以後 GA4・`/track` とも送信停止。`?notrack=0` で解除）。

> 未設定なら解析オフ（何も送信しない）。ローカル検証時のみ `.env` に `GA4_ID` を置いてもよいが、本番はVercelの環境変数で管理する。

---

## 2. 見るべき指標（優先順）

| 優先 | 指標 | 取得元 | 意味 |
|---|---|---|---|
| ★★★ | **`select_item`（商品クリック）** | GA4イベント / `/track` | **収益に最も近い先行指標**。アフィリンクのクリック数。 |
| ★★☆ | **収集実行**（家具を集めた回数） | （未計測・下記§4で追加候補） | アプリの中核操作。エンゲージメントの証。 |
| ★★☆ | **アプリ起動 / 画像読み込み** | （未計測・下記§4） | 「触ってみた」到達。LP→アプリの転換の分母。 |
| ★★☆ | **流入（ページ別・チャネル別）** | GA4 標準（page_location / session_source） | どのLP・どのチャネル（note/SNS/検索）が効いているか。 |
| ★☆☆ | 滞在・直帰・スクロール | GA4 標準（拡張計測） | LPのコンテンツ品質の目安。 |

### LP → アプリ の転換を見る仕掛け（実装済み）
- 各LPの CTA は `/?ref=lp-<slug>` へリンク。GA4 は `page_location` にこの `ref` を含むため、**どのLP経由でアプリに来たか**を GA4 上で分別できる（アプリ側の改修は不要）。
- 例：GA4 探索で `page_location` に `ref=lp-hitorigurashi-sofa` を含むセッションを絞り込み、その後の `select_item` 数を見る。

---

## 3. 実装済みのイベント／エンドポイント

### `select_item`（GA4イベント）＋ `/track`（サーバーログ）
`room-studio.html` の `trackClick(id, type, url, shop)` が、商品の「詳細/購入」クリック時に発火：

- **GA4**: `gtag('event','select_item', { item_id, link_type, link_url, shop })`
- **サーバー**: `GET /track?id&type&url&shop&src=web` → `_site.log_track()` が1行を stdout に出力（Vercelのファンクションログに残る）

パラメータの意味：
- `item_id` … 楽天 itemCode 等の商品ID
- `link_type` … `library:<source>` or `layer:<source>`（クリック箇所×収集元）
- `link_url` … 遷移先（アフィリンク）
- `shop` … **メーカー/店舗名**（STEP0 で追加。メーカー別のクリック分析用）

### メーカー別計測（STEP0 での軽微追加）
- 収集商品は `shop`（店舗名）を保持している。`trackClick` の第4引数に `shop` を渡すよう追加し、`/track` と `select_item` の両方に含めた。
- これにより「どのメーカー/店舗の商品がクリックされたか」を後から集計できる（GA4 のカスタムディメンションに `shop` を登録すれば探索で軸にできる）。
- 過剰実装は避け、既存の2クリック導線（ライブラリ / レイヤー）にのみ適用。

---

## 4. 未計測・将来の拡張候補（本STEPの範囲外）

集客の受け皿としては上記で足りるが、転換率を精緻に見るなら以下を将来追加する余地がある（**今回は実装しない**）：

- **`app_start`／`room_loaded`**：画像読み込み完了時に GA4 イベント。LP→起動→収集→クリックのファネルが完成する。
- **`collect_run`**：収集実行時に `genre/type/taste/count` を含む GA4 イベント。需要のあるカテゴリが分かる。
- 追加する場合の実装位置（参考）：`loadRoom` 系／`doCollect`（`room-studio.html`）。**コア操作ロジックに触れるため、STEP0の「触れない」方針の対象**。別STEPで慎重に。

---

## 5. `/track` の「後で差し替える箇所」（課題#6）

現状 `/track` は**集計DBを持たず stdout ログのみ**。本格的な集計には差し替えが必要。

- 差し替え箇所は **1関数に集約済み**：`api/_site.py` の `log_track(event)`。
  ```python
  def log_track(event):
      # 現状: print("TRACK " + json.dumps(event))  ← Vercelログに出るだけ
      # 将来: ここを DB / KV / 外部計測SaaS への書き込みに差し替える（呼び出し側は無改修）
  ```
- 呼び出し側（`/track` エンドポイント）は `event` dict を渡すだけなので、**`log_track` の中身を変えるだけ**で永続化先を追加できる（例：Vercel KV、Supabase、外部イベントAPI）。
- GA4 で足りる指標は GA4 に寄せ、`/track` は「サーバー側で確実に取りたい生ログ」用途に温存する、という役割分担が現実的。

---

## 6. まとめ（今すぐやること / 後回しでよいこと）

- **今すぐ（ユーザー）**：GA4プロパティ作成 → `GA4_ID` を Vercel に設定 → 再デプロイ → リアルタイムで疎通確認。必要なら `shop` をカスタムディメンション登録。
- **後回し（別STEP）**：`app_start`/`collect_run` の追加、`/track` の永続化（DB化）、メーカー別レポートの定型化。
