# -*- coding: utf-8 -*-
"""Vercel entrypoint — a single FastAPI app (Vercel's first-class Python path).

Serves the app HTML + the lightweight API (/health, /collect, /imgproxy) using the
shared stdlib core. The heavy LaMa /inpaint is NOT here (the browser falls back to
PatchMatch on the hosted site). Local dev still uses server.py (LaMa included)."""
import os
import sys
import time
from urllib.parse import urlsplit as _urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

sys.path.insert(0, os.path.dirname(__file__))
import _collect_core as core  # noqa: E402
import _bgcut_core as bgcut_core  # noqa: E402  (server-side AI background removal; heavy deps lazy)
import _site  # noqa: E402  (click tracking + legal pages)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root (parent of api/)
app = FastAPI()

_GATE_API = ("/collect", "/item", "/imgproxy", "/bgcut", "/inpaint", "/track")

# ---- 旧ドメインを本番へ寄せる（docs/GA4_ACCESS_REPORT.md §10-7）-----------------
# 独自ドメインへ移行したあとも、Vercel が最初に配った `*.vercel.app` の本番URLは生きて
# いて、同じ配信物＝同じ GA4 タグを注入したまま 200 を返す。実測で全期間の 8.7% が本番
# 以外のホストだった。ホスト名は GA4 のレポートでは既定で見えないので、混ざっていること
# 自体に気づけない（気づいたのは hostName を明示して引き直したから）。
#
# ここで寄せるのは **既知の旧ホストだけ**。「roomstudio.jp 以外は全部リダイレクト」に
# すると、プレビュー配信（`room-studio-<hash>-....vercel.app`）が本番へ飛んで**動作確認
# そのものができなくなる**。プレビューの計測混入は Vercel 側で環境変数を Production 限定
# にして止める話で、リダイレクトで解く問題ではない。
#
# 308 を使う理由: 301/302 と違い method と body を保持する。旧ドメイン宛ての POST
# （/collect・/bgcut）が GET に化けて 405 になるのを防ぐ。
_LEGACY_HOSTS = frozenset(
    h.strip().lower() for h in os.environ.get("LEGACY_HOSTS", "room-studio-fawn.vercel.app").split(",")
    if h.strip())


def _canonical_host():
    """SITE_BASE_URL のホスト名（未設定＝旧ドメインのまま、のときは空を返す）。

    空を返す＝リダイレクトしない。SITE_BASE_URL が未設定の環境では `_DEFAULT_BASE` が
    旧ドメイン自身なので、素直に書くと**自分から自分へ 308 する無限ループ**になる。"""
    host = _urlsplit(_site.SITE_BASE_URL).netloc.split("@")[-1].lower()
    return "" if not host or host in _LEGACY_HOSTS else host


_CANON_HOST = _canonical_host()


@app.middleware("http")
async def _canonical_host_redirect(request, call_next):
    # 先頭に置く（Starlette は先に登録したものが外側＝先に走る）。旧ドメインへのアクセスは
    # アプリ本体を1バイトも配らずに折り返す＝GA4 タグを注入した HTML が出ない。
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if _CANON_HOST and host in _LEGACY_HOSTS:
        # path も query もそのまま持っていく。落とすと utm_* が消えて、旧ドメイン経由の
        # 流入が GA4 で (direct)/(none) になる（退役LPの301と同じ理由・指示031 A3）。
        return RedirectResponse(str(request.url.replace(scheme="https", netloc=_CANON_HOST)),
                                status_code=308)
    return await call_next(request)


