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
import hmac
import html as _html

# ---- optional access gate (for a PRIVATE web deployment) --------------------
# When ACCESS_TOKEN is set, the whole app requires the token (login page + cookie).
# When empty (the public deployment / local dev), the gate is OFF and nothing changes.
# This lets a separate, crawler-enabled deployment be reachable on the web but usable
# only by the operator, without affecting the public official build.
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "").strip()
ACCESS_COOKIE = "rs_access"


def _eq(a, b):
    try:
        return hmac.compare_digest(a or "", b or "")
    except Exception:  # noqa: BLE001
        return False


def key_matches(key):
    """True only when the gate is on AND the supplied key equals the token."""
    return bool(ACCESS_TOKEN) and _eq(key, ACCESS_TOKEN)


def access_ok(cookie_val, query_key):
    """Gate check. True when disabled, or a valid cookie / ?key is presented."""
    if not ACCESS_TOKEN:
        return True
    return _eq(cookie_val, ACCESS_TOKEN) or _eq(query_key, ACCESS_TOKEN)


def login_html():
    return ("""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>非公開｜Room Studio</title>
<style>body{margin:0;height:100vh;display:grid;place-items:center;background:#FBFAF8;color:#2A2824;
font-family:"Zen Kaku Gothic New",system-ui,sans-serif}form{display:flex;gap:8px;flex-direction:column;width:260px}
h1{font-size:15px;margin:0 0 4px;text-align:center}p{font-size:12px;color:#7C776E;margin:0 0 12px;text-align:center}
input{padding:11px;border:1px solid rgba(0,0,0,.15);border-radius:8px;font-size:14px}
button{padding:11px;border:0;border-radius:8px;background:#2A2824;color:#FBFAF8;font-weight:700;cursor:pointer}</style>
</head><body><form method="get" action="/"><h1>非公開エリア</h1><p>アクセスキーを入力してください</p>
<input name="key" type="password" placeholder="アクセスキー" autofocus autocomplete="current-password">
<button type="submit">入る</button></form></body></html>""")

# ---- operator info (overridable via env per deployment) -----------------------
# Defaults are publish-safe: a trade-name style operator line, and empty contact /
# address (legal_html skips empty rows — contact disclosure is optional for an
# affiliate-only site; 特商法 applies only when we sell something ourselves).
SITE_NAME = os.environ.get("SITE_NAME", "Room Studio")
OPERATOR_NAME = os.environ.get("OPERATOR_NAME", "Room Studio 運営者（個人運営）")
OPERATOR_CONTACT = os.environ.get("OPERATOR_CONTACT", "").strip()
OPERATOR_ADDRESS = os.environ.get("OPERATOR_ADDRESS", "").strip()

# ---- canonical base URL (overridable via env for custom-domain migration) -----
# The app HTML ships with canonical/OGP/JSON-LD pointing at the legacy vercel.app
# domain (see _DEFAULT_BASE). Setting SITE_BASE_URL (e.g. https://roomstudio.jp)
# rewrites all of them at serve time (inject_base_url). Unset = no change (fallback).
# No trailing slash (we append paths ourselves).
_DEFAULT_BASE = "https://room-studio-fawn.vercel.app"
SITE_BASE_URL = (os.environ.get("SITE_BASE_URL", "").strip().rstrip("/") or _DEFAULT_BASE)


# ---- analytics (GA4) ---------------------------------------------------------
# Set env GA4_ID (e.g. G-XXXXXXXXXX) to enable analytics: the id is stamped into
# the served HTML, where the app then loads gtag.js. Unset = nothing is sent.
GA4_ID = os.environ.get("GA4_ID", "").strip()


def inject_ga4(html):
    """Stamp the GA4 measurement id into the app HTML (no-op when unset)."""
    if not GA4_ID:
        return html
    safe = _safe_ga4()
    return html.replace("const GA4_ID=''", "const GA4_ID='" + safe + "'", 1)


def _safe_ga4():
    return GA4_ID.replace("\\", "").replace("'", "").replace("<", "")


def inject_base_url(html):
    """Rewrite the hardcoded canonical/OGP/JSON-LD base URL to SITE_BASE_URL.
    No-op when SITE_BASE_URL is unset (equals the legacy default)."""
    if SITE_BASE_URL == _DEFAULT_BASE:
        return html
    return html.replace(_DEFAULT_BASE, SITE_BASE_URL)


def render_app_html(html):
    """Serve-time injections for the single-file app: base URL + GA4.
    Both the Vercel entry (api/index.py) and local server.py call this."""
    return inject_ga4(inject_base_url(html))


