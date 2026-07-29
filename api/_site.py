# -*- coding: utf-8 -*-
"""Room Studio — site-level concerns (standard library only).

- log_track(event): append-only click/impression logging (stdout; captured by Vercel logs).
- legal_html(kind): operator info / privacy / 特商法 static pages (placeholders to fill in).

Shared by server.py (local) and api/index.py (Vercel). No third-party imports.
Operator details are read from env so they can be set per-deployment without code edits.
"""

import os
import re
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
# faq=[(q, a)] (→ FAQPage JSON-LD), `eyebrow` the small mono label above the H1.
# Only one LP is published today; the template and the renderer stay plural-safe, so
# adding another dict here is all it takes. Two keys only matter with 2+ pages:
# related=[slug] (→ internal links) and `anchor`, which overrides the link text other
# LPs use for this page — an H1 that leads with a pain reads badly in a link list, so
# the anchor keeps the search-intent wording of the title.
# Keep copy honest: general interior guidance + the app's real features; avoid
# fabricated statistics or hard product claims (hedge where it depends).
# The CTA links to the app at /?ref=lp-<slug> (attribution via GA4 page_location;
# no app-side change needed). Deep-linking into a preset collection is a future
# enhancement (the app has no preset query params today — see STEP0_REPORT.md).
# =============================================================================
LANDING_PAGES = [
    {
        "slug": "moyougae-simulation",
        "title": "模様替えシミュレーション：自分の部屋の写真で試す",
        "desc": "模様替えは、やってみるまで仕上がりが分からないもの。Room Studioなら自分の部屋の写真に家具を置き、床や壁の色や素材まで変えて、部屋に合うかを無料で試せます。登録もインストールも不要です。",
        "eyebrow": "集めた画像 / 自分の部屋",
        "h1": "集めた画像は、自分の部屋じゃない",
        "lead": "光の入り方も、間取りも、もとの床の色も違う。だから「自分の部屋だとどう見えるか」は、自分の部屋の写真の上でしか分かりません。憧れの雰囲気に近づけるかどうかも、家具や床・壁ごと変えて先に試せます。",
        # The hero sits ON the image now, so its copy is cut to two sentences. The
        # full `lead` above is kept because section 01 covers the same ground in
        # depth — nothing is lost from the page, only from the first screen.
        "hero_lead": "いいなと思って集めた画像は、どれも他人の部屋。自分の部屋だとどう見えるかは、自分の部屋の写真の上でしか分かりません。",
        "sections": [
            ("集めた画像は、自分の部屋ではない", "画像を集めていくと、好きな色や素材の傾向は見えてきます。でも、そこから先が難しい。集めた画像はどれも他人の部屋で、窓の位置も光の入り方も、もとの床や壁の色も違うからです。同じ色のソファでも、床が濃い部屋と明るい部屋では見え方が変わります。答えが出る場所は、集めた画像の側ではなく、自分の部屋の写真の上です。"),
            ("自分の部屋の写真の上で、確かめる", "スマホで撮った部屋の写真をそのまま読み込めます。壁や床は面を選んで色や素材を変えられるので、「床を明るい木目にしたら」「壁をグレーに寄せたら」を、いまの光と間取りのまま見比べられます。家具はテイスト欄に好きな言葉を入れて集め、置いたあとに大きさや向き、色や素材を調整できます。ラグやカーテン、照明も同じように集められます。"),
            ("目指したいテイストを決めて、寄せていく", "たとえば北欧テイストなら、明るい木の質感と白やグレーのベースに、差し色を少しだけ効かせるのが定番です。ナチュラルなら生成りや麻の素材感を、インダストリアルなら黒や金属を効かせる、というようにテイストごとの定石があります。ただ、同じ組み合わせでも部屋の光やもとの床の色が違えば見え方は変わります。テイスト欄は自由記述なので、目指したい言葉をそのまま入れて家具を集め、床を明るい木目に、壁を白やグレーに、といった調整と合わせて自分の部屋で確かめてみてください。"),
        ],
        "faq": [
            ("集めた画像のイメージを、自分の部屋で確かめる方法はありますか？", "自分の部屋の写真の上で試してみるのがおすすめです。集めた画像は他人の部屋なので、光の入り方も間取りも、もとの床や壁の色も違います。Room Studioなら、部屋の写真で床や壁、家具の色や素材を変えて見比べられるので、どの方向が自分の部屋に合うかを判断しやすくなります。"),
            ("好きなテイストに合わせて、色はどうまとめればいいですか？", "明るいベースに素材の質感を合わせ、差し色を少しだけ効かせるのが基本です。北欧なら白やグレーに木の質感、ナチュラルなら生成りや麻、といったようにテイストごとの定石があります。ただ同じ色でも部屋によって見え方が変わるので、実際の部屋の写真で床や壁の色を変え、収集機能のテイスト欄に目指したい言葉を入れて集めた家具を置いて確かめると、近づけやすくなります。"),
            ("片付いていない部屋の写真でも試せますか？", "はい。写り込んだ気になるものは消してから試せるので、片付けきれていない部屋の写真のままで大丈夫です。登録もアプリのインストールも不要、無料でブラウザからそのまま使えます。部屋の写真は原則としてお使いの端末の中で処理されます。"),
        ],
        "hero": {"alt": "木の質感のある明るいリビングのイメージ",
                 "note": "画像が入ります：明るい木の質感の無人リビング（横長・人物やブランドの写り込みなし）"},
        # Shows labelled placeholder boxes for the before/after slots while the operator
        # prepares the captures. Drop this key to hide the block until both files exist.
        "ph": True,
        "ba": {"heading": "床と壁の色を変える前と、後", "label_b": "Before", "label_a": "After",
               "note_b": "編集前：ふつうの部屋", "note_a": "編集後：床と壁の色と素材を変えた同じ部屋",
               "ph_b": "Before画像が入ります／家具の少ないプレーンな部屋",
               "ph_a": "After画像が入ります／同じ部屋をRoom Studioで床・壁だけ加工",
               "alt_b": "Room Studioで床と壁の色を変える前の部屋",
               "alt_a": "Room Studioで床と壁の色と素材を変えた後の部屋",
               "cap": "Room Studioで同じ部屋の床と壁だけを変えた例（Before → After）"},
        "cta": "自分の部屋で試す",
    },
]

_LP_BY_SLUG = {p["slug"]: p for p in LANDING_PAGES}

# URLs retired on 2026-07-28. They were public and indexed, so they 301 to the live
# page instead of 404-ing — the accumulated ranking signal and any inbound links or
# bookmarks carry over. Never re-use one of these keys as a live slug.
#
# Every entry points at the CURRENT slug, never at another retired one: when the LP
# was renamed hokuo-interior → moyougae-simulation the three older slugs were
# repointed too, so each is a single 301 rather than a 301→301 chain. Keep it that
# way on the next rename — repoint all of these, do not add a new hop.
LP_REDIRECTS = {
    "hokuo-interior": "moyougae-simulation",
    "6jo-hitorigurashi-layout": "moyougae-simulation",
    "hitorigurashi-sofa": "moyougae-simulation",
    "chintai-kabe-makeover": "moyougae-simulation",
}


def landing_redirect(slug):
    """Path to 301 a retired LP slug to, or None when there is nothing to redirect.

    Guards against a redirect loop: a slug that is still live, or one pointing at a
    target that no longer exists (or at itself), returns None so the caller 404s."""
    if slug in _LP_BY_SLUG:
        return None
    target = LP_REDIRECTS.get(slug)
    if not target or target == slug or target not in _LP_BY_SLUG:
        return None
    return "/lp/" + target


def landing_slugs():
    """All landing-page slugs (sitemap uses this)."""
    return [p["slug"] for p in LANDING_PAGES]


def _phrase(text):
    """Escape a heading, wrapping each 読点-delimited phrase in an inline-block span.

    Japanese lines may break between any two characters, so a narrow column happily
    splits 「北欧インテリア」 into 「北欧イン/テリア」. An inline-block is shrink-to-fit,
    so the browser prefers to break BETWEEN the phrases; a phrase wider than the line
    still wraps inside its own box, which means this can never cause overflow.
    (`word-break:auto-phrase` in the stylesheet does the same job on engines that
    implement it — this is the part that works everywhere.) Text content is unchanged,
    so headings still read identically to crawlers."""
    esc = _html.escape
    parts = [p + "、" for p in text.split("、")]
    parts[-1] = parts[-1][:-1]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return esc(text)
    return "".join(f"<span>{esc(p)}</span>" for p in parts)


def _img(name, alt, cls, w, h, eager=False):
    """A filled image slot (the operator has dropped a file in /lp-assets).
    Space is reserved twice over — the container's aspect-ratio and the intrinsic
    width/height attributes — so neither path can produce layout shift.
    `eager` is for the hero only: it is above the fold, so lazy-loading it would
    delay LCP. Everything below the fold stays lazy."""
    esc = _html.escape
    load = ('loading="eager" fetchpriority="high"' if eager else 'loading="lazy"')
    return (f'<figure class="{("media " + cls).strip()}"><img src="/lp-assets/{esc(name)}" '
            f'alt="{esc(alt)}" width="{w}" height="{h}" {load}></figure>')


def _img_ph(cls, note):
    """An EMPTY image slot, drawn as a labelled placeholder box.

    Only used where the LP opts in via `ph: True` (see landing_html). It reserves
    exactly the same space as the real image, so dropping the file in later cannot
    shift the layout. `aria-hidden` + the surrounding <figure> keep it out of the
    accessibility tree — it is scaffolding, not content."""
    esc = _html.escape
    return (f'<figure class="{("media media-empty " + cls).strip()}" aria-hidden="true">'
            f'<span class="ph-note">{esc(note)}</span></figure>')


def _hero_video(sources, poster_url):
    """A full-bleed ambient hero video (NOT A HOTEL-style), as inline markup.

    Decorative by design: muted, looping, no controls, so it carries atmosphere
    rather than information — hence `aria-hidden`, which keeps a controlless media
    element out of the accessibility tree instead of announcing an unusable player.
    The h1/lead beside it carry the meaning. `poster` is the still hero photo when
    one exists, so the first paint (and the LCP candidate) is an image rather than
    an empty box, and it is also what shows if decoding fails or autoplay is denied.
    `autoplay` is in the markup so it works without JS; the page script pauses it
    when the visitor prefers reduced motion."""
    esc = _html.escape
    poster = f' poster="{esc(poster_url)}"' if poster_url else ""
    srcs = "".join(f'<source src="{esc(src)}" type="{esc(ct)}">' for src, ct in sources)
    return ('<figure class="media media-wide media-video">'
            f'<video autoplay muted loop playsinline preload="metadata"{poster} '
            f'width="1600" height="900" aria-hidden="true" tabindex="-1">{srcs}</video>'
            '</figure>')