@app.middleware("http")
async def _access_gate(request, call_next):
    # Opt-in gate: only active when ACCESS_TOKEN env is set (private web deployment).
    if not _site.ACCESS_TOKEN:
        return await call_next(request)
    path = request.url.path
    if path in ("/health", "/robots.txt"):  # probes + crawler directives stay open
        return await call_next(request)
    key = request.query_params.get("key")
    if _site.access_ok(request.cookies.get(_site.ACCESS_COOKIE), key):
        resp = await call_next(request)
        if _site.key_matches(key):  # authenticated via ?key → persist a cookie
            resp.set_cookie(_site.ACCESS_COOKIE, _site.ACCESS_TOKEN, httponly=True,
                            samesite="lax", max_age=2592000, path="/")
        return resp
    if any(path.startswith(p) for p in _GATE_API):
        return Response("unauthorized", status_code=401)
    return HTMLResponse(_site.login_html(), status_code=401)


@app.get("/health")
def health():
    # provider/mode make it visible on the public URL that the crawler is NOT enabled.
    return {"ok": True, "inpaint": False, "collect": True, "bgcut": bgcut_core.available(),
            **core.provider_status()}


def _req_referer(request: Request):
    # Rakuten requires Referer/Origin matching a registered site → use the request's own domain
    host = request.headers.get("host", "")
    if host and "localhost" not in host and "127.0.0.1" not in host:
        proto = request.headers.get("x-forwarded-proto", "https")
        return f"{proto}://{host}/"
    return None


@app.get("/collect")
def collect(request: Request, type: str = "", taste: str = "", count: int = 50,
           source: str = "", shop: str = "", provider: str = ""):
    try:
        return core.collect(type, taste, count, source, shop, _req_referer(request), provider or None)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.get("/shops")
def shops(request: Request, query: str = "", type: str = "", provider: str = ""):
    try:
        return {"shops": core.search_shops(query, type, _req_referer(request), provider or None)}
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.get("/item")
def item(request: Request, code: str = "", source: str = "", provider: str = ""):
    try:
        it = core.fetch_item(code, source, _req_referer(request), provider or None)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    if it is None:
        raise HTTPException(status_code=404, detail="item not found")
    return it


@app.get("/imgproxy")
def imgproxy(url: str = ""):
    try:
        data, ctype = core.imgproxy_fetch(url)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/bgcut")
def bgcut(url: str = "", v: str = "1"):
    # AI background removal for collected images (ISNet via onnxruntime). Transient like
    # /imgproxy — nothing is stored; `v` versions the edge cache alongside the model.
    try:
        data, _ctype = core.imgproxy_fetch(url)
        png = bgcut_core.cut_png(data)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400, s-maxage=2592000"})


@app.get("/track")
def track(id: str = "", type: str = "", url: str = "", src: str = "", shop: str = "",
          item_category: str = "", count: str = "", rank: str = "", score: str = "",
          ranked: str = "", source: str = "", item_id: str = ""):
    # Purchase/affiliate click logging. Self-clicks are excluded client-side (localStorage opt-out).
    # `shop` (maker/storefront) enables per-maker click analysis later.
    # 指示016 also routes collect_done / collect_shop / place_item here: collect_shop is the
    # denominator (images handed out per shop), place_item the numerator (actually placed).
    # Nothing personal is accepted and no score is persisted server-side.
    _site.log_track({"id": id or item_id, "type": type, "url": url, "src": src, "shop": shop,
                     "cat": item_category, "count": count, "rank": rank, "score": score,
                     "ranked": ranked, "source": source})
    return Response(status_code=204)


@app.get("/robots.txt")
def robots():
    return Response(_site.robots_txt(), media_type="text/plain; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/sitemap.xml")
def sitemap():
    return Response(_site.sitemap_xml(_app_lastmod()), media_type="application/xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/try", response_class=HTMLResponse)
