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
# picks them up automatically. Each dict: sections=[(heading, body)] real copy,
# faq=[(q, a)] (→ FAQPage JSON-LD), related=[slug] (→ internal links, anchor=H1).
# Keep copy honest: general interior guidance + the app's real features; avoid
# fabricated statistics or hard product claims (hedge where it depends).
# The CTA links to the app at /?ref=lp-<slug> (attribution via GA4 page_location;
# no app-side change needed). Deep-linking into a preset collection is a future
# enhancement (the app has no preset query params today — see STEP0_REPORT.md).
# =============================================================================
LANDING_PAGES = [
    {
        "slug": "6jo-hitorigurashi-layout",
        "title": "6畳 一人暮らしの部屋を、色と配置で広く見せる",
        "desc": "6畳ワンルームを広くすっきり見せるには色使いが大切。Room Studioなら部屋の写真に家具を置き、壁や床の色を変えながら広く見えるバランスを無料で試せます。",
        "h1": "6畳・一人暮らしの部屋を、色で広く見せる",
        "lead": "6畳ワンルームは、家具や壁の色みで「広く見えるか」が大きく変わります。Room Studioなら、部屋の写真に家具を置いて、壁や床の色まで変えながら、すっきり見えるバランスを先に試せます。",
        "sections": [
            ("6畳を広く見せる色の使い方", "限られた6畳を広く見せるコツは、色にあります。壁や大きな家具を明るめ・淡めの色でそろえると圧迫感が出にくく、部屋が広く感じられます。逆に濃い色や色数が多いとごちゃつきがち。まずは「ベースは明るい色、差し色は少しだけ」を意識すると、6畳でもすっきりまとまります。"),
            ("写真に家具を置いて、配置と色を試す", "Room Studioは、あなたの部屋の写真に家具を置いて、大きさや向きを調整しながらレイアウトを試せます。さらに置いた家具の色も変えられるので、「この位置にこの色を置いたら広く見えるか」を、実際の部屋で確かめられます。これから買う家具だけでなく、いま使っているテレビや収納を写真に撮って背景を切り抜けば、それも部屋に置いて模様替え後の6畳を具体的にイメージできます。"),
            ("壁・床の色や雑貨でも印象を変える", "家具だけでなく、壁や床の色を変えると部屋全体の印象は大きく変わります。床を明るい木目にする、壁を淡いトーンにする——そんな「もし変えたら」を写真の上で試せます。ソファやテーブルだけでなく、ラグやカーテン、フロアランプといった雑貨の色みも6畳の見え方を左右するので、大きな家具は淡めに、ラグやクッションで差し色を少し、といった調整もまとめて確かめられます。"),
        ],
        "faq": [
            ("6畳のワンルームでも家具は置けますか？", "置き方しだいで十分に暮らせます。大きな家具は壁沿いにまとめ、色を明るめでそろえると圧迫感が出にくくなります。Room Studioなら、置いてみてから広く見えるかを写真で確かめられます。"),
            ("狭い部屋を広く見せるには何色がいいですか？", "壁や大きな家具を明るく淡いトーンでそろえ、差し色は少しだけにするのが基本です。実際の部屋の写真で色を変えて見比べると、自分の部屋に合うトーンが見つけやすくなります。"),
        ],
        "related": ["hitorigurashi-sofa", "hokuo-interior", "chintai-kabe-makeover"],
        "cta": "6畳の部屋づくりを試す",
    },
    {
        "slug": "hitorigurashi-sofa",
        "title": "一人暮らしのソファを、部屋に合う色で選ぶ",
        "desc": "一人暮らしのソファは色や素材で部屋の印象が決まります。Room Studioなら部屋の写真にソファを置いて、色や素材を変えながら部屋に馴染むかを無料で試せます。",
        "h1": "一人暮らしのソファ、部屋に合う色で選ぶ",
        "lead": "ソファは部屋のなかでも存在感が大きい家具。だからこそ、色や素材が部屋に合っていないと、せっかく選んでも浮いて見えてしまいます。Room Studioなら、自分の部屋の写真に気になるソファを置いて、色や素材を変えながら「部屋に馴染むか」を先に確かめられます。",
        "sections": [
            ("一人暮らしのソファは「色と雰囲気」で決まる", "ソファは面積が大きいぶん、色や素材で部屋全体の印象がぐっと変わります。ナチュラルにまとめたいなら明るいファブリック、引き締めたいならダークカラーやレザー調、と「どんな雰囲気の部屋にしたいか」から考えると色を絞りやすくなります。サイズは置ける範囲で選べば大丈夫。まずは色と質感からイメージを固めましょう。"),
            ("部屋の写真で、色・素材を変えて試す", "「ベージュとグレー、どっちが部屋に合う？」——頭の中で迷うより、実際の部屋で見比べるのが一番です。Room Studioは、あなたの部屋の写真に置いたソファの色や素材をその場で変えられるので、気になる色をいくつも並べて確かめられます。いま使っているテレビ台やローテーブルを写真に撮って背景を切り抜き、一緒に並べれば、ソファを買い替えた後の部屋を具体的に見られます。"),
            ("床・壁・カーテンや小物と合わせて、全体で決める", "ソファ単体では良く見えても、部屋に置くと意外と浮くことがあります。Room Studioなら床や壁の色も一緒に変えられるので、カーテンやラグを含めた「部屋全体のトーン」で判断できます。ソファに合わせてラグやクッション、フロアランプの色をそろえるとまとまりが出るので、こうした小物も一緒に置いて見比べましょう。しっくりくる組み合わせが見つかったら、商品リンクからそのまま詳細をチェックできます。"),
        ],
        "faq": [
            ("一人暮らしにはどんなソファが人気ですか？", "省スペースな2人掛けやコンパクトソファなど、部屋を広く使える設計のものがよく選ばれます。大きさよりまず、部屋に合う色や質感から絞るのがおすすめです。"),
            ("ソファの色は何色が部屋に合わせやすいですか？", "ベージュやグレーなどのニュートラルカラーは、床やカーテンと合わせやすく失敗しにくい色です。実際の部屋の写真で色を変えて見比べると安心して選べます。"),
            ("買う前に部屋に合うか確認できますか？", "はい。Room Studioなら、部屋の写真に気になるソファを置いて、色や素材を変えながら馴染むかを試せます。しっくりきたら商品リンクから詳細を確認できます。"),
        ],
        "related": ["6jo-hitorigurashi-layout", "hokuo-interior"],
        "cta": "色違いのソファを部屋で見比べる",
    },
    {
        "slug": "chintai-kabe-makeover",
        "title": "賃貸の壁、貼る前に色と雰囲気を試す（原状回復OK）",
        "desc": "賃貸の壁の模様替えは「部屋に合う色か」を貼る前に知りたいもの。Room Studioなら部屋の写真の壁だけ色や素材を変えて、仕上がりの雰囲気を無料で試せます。",
        "h1": "賃貸の壁、貼る前に色と雰囲気を試す",
        "lead": "貼ってはがせる壁紙やウォールシート。気になるけれど、「部屋に合うか」「思ったより派手にならないか」は貼ってみないと分からない…。Room Studioなら、部屋の写真の壁だけ色や素材を変えて、仕上がりの雰囲気を先に確かめられます。",
        "sections": [
            ("賃貸でも楽しめる壁の模様替え", "賃貸では原状回復が前提ですが、貼ってはがせるタイプの壁紙やシートなど、退去時に戻しやすい方法もいろいろあります（対応可否や仕上がりは製品によって異なるので、購入前に商品ページの説明を確認しましょう）。まずは「どんな色・雰囲気にしたいか」を決めるのが、失敗しない第一歩です。"),
            ("壁だけ色・素材を変えてみる", "Room Studioは、写真のなかの壁だけを選んで色や素材を変えられます。一面だけアクセントカラーにする、木目や漆喰風の質感を試す——といった「貼ったらどう見えるか」を、部屋の実際の光や家具ごと確認できます。壁の色を変えたうえで、いま置いている家具を写真で一緒に並べれば、家具と新しい壁色の相性も先に確認できます。"),
            ("家具やカーテンと合うかを見比べる", "壁の色は、家具やカーテンとの組み合わせで印象が変わります。Room Studioの比較機能を使えば、変える前と後を並べて見比べられるので、壁に合わせてカーテンやアートの色みまで含めて、「本当にこの色でいいか」を落ち着いて判断できます。"),
        ],
        "faq": [
            ("貼ってはがせる壁紙なら、賃貸でも必ず元に戻せますか？", "「はがせる」とされる壁紙でも、貼る期間や下地の状態によっては、はがす際に既存の壁紙を傷めたり、のり跡が残ったりすることがあります。原状回復できるかは製品や物件によって異なるため、購入前に商品説明を確認し、心配な場合は目立たない場所で試すのがおすすめです。賃貸借契約書の原状回復の取り決めも確認しておくと安心です。"),
            ("Room Studioで壁の色を変えると、実際に貼らずに確認できますか？", "はい。写真の中の壁だけを選んで色や素材を変えられるので、実際に壁紙を貼る前に「部屋に合う色か」「派手すぎないか」を確かめられます。あくまで画面上の仕上がりイメージなので、実際の製品の色や質感は商品ページでも確認してください。"),
        ],
        "related": ["6jo-hitorigurashi-layout", "hokuo-interior"],
        "cta": "壁の色を試してみる",
    },
    {
        "slug": "hokuo-interior",
        "title": "北欧インテリアの部屋づくりを、色と質感で試す",
        "desc": "北欧インテリアは色と素材の組み合わせが決め手。Room Studioなら部屋の写真で家具や床・壁の色を変えて、北欧らしい雰囲気になるかを無料で試せます。",
        "h1": "北欧インテリアの部屋づくりを、色と質感で試す",
        "lead": "明るい木の質感、白やグレーのベースに効かせる差し色。北欧テイストは「色と素材の組み合わせ」で決まります。Room Studioなら、部屋の写真で家具や床・壁の色を変えながら、北欧らしい雰囲気になるかを先に試せます。",
        "sections": [
            ("北欧インテリアは色と質感でつくる", "北欧テイストは、明るい木の質感、白やグレーのニュートラルカラー、そこに少しだけ差し色を効かせるのが定番です。派手さより「明るさと素材感」でまとめるのがポイント。まずは目指したいトーンを決めると、家具や色の選び方が定まってきます。"),
            ("「北欧」で家具を集めて置いてみる", "Room Studioの収集機能で、テイスト欄に「北欧」と入れて家具を集められます。気になった家具を部屋の写真に置き、色や素材を調整しながら、自分の部屋が北欧の雰囲気になるかを試せます。新しく買う家具だけでなく、いま持っている家具を写真に撮って置き、北欧テイストに馴染むかを試すこともできます。"),
            ("床・壁の色や雑貨で世界観を仕上げる", "北欧らしさは、床や壁のトーンでぐっと近づきます。床を明るい木目に、壁を白やグレーに——写真の上で変えて、家具と合わせた全体の世界観を確かめましょう。観葉植物やアート、あたたかみのある照明を加えると北欧らしさがぐっと増すので、こうした雑貨も「北欧」のテイストで集めて部屋に合わせられます。しっくりきたら、商品リンクから家具の詳細もチェックできます。"),
        ],
        "faq": [
            ("北欧インテリアはどんな色でまとめればいいですか？", "白やグレーなどの明るいベースに、木の質感を合わせ、差し色を少しだけ効かせるのが定番です。実際の部屋の写真で床や壁の色を変えて、明るさと素材感を確かめると近づけやすくなります。"),
            ("北欧風の家具はどうやって探せますか？", "Room Studioの収集機能で、テイスト欄に「北欧」と入れて家具を集められます。集めた家具を部屋の写真に置き、色や素材を調整しながら雰囲気を試せます。"),
        ],
        "related": ["hitorigurashi-sofa", "6jo-hitorigurashi-layout", "chintai-kabe-makeover"],
        "cta": "北欧の部屋づくりを試す",
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
        f"<section><h2>{esc(h)}</h2><p>{esc(body)}</p></section>"
        for h, body in p["sections"])
    # FAQ block + FAQPage structured data (only when the LP defines questions).
    faq = p.get("faq") or []
    faq_html = faq_jsonld = ""
    if faq:
        items = "\n".join(
            f'<section class="faq"><h3>{esc(q)}</h3><p>{esc(a)}</p></section>'
            for q, a in faq)
        faq_html = f'<h2 class="faq-h">よくある質問</h2>\n{items}'
        faq_jsonld = '<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq],
        }, ensure_ascii=False) + "</script>"
    # Internal links to related LPs (anchor text = each target's H1).
    related = [s for s in (p.get("related") or []) if s in _LP_BY_SLUG]
    rel_html = ""
    if related:
        links = "\n".join(
            f'<li><a href="/lp/{s}">{esc(_LP_BY_SLUG[s]["h1"])}</a></li>' for s in related)
        rel_html = f'<section class="related"><h2>関連ページ</h2>\n<ul>\n{links}\n</ul></section>'
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
<script type="application/ld+json">{jsonld}</script>{faq_jsonld}{ga4}
<style>
  body{{margin:0;background:#FBFAF8;color:#2A2824;font-family:"Zen Kaku Gothic New",system-ui,sans-serif;line-height:1.8}}
  .wrap{{max-width:760px;margin:0 auto;padding:40px 20px 72px}}
  a{{color:#3B6FE0}}
  h1{{font-size:24px;margin:0 0 10px;line-height:1.4}}
  .lead{{font-size:15px;color:#57534c;margin:0 0 8px}}
  .pr{{font-size:12px;color:#7C776E;margin:0 0 28px}}
  section{{border-top:1px solid rgba(0,0,0,.1);padding:20px 0}}
  h2{{font-size:16px;margin:0 0 8px}}
  h3{{font-size:14.5px;margin:0 0 6px;font-weight:700}}
  p{{margin:0;font-size:14px;color:#3f3b36}}
  .faq-h{{margin-top:8px}}
  .faq{{padding:16px 0}}
  .related{{border-top:1px solid rgba(0,0,0,.1);padding-top:18px}}
  .related ul{{margin:8px 0 0;padding-left:1.1em}}
  .related li{{font-size:14px;margin:5px 0}}
  .cta{{display:block;text-align:center;margin:28px 0 8px;padding:15px 20px;background:#2A2824;color:#FBFAF8;
        text-decoration:none;border-radius:10px;font-weight:700;font-size:15px}}
  nav{{margin-top:32px;font-size:12px;display:flex;gap:14px;flex-wrap:wrap;color:#7C776E}}
</style></head><body><div class="wrap">
<h1>{esc(p['h1'])}</h1>
<p class="lead">{esc(p['lead'])}</p>
<p class="pr">{esc(_PR_LINE)}</p>
{sections}
{faq_html}
<a class="cta" href="{esc(app_url)}">{esc(p['cta'])} →</a>
{rel_html}
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
