#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Room Studio — ローカル AI 補完サーバー（LaMa / CPU対応）

これは「消しゴム」を Photoshop の「コンテンツに応じた塗りつぶし」相当の品質にするための
ローカルサーバーです。GPU が無くても CPU で動きます（初回はモデルを自動ダウンロード）。

使い方:
    pip install -r requirements.txt
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
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from PIL import Image
import numpy as np
import os
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
    return {"inpaint": _check_import(), "model": "lama", "loaded": _model is not None}


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


# ---- アプリ本体（room-studio.html）を同一オリジンで配信 ----
@app.get("/", response_class=HTMLResponse)
@app.get("/room-studio.html", response_class=HTMLResponse)
def index():
    path = os.path.join(APP_DIR, "room-studio.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>room-studio.html が見つかりません</h1>"
                            "<p>server.py と同じフォルダに置いてください。</p>", status_code=404)
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    print(f"Room Studio: http://127.0.0.1:{PORT}  を開いてください")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
