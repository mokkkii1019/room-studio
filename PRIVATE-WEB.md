# 非公開ウェブ版（クローラ）のデプロイ手順

自分だけがアクセスできる、スクレイピング（IKEA / Shopify）版をウェブに立てるための手順。
**公開版（`main`）は一切変更せず**、別プロジェクト＋別ブランチで運用する。

## 仕組み（二重の分離）

| | 公開版 | 非公開版（これ） |
|---|---|---|
| ブランチ | `main` | `private-web` |
| クローラ同梱 | ✗（`.vercelignore` で除外） | ○（`private-web` では除外を外す） |
| `APP_MODE` | `public`（既定） | `private` |
| `COLLECT_PROVIDER` | `official`（既定） | `crawler` |
| アクセス制限 | なし（誰でも） | `ACCESS_TOKEN`（合言葉） |
| 収集元 | 楽天API | IKEA / RUGHAUS / KANADEMONO / BAUHAUS |

- アクセスゲートは `ACCESS_TOKEN` を**設定した時だけ**有効（`api/_site.py` + 各サーバのミドルウェア）。
  未設定＝公開版・ローカルは無変更。
- `main` は crawler をファイルごと除外＋`APP_MODE=public` で実行時 403 の**二重防御**。取り違え厳禁。

## 手順（Vercel）

1. **Add New → Project → Import**（同じリポジトリを2つ目のプロジェクトとして）。
   - **Framework Preset＝FastAPI**（重要。Other にすると全パス 404／Function Invocations 0）。
   - Root Directory `./`、Build/Install/Output は上書きしない（自動）。
2. **Environment Variables（Production）**：
   - `APP_MODE=private`
   - `COLLECT_PROVIDER=crawler`
   - `ACCESS_TOKEN=<長めの合言葉>`（例: `python -c "import secrets;print(secrets.token_urlsafe(24))"`）
   - 楽天キーは不要（IKEA/Shopify はキー不要）。
3. **本番ブランチを `private-web` に**：Settings → **Environments → Production → Branch Tracking** を `private-web` に変更 → Save。
4. **再デプロイ**：`private-web` に push（空コミットでも可）／または Deployments の該当行 ⋯ → Redeploy／または該当デプロイを ⋯ → Promote to Production。

## 確認

- `https://<非公開URL>/health` → `{"provider":"crawler","mode":"private", ...}` なら成功。
- 初回だけ `https://<非公開URL>/?key=<合言葉>` でログイン（Cookie 30日保持）。以後は普通のURLでOK。
- 家具タブに IKEA/RUGHAUS/KANADEMONO/BAUHAUS が並ぶ。

## つまずき集

- **404: NOT_FOUND ＋ Function Invocations 0** → Framework Preset が Other。**FastAPI** に変更して再デプロイ。
- **`/health` が official/public** → `APP_MODE`/`COLLECT_PROVIDER` 未反映。環境変数を設定して**再デプロイ**（設定だけでは反映されない）。
- **収集が 500** → 本番ブランチが `private-web` になっていない（`main` はクローラ非同梱なので crawler モードだと import 失敗）。Branch Tracking を確認。
- **IKEA が空/失敗** → Vercel 共有IPがブロックされやすい。RUGHAUS/KANADEMONO/BAUHAUS を試す。自分用に軽く。
- **「楽天 家具メーカー」が効かない** → crawler モードでは楽天は使えない（プロバイダ固定）。楽天は公開版で。

## メンテ（`main` の変更を反映）

`private-web` は `main` との差分が `.vercelignore` 1行のみになるよう保つ。反映時は：

```
git checkout private-web
git merge main        # .vercelignore で競合したら「crawler を除外しない」private-web 側を採用
git push origin private-web
```