def _hero_svg(alt):
    """A calm, clearly-illustrative interior scene as inline SVG (no external file).
    Shown as the hero visual when no free-stock photo is present, so the page reads
    as finished rather than empty and upgrades automatically once a real photo is
    dropped into /lp-assets. Decorative only — it never poses as a real photograph
    or a Room Studio edit (the before/after proof block stays photo-only).

    Drawn in the app's own palette (greige ground, ink line work, one muted accent)
    so a photo-less LP still reads as part of the product rather than as clip-art."""
    label = _html.escape(alt or "部屋のインテリアのイメージイラスト")
    shapes = (
        '<rect width="1600" height="900" fill="#F4F2ED"/>'
        # soft ground / light pool — the only filled masses, kept very close in value
        '<rect y="648" width="1600" height="252" fill="#EFECE5"/>'
        '<circle cx="352" cy="300" r="186" fill="#EAE6DD"/>'
        '<ellipse cx="1010" cy="742" rx="470" ry="34" fill="#E7E3DA"/>'
        # everything below is line work in the app ink colour
        '<g fill="none" stroke="#2A2824" stroke-opacity=".42" stroke-width="4" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M0 648H1600"/>'
        # window (left)
        '<rect x="212" y="158" width="300" height="336" rx="6"/>'
        '<path d="M362 158V494M212 326h300"/>'
        '<path d="M196 512h332"/>'
        # plant (left, on the floor)
        '<path d="M120 648l12-92h72l12 92"/>'
        '<path d="M156 556c-26-30-32-72-14-104M168 556c22-34 24-78 4-110M162 556c0-40 14-72 40-92"/>'
        # framed art (centre)
        '<rect x="688" y="206" width="164" height="204" rx="4"/>'
        '<path d="M706 372l40-58 30 34 34-46 24 68"/>'
        # floor lamp (right)
        '<path d="M1332 348h96l-22-74h-52z"/>'
        '<path d="M1380 348v300"/><path d="M1344 648h72"/>'
        # sofa (centre)
        '<path d="M782 566v-64a22 22 0 0 1 22-22h404a22 22 0 0 1 22 22v64"/>'
        '<rect x="748" y="566" width="524" height="112" rx="20"/>'
        '<path d="M782 678v40M1238 678v40"/>'
        '<path d="M1010 566v112"/>'
        # low table
        '<rect x="600" y="612" width="150" height="16" rx="6"/>'
        '<path d="M618 628v34M732 628v34"/>'
        '</g>'
        # single muted accent: the light from the window
        '<circle cx="352" cy="300" r="52" fill="#2A2824" fill-opacity=".07"/>'
    )
    return ('<figure class="media media-illus">'
            '<svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" '
            'role="img" aria-label="' + label + '" xmlns="http://www.w3.org/2000/svg">'
            + shapes + '</svg></figure>')


# "How it works" steps, held apart from the page copy so every LP shares one wording.
# Copy is honest: no login/install on the public web app; edits happen on the photo;
# product links go to the ECs. Rendered as mono-numbered rows (no icons) to match
# the app's own chrome.
_STEPS = [
    ("01", "部屋の写真を読み込む",
     "スマホで撮った写真をそのまま。会員登録もインストールもいりません。"),
    ("02", "置いて、色と素材を変える",
     "家具の配置も、壁・床の色や質感も、写真の上でその場で変えられます。"),
    ("03", "見比べて、リンクへ",
     "変える前と後を並べて見比べ、しっくりきたら商品リンクから詳細へ。"),
]


