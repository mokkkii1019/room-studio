#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Room Studio — ローカル AI 補完サーバー（LaMa / CPU対応）

これは「消しゴム」を Photoshop の「コンテンツに応じた塗りつぶし」相当の品質にするための
ローカルサーバーです。GPU が無くても CPU で動きます（初回はモデルを自動ダウンロード）。

使い方:
    pip install -r requirements-local.txt
    # GPUが無いPCでは、軽量なCPU版torchを先に入れると速くて容量も小さいです:
    #   pip install torch --index-url https://download.pytorch.org/whl/cpu
    python server.py

その後ブラウザで  http://127.0.0.1:7865  を開くと、アプリが配信され、
「消しゴム」タブに『AI補完エンジン（LaMa）に接続済み』と表示されます。
（room-studio.html を直接ファイルで開いても、このサーバーが起動していれば自動検出します。）

エンドポイント:
    GET  /health   -> {"inpaint": true/false, "model": "lama", "loaded": bool}
    POST /inpaint  -> {"image": <dataURL>, "mask": <dataURL>}  ->  {"image": <dataURL>}
                      mask は白(255)=消す領域。
"""

import base64
import io
import re
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from PIL import Image
import numpy as np
import os
import json
import urllib.parse
import urllib.request
import urllib.error
import uvicorn

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 7865

app = FastAPI(title="Room Studio Inpaint Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

# ---- モデルは初回リクエスト時に遅延ロード（起動を速く保つ） ----
_model = None
_model_lock = threading.Lock()
_import_ok = None  # simple_lama_inpainting が import 可能か


def _check_import() -> bool:
    global _import_ok
    if _import_ok is None:
        try:
            import simple_lama_inpainting  # noqa: F401
            _import_ok = True
        except Exception as e:  # pragma: no cover
            print("simple-lama-inpainting を import できません:", e)
            _import_ok = False
    return _import_ok


def get_model():
    """SimpleLama を一度だけ構築（CPU/GPU 自動判定）。初回はモデルDLが走る。"""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from simple_lama_inpainting import SimpleLama
                print("LaMa モデルをロード中…（初回はダウンロードがあります）")
                _model = SimpleLama()  # CUDA があれば自動でGPU、無ければCPU
                print("LaMa モデルのロード完了")
    return _model


# ---- ユーティリティ ----
def data_url_to_image(data_url: str, mode: str = "RGB") -> Image.Image:
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    img = Image.open(io.BytesIO(raw))
    return img.convert(mode)


def image_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/png;base64," + b64


class InpaintReq(BaseModel):
    image: str
    mask: str


@app.get("/health")
def health():
    return {"inpaint": _check_import(), "model": "lama", "loaded": _model is not None,
            **core.provider_status()}


@app.post("/inpaint")
def inpaint(req: InpaintReq):
    if not _check_import():
        raise HTTPException(status_code=503, detail="simple-lama-inpainting 未インストール")
    try:
        image = data_url_to_image(req.image, "RGB")
        mask = data_url_to_image(req.mask, "L")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"画像のデコードに失敗: {e}")

    # サイズ合わせ
    if mask.size != image.size:
        mask = mask.resize(image.size, Image.NEAREST)
    # 2値化（白=消す領域）
    m = np.array(mask)
    m = np.where(m > 127, 255, 0).astype("uint8")
    mask = Image.fromarray(m, mode="L")

    model = get_model()
    try:
        result = model(image, mask)  # PIL.Image (RGB)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"補完に失敗: {e}")

    if not isinstance(result, Image.Image):
        result = Image.fromarray(np.array(result))
    result = result.convert("RGB")
    # 念のため元サイズへ
    if result.size != image.size:
        result = result.resize(image.size, Image.BICUBIC)
    return {"image": image_to_data_url(result)}


# ---- 収集 / 画像リレー：ロジックは api/_collect_core（stdlib）に集約し Vercel と共有 ----
import sys as _sys
_sys.path.insert(0, os.path.join(APP_DIR, "api"))
import _collect_core as core  # noqa: E402
import _site  # noqa: E402  (click tracking + legal pages + access gate)

_GATE_API = ("/collect", "/item", "/imgproxy", "/inpaint", "/track")


@app.middleware("http")
async def _access_gate(request, call_next):
    # Opt-in gate: only active when ACCESS_TOKEN env is set (private web deployment).
    if not _site.ACCESS_TOKEN:
        return await call_next(request)
    path = request.url.path
    if path in ("/health", "/robots.txt"):
        return await call_next(request)
    key = request.query_params.get("key")
    if _site.access_ok(request.cookies.get(_site.ACCESS_COOKIE), key):
        resp = await call_next(request)
        if _site.key_matches(key):
            resp.set_cookie(_site.ACCESS_COOKIE, _site.ACCESS_TOKEN, httponly=True,
                            samesite="lax", max_age=2592000, path="/")
        return resp
    if any(path.startswith(p) for p in _GATE_API):
        return Response("unauthorized", status_code=401)
    return HTMLResponse(_site.login_html(), status_code=401)


@app.get("/collect")
def collect(type: str, taste: str = "", count: int = 50, source: str = "", shop: str = "", provider: str = ""):
    """家具店の商品を種類＋テイストで検索（ロジックは api/_collect_core・プロバイダ経由）。"""
    try:
        return core.collect(type, taste, count, source, shop, None, provider or None)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.get("/shops")
def shops(query: str = "", type: str = "", provider: str = ""):
    """楽天の全ショップからメーカー/店舗を検索（[{code,name,count}]）。"""
    try:
        return {"shops": core.search_shops(query, type, None, provider or None)}
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@app.get("/item")
def item(code: str = "", source: str = "", provider: str = ""):
    """商品コードで1件再取得（参照のみ保存の再ハイドレーション用）。"""
    try:
        it = core.fetch_item(code, source, None, provider or None)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    if it is None:
        raise HTTPException(status_code=404, detail="item not found")
    return it


@app.get("/imgproxy")
def imgproxy(url: str):
    """外部画像を同一オリジンで中継（キャンバス汚染を防ぐ。許可ホストのみ）。"""
    try:
        data, ctype = core.imgproxy_fetch(url)
    except core.CollectError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/track")
def track(id: str = "", type: str = "", url: str = "", src: str = "", shop: str = ""):
    """購入/アフィリンクのクリック計測（自己クリックはクライアント側で除外）。
    shop（メーカー/店舗）はメーカー別のクリック分析に使う。"""
    _site.log_track({"id": id, "type": type, "url": url, "src": src, "shop": shop})
    return Response(status_code=204)


@app.get("/robots.txt")
def robots():
    """検索エンジン向けクロール許可＋sitemapの提示（私的版=ACCESS_TOKEN時は全拒否）。"""
    return Response(_site.robots_txt(), media_type="text/plain; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/sitemap.xml")
def sitemap():
    """トップ・法務ページ・全LPを列挙する sitemap（SITE_BASE_URL 基準）。"""
    return Response(_site.sitemap_xml(_app_lastmod()), media_type="application/xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/lp/{slug}", response_class=HTMLResponse)
def landing(slug: str):
    """検索意図別ランディングページ（サーバーレンダリング・GA4対応）。"""
    page = _site.landing_html(slug, os.path.join(APP_DIR, "lp-assets"))
    if page is None:
        raise HTTPException(status_code=404, detail="not found")
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/lp-assets/{name}")
def lp_asset(name: str):
    """LP用画像（ヒーロー写真／before-afterキャプチャ）。lp-assets/ に置いたファイルを配信。"""
    res = _site.lp_asset(os.path.join(APP_DIR, "lp-assets"), name)
    if res is None:
        raise HTTPException(status_code=404, detail="not found")
    data, ctype = res
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


def _app_lastmod():
    """room-studio.html の更新日時（YYYY-MM-DD）。sitemap の <lastmod> に使う。"""
    try:
        return time.strftime("%Y-%m-%d", time.localtime(
            os.path.getmtime(os.path.join(APP_DIR, "room-studio.html"))))
    except Exception:
        return None


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
    path = os.path.join(APP_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="not found")
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/og.png")
def og_png():
    """OGP画像（SNSシェア用カード）。"""
    return _png("og.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return _png("apple-touch-icon.png")


# ---- アプリ本体（room-studio.html）を同一オリジンで配信 ----
@app.get("/", response_class=HTMLResponse)
@app.get("/room-studio.html", response_class=HTMLResponse)
def index():
    path = os.path.join(APP_DIR, "room-studio.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>room-studio.html が見つかりません</h1>"
                            "<p>server.py と同じフォルダに置いてください。</p>", status_code=404)
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(_site.render_app_html(f.read()),
                            headers={"Cache-Control": "no-cache, max-age=0, must-revalidate"})


if __name__ == "__main__":
    print(f"Room Studio: http://127.0.0.1:{PORT}  を開いてください")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
