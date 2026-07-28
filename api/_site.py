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
