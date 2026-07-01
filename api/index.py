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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root (parent of api/)
app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True, "inpaint": False, "collect": True}


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


_HTML = None


def _html():
    global _HTML
    if _HTML is None:
        with open(os.path.join(ROOT, "room-studio.html"), encoding="utf-8") as f:
            _HTML = f.read()
    return _HTML


@app.get("/", response_class=HTMLResponse)
@app.get("/room-studio.html", response_class=HTMLResponse)
def index():
    # Always serve the latest HTML (the app is one self-contained file that updates often).
    # Without this, mobile browsers can keep showing a stale cached version.
    return HTMLResponse(_html(), headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"})
