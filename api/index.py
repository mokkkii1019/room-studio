# -*- coding: utf-8 -*-
"""Vercel entrypoint — a single FastAPI app (Vercel's first-class Python path).

Serves the app HTML + the lightweight API (/health, /collect, /imgproxy) using the
shared stdlib core. The heavy LaMa /inpaint is NOT here (the browser falls back to
PatchMatch on the hosted site). Local dev still uses server.py (LaMa included)."""
import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

sys.path.insert(0, os.path.dirname(__file__))
import _collect_core as core  # noqa: E402
import _site  # noqa: E402  (click tracking + legal pages)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root (parent of api/)
app = FastAPI()

_GATE_API = ("/collect", "/item", "/imgproxy", "/inpaint", "/track")


@app.middleware("http")
async def _access_gate(request, call_next):
    # Opt-in gate: only active when ACCESS_TOKEN env is set (private web deployment).
    if not _site.ACCESS_TOKEN:
        return await call_next(request)
    path = request.url.path
    if path == "/health":  # health stays open for probes
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
    return {"ok": True, "inpaint": False, "collect": True, **core.provider_status()}


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


@app.get("/track")
def track(id: str = "", type: str = "", url: str = "", src: str = ""):
    # Purchase/affiliate click logging. Self-clicks are excluded client-side (localStorage opt-out).
    _site.log_track({"id": id, "type": type, "url": url, "src": src})
    return Response(status_code=204)


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
            _HTML = _site.inject_ga4(f.read())
    return _HTML


@app.get("/", response_class=HTMLResponse)
@app.get("/room-studio.html", response_class=HTMLResponse)
def index():
    # Always serve the latest HTML (the app is one self-contained file that updates often).
    # Without this, mobile browsers can keep showing a stale cached version.
    return HTMLResponse(_html(), headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"})