def _steps_html():
    """Render the shared 3-step 'how it works' section."""
    esc = _html.escape
    items = "\n".join(
        f'<div class="step rv"><span class="idx">{esc(no)}</span>'
        f'<h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for no, t, b in _STEPS)
    return ('<section class="sec"><div class="wrap"><div class="grid2">'
            '<div class="col-h"><span class="idx">HOW IT WORKS</span><h2>使い方は、3ステップ</h2></div>'
            f'<div class="steps">\n{items}\n</div>'
            '</div></div></section>')


# "What you can do" capability cards, shared by every LP. Each line maps to a
# real app feature described in the LP copy — placing furniture, changing colour /
# material, editing walls & floors, dropping in cut-out photos of owned furniture,
# collecting by taste, and the product links. No fabricated features or claims.
_FEATURES = [
    ("家具を置く", "気になる家具を部屋の写真に置き、大きさや向きを整えられます。"),
    ("色と素材を変える", "家具の色や素材をその場で切り替え、部屋に馴染む組み合わせを探せます。"),
    ("壁・床を変える", "壁だけ・床だけを選んで、色や質感を変えた仕上がりを試せます。"),
    ("手持ちの家具も置く", "いま使っている家具を撮って背景を切り抜き、模様替え後の部屋に並べられます。"),
    ("テイストで集める", "「北欧」などのテイストで家具を集めて、まとめて置いて試せます。"),
    ("商品リンクで詳細へ", "しっくりくる組み合わせが見つかったら、商品リンクから詳細を確認できます。"),
]


def _features_html():
    """Render the shared 'what you can do' capability grid.
    A hairline lattice (1px grid gaps over a rule-coloured background) rather than
    six bordered cards — the same flat treatment the rest of the page uses."""
    esc = _html.escape
    cards = "\n".join(
        f'<div class="feat-card"><span class="idx">{i:02d}</span>'
        f'<h3>{esc(t)}</h3><p>{esc(b)}</p></div>'
        for i, (t, b) in enumerate(_FEATURES, 1))
    return ('<section class="sec"><div class="wrap">'
            '<div class="sec-h rv"><span class="idx">FEATURES</span>'
            '<h2>写真の上で、模様替えをまるごと</h2></div>'
            f'<div class="feat-grid rv">\n{cards}\n</div></div></section>')


def landing_html(slug, assets_dir=None):
    """Render a single landing page, or None if the slug is unknown.
    `assets_dir` (the /lp-assets directory): image slots render only for files that
    exist there — missing images are omitted cleanly rather than shown as empty
    boxes, so the page reads as intentional before the operator adds photos."""
    p = _LP_BY_SLUG.get(slug)
    if not p:
        return None
    def _has(nm):
        return bool(assets_dir) and _lp_asset_path(assets_dir, nm) is not None
    esc = _html.escape
    url = f"{SITE_BASE_URL}/lp/{slug}"
    app_url = f"/?ref=lp-{slug}"
    ga4 = ga4_head_snippet()
    # Body sections: editorial two-column blocks, numbered 01.. in a mono index.
    # The first sits directly under the hero; the rest follow the before/after visual.
    secs = p["sections"]

    def _block(i, h, b):
        return ('<section class="sec"><div class="wrap"><div class="grid2 rv">'
                f'<div class="col-h"><span class="idx">{i:02d}</span><h2>{_phrase(h)}</h2></div>'
                f'<div class="col-b"><p>{esc(b)}</p></div>'
                '</div></div></section>')
    sec0 = "".join(_block(i, h, b) for i, (h, b) in enumerate(secs[:1], 1))
    sec_rest = "\n".join(_block(i, h, b) for i, (h, b) in enumerate(secs[1:], 2))
    # Hero photo (free-stock room, slot A) + before/after app captures (slot B).
    # `ph` opts an LP into showing labelled placeholder boxes while slot B is still
    # empty; without it the block stays hidden until both captures exist.
    show_ph = bool(p.get("ph"))
    hero = p.get("hero") or {}
    hero_alt = hero.get("alt", "")
    # Hero visual, best available first: an ambient video, else a real free-stock
    # photo, else a calm inline SVG illustration so it is never empty. Each tier
    # upgrades automatically as the operator drops files into /lp-assets.
    # The hero is above the fold, hence eager.
    hero_vid = [(f"/lp-assets/{slug}-hero{ext}", ct) for ext, ct in _LP_VIDEO_CT.items()
                if _lp_asset_path(assets_dir, f"{slug}-hero{ext}", _LP_VIDEO_CT)
                ] if assets_dir else []
    if hero_vid:
        hero_fig = _hero_video(hero_vid, f"/lp-assets/{slug}-hero" if _has(f"{slug}-hero") else "")
    elif _has(f"{slug}-hero"):
        hero_fig = _img(f"{slug}-hero", hero_alt, "media-fill", 2400, 1350, eager=True)
    else:
        hero_fig = _hero_svg(hero_alt)
    # The hero is now full-bleed with the copy sitting ON the media, so it always
    # carries a scrim. The scrim is not decorative polish — white text over an
    # unknown photo is unreadable without it (see .hero-scrim for the contrast
    # budget), and it is applied on the illustration fallback too.
    hero_media = (f'<div class="hero-media">{hero_fig}</div>'
                  '<div class="hero-scrim" aria-hidden="true"></div>')
    steps_html = _steps_html()
    feat_html = _features_html()
    ba = p.get("ba")
    ba_html = ""
    # The signature visual of the LP: Before = a plain room the operator supplies,
    # After = that SAME room actually edited in Room Studio and screenshotted. The
    # After image must be real product output — never a stock photo or a mockup —
    # because the whole block exists to prove the feature does what the page claims.
    if ba and (show_ph or (_has(f"{slug}-before") and _has(f"{slug}-after"))):
        both = _has(f"{slug}-before") and _has(f"{slug}-after")

        def _side(role, alt, note, label, cls):
            fig = (_img(f"{slug}-{role}", alt, "", 1600, 900) if _has(f"{slug}-{role}")
                   else _img_ph("", note))
            return (f'<div class="cmp-side {cls}">{fig}'
                    f'<span class="cmp-tag">{esc(label)}</span></div>')
        sides = (_side("before", ba["alt_b"], ba.get("ph_b", ""), ba["label_b"], "b")
                 + _side("after", ba["alt_a"], ba.get("ph_a", ""), ba["label_a"], "a"))
        if both:
            # Both captures exist → a draggable comparison. The range input carries the
            # whole interaction, so it is keyboard-operable for free; without JS the CSS
            # falls back to the plain two-up grid below (no --x is ever applied).
            aria = f'{ba["label_b"]}と{ba["label_a"]}の表示位置'
            cmp_html = (
                f'<div class="cmp" data-cmp style="--x:50%">{sides}'
                '<input class="cmp-range" type="range" min="0" max="100" value="50" step="0.1" '
                f'aria-label="{esc(aria)}">'
                '<span class="cmp-bar" aria-hidden="true"><span class="cmp-knob"></span></span>'
                '</div>'
                '<p class="cmp-hint">ハンドルを左右に動かすと見比べられます。</p>')
        else:
            cmp_html = (f'<div class="cmp cmp-static">{sides}</div>'
                        f'<p class="cmp-hint">{esc(ba["note_b"])}／{esc(ba["note_a"])}</p>')
        ba_html = (
            # A live before/after becomes a full-bleed band, so the page reads
            # text → big image → text. While the captures are still placeholders it
            # stays inside .wrap: a dashed empty box spanning the viewport would read
            # as a broken page rather than as scaffolding.
            f'<section class="sec sec-ba {"is-live" if both else "is-ph"}"><div class="wrap">'
            f'<div class="sec-h rv"><span class="idx">BEFORE / AFTER</span>'
            f'<h2>{_phrase(ba["heading"])}</h2></div>\n<div class="rv">{cmp_html}</div>\n'
            f'<p class="cap">{esc(ba["cap"])}</p></div></section>')
    # FAQ block (styled as cards) + FAQPage structured data (unchanged content).
    faq = p.get("faq") or []
    faq_html = faq_jsonld = ""
    if faq:
        items = "\n".join(
            f'<div class="faq rv"><h3>{_phrase(q)}</h3><p>{esc(a)}</p></div>' for q, a in faq)
        faq_html = ('<section class="sec"><div class="wrap">'
                    '<div class="sec-h rv"><span class="idx">FAQ</span>'
                    f'<h2>よくある質問</h2></div>\n<div class="faq-list">{items}</div>'
                    '</div></section>')
        faq_jsonld = '<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq],
        }, ensure_ascii=False) + "</script>"
    # Internal links to related LPs, as cards. Anchor text = the target's H1, unless it
    # defines `anchor` — an LP whose H1 leads with a pain rather than its search intent
    # reads better in a link list under the wording of its title.
    related = [s for s in (p.get("related") or []) if s in _LP_BY_SLUG]
    rel_html = ""
    if related:
        def _anchor(s):
            t = _LP_BY_SLUG[s]
            return t.get("anchor") or t["h1"]
        cards = "\n".join(
            f'<a class="rel-a rv" href="/lp/{s}"><span>{esc(_anchor(s))}</span>'
            '<span class="arw">→</span></a>' for s in related)
        rel_html = ('<section class="sec"><div class="wrap">'
                    '<div class="sec-h rv"><span class="idx">MORE</span>'
                    f'<h2>関連ページ</h2></div>\n<div class="rel-list">\n{cards}\n</div>'
                    '</div></section>')
    cta = esc(p["cta"])
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
<script>document.documentElement.className+=" js";</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  /* Tokens are the app's own (room-studio.html :root) so the LP and the editor read
     as one product: greige ground, ink type, hairline rules, one blue accent. */
  :root{{--bg:#FBFAF8;--sub:#F4F2ED;--ink:#2A2824;--muted:#7C776E;--faint:#A49E94;
    --line:rgba(0,0,0,.10);--hair:rgba(0,0,0,.07);--accent:#3B6FE0;--r:4px}}
  *{{box-sizing:border-box}}
  html{{-webkit-text-size-adjust:100%}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-size:15px;line-height:1.9;
    font-family:"Zen Kaku Gothic New",system-ui,-apple-system,sans-serif;
    -webkit-font-smoothing:antialiased;font-feature-settings:"palt" 1}}
  img{{max-width:100%;display:block}}
  a{{color:inherit}}
  .wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
  .idx{{display:block;font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10.5px;
    letter-spacing:.2em;color:var(--faint);margin:0 0 14px}}
  /* auto-phrase keeps Japanese headings from breaking mid-word (「北欧イン/テリア」);
     browsers without it fall back to the normal break rules. Deliberately no
     overflow-wrap here — it re-enables break-anywhere and cancels auto-phrase. */
  h1,h2,h3{{letter-spacing:.01em;word-break:auto-phrase}}
  /* phrase spans from _phrase(): shrink-to-fit boxes, so a line prefers to break
     between them and only wraps inside one when the phrase alone is too wide. */
  h1>span,h2>span,h3>span{{display:inline-block}}
  h2{{font-size:clamp(20px,2.6vw,28px);font-weight:900;line-height:1.6;margin:0}}
  /* sticky bar */
  .bar{{position:sticky;top:0;z-index:50;background:rgba(251,250,248,.85);
    backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);
    border-bottom:1px solid var(--hair)}}
  .bar-in{{display:flex;align-items:center;gap:14px;height:58px}}
  .brand{{margin-right:auto;display:flex;align-items:baseline;gap:10px;text-decoration:none}}
  .brand .mark{{font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:700;font-size:14px;
    letter-spacing:.02em;white-space:nowrap}}
  .brand .mark b{{background:var(--ink);color:var(--bg);padding:2px 6px;border-radius:3px}}
  .brand .tag{{font-size:11.5px;color:var(--muted);white-space:nowrap}}
  /* buttons */
  .btn{{display:inline-flex;align-items:center;gap:12px;background:var(--ink);color:var(--bg);
    text-decoration:none;font-weight:700;font-size:15px;letter-spacing:.03em;padding:17px 32px;
    border-radius:var(--r);white-space:nowrap;transition:opacity .2s ease,transform .2s ease}}
  .btn:hover{{opacity:.85;transform:translateY(-1px)}}
  .btn .ar{{font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:400;font-size:13px}}
  .btn.sm{{font-size:12.5px;padding:9px 16px;gap:8px}}
  .cta-row{{display:flex;align-items:center;gap:20px;flex-wrap:wrap}}
  .cta-note{{font-size:12px;color:var(--faint);letter-spacing:.03em}}
  /* ---- hero: full-bleed media with the copy sitting on top ------------------
     78vh sits in the middle of the 70–85vh band. It is deliberately NOT 100vh:
     the next section has to peek above the fold, otherwise a full-screen hero
     reads as the whole page and people leave. max-height keeps it sane on tall
     desktop monitors; svh (with a vh fallback) stops iOS from jumping when the
     URL bar collapses. */
  .hero{{position:relative;display:flex;flex-direction:column;justify-content:flex-end;
    isolation:isolate;overflow:hidden;min-height:78vh;min-height:78svh;max-height:900px;
    padding:0 0 clamp(56px,8vh,96px)}}
  .hero-media{{position:absolute;inset:0;z-index:0}}
  .hero-media .media{{position:absolute;inset:0;aspect-ratio:auto;height:100%}}
  /* Contrast budget: the copy is white over an image we do not control, so the
     scrim is sized for the worst case — a pure-white photo. Under the text the
     scrim is >=.62, i.e. 255*0.38 = 97 -> about 6.2:1 against white, clearing
     WCAG AA (4.5:1) for the 15px lead as well as the h1. On the illustration
     fallback (#F4F2ED) the same scrim gives roughly 9.7:1. */
  .hero-scrim{{position:absolute;inset:0;z-index:1;pointer-events:none;
    background:linear-gradient(90deg,rgba(18,16,14,.78) 0%,rgba(18,16,14,.66) 30%,
      rgba(18,16,14,.42) 55%,rgba(18,16,14,.16) 80%,rgba(18,16,14,.06) 100%)}}
  .hero-in{{position:relative;z-index:2;color:#fff}}
  .hero .eyebrow{{color:rgba(255,255,255,.72)}}
  .hero h1{{color:#fff;text-wrap:balance}}
  .hero .lead{{color:rgba(255,255,255,.88)}}
  .hero .cta-note{{color:rgba(255,255,255,.66)}}
  .hero .btn{{background:#fff;color:var(--ink)}}
  .hero .btn:hover{{opacity:1;background:rgba(255,255,255,.88)}}
  .eyebrow{{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.22em;
    color:var(--faint);margin:0 0 clamp(20px,3vw,30px)}}
  h1{{font-size:clamp(30px,6.2vw,68px);font-weight:900;line-height:1.34;letter-spacing:.035em;
    max-width:16em;margin:0 0 clamp(22px,3vw,32px)}}
  .lead{{font-size:clamp(14.5px,1.5vw,16.5px);color:var(--muted);line-height:2.05;max-width:32em;
    margin:0 0 clamp(28px,4vw,42px)}}
  /* scroll cue: a plain link, so it is keyboard reachable and focusable */
  .cue{{position:absolute;z-index:2;left:50%;bottom:18px;transform:translateX(-50%);
    width:44px;height:44px;display:grid;place-items:center;border-radius:50%;
    text-decoration:none;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.28)}}
  .cue-a{{width:9px;height:9px;border-right:1.6px solid #fff;border-bottom:1.6px solid #fff;
    transform:translateY(-2px) rotate(45deg);animation:cue 2.4s ease-in-out infinite}}
  @keyframes cue{{0%,100%{{transform:translateY(-3px) rotate(45deg)}}50%{{transform:translateY(2px) rotate(45deg)}}}}
  /* media boxes elsewhere on the page */
  .media{{position:relative;margin:0;background:var(--sub);overflow:hidden;display:grid;place-items:center}}
  .media-wide,.media-illus{{aspect-ratio:16/9;max-height:76vh}}
  .media img,.media svg,.media video{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
  /* Empty slot: same box, same greige, only the border turns dashed — it reads as
     scaffolding rather than a broken image, and dropping the file in shifts nothing. */
  .media-empty{{border:1px dashed var(--line)}}
  .ph-note{{font-size:12px;line-height:1.8;color:var(--muted);text-align:center;padding:0 18px;max-width:22em}}
  /* sections */
  .sec{{padding:clamp(72px,10vw,140px) 0;border-top:1px solid var(--hair)}}
  .grid2{{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);
    gap:clamp(20px,5vw,72px);align-items:start}}
  .col-b p{{margin:0;color:#4C4640;font-size:15px;line-height:2.1}}
  .sec-h{{margin:0 0 clamp(28px,4vw,44px)}}
  /* steps */
  .step{{padding:clamp(20px,2.6vw,28px) 0;border-top:1px solid var(--hair)}}
  .step:first-child{{border-top:0;padding-top:0}}
  .step .idx{{margin-bottom:10px}}
  .step h3{{font-size:clamp(16px,1.9vw,19px);font-weight:700;margin:0 0 8px;line-height:1.7}}
  .step p{{margin:0;color:var(--muted);font-size:14px;line-height:1.95}}
  /* features: a hairline lattice, not six bordered cards */
  .feat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;
    background:var(--hair);border:1px solid var(--hair)}}
  .feat-card{{background:var(--bg);padding:clamp(22px,2.6vw,32px)}}
  .feat-card .idx{{margin-bottom:12px}}
  .feat-card h3{{font-size:15.5px;font-weight:700;margin:0 0 7px;line-height:1.7}}
  .feat-card p{{margin:0;color:var(--muted);font-size:13.5px;line-height:1.95}}
  /* A live before/after breaks out of .wrap to a full-bleed band, giving the page
     a text -> big image -> text rhythm. 100vw + the negative margin trick, with
     no horizontal scrollbar because the body never overflows. */
  .sec-ba.is-live > .wrap{{max-width:none;padding:0}}
  /* Height is set explicitly: at full width a 4/3 (or 16/9) aspect-ratio box would
     be over 1000px tall and swallow the screen. A capped band keeps it cinematic. */
  .sec-ba.is-live .cmp{{max-width:none}}
  .js .sec-ba.is-live .cmp:not(.cmp-static){{max-width:none;aspect-ratio:auto;
    height:min(72vh,700px);border-radius:0}}
  .sec-ba.is-live .sec-h,.sec-ba.is-live .cap,.sec-ba.is-live .cmp-hint{{
    max-width:1080px;margin-left:auto;margin-right:auto;padding:0 24px}}
  /* before/after: two-up by default, a drag comparison once JS is available */
  .cmp{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  .cmp-side{{position:relative}}
  .cmp-side .media{{aspect-ratio:16/9}}
  .cmp-tag{{position:absolute;top:12px;left:12px;z-index:2;background:rgba(42,40,36,.74);
    color:#FBFAF8;border-radius:3px;padding:5px 10px;
    font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10px;letter-spacing:.16em}}
  .cmp-bar,.cmp-range{{display:none}}
  .js .cmp:not(.cmp-static){{display:block;position:relative;aspect-ratio:16/9;max-width:1000px;
    margin:0 auto;overflow:hidden;background:var(--sub);border-radius:var(--r);touch-action:pan-y}}
  .js .cmp:not(.cmp-static) .cmp-side{{position:absolute;inset:0}}
  .js .cmp:not(.cmp-static) .cmp-side .media{{position:absolute;inset:0;aspect-ratio:auto}}
  .js .cmp:not(.cmp-static) .cmp-side.a{{clip-path:inset(0 0 0 var(--x,50%))}}
  .js .cmp:not(.cmp-static) .cmp-side.a .cmp-tag{{left:auto;right:12px}}
  .js .cmp:not(.cmp-static) .cmp-range{{display:block;position:absolute;inset:0;width:100%;height:100%;
    margin:0;padding:0;opacity:0;z-index:4;cursor:ew-resize;background:none;
    -webkit-appearance:none;appearance:none}}
  .cmp-range::-webkit-slider-thumb{{-webkit-appearance:none;width:56px;height:100%;cursor:ew-resize}}
  .cmp-range::-moz-range-thumb{{width:56px;height:100%;border:0;border-radius:0;background:transparent}}
  .js .cmp:not(.cmp-static) .cmp-bar{{display:block;position:absolute;top:0;bottom:0;
    left:var(--x,50%);width:2px;margin-left:-1px;z-index:3;pointer-events:none;
    background:rgba(251,250,248,.92);box-shadow:0 0 0 1px rgba(0,0,0,.10)}}
  .cmp-range:focus-visible ~ .cmp-bar{{background:var(--accent);box-shadow:0 0 0 2px rgba(59,111,224,.4)}}
  .cmp-knob{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:46px;height:46px;
    border-radius:50%;background:var(--bg);box-shadow:0 2px 12px rgba(0,0,0,.22)}}
  .cmp-knob::before{{content:"◀ ▶";position:absolute;inset:0;display:grid;place-items:center;
    font-size:11px;color:var(--ink)}}
  .cmp-hint{{text-align:center;color:var(--faint);font-size:12.5px;margin:16px 0 0}}
  .cap{{text-align:center;color:var(--muted);font-size:13px;margin:clamp(20px,3vw,28px) 0 0}}
  /* faq */
  .faq{{padding:clamp(20px,2.6vw,28px) 0;border-top:1px solid var(--hair);display:grid;
    grid-template-columns:minmax(0,340px) minmax(0,1fr);gap:clamp(12px,5vw,72px)}}
  .faq h3{{font-size:15.5px;font-weight:700;margin:0;line-height:1.8}}
  .faq p{{margin:0;color:var(--muted);font-size:14px;line-height:2}}
  /* related */
  .rel-a{{display:flex;align-items:center;justify-content:space-between;gap:20px;text-decoration:none;
    padding:clamp(20px,2.4vw,26px) 0;border-top:1px solid var(--hair);font-weight:700;
    font-size:clamp(15px,1.8vw,18px);line-height:1.7;transition:padding-left .22s ease,color .22s ease}}
  .rel-a:hover{{padding-left:10px;color:var(--accent)}}
  .rel-a .arw{{flex:0 0 auto;font-family:"JetBrains Mono",ui-monospace,monospace;font-weight:400;
    color:var(--faint)}}
  /* footer */
  .foot h2{{font-size:clamp(22px,3.4vw,38px);max-width:16em;margin:0 0 clamp(26px,4vw,38px)}}
  .pr{{font-size:11.5px;color:var(--faint);line-height:1.8;max-width:44em;margin:clamp(44px,6vw,72px) 0 0}}
  nav.legal{{margin-top:16px;display:flex;gap:18px;flex-wrap:wrap;font-size:12px}}
  nav.legal a{{color:var(--muted);text-decoration:none}}
  nav.legal a:hover{{color:var(--ink);text-decoration:underline}}
  /* mobile dock CTA: slides in once the hero CTA has scrolled away */
  .dock{{position:fixed;left:0;right:0;bottom:0;z-index:60;display:none;
    padding:10px 16px calc(10px + env(safe-area-inset-bottom));background:rgba(251,250,248,.94);
    backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border-top:1px solid var(--hair);
    transform:translateY(130%);transition:transform .3s ease}}
  .dock .btn{{width:100%;justify-content:center;padding:15px 20px}}
  .dock.show{{transform:none}}
  /* scroll reveal (only ever applied when JS is running, so no-JS shows everything) */
  .js .rv{{opacity:0;transform:translateY(18px)}}
  .js .rv.in{{opacity:1;transform:none;
    transition:opacity .8s ease,transform .8s cubic-bezier(.22,.61,.36,1)}}
  a:focus-visible,.btn:focus-visible{{outline:2px solid var(--accent);outline-offset:3px;border-radius:3px}}
  /* The hero sits on a dark scrim, where the blue accent ring is hard to see.
     White keeps the focus indicator visible against the photo. */
  .hero a:focus-visible{{outline-color:#fff}}
  @media (prefers-reduced-motion:reduce){{
    *{{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
    .js .rv{{opacity:1;transform:none}}
    .cue-a{{transform:translateY(-1px) rotate(45deg)}}
  }}
  @media (max-width:860px){{.feat-grid{{grid-template-columns:repeat(2,1fr)}}}}
  @media (max-width:820px){{
    .grid2{{grid-template-columns:1fr;gap:14px}}
    .faq{{grid-template-columns:1fr;gap:8px}}
    /* 狭い幅では帯の高さを固定せず 16:9 のまま出す。高さを固定すると cover で
       左右が大きく切られ、部屋の全体が見えなくなる（before/after は「同じ部屋が
       どう変わったか」を見せるものなので、切り取るより小さく全体を出す方がよい）。 */
    .js .sec-ba.is-live .cmp:not(.cmp-static){{height:auto;aspect-ratio:16/9}}
  }}
  @media (max-width:760px){{.dock{{display:block}}}}
  @media (max-width:680px){{.brand .tag{{display:none}}}}
  @media (max-width:820px){{
    /* the copy spans the full width here, so the scrim has to darken from the
       bottom instead of from the left — same >=.62 under the text. */
    .hero-scrim{{background:linear-gradient(180deg,rgba(18,16,14,.34) 0%,
      rgba(18,16,14,.52) 42%,rgba(18,16,14,.74) 74%,rgba(18,16,14,.84) 100%)}}
    .hero{{min-height:76vh;min-height:76svh;padding-bottom:clamp(64px,10vh,96px)}}
    h1{{letter-spacing:.02em;max-width:none}}
  }}
  @media (max-width:560px){{
    .wrap{{padding:0 20px}}
    .feat-grid{{grid-template-columns:1fr}}
    .cmp{{grid-template-columns:1fr}}
    .btn{{width:100%;justify-content:center}}
    .bar .btn.sm{{width:auto}}
  }}
</style></head><body>
<header class="bar"><div class="wrap bar-in">
<a class="brand" href="{esc(app_url)}"><span class="mark">Room<b>Studio</b></span><span class="tag">部屋の写真で試す模様替え</span></a>
<a class="btn sm" href="{esc(app_url)}">試してみる<span class="ar">→</span></a>
</div></header>
<main>
<section class="hero">
{hero_media}
<div class="wrap hero-in">
<p class="eyebrow">{esc(p.get('eyebrow', SITE_NAME))}</p>
<h1>{_phrase(p['h1'])}</h1>
<p class="lead">{esc(p.get('hero_lead') or p['lead'])}</p>
<div class="cta-row"><a class="btn hero-cta" href="{esc(app_url)}">{cta}<span class="ar">→</span></a>
<span class="cta-note">登録不要</span></div>
</div>
<a class="cue" href="#start" aria-label="下へスクロール"><span class="cue-a" aria-hidden="true"></span></a>
</section>
<span id="start"></span>
{sec0}
{steps_html}
{ba_html}
{sec_rest}
{feat_html}
{faq_html}
{rel_html}
<section class="sec foot"><div class="wrap">
<h2>あなたの部屋の写真で、試してみませんか。</h2>
<div class="cta-row"><a class="btn" href="{esc(app_url)}">{cta}<span class="ar">→</span></a>
<span class="cta-note">登録不要・インストール不要・ブラウザで完結</span></div>
<p class="pr">{esc(_PR_LINE)}</p>
<nav class="legal"><a href="/">アプリを開く</a><a href="/about">運営者情報</a><a href="/privacy">プライバシーポリシー</a><a href="/tokushoho">特商法表記</a></nav>
</div></section>
</main>
<div class="dock"><a class="btn" href="{esc(app_url)}">{cta}<span class="ar">→</span></a></div>
<script>
(function(){{
  var d=document,rm=false;
  try{{rm=matchMedia("(prefers-reduced-motion:reduce)").matches}}catch(e){{}}
  if(rm){{
    // Reduced motion: the ambient hero must not loop. autoplay lives in the markup
    // so it still plays with JS off; here we stop it and fall back to the poster.
    [].forEach.call(d.querySelectorAll("video[autoplay]"),function(v){{
      try{{v.removeAttribute("autoplay");v.pause();v.currentTime=0;}}catch(e){{}}
    }});
  }}
  var rv=[].slice.call(d.querySelectorAll(".rv"));
  if(rm||!("IntersectionObserver" in window)){{
    rv.forEach(function(e){{e.classList.add("in")}});
  }}else{{
    var io=new IntersectionObserver(function(en){{
      en.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add("in");io.unobserve(x.target)}}}});
    }},{{rootMargin:"0px 0px -6% 0px",threshold:.06}});
    rv.forEach(function(e){{io.observe(e)}});
  }}
  [].forEach.call(d.querySelectorAll("[data-cmp]"),function(c){{
    var r=c.querySelector(".cmp-range");if(!r)return;
    var set=function(){{c.style.setProperty("--x",r.value+"%")}};
    r.addEventListener("input",set);set();
  }});
  var dock=d.querySelector(".dock"),hc=d.querySelector(".hero-cta");
  if(dock&&hc&&"IntersectionObserver" in window){{
    new IntersectionObserver(function(en){{
      var e=en[0];
      dock.classList.toggle("show",!e.isIntersecting&&e.boundingClientRect.top<0);
    }},{{threshold:0}}).observe(hc);
  }}
}})();
</script>
</body></html>"""


# =============================================================================
# /try — スマホ30秒ミニ体験（docs/BUZZ_FOUNDATION_INSTRUCTIONS.md §1）
#
# SNSからスマホで来た人に「3秒で表示、30秒で変わる体験」をさせるための超軽量ページ。
# アプリ本体（room-studio.html・319KB）は SAM/LaMa/楽天収集まで一体化しており、
# 読み込むだけで性能目標に届かない。そこで本体には一切触れず、LPと同じ流儀で
# ここに独立した自己完結ページを生成する（ビルド不要・外部依存ゼロ）。
#
# 面の指定は本体のようにブラシ/SAM/ポリゴンで選ばせるのではなく、部屋ごとに
# **正規化ポリゴン座標を固定で持つ**。0..1 の相対座標なので写真の実寸に依存せず、
# 写真が確定したら座標だけ差し替えればよい。マスク画像を配信するより軽く、
# 運営が用意するのは写真1枚で済む。
#
# 再着色は本体 rebuildSurface() の移植ではなく最小の再実装。元ピクセルの明度を
# 保ったまま色相・彩度だけ差し替える方式で、質感（木目・陰影）が残る。
# =============================================================================

# 壁・床のスウォッチ。1色目は必ず「元のまま」。色数を絞るのは操作を迷わせないため。
TRY_WALL_COLORS = [
    ("元のまま", ""),
    ("生成り", "#EFE9DF"),
    ("グレージュ", "#D6CEC2"),
    ("淡いグリーン", "#C7D3C6"),
    ("ブルーグレー", "#C4CED7"),
    ("チャコール", "#6E6A64"),
]
TRY_FLOOR_COLORS = [
    ("元のまま", ""),
    ("明るい木", "#DCC29B"),
    ("ナチュラル", "#C6A67E"),
    ("ウォルナット", "#8A6A4E"),
    ("グレー木目", "#B5AFA6"),
]

# サンプル部屋。`img` のファイルが lp-assets/ にあればそれを、無ければ簡易SVG相当の
# プレースホルダをキャンバスに描く（どちらでも再着色の経路は同一）。
# poly は 0..1 の正規化座標。**窓やドアは避けて定義する**（囲むと一緒に着色されるため）。
# `walls` は面ごとのポリゴンの配列（左・正面・右など）。1枚の平面しか無い部屋なら1要素でよい。
# **天井は含めない**（理由は docs/BUZZ_FOUNDATION_PLAN.md）。
# 座標は 0..1 の正規化。実写真に差し替えるときは、この座標だけ写真に合わせて引き直す。
#
# 座標は try-room-1（白壁3面＋オーク床の空室・1100x733）から実測して定義した。
# 壁/床の境界は「下向きに走査して暖色（木床）になる最初の行」を列ごとに拾って直線を当て、
# 壁/天井の境界は白同士で目視できないためコントラストを伸ばして稜線を読み取っている。
# 奥壁は窓を避けるため「窓の左・窓の上・窓の右」の3枚に割っている（1枚の多角形に穴を
# 開ける代わり。walls が配列なので素直に表現できる）。
TRY_ROOM = {
    "img": "try-room-1",
    "walls": [
        # 左壁: 天井稜線 (0,0.115)→(0.25,0.245)、床線 (0,0.784)→(0.25,0.633)
        [[0.000, 0.115], [0.250, 0.245], [0.250, 0.633], [0.000, 0.784]],
        # 奥壁・窓の左
        [[0.250, 0.245], [0.412, 0.243], [0.412, 0.620], [0.300, 0.623], [0.250, 0.633]],
        # 奥壁・窓の上（窓の開口 x0.412-0.578 / y0.293-0.607 を避ける）
        [[0.412, 0.243], [0.578, 0.242], [0.578, 0.293], [0.412, 0.293]],
        # 奥壁・窓の右（x0.665 付近に入隅があり床線が一段下がる）
        [[0.578, 0.242], [0.755, 0.232], [0.755, 0.649], [0.680, 0.643],
         [0.665, 0.623], [0.650, 0.618], [0.578, 0.619]],
        # 右壁: 天井稜線 (0.755,0.232)→(1,0.075)、床線 (0.755,0.649)→(1,0.816)
        [[0.755, 0.232], [1.000, 0.075], [1.000, 0.816], [0.755, 0.649]],
    ],
    "floor": [[0.000, 0.784], [0.250, 0.633], [0.300, 0.623], [0.650, 0.618],
              [0.665, 0.623], [0.680, 0.643], [0.755, 0.649], [1.000, 0.816],
              [1.000, 1.000], [0.000, 1.000]],
    # 家具プレースホルダの配置（正規化）。実画像 try-furni-1 があればそれを描く。
    # 奥壁の手前・床の上に収まる位置。
    "furni": [0.32, 0.595, 0.36, 0.195],
}

# 収益接点。楽天の商品は実行時にAPIで取るものでURLを固定できないため、既定は空。
# 運営が実在の商品を1〜2件ここに入れるとブロックが出る（空ならセクションごと非表示）。
# 形式: {"title": ..., "url": <アフィリエイトURL>, "shop": ...}
TRY_PRODUCTS = []


ROOM_ENGINE_JS = r"""/* /try と /demo が共有する部屋の描画エンジン。
   ページ側は RS.init() で初期化し、setColor/setFurni/setBefore を叩くだけ。
   ここに UI も計測も持たせない（/try はスウォッチ、/demo はタイムラインが叩く）。 */
window.RS=(function(){
  var cv, ctx;
  var W, H;
  var base;
  var bx;
  var groups={}, state={wall:'',floor:'',furni:false,before:false}, furniImg=null, CFG, onReady;

  function ev(name,params){ try{ if(window.gtag) window.gtag('event',name,params||{}); }catch(e){} }

  /* --- 素の部屋を描く。写真があればそれを cover で敷き、無ければプレースホルダの
     部屋を描く。どちらでも以降の再着色の経路は同一なので、写真が来たら差し替わるだけ。 --- */
  function fill(c,poly,style){
    c.beginPath();
    poly.forEach(function(p,i){ var x=p[0]*W, y=p[1]*H; if(i) c.lineTo(x,y); else c.moveTo(x,y); });
    c.closePath(); c.fillStyle=style; c.fill();
  }
  /* 実写真が来るまでのプレースホルダ。一点透視で左・正面・右の壁と床を描き、
     3面に**わざと違う明るさ**を与える（正面が最も明るく、左が最も暗い）。
     再着色後もこの明暗差が残ることが、面ごとの光を潰していない証拠になる。
     天井は描くが着色対象のポリゴンには入れない＝除外の挙動もここで確認できる。 */
  function drawPlaceholder(c){
    fill(c,[[0,0],[0.22,0.10],[0.78,0.10],[1,0]],'#F3F1ED');   // 天井（着色対象外）
    fill(c,CFG.walls[0],'#D8D2C8');                            // 左壁（暗め）
    fill(c,CFG.walls[1],'#EAE6DE');                            // 正面壁（明るい）
    fill(c,CFG.walls[2],'#E0DAD1');                            // 右壁（中間）
    fill(c,CFG.floor,'#CDBFA8');                               // 床
    var hz=0.62*H, fg=c.createLinearGradient(0,hz,0,H);        // 奥ほど暗い＝明暗差
    fg.addColorStop(0,'rgba(0,0,0,.18)'); fg.addColorStop(1,'rgba(255,255,255,.10)');
    c.save(); c.beginPath();
    CFG.floor.forEach(function(p,i){ var x=p[0]*W, y=p[1]*H; if(i) c.lineTo(x,y); else c.moveTo(x,y); });
    c.closePath(); c.clip(); c.fillStyle=fg; c.fillRect(0,hz,W,H-hz);
    for(var i=0;i<20;i++){ c.fillStyle='rgba(0,0,0,.05)'; c.fillRect(0,hz+((H-hz)/20)*i,W,1); }
    c.restore();
  }
  /* 窓・巾木は面の「上」に描く。壁ポリゴンに含めると一緒に着色されてしまうため、
     実写真を使うときも同じ理由でポリゴンは窓やドアを避けて定義する。 */
  function drawFg(c){
    if(CFG.img) return;                            // 実写真のときは前景を描かない
    c.fillStyle='#F8F6F2'; c.fillRect(W*0.28,H*0.18,W*0.20,H*0.28);
    c.strokeStyle='rgba(42,40,36,.32)'; c.lineWidth=3;
    c.strokeRect(W*0.28,H*0.18,W*0.20,H*0.28);
    c.beginPath(); c.moveTo(W*0.38,H*0.18); c.lineTo(W*0.38,H*0.46); c.stroke();
    c.fillStyle='rgba(42,40,36,.14)'; c.fillRect(W*0.22,H*0.62-5,W*0.56,5);
  }
  function drawFurni(c){
    if(furniImg){
      c.drawImage(furniImg, CFG.frect[0]*W, CFG.frect[1]*H, CFG.frect[2]*W, CFG.frect[3]*H);
      return;
    }
    /* 実画像 try-furni-1 が未配置のときのシルエット。面ごとに明度を変えて
       背もたれ・座面・肘掛けを描き分けないと、ただの板に見えてしまう。 */
    var x=CFG.frect[0]*W, y=CFG.frect[1]*H, w=CFG.frect[2]*W, h=CFG.frect[3]*H;
    var rr=function(px,py,pw,ph,r,fill){
      c.beginPath();
      if(c.roundRect) c.roundRect(px,py,pw,ph,r); else c.rect(px,py,pw,ph);
      c.fillStyle=fill; c.fill();
    };
    c.fillStyle='rgba(0,0,0,.13)';                                  // 接地影
    c.beginPath(); c.ellipse(x+w/2, y+h*0.99, w*0.52, h*0.07, 0, 0, 6.2832); c.fill();
    rr(x+w*0.07, y+h*0.86, w*0.05, h*0.14, 2, '#8C7A6D');           // 脚
    rr(x+w*0.88, y+h*0.86, w*0.05, h*0.14, 2, '#8C7A6D');
    rr(x+w*0.04, y,        w*0.92, h*0.56, h*0.14, '#B3A08B');      // 背もたれ（やや暗い）
    rr(x,        y+h*0.44, w,      h*0.44, h*0.13, '#C6B4A0');      // 座面（明るい）
    rr(x,        y+h*0.30, w*0.11, h*0.58, h*0.10, '#AD9A85');      // 肘掛け 左
    rr(x+w*0.89, y+h*0.30, w*0.11, h*0.58, h*0.10, '#AD9A85');      // 肘掛け 右
    c.fillStyle='rgba(0,0,0,.10)';                                  // 座面の切れ目
    c.fillRect(x+w*0.49, y+h*0.48, w*0.02, h*0.36);
  }

  function bbox(poly){
    var x0=1,y0=1,x1=0,y1=0;
    poly.forEach(function(p){ x0=Math.min(x0,p[0]); y0=Math.min(y0,p[1]);
                              x1=Math.max(x1,p[0]); y1=Math.max(y1,p[1]); });
    return {x:Math.floor(x0*W), y:Math.floor(y0*H),
             w:Math.ceil((x1-x0)*W), h:Math.ceil((y1-y0)*H)};
  }
  /* ポリゴンでクリップして素の部屋を写し取る＝これがそのままマスクになる（縁のAAも無料）。 */
  function makeLayer(poly){
    var c=document.createElement('canvas'); c.width=W; c.height=H;
    var x=c.getContext('2d',{willReadFrequently:true});
    x.save(); x.beginPath();
    poly.forEach(function(p,i){ var px=p[0]*W, py=p[1]*H; if(i) x.lineTo(px,py); else x.moveTo(px,py); });
    x.closePath(); x.clip(); x.drawImage(base,0,0); x.restore();
    var bb=bbox(poly);
    var src=x.getImageData(bb.x,bb.y,bb.w,bb.h), sd=src.data, sum=0, n=0;  // 合計輝度と画素数
    for(var i=0;i<sd.length;i+=4){
      if(!sd[i+3]) continue;
      var r=sd[i],g=sd[i+1],bl=sd[i+2];
      var mx=r>g?(r>bl?r:bl):(g>bl?g:bl), mn=r<g?(r<bl?r:bl):(g<bl?g:bl);
      sum+=(mx+mn)/510; n++;
    }
    return {cv:c, ctx:x, bb:bb, src:src, sumL:sum, n:n};
  }
  function hex2hs(hex){
    var r=parseInt(hex.substr(1,2),16)/255, g=parseInt(hex.substr(3,2),16)/255, b=parseInt(hex.substr(5,2),16)/255;
    var mx=Math.max(r,g,b), mn=Math.min(r,g,b), d=mx-mn, h=0, l=(mx+mn)/2;
    var s=d===0?0:d/(1-Math.abs(2*l-1));
    if(d!==0){ if(mx===r) h=((g-b)/d)%6; else if(mx===g) h=(b-r)/d+2; else h=(r-g)/d+4; h*=60; if(h<0)h+=360; }
    return [h,s,l];
  }
  function hsl2rgb(h,s,l){
    var c=(1-Math.abs(2*l-1))*s, x=c*(1-Math.abs((h/60)%2-1)), m=l-c/2, r=0,g=0,b=0;
    if(h<60){r=c;g=x;} else if(h<120){r=x;g=c;} else if(h<180){g=c;b=x;}
    else if(h<240){g=x;b=c;} else if(h<300){r=x;b=c;} else {r=c;b=x;}
    return [(r+m)*255,(g+m)*255,(b+m)*255];
  }
  /* 色相・彩度は目標色に置き換え、明度は「面全体を目標色の明るさへ寄せる」オフセットだけ
     かける。ピクセルごとの明暗差（木目・陰影・光のむら）はそのまま残るので、ベタ塗りに
     ならずに「その部屋の壁が別の色だったら」に見える。オフセットを入れないと、
     ウォルナットのような暗い色を選んでも床が暗くならず不自然になる。 */
  /* 壁が左・正面・右のように複数面あるとき、明度オフセットを面ごとに出すと
     各面が同じ明るさへ正規化され、**面ごとの光の違い（正面は明るく側面は暗い）が
     潰れて書き割りになる**。そのためオフセットはグループ全体の平均輝度から1つだけ
     求め、全面に同じ値を適用する。面どうしの相対的な明暗差はそのまま残る。 */
  function tint(L,hex,strength,meanL){
    var s=L.src, d=L.ctx.createImageData(s.width,s.height), sd=s.data, dd=d.data;
    var t=hex2hs(hex), th=t[0], ts=t[1];
    var dl=(t[2]-meanL)*0.92;                     // グループ共通の明度オフセット
    for(var i=0;i<sd.length;i+=4){
      var a=sd[i+3];
      if(!a){ dd[i+3]=0; continue; }
      var r=sd[i], g=sd[i+1], b=sd[i+2];
      var mx=r>g?(r>b?r:b):(g>b?g:b), mn=r<g?(r<b?r:b):(g<b?g:b);
      var nl=(mx+mn)/510+dl; nl=nl<0.03?0.03:(nl>0.97?0.97:nl);
      var rgb=hsl2rgb(th,ts,nl);
      dd[i]  = r+(rgb[0]-r)*strength;
      dd[i+1]= g+(rgb[1]-g)*strength;
      dd[i+2]= b+(rgb[2]-b)*strength;
      dd[i+3]= a;
    }
    L.ctx.putImageData(d, L.bb.x, L.bb.y);
  }

  /* 面のグループ（壁=複数面 / 床=1面）。平均輝度はグループ単位で持つ。 */
  function makeGroup(polys){
    var ls=polys.map(makeLayer), sum=0, n=0;
    ls.forEach(function(L){ sum+=L.sumL; n+=L.n; });
    return {layers:ls, meanL:n?sum/n:0.5};
  }
  function render(){
    ctx.clearRect(0,0,W,H);
    ctx.drawImage(base,0,0);
    if(!state.before){
      ['wall','floor'].forEach(function(k){
        if(!state[k]) return;
        groups[k].layers.forEach(function(L){ ctx.drawImage(L.cv,0,0); });
      });
    }
    drawFg(ctx);
    if(state.furni && !state.before) drawFurni(ctx);
  }
  function setColor(kind,hex){
    state[kind]=hex;
    if(hex){
      var G=groups[kind], st=(kind==='wall'?0.86:0.80);
      G.layers.forEach(function(L){ tint(L,hex,st,G.meanL); });
    }
    render();
  }

  function boot(){
    groups.wall=makeGroup(CFG.walls); groups.floor=makeGroup([CFG.floor]);
    render();
    onReady();
  }
  function start(){
    if(CFG.img){
      var im=new Image(); im.decoding='async';
      im.onload=function(){
        var sc=Math.max(W/im.width, H/im.height), dw=im.width*sc, dh=im.height*sc;
        bx.drawImage(im,(W-dw)/2,(H-dh)/2,dw,dh); boot();
      };
      im.onerror=function(){ drawPlaceholder(bx); boot(); };
      im.src=CFG.img;
    } else { drawPlaceholder(bx); boot(); }
    if(CFG.furni){ var f=new Image(); f.onload=function(){ furniImg=f; if(state.furni) render(); }; f.src=CFG.furni; }
  }
  return {
    init:function(cfg, canvas, cb){
      CFG=cfg; cv=canvas; onReady=cb||function(){};
      ctx=cv.getContext('2d',{willReadFrequently:true});
      W=cv.width; H=cv.height;
      base=document.createElement('canvas'); base.width=W; base.height=H;
      bx=base.getContext('2d',{willReadFrequently:true});
      start();
    },
    setColor:setColor,
    setFurni:function(v){ state.furni=!!v; render(); },
    setBefore:function(v){ state.before=!!v; render(); },
    state:state, render:render, ev:ev
  };
})();
"""


def _try_swatches(items, kind):
    esc = _html.escape
    out = []
    for i, (label, hexv) in enumerate(items):
        style = f' style="background:{esc(hexv)}"' if hexv else ""
        cls = "sw" + (" sw-none" if not hexv else "") + (" on" if i == 0 else "")
        out.append(f'<button class="{cls}" type="button" role="radio" aria-checked="'
                   f'{"true" if i == 0 else "false"}" data-kind="{kind}" '
                   f'data-color="{esc(hexv)}" aria-label="{esc(label)}" title="{esc(label)}">'
                   f'<i{style}></i><span>{esc(label)}</span></button>')
    return "\n".join(out)


def try_html(assets_dir=None):
    """Render /try — the lightweight mobile mini-experience. Self-contained."""
    esc = _html.escape
    url = f"{SITE_BASE_URL}/try"
    app_url = "/?ref=try"
    ga4 = ga4_head_snippet()
    title = "30秒でためす模様替え｜部屋の壁と床の色を変えてみる"
    desc = ("スマホでそのまま。サンプルの部屋の壁と床の色をタップで切り替えて、"
            "模様替えの見え方を30秒でためせます。登録もインストールも不要です。")
    has_room = bool(assets_dir) and _lp_asset_path(assets_dir, TRY_ROOM["img"]) is not None
    has_furni = bool(assets_dir) and _lp_asset_path(assets_dir, "try-furni-1") is not None
    room_src = f"/lp-assets/{TRY_ROOM['img']}" if has_room else ""
    furni_src = "/lp-assets/try-furni-1" if has_furni else ""
    prod_html = ""
    if TRY_PRODUCTS:
        rows = "\n".join(
            f'<a class="prod" href="{esc(p["url"])}" target="_blank" rel="nofollow noopener sponsored" '
            f'data-track="{esc(p.get("shop", ""))}">{esc(p["title"])}<span class="arw">→</span></a>'
            for p in TRY_PRODUCTS)
        prod_html = ('<section class="blk"><h2>この部屋で使った家具</h2>'
                     f'<div class="prods">{rows}</div>'
                     '<p class="fine">リンク先は各ECサイトです（PR）。</p></section>')
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "description": desc, "url": url, "inLanguage": "ja",
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_BASE_URL + "/"},
    }, ensure_ascii=False)
    cfg = json.dumps({
        "img": room_src, "furni": furni_src,
        "walls": TRY_ROOM["walls"], "floor": TRY_ROOM["floor"], "frect": TRY_ROOM["furni"],
    }, ensure_ascii=False)
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}｜{esc(SITE_NAME)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(url)}">
<meta property="og:image" content="{esc(SITE_BASE_URL)}/og.png">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{jsonld}</script>{ga4}
<style>
  /* 性能最優先のため Web フォントは読まない（本体/LPは Google Fonts を使うが、
     ここは初回表示3秒が要件なのでレンダリングブロッキングを持ち込まない）。 */
  :root{{--bg:#FBFAF8;--sub:#F1EFEA;--ink:#2A2824;--muted:#7C776E;--faint:#A49E94;
    --line:rgba(0,0,0,.10);--hair:rgba(0,0,0,.07);--accent:#3B6FE0;--r:10px}}
  *{{box-sizing:border-box}}
  html{{-webkit-text-size-adjust:100%}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-size:15px;line-height:1.7;
    font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif;
    -webkit-font-smoothing:antialiased;font-feature-settings:"palt" 1}}
  img{{max-width:100%;display:block}}
  a{{color:inherit}}
  .wrap{{max-width:560px;margin:0 auto;padding:0 16px}}
  header.bar{{position:sticky;top:0;z-index:20;background:rgba(251,250,248,.92);
    backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--hair)}}
  .bar-in{{display:flex;align-items:center;gap:10px;height:50px}}
  .mark{{font-weight:800;font-size:14px;letter-spacing:.02em;margin-right:auto}}
  .mark b{{background:var(--ink);color:var(--bg);padding:2px 6px;border-radius:4px}}
  h1{{font-size:clamp(19px,5.2vw,25px);font-weight:800;line-height:1.5;margin:18px 0 6px;
    letter-spacing:.01em}}
  .sub{{color:var(--muted);font-size:13.5px;margin:0 0 14px}}
  /* ステージ: 画像の縦横比が決まるまで箱を確保して CLS を出さない */
  .stage{{position:relative;background:var(--sub);border-radius:var(--r);overflow:hidden;
    aspect-ratio:3/2}}
  .stage canvas{{width:100%;height:100%;display:block;touch-action:pan-y}}
  .badge{{position:absolute;left:10px;top:10px;background:rgba(42,40,36,.72);color:#fff;
    font-size:11px;letter-spacing:.08em;padding:4px 9px;border-radius:99px;pointer-events:none;
    opacity:0;transition:opacity .18s}}
  .badge.on{{opacity:1}}
  .ctl{{margin:14px 0 0}}
  .ctl h2{{font-size:12px;font-weight:700;color:var(--muted);letter-spacing:.08em;margin:0 0 8px}}
  .sws{{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch}}
  .sw{{flex:0 0 auto;border:0;background:none;padding:0;cursor:pointer;width:56px;
    display:flex;flex-direction:column;align-items:center;gap:5px;font:inherit}}
  .sw i{{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);display:block;
    background:var(--sub);transition:transform .15s,box-shadow .15s}}
  .sw.sw-none i{{background:
    linear-gradient(135deg,transparent 46%,var(--faint) 46%,var(--faint) 54%,transparent 54%),var(--sub)}}
  .sw span{{font-size:10.5px;color:var(--muted);line-height:1.3;text-align:center}}
  .sw.on i{{box-shadow:0 0 0 2px var(--ink);transform:scale(1.04)}}
  .sw.on span{{color:var(--ink);font-weight:700}}
  .row{{display:flex;gap:8px;margin:16px 0 0;flex-wrap:wrap}}
  .tog{{flex:1 1 0;min-width:130px;border:1px solid var(--line);background:#fff;color:var(--ink);
    border-radius:var(--r);padding:12px 10px;font:inherit;font-size:13.5px;font-weight:700;cursor:pointer}}
  .tog[aria-pressed="true"]{{background:var(--ink);color:var(--bg);border-color:var(--ink)}}
  .btn{{display:flex;align-items:center;justify-content:center;gap:8px;background:var(--ink);
    color:var(--bg);text-decoration:none;font-weight:700;font-size:15.5px;padding:16px 20px;
    border-radius:var(--r);width:100%;border:0;cursor:pointer;font-family:inherit}}
  .cta-note{{font-size:12px;color:var(--faint);text-align:center;margin:8px 0 0}}
  .blk{{padding:26px 0;border-top:1px solid var(--hair);margin-top:26px}}
  .blk h2{{font-size:15px;font-weight:800;margin:0 0 8px}}
  .blk p{{margin:0;font-size:13.5px;color:var(--muted)}}
  .pcbox{{background:var(--sub);border-radius:var(--r);padding:14px;margin-top:10px}}
  .pcbox p{{margin:0 0 10px;font-size:13px;color:#4C4640}}
  .copy{{border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px 12px;
    font:inherit;font-size:13px;font-weight:700;cursor:pointer;width:100%}}
  .prods{{display:flex;flex-direction:column;gap:8px}}
  .prod{{display:flex;justify-content:space-between;gap:10px;border:1px solid var(--line);
    background:#fff;border-radius:8px;padding:12px;text-decoration:none;font-size:13.5px;font-weight:700}}
  .fine{{font-size:11.5px;color:var(--faint);margin:8px 0 0}}
  .rel{{display:block;padding:14px 0;border-top:1px solid var(--hair);text-decoration:none;
    font-weight:700;font-size:14px}}
  footer{{padding:24px 0 40px;border-top:1px solid var(--hair);margin-top:26px}}
  .pr{{font-size:11px;color:var(--faint);line-height:1.7;margin:0}}
  nav.legal{{margin-top:12px;display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px}}
  nav.legal a{{color:var(--muted);text-decoration:none}}
  button:focus-visible,a:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
  @media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style></head><body>
<header class="bar"><div class="wrap bar-in">
<span class="mark">Room<b>Studio</b></span>
<a class="sw-link" href="{esc(app_url)}" style="font-size:12.5px;font-weight:700;text-decoration:none">フル版 →</a>
</div></header>
<main class="wrap">
<h1>この部屋の壁と床、<br>色を変えてみてください</h1>
<p class="sub">タップするだけ。写真のアップロードは要りません。</p>

<div class="stage" id="stage">
  <canvas id="cv" width="1200" height="800" aria-label="サンプルの部屋。壁と床の色を切り替えられます"></canvas>
  <span class="badge" id="badge">BEFORE</span>
</div>

<div class="ctl"><h2>壁の色</h2><div class="sws" role="radiogroup" aria-label="壁の色">
{_try_swatches(TRY_WALL_COLORS, "wall")}
</div></div>
<div class="ctl"><h2>床の色</h2><div class="sws" role="radiogroup" aria-label="床の色">
{_try_swatches(TRY_FLOOR_COLORS, "floor")}
</div></div>

<div class="row">
  <button class="tog" id="togFurni" type="button" aria-pressed="false">家具を置く</button>
  <button class="tog" id="togBefore" type="button" aria-pressed="false">変える前と見比べる</button>
</div>

<div class="blk">
  <h2>自分の部屋の写真でやってみる</h2>
  <p>同じことを、自分の部屋の写真の上でできます。家具を置く・不要なものを消すまで、ブラウザだけで完結します。</p>
  <div style="margin-top:12px"><a class="btn" id="ctaMain" href="{esc(app_url)}">自分の部屋で試す →</a></div>
  <p class="cta-note">登録不要・インストール不要</p>
  <div class="pcbox" id="pcbox" hidden>
    <p><b>パソコンで開くと</b>、写真の読み込み・家具の配置・不要物の削除までフル機能が使えます。このページのURLを控えておくと便利です。</p>
    <button class="copy" id="btnCopy" type="button">このページのURLをコピー</button>
  </div>
</div>
{prod_html}
<a class="rel" href="/lp/moyougae-simulation">模様替えシミュレーションとは？ <span class="arw">→</span></a>
<footer>
<p class="pr">{esc(_PR_LINE)}</p>
<nav class="legal"><a href="/">アプリを開く</a><a href="/about">運営者情報</a><a href="/privacy">プライバシーポリシー</a><a href="/tokushoho">特商法表記</a></nav>
</footer>
</main>
<script>{ROOM_ENGINE_JS}</script>
<script>
(function(){{
  var cfg={cfg};
  RS.init(cfg, document.getElementById('cv'), function(){{
    RS.ev('try_view',{{has_photo:!!cfg.img, planes:cfg.walls.length}});
  }});
  var d=document, bd=d.getElementById('badge');
  function setBefore(v){{
    RS.setBefore(v);
    d.getElementById('togBefore').setAttribute('aria-pressed', v?'true':'false');
    bd.textContent = v?'BEFORE':'AFTER';
    bd.classList.toggle('on', v || !!(RS.state.wall||RS.state.floor));
  }}
  Array.prototype.forEach.call(d.querySelectorAll('.sw'),function(b){{
    b.addEventListener('click',function(){{
      var kind=b.dataset.kind;
      Array.prototype.forEach.call(d.querySelectorAll('.sw[data-kind="'+kind+'"]'),function(o){{
        o.classList.toggle('on',o===b); o.setAttribute('aria-checked',o===b?'true':'false');
      }});
      if(RS.state.before) setBefore(false);
      RS.setColor(kind,b.dataset.color);
      bd.classList.toggle('on', !!(RS.state.wall||RS.state.floor));
      RS.ev('try_color_change',{{surface:kind,color:b.dataset.color||'original'}});
    }});
  }});
  d.getElementById('togBefore').addEventListener('click',function(){{
    setBefore(!RS.state.before); RS.ev('try_before_after',{{on:RS.state.before}});
  }});
  d.getElementById('togFurni').addEventListener('click',function(){{
    RS.setFurni(!RS.state.furni);
    this.setAttribute('aria-pressed',RS.state.furni?'true':'false');
    this.textContent=RS.state.furni?'家具を外す':'家具を置く';
    RS.ev('try_furniture',{{on:RS.state.furni}});
  }});
  d.getElementById('ctaMain').addEventListener('click',function(){{ RS.ev('try_cta_click',{{to:'app'}}); }});
  Array.prototype.forEach.call(d.querySelectorAll('.prod'),function(a){{
    a.addEventListener('click',function(){{
      RS.ev('select_item',{{link_url:a.href,shop:a.dataset.track||''}});
      try{{ var q=new URLSearchParams({{id:'',type:'try',url:a.href,shop:a.dataset.track||'',src:'try'}});
            if(navigator.sendBeacon) navigator.sendBeacon('/track?'+q.toString()); }}catch(e){{}}
    }});
  }});
  /* スマホには「PCで開くとフル機能」の案内とURLコピーを出す（本体はPC前提のため）。 */
  if(matchMedia('(max-width:820px)').matches){{
    d.getElementById('pcbox').hidden=false;
    d.getElementById('btnCopy').addEventListener('click',function(){{
      var u=location.origin+'/', btn=this;
      var ok=function(){{ btn.textContent='コピーしました';
        setTimeout(function(){{ btn.textContent='このページのURLをコピー'; }},1800); }};
      var ng=function(){{ prompt('URLをコピーしてください',u); }};
      if(navigator.clipboard&&navigator.clipboard.writeText){{ navigator.clipboard.writeText(u).then(ok,ng); }}
      else {{ ng(); }}
      RS.ev('try_copy_url');
    }});
  }}
}})();
</script>
</body></html>"""


# =============================================================================
# /demo — 自動デモモード（docs/BUZZ_FOUNDATION_INSTRUCTIONS.md §2）
#
# 運営が「画面録画を開始してURLを開くだけ」でショート動画の素材が撮れる状態にする。
# 手動操作の撮影をなくすのが目的なので、開いた瞬間から勝手に「変身」が再生される。
#
# 描画は /try と同じ ROOM_ENGINE_JS を使う。ここが持つのはタイムラインだけ。
#
# タイムラインは**実時間（performance.now）基準**で駆動する。BUZZ_FOUNDATION_PLAN の
# 当初の申し送りでは「フレーム基準」としていたが、これは誤りだったので変更した。
# フレーム数で刻むと、コマ落ちしたぶんだけ実尺が伸びて 15秒/30秒 が狂う。録画素材と
# しては**尺が毎回きっかり同じ**であることが最優先なので、実時間で刻んで各フェーズの
# 開始位置を総尺の比率で決めている（コマ落ちしても尺は変わらない）。
# =============================================================================

# 再生するテイスト。?preset= で選ぶ。値は (壁, 床) の16進。
DEMO_PRESETS = {
    "natural": [("#EFE9DF", "#DCC29B"), ("#D6CEC2", "#C6A67E"), ("#C7D3C6", "#8A6A4E")],
    "grey":    [("#D6CEC2", "#B5AFA6"), ("#C4CED7", "#8A6A4E"), ("#6E6A64", "#B5AFA6")],
    "green":   [("#C7D3C6", "#DCC29B"), ("#C7D3C6", "#8A6A4E"), ("#6E6A64", "#8A6A4E")],
}
DEMO_DEFAULT_PRESET = "natural"


def demo_html(assets_dir=None, length=15, ratio="16x9", clean=False, preset=None):
    """Render /demo — the auto-playing recording source. noindex, not in sitemap."""
    esc = _html.escape
    length = 30 if str(length) == "30" else 15
    vertical = (str(ratio) == "9x16")
    preset = preset if preset in DEMO_PRESETS else DEMO_DEFAULT_PRESET
    ga4 = ga4_head_snippet()
    has_room = bool(assets_dir) and _lp_asset_path(assets_dir, TRY_ROOM["img"]) is not None
    has_furni = bool(assets_dir) and _lp_asset_path(assets_dir, "try-furni-1") is not None
    cfg = json.dumps({
        "img": f"/lp-assets/{TRY_ROOM['img']}" if has_room else "",
        "furni": "/lp-assets/try-furni-1" if has_furni else "",
        "walls": TRY_ROOM["walls"], "floor": TRY_ROOM["floor"], "frect": TRY_ROOM["furni"],
    }, ensure_ascii=False)
    steps = json.dumps(DEMO_PRESETS[preset], ensure_ascii=False)
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>自動デモ｜{esc(SITE_NAME)}</title>
<meta name="robots" content="noindex, nofollow">{ga4}
<style>
  :root{{--bg:#FBFAF8;--ink:#2A2824;--muted:#7C776E}}
  *{{box-sizing:border-box}}
  html,body{{margin:0;height:100%;background:{'#141210' if vertical else 'var(--bg)'}}}
  body{{color:var(--ink);display:grid;place-items:center;overflow:hidden;
    font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif}}
  /* 縦型は 9:16 のレターボックス。ショート動画がこの比率なので、録画の外枠をここで作る。 */
  .frame{{position:relative;background:var(--bg);overflow:hidden;
    {'aspect-ratio:9/16;height:100vh;max-width:100vw' if vertical else 'aspect-ratio:16/9;width:100vw;max-height:100vh'}}}
  .inner{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;
    gap:{'22px' if vertical else '0'};padding:{'0 0 5vh' if vertical else '0'}}}
  .stage{{position:relative;width:100%;{'aspect-ratio:3/2;flex:0 0 auto' if vertical else 'flex:1 1 auto;min-height:0'}}}
  canvas{{width:100%;height:100%;display:block;object-fit:cover}}
  /* 16:9 はキャプションを画面下部のオーバーレイにする。フロー配置のままだと
     ステージが高さを取り切ってキャプションが枠外へ押し出されるため。 */
  .cap{{text-align:center;padding:0 6%;{'''position:absolute;left:0;right:0;bottom:7vh;
    color:#fff;text-shadow:0 1px 14px rgba(0,0,0,.55)''' if not vertical else ''}}}
  .cap h1{{font-size:{'clamp(20px,4.6vw,34px)' if vertical else 'clamp(18px,2.2vw,30px)'};
    font-weight:800;margin:0 0 6px;letter-spacing:.01em;line-height:1.5}}
  .cap p{{margin:0;color:{'var(--muted)' if vertical else 'rgba(255,255,255,.86)'};
    font-size:{'clamp(12px,2.6vw,17px)' if vertical else '15px'}}}
  .brand{{position:absolute;left:0;right:0;bottom:{'3.2vh' if vertical else '2.6vh'};text-align:center;
    font-size:{'clamp(11px,2.4vw,15px)' if vertical else '12.5px'};font-weight:700;letter-spacing:.08em;
    color:{'var(--muted)' if vertical else 'rgba(255,255,255,.72)'};z-index:2}}
  .scrim{{position:absolute;left:0;right:0;bottom:0;height:32%;pointer-events:none;
    background:linear-gradient(180deg,rgba(20,18,16,0),rgba(20,18,16,.55));
    display:{'none' if vertical else 'block'}}}
  .badge{{position:absolute;left:14px;top:14px;background:rgba(42,40,36,.72);color:#fff;
    font-size:11px;letter-spacing:.14em;padding:5px 11px;border-radius:99px;z-index:2}}
  /* ?clean=1: 録画に映り込む文字や枠をすべて外し、部屋だけにする */
  body.clean .cap,body.clean .brand,body.clean .badge,body.clean .scrim{{display:none}}
  body.clean .inner{{padding:0;gap:0}}
  body.clean .stage{{{'height:100%;aspect-ratio:auto' if vertical else ''}}}
</style></head><body{' class="clean"' if clean else ''}>
<div class="frame"><div class="inner">
  <div class="stage">
    <canvas id="cv" width="1200" height="800"></canvas>
    <span class="scrim" aria-hidden="true"></span>
    <span class="badge" id="badge">BEFORE</span>
  </div>
  <div class="cap">
    <h1>壁と床の色を変えるだけで、<br>部屋はここまで変わる</h1>
    <p>部屋の写真の上で試せます</p>
  </div>
</div><div class="brand">ROOM STUDIO</div></div>
<script>{ROOM_ENGINE_JS}</script>
<script>
(function(){{
  var cfg={cfg}, steps={steps}, LEN={length}*1000;
  var bd=document.getElementById('badge');
  /* フェーズは総尺に対する比率で持つ。15秒でも30秒でも同じ構成のまま伸縮する。 */
  var PH=[
    /* ループ先頭では色も必ず元に戻す。戻さないと2周目以降の AFTER が、
       前の周回の最終色から始まってしまい「変わっていく」感じが出ない。 */
    {{at:0.00, run:function(){{ RS.setColor('wall',''); RS.setColor('floor','');
      RS.setBefore(true); RS.setFurni(false); bd.textContent='BEFORE'; }}}},
    {{at:0.17, run:function(){{ RS.setBefore(false); RS.setFurni(true);  bd.textContent='AFTER'; }}}},
    {{at:0.27, run:function(){{ RS.setColor('wall', steps[0][0]); }}}},
    {{at:0.40, run:function(){{ RS.setColor('floor',steps[0][1]); }}}},
    {{at:0.55, run:function(){{ RS.setColor('wall', steps[1][0]); RS.setColor('floor',steps[1][1]); }}}},
    {{at:0.72, run:function(){{ RS.setColor('wall', steps[2][0]); RS.setColor('floor',steps[2][1]); }}}},
    {{at:0.88, run:function(){{ RS.setBefore(true);  bd.textContent='BEFORE'; }}}},
    {{at:0.94, run:function(){{ RS.setBefore(false); bd.textContent='AFTER'; }}}}
  ];
  var t0=null, done=-1;
  function frame(now){{
    if(t0===null) t0=now;
    var p=((now-t0)%LEN)/LEN;                 // 0..1 をループ
    var i=-1;
    for(var k=0;k<PH.length;k++){{ if(p>=PH[k].at) i=k; }}
    if(i!==done){{
      if(i<done){{ done=-1; }}               // ループ先頭に戻った
      for(var j=done+1;j<=i;j++) PH[j].run(); // 取りこぼしたフェーズも順に適用
      done=i;
    }}
    requestAnimationFrame(frame);
  }}
  RS.init(cfg, document.getElementById('cv'), function(){{
    /* demo は「意図して開いた録画用ページ」なので、省モーション設定でも再生する
       （指示書 §2 の但し書き）。ただし自動再生する旨は URL とタイトルで自明。 */
    requestAnimationFrame(frame);
  }});
}})();
</script>
</body></html>"""


# ---- landing-page assets (/lp-assets/<name>) ---------------------------------
_LP_IMG_CT = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".png": "image/png", ".avif": "image/avif"}
# webm first: browsers pick the first <source> they can decode, and VP9/webm is the
# smaller file wherever it is supported. mp4/H.264 stays as the universal fallback.
_LP_VIDEO_CT = {".webm": "video/webm", ".mp4": "video/mp4"}
_LP_ASSET_CT = dict(_LP_IMG_CT, **_LP_VIDEO_CT)

# One response is capped well under Vercel's ~4.5MB serverless response limit. An
# open-ended range ("bytes=0-") is answered with at most this much and a 206, which
# is a legal partial answer — so a hero video larger than the cap still streams
# instead of failing outright. See docs/LP_IMAGE_GUIDE.md for the recommended size.
_LP_MAX_CHUNK = 3 * 1024 * 1024


def _lp_asset_path(assets_dir, name, types=None):
    """Resolve an LP asset to an existing file path under assets_dir, or None.

    Path-safe: only a bare filename is accepted. `types` is the extension→MIME map
    to consider; a name WITHOUT an extension is tried against each type in turn.
    It defaults to images only, so an image slot keeps resolving to the picture even
    when a same-named video sits beside it (`<slug>-hero.webp` vs `<slug>-hero.mp4`)."""
    types = types or _LP_IMG_CT
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", name or ""):
        return None
    ext = os.path.splitext(name)[1].lower()
    names = [name] if ext in types else [name + e for e in types]
    for fn in names:
        if os.path.splitext(fn)[1].lower() not in types:
            continue
        path = os.path.join(assets_dir, fn)
        if os.path.isfile(path):
            return path
    return None


def _parse_range(header, size):
    """Parse a single HTTP byte range into an inclusive (start, end), or None.

    Returns None for a malformed, multi-range or unsatisfiable header — the caller
    turns that into 416. Supports "bytes=N-", "bytes=N-M" and the suffix "bytes=-N"."""
    m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", header or "")
    if not m or size <= 0:
        return None
    first, last = m.group(1), m.group(2)
    if first == "":                       # suffix range: the final `last` bytes
        if last == "":
            return None
        start, end = max(0, size - int(last)), size - 1
    else:
        start = int(first)
        end = int(last) if last else size - 1
    if start >= size or end < start:
        return None
    return start, min(end, size - 1)


def lp_asset_range(assets_dir, name, range_header=None):
    """(status, body, headers) for an LP asset, or None when it does not exist.

    Honours one HTTP Range with a 206. This is what makes the video hero viable:
    iOS Safari refuses to play a <video> served by an endpoint that ignores Range,
    and an unranged full-file response would also hit Vercel's response size cap."""
    path = _lp_asset_path(assets_dir, name, _LP_ASSET_CT)
    if not path:
        return None
    ctype = _LP_ASSET_CT[os.path.splitext(path)[1].lower()]
    size = os.path.getsize(path)
    headers = {"Content-Type": ctype, "Accept-Ranges": "bytes",
               "Cache-Control": "public, max-age=86400"}
    if range_header:
        rng = _parse_range(range_header, size)
        if rng is None:
            headers["Content-Range"] = f"bytes */{size}"
            return 416, b"", headers
        start, end = rng
        end = min(end, start + _LP_MAX_CHUNK - 1)     # keep the response under the cap
        with open(path, "rb") as f:
            f.seek(start)
            body = f.read(end - start + 1)
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(len(body))
        return 206, body, headers
    with open(path, "rb") as f:
        body = f.read()
    headers["Content-Length"] = str(len(body))
    return 200, body, headers


def lp_asset(assets_dir, name):
    """Return (bytes, content_type) for a whole LP asset, or None if not found.
    Kept for the /materials/ route, which serves small tiles and never needs ranges."""
    res = lp_asset_range(assets_dir, name)
    if res is None:
        return None
    _status, body, headers = res
    return body, headers["Content-Type"]


# ---- robots.txt / sitemap.xml -------------------------------------------------
def robots_txt():
    """robots.txt body. Private deployments (ACCESS_TOKEN set) disallow everything;
    the public site allows all and advertises the sitemap."""
    if ACCESS_TOKEN:
        return "User-agent: *\nDisallow: /\n"
    # /demo は運営が録画に使う自動再生ページ。認証は掛けないがクロールはさせない
    # （sitemap にも載せず、ページ側にも noindex を付けてある。三重に塞ぐ）。
    return (f"User-agent: *\nAllow: /\nDisallow: /demo\n"
            f"Sitemap: {SITE_BASE_URL}/sitemap.xml\n")


def sitemap_xml(lastmod=None):
    """sitemap.xml body listing the top page, legal pages and every landing page.
    `lastmod` is a YYYY-MM-DD string (caller passes the app's file mtime); falls
    back to today if omitted."""
    lm = lastmod or time.strftime("%Y-%m-%d")
    # /try は SNS からの着地ページなので通常どおり公開・掲載する
    # （運営専用の /demo は §2 で noindex + 非掲載にする）。
    paths = ["/", "/try", "/about", "/privacy", "/tokushoho"] + [f"/lp/{s}" for s in landing_slugs()]
    esc = _html.escape
    urls = "\n".join(
        f"  <url><loc>{esc(SITE_BASE_URL + p)}</loc><lastmod>{esc(lm)}</lastmod></url>"
        for p in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")