def ga4_head_snippet():
    """A standalone gtag.js loader for server-rendered pages (landing pages).
    Mirrors the app's behaviour: honours the rs_notrack opt-out; empty when GA4 unset."""
    if not GA4_ID:
        return ""
    safe = _safe_ga4()
    return (
        "<script>(function(){try{if(localStorage.getItem('rs_notrack')==='1')return;}catch(e){}"
        "var s=document.createElement('script');s.async=true;"
        "s.src='https://www.googletagmanager.com/gtag/js?id=" + safe + "';document.head.appendChild(s);"
        "window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments);};"
        "gtag('js',new Date());gtag('config','" + safe + "');})();</script>"
    )


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
        f'<section><h2>{esc(k)}</h2><p>{esc(v)}</p></section>' for k, v in rows if (v or "").strip())
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


# =============================================================================
# Landing pages (search-intent SEO). Server-rendered, self-contained, GA4-aware.
#
# All landing pages are defined in ONE place (LANDING_PAGES) so sitemap_xml()
# picks them up automatically. Copy is intentionally placeholder-only: each
# section carries an author instruction (<!-- ... -->) plus visible dummy text.
# Do NOT fabricate statistics or hard claims — the operator fills these in.
# The CTA links to the app at /?ref=lp-<slug> (attribution via GA4 page_location;
# no app-side change needed). Deep-linking into a preset collection is a future
# enhancement (the app has no preset query params today — see STEP0_REPORT.md).
# =============================================================================
LANDING_PAGES = [
    {
        "slug": "6jo-hitorigurashi-layout",
        "title": "6畳 一人暮らしのレイアウトを写真で試す",
        "desc": "6畳ワンルームの家具レイアウトを、自分の部屋の写真にそのまま家具を置いて無料でシミュレーション。買う前に配置を確かめられます。",
        "h1": "6畳・一人暮らしのレイアウトを、写真で試す",
        "lead": "限られた6畳をどう使うか。実際の部屋写真に家具を置いて、買う前に配置を試せます。",
        "sections": [
            ("6畳ワンルームでよくある悩み", "6畳・一人暮らしで家具配置に悩むポイント（動線・ベッドとデスクの兼ね合い等）を150〜300字で。断定的な数値は避ける。"),
            ("Room Studio でできること", "写真に家具を置く／壁・床の色を替える／不要物を消す、の3点を一人暮らし目線で150〜200字。"),
            ("配置を試す手順", "①部屋の写真を開く ②ソファやベッドを収集・配置 ③サイズ感を確認、の流れを箇条書きで補足。"),
        ],
        "cta": "6畳レイアウトを試してみる",
    },
    {
        "slug": "hitorigurashi-sofa",
        "title": "一人暮らしのソファ 選び方と配置シミュレーション",
        "desc": "一人暮らしに合うソファのサイズ・配置を、部屋の写真に置いて確認。買ってから「大きすぎた」を防ぐ無料シミュレーターです。",
        "h1": "一人暮らしのソファ、置いてから選ぶ",
        "lead": "1〜2人掛け？ ローソファ？ 実際の部屋に置いて大きさと余白を確かめてから選べます。",
        "sections": [
            ("一人暮らしのソファ選びの基準", "サイズ・幅・圧迫感・動線など選び方の観点を150〜300字で。メーカー名の断定的推奨は避ける。"),
            ("写真に置いてサイズ感を確認", "収集したソファ画像を部屋に配置し、拡縮・向き変更で余白を見る使い方を150字程度。"),
            ("色・素材で部屋に合わせる", "ソファの色替え・素材変更で内装と合わせられる点を100〜150字。"),
        ],
        "cta": "ソファを部屋に置いて試す",
    },
    {
        "slug": "chintai-kabe-makeover",
        "title": "賃貸の壁を模様替え（原状回復OK）を写真で試す",
        "desc": "賃貸の壁の色や雰囲気を、原状回復を気にせず写真上でシミュレーション。実際に貼る前にイメージを固められます。",
        "h1": "賃貸の壁、貼る前に写真で試す",
        "lead": "壁紙シートやペイントを検討する前に、写真の壁だけ色・素材を替えて仕上がりを確認できます。",
        "sections": [
            ("賃貸の壁を変えたいときの選択肢", "原状回復可能な壁装飾（貼ってはがせる壁紙等）の一般的な選択肢を150〜300字で。製品の効果を断定しない。"),
            ("壁だけ色・素材を替える", "面（ポリゴン）選択やAI選択で壁の一面だけを選び、色・素材を替える手順を150字程度。"),
            ("元の写真と見比べる", "before/after比較スライダーで施工前後のイメージを見比べられる点を100字程度。"),
        ],
        "cta": "壁の模様替えを試す",
    },
    {
        "slug": "hokuo-interior",
        "title": "北欧インテリアの部屋づくりを写真で試す",
        "desc": "北欧テイストの家具・カラーを、自分の部屋の写真でシミュレーション。買う前にコーディネートのイメージを固められます。",
        "h1": "北欧インテリアの部屋づくりを、写真で試す",
        "lead": "木の質感と明るい色。北欧テイストの家具を部屋の写真に置いて、全体の雰囲気を確かめられます。",
        "sections": [
            ("北欧インテリアの特徴", "木材・ニュートラルカラー・シンプルな家具など北欧テイストの一般的な特徴を150〜300字で。"),
            ("テイスト指定で家具を集める", "収集の「テイスト」欄に『北欧』と入れて家具を集め、部屋に配置する使い方を150字程度。"),
            ("床・壁の色で世界観を作る", "床材や壁色を明るいトーンに替えて北欧の雰囲気に寄せる方法を100〜150字。"),
        ],
        "cta": "北欧インテリアを試す",
    },
]