def try_page():
    # /try — スマホ30秒ミニ体験（BUZZ_FOUNDATION_INSTRUCTIONS §1）。
    # アプリ本体は読み込まない独立ページ。サンプル画像は lp-assets/ から取る。
    # 既定では非公開（_site.TRY_DEMO_ENABLED の由来コメントを参照）。実装は残してある
    # ので、環境変数 ENABLE_TRY_DEMO=1 を足せばこの行より下がそのまま動く。
    if not _site.TRY_DEMO_ENABLED:
        raise HTTPException(status_code=404)
    return HTMLResponse(_site.try_html(os.path.join(ROOT, "lp-assets")),
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/demo", response_class=HTMLResponse)
def demo_page(len: str = "15", ratio: str = "16x9", clean: str = "", preset: str = ""):
    # /demo — 自動デモ（録画用）。noindex + robots Disallow + sitemap非掲載。
    # /try と同じスイッチで止めている（録画元が /try と同じ素材・同じ描画エンジンで、
    # 公開に耐えないと判断された対象そのものなので、片方だけ残す意味がない）。
    if not _site.TRY_DEMO_ENABLED:
        raise HTTPException(status_code=404)
    page = _site.demo_html(os.path.join(ROOT, "lp-assets"), length=len,
                           ratio=ratio, clean=bool(clean), preset=preset or None)
    # no-store: 録画のたびに最新が出るように。X-Robots-Tag はページの noindex と二重掛け。
    return HTMLResponse(page, headers={"Cache-Control": "no-store",
                                       "X-Robots-Tag": "noindex, nofollow"})


@app.get("/lp/{slug}", response_class=HTMLResponse)
def landing(slug: str, request: Request):
    page = _site.landing_html(slug, os.path.join(ROOT, "lp-assets"))
    if page is None:
        # A retired LP keeps its search equity by 301-ing to the surviving page.
        dest = _site.landing_redirect(slug)
        if dest:
            # Carry the query string across (指示031・A3). Dropping it loses any utm_*
            # on the way, so a visit that arrived through a retired slug would land in
            # GA4 as (direct)/(none) — the campaign is unrecoverable after the hop.
            return RedirectResponse(_site.with_query(dest, request.url.query), status_code=301)
        raise HTTPException(status_code=404, detail="not found")
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/lp-assets/{name}")
def lp_asset(name: str, request: Request):
    # Landing-page media (hero photo/video, before-after captures) from lp-assets/.
    # Range-aware: the hero video will not play on iOS Safari without it.
    res = _site.lp_asset_range(os.path.join(ROOT, "lp-assets"), name,
                               request.headers.get("range"))
    if res is None:
        raise HTTPException(status_code=404, detail="not found")
    status, body, headers = res
    return Response(content=body, status_code=status, headers=headers)


@app.get("/materials/{name}")
def material_asset(name: str):
    # 素材タイル（CC0, ambientCG）。materials/ の <key>.jpg と <key>_t.jpg を配信。
    # 内容は不変なので lp-assets より長めにキャッシュさせる。出典は docs/MATERIALS_CC0.md。
    res = _site.lp_asset(os.path.join(ROOT, "materials"), name)
    if res is None:
        raise HTTPException(status_code=404, detail="not found")
    data, ctype = res
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/about", response_class=HTMLResponse)
def about():
    return HTMLResponse(_site.legal_html("about"))


@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return HTMLResponse(_site.legal_html("privacy"))


@app.get("/tokushoho", response_class=HTMLResponse)
def tokushoho():
    return HTMLResponse(_site.legal_html("tokushoho"))


def _png(name):
    path = os.path.join(ROOT, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not found")
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/og.png")
def og_png():
    return _png("og.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return _png("apple-touch-icon.png")


_HTML = None


def _html():
    global _HTML
    if _HTML is None:
        with open(os.path.join(ROOT, "room-studio.html"), encoding="utf-8") as f:
            _HTML = _site.render_app_html(f.read())
    return _HTML


def _app_lastmod():
    """YYYY-MM-DD mtime of the app HTML, for sitemap <lastmod> (None on failure)."""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(
            os.path.getmtime(os.path.join(ROOT, "room-studio.html"))))
    except Exception:  # noqa: BLE001
        return None


@app.get("/", response_class=HTMLResponse)
@app.get("/room-studio.html", response_class=HTMLResponse)
def index():
    # Always serve the latest HTML (the app is one self-contained file that updates often).
    # Without this, mobile browsers can keep showing a stale cached version.
    return HTMLResponse(_html(), headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"})
