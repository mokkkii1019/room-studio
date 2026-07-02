# -*- coding: utf-8 -*-
"""Room Studio — site-level concerns (standard library only).

- log_track(event): append-only click/impression logging (stdout; captured by Vercel logs).
- legal_html(kind): operator info / privacy / 特商法 static pages (placeholders to fill in).

Shared by server.py (local) and api/index.py (Vercel). No third-party imports.
Operator details are read from env so they can be set per-deployment without code edits.
"""

import os
import json
import time
import html as _html

# ---- operator info (fill via env on the deployment; safe placeholders otherwise) ----
SITE_NAME = os.environ.get("SITE_NAME", "Room Studio")
OPERATOR_NAME = os.environ.get("OPERATOR_NAME", "（運営者名を SITE 環境変数で設定してください）")
OPERATOR_CONTACT = os.environ.get("OPERATOR_CONTACT", "（連絡先メール等を設定してください）")
OPERATOR_ADDRESS = os.environ.get("OPERATOR_ADDRESS", "（所在地。特商法表記が必要な場合に記載）")


def log_track(event):
    """Emit one structured click/impression line. Best-effort; never raises.
    On Vercel this lands in the function logs; locally it prints to the server console.
    (No DB in this phase — swap this for a real sink later without touching callers.)"""
    try:
        event = dict(event or {})
        event.setdefault("ts", int(time.time()))
        print("TRACK " + json.dumps(event, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass


_PR_LINE = ("本サイトはアフィリエイト広告（PR）を含みます。商品情報は各ECサイトの提供に基づき、"
            "価格・在庫等は変動します。商品情報提供：楽天ウェブサービス。")

_PAGES = {
    "about": ("運営者情報", [
        ("サイト名", SITE_NAME),
        ("運営者", OPERATOR_NAME),
        ("連絡先", OPERATOR_CONTACT),
        ("収益に関する表記", "本サイトはアフィリエイト広告（PR）による収益で運営しています。"),
        ("商品情報のクレジット", "商品情報提供：楽天ウェブサービス。"),
    ]),
    "privacy": ("プライバシーポリシー", [
        ("画像の取り扱い", "アップロードされた部屋・家具の画像は、原則としてご利用の端末内（ブラウザ）で処理され、"
                          "運営サーバーに保存しません。"),
        ("アクセス解析", "利用状況の把握のため、クリック計測やアクセス解析（GA4等）を利用する場合があります。"
                        "個人を特定しない統計目的で使用します。"),
        ("アフィリエイト", "購入リンクはアフィリエイト広告（PR）を含みます。遷移先サイトでの取り扱いは各サイトの"
                          "ポリシーに従います。"),
        ("お問い合わせ", OPERATOR_CONTACT),
    ]),
    "tokushoho": ("特定商取引法に基づく表記", [
        ("販売事業者", OPERATOR_NAME),
        ("所在地", OPERATOR_ADDRESS),
        ("連絡先", OPERATOR_CONTACT),
        ("備考", "本表記は有料サービス（課金）導入時に必要事項を記載するための枠です。"
                "現時点では課金機能は提供していません。"),
    ]),
}


def legal_html(kind):
    """Return a simple, self-contained static page. kind ∈ about|privacy|tokushoho."""
    title, rows = _PAGES.get(kind, _PAGES["about"])
    esc = _html.escape
    body = "\n".join(
        f'<section><h2>{esc(k)}</h2><p>{esc(v)}</p></section>' for k, v in rows)
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}｜{esc(SITE_NAME)}</title>
<style>
  body{{margin:0;background:#FBFAF8;color:#2A2824;font-family:"Zen Kaku Gothic New",system-ui,sans-serif;line-height:1.7}}
  .wrap{{max-width:720px;margin:0 auto;padding:32px 20px 60px}}
  a{{color:#3B6FE0}}
  h1{{font-size:20px;margin:0 0 6px}} .pr{{font-size:12px;color:#7C776E;margin:0 0 24px}}
  section{{border-top:1px solid rgba(0,0,0,.1);padding:16px 0}}
  h2{{font-size:13.5px;margin:0 0 4px}} p{{margin:0;font-size:13px;color:#3f3b36;white-space:pre-wrap}}
  nav{{margin-top:28px;font-size:12px;display:flex;gap:14px;flex-wrap:wrap}}
</style></head><body><div class="wrap">
<h1>{esc(title)}</h1>
<p class="pr">{esc(_PR_LINE)}</p>
{body}
<nav><a href="/">← アプリに戻る</a><a href="/about">運営者情報</a><a href="/privacy">プライバシーポリシー</a><a href="/tokushoho">特商法表記</a></nav>
</div></body></html>"""