_LP_BY_SLUG = {p["slug"]: p for p in LANDING_PAGES}


def landing_slugs():
    """All landing-page slugs (sitemap uses this)."""
    return [p["slug"] for p in LANDING_PAGES]


def landing_html(slug):
    """Render a single landing page, or None if the slug is unknown."""
    p = _LP_BY_SLUG.get(slug)
    if not p:
        return None
    esc = _html.escape
    url = f"{SITE_BASE_URL}/lp/{slug}"
    app_url = f"/?ref=lp-{slug}"
    ga4 = ga4_head_snippet()
    sections = "\n".join(
        f"<section><h2>{esc(h)}</h2>\n<!-- 執筆指示: {esc(instr)} -->\n"
        f'<p class="ph">（本文プレースホルダ）{esc(instr)}</p></section>'
        for h, instr in p["sections"])
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "WebPage",
        "name": p["title"], "description": p["desc"], "url": url, "inLanguage": "ja",
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_BASE_URL + "/"},
    }, ensure_ascii=False)
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(p['title'])}｜{esc(SITE_NAME)}</title>
<meta name="description" content="{esc(p['desc'])}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:title" content="{esc(p['title'])}">
<meta property="og:description" content="{esc(p['desc'])}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{esc(SITE_BASE_URL)}/og.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{jsonld}</script>{ga4}
<style>
  body{{margin:0;background:#FBFAF8;color:#2A2824;font-family:"Zen Kaku Gothic New",system-ui,sans-serif;line-height:1.8}}
  .wrap{{max-width:760px;margin:0 auto;padding:40px 20px 72px}}
  a{{color:#3B6FE0}}
  h1{{font-size:24px;margin:0 0 10px;line-height:1.4}}
  .lead{{font-size:15px;color:#57534c;margin:0 0 8px}}
  .pr{{font-size:12px;color:#7C776E;margin:0 0 28px}}
  section{{border-top:1px solid rgba(0,0,0,.1);padding:20px 0}}
  h2{{font-size:16px;margin:0 0 8px}}
  p{{margin:0;font-size:14px;color:#3f3b36}}
  .ph{{color:#9a9384;font-style:italic}}
  .cta{{display:block;text-align:center;margin:28px 0 8px;padding:15px 20px;background:#2A2824;color:#FBFAF8;
        text-decoration:none;border-radius:10px;font-weight:700;font-size:15px}}
  nav{{margin-top:32px;font-size:12px;display:flex;gap:14px;flex-wrap:wrap;color:#7C776E}}
</style></head><body><div class="wrap">
<h1>{esc(p['h1'])}</h1>
<p class="lead">{esc(p['lead'])}</p>
<p class="pr">{esc(_PR_LINE)}</p>
{sections}
<a class="cta" href="{esc(app_url)}">{esc(p['cta'])} →</a>
<nav><a href="/">アプリを開く</a><a href="/about">運営者情報</a><a href="/privacy">プライバシーポリシー</a><a href="/tokushoho">特商法表記</a></nav>
</div></body></html>"""


# ---- robots.txt / sitemap.xml -------------------------------------------------
def robots_txt():
    """robots.txt body. Private deployments (ACCESS_TOKEN set) disallow everything;
    the public site allows all and advertises the sitemap."""
    if ACCESS_TOKEN:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n"


def sitemap_xml(lastmod=None):
    """sitemap.xml body listing the top page, legal pages and every landing page.
    `lastmod` is a YYYY-MM-DD string (caller passes the app's file mtime); falls
    back to today if omitted."""
    lm = lastmod or time.strftime("%Y-%m-%d")
    paths = ["/", "/about", "/privacy", "/tokushoho"] + [f"/lp/{s}" for s in landing_slugs()]
    esc = _html.escape
    urls = "\n".join(
        f"  <url><loc>{esc(SITE_BASE_URL + p)}</loc><lastmod>{esc(lm)}</lastmod></url>"
        for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")
