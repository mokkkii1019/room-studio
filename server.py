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


# ---- ネットから家具画像を収集（楽天市場 商品検索API：家具店の商品写真） ----
# 設定方法は2通り（どちらでも可）:
#   1) このフォルダの .env ファイルに記載（.env.example をコピーして作成）
#   2) OSの環境変数に設定
# 無料の楽天アプリID取得: https://webservice.rakuten.co.jp/
def _load_dotenv():
    """server.py と同じフォルダの .env を読み、未設定の環境変数だけ補完する（KEY=VALUE 形式）。"""
    path = os.path.join(APP_DIR, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as e:  # noqa: BLE001
        print(".env の読み込みに失敗:", e)


_load_dotenv()
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID", "").strip()          # アプリケーションID（UUID）
RAKUTEN_ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()  # アクセスキー（新仕様で必須）
RAKUTEN_AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip()
# 新APIは Referer と Origin（許可されたWebサイトに一致）が必須。既定: github.com
RAKUTEN_REFERER = os.environ.get("RAKUTEN_REFERER", "https://github.com/").strip()
_rp = urllib.parse.urlsplit(RAKUTEN_REFERER)
RAKUTEN_ORIGIN = os.environ.get("RAKUTEN_ORIGIN", "").strip() or (
    f"{_rp.scheme}://{_rp.netloc}" if _rp.scheme and _rp.netloc else "https://github.com")
RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
INTERIOR_GENRE = "100804"  # インテリア・寝具・収納（人物/風景の混入が少ない商品写真）

# 種類キー -> (検索キーワード, ジャンルID or None)。フロントの選択肢と一致させる。
TYPE_QUERY = {
    "chair": ("椅子 チェア", INTERIOR_GENRE),
    "dining_table": ("ダイニングテーブル", INTERIOR_GENRE),
    "sofa": ("ソファ", INTERIOR_GENRE),
    "bed": ("ベッド フレーム", INTERIOR_GENRE),
    "coffee_table": ("ローテーブル センターテーブル", INTERIOR_GENRE),
    "lampshade": ("ランプシェード", INTERIOR_GENRE),
    "table_lamp": ("テーブルランプ", INTERIOR_GENRE),
    "carpet": ("ラグ カーペット", INTERIOR_GENRE),
    "plant": ("観葉植物", None),  # 家具ジャンル外
    "chest": ("サイドボード キャビネット", INTERIOR_GENRE),
    "art": ("アートポスター 絵画 ウォールアート", INTERIOR_GENRE),
    "floor_lamp": ("フロアランプ スタンドライト", INTERIOR_GENRE),
    "mirror": ("鏡 ミラー", INTERIOR_GENRE),
    "shelf": ("シェルフ 棚 オープンシェルフ ラック", INTERIOR_GENRE),
    "cushion": ("クッション ブランケット スロー", INTERIOR_GENRE),
}

# 種類キー -> タイトルに「いずれか」を含む必要がある語（関係ないカテゴリの混入を除去）。
TYPE_MATCH = {
    "chair": ["椅子", "チェア", "いす", "chair", "スツール", "stool", "アームチェア"],
    "dining_table": ["ダイニングテーブル", "ダイニング", "dining"],
    "sofa": ["ソファ", "ソファー", "sofa", "カウチ", "couch", "ラブソファ"],
    "bed": ["ベッド", "bed", "ベットフレーム", "ベッドフレーム"],
    "coffee_table": ["ローテーブル", "コーヒーテーブル", "センターテーブル", "リビングテーブル", "coffee table"],
    "lampshade": ["ランプシェード", "シェード", "lampshade", "ペンダントライト", "ペンダントランプ"],
    "table_lamp": ["テーブルランプ", "デスクランプ", "テーブルライト", "table lamp", "デスクライト"],
    "carpet": ["ラグ", "カーペット", "rug", "絨毯", "じゅうたん", "ラグマット"],
    "plant": ["観葉植物", "フェイクグリーン", "人工観葉", "造花", "グリーン", "plant", "ボタニカル"],
    "chest": ["サイドボード", "キャビネット", "チェスト", "sideboard", "cabinet", "収納棚"],
    "art": ["アート", "ポスター", "絵画", "ウォール", "パネル", "art", "poster", "ファブリックパネル"],
    "floor_lamp": ["フロアランプ", "フロアライト", "スタンドライト", "floor lamp", "フロアスタンド"],
    "mirror": ["ミラー", "鏡", "mirror", "姿見"],
    "shelf": ["シェルフ", "棚", "ラック", "shelf", "rack", "ウォールシェルフ", "本棚"],
    "cushion": ["クッション", "ブランケット", "スロー", "cushion", "blanket", "throw", "ひざ掛け", "膝掛け", "ピロー", "枕"],
}
# どの種類でも除外したいアクセサリ/部品系の語（本体ではない）。
TYPE_EXCLUDE = ["カバー", "ケース", "リペア", "交換用", "替えカバー", "脚のみ", "脚単品", "パーツ", "ステッカー", "シール"]


def _numbered_variants(url, maxn):
    """画像URL末尾の連番（…-1.jpg / …-21a.jpg 等）を 1..maxn の素直な連番に振り直したURL列を返す。
    楽天の代表画像は -1,-2,-3 とは限らない（-21a 等のことも）ため、主要画像になりやすい小さい連番を補完する。"""
    m = re.match(r'^(.*[^\d])(\d+)([a-zA-Z]*)(\.\w+)(\?.*)?$', url)
    if not m:
        return []
    pre, _num, _sfx, ext, q = m.group(1), m.group(2), m.group(3), m.group(4), (m.group(5) or "")
    return [f"{pre}{n}{ext}{q}" for n in range(1, maxn + 1)]


def _relevant(title, type_):
    """商品名が指定カテゴリに合致するか（混入除去）。"""
    t = (title or "").lower()
    if not t:
        return False
    if any(x.lower() in t for x in TYPE_EXCLUDE):
        return False
    inc = TYPE_MATCH.get(type_)
    if not inc:
        return True
    return any(k.lower() in t for k in inc)


# ---- IKEA 公式サイトの検索（フロントが使う商品検索JSON。APIキー不要） ----
# 注: スクレイピングは各社規約/robots に抵触しうる。個人利用・低頻度・UA明示で運用する想定。
IKEA_ENDPOINT = "https://sik.search.blue.cdtapps.com/jp/ja/search-result-page"
IKEA_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoomStudio/1.0 (personal room-preview)"
IKEA_TYPE_KW = {
    "chair": "チェア", "dining_table": "ダイニングテーブル", "sofa": "ソファ", "bed": "ベッド",
    "coffee_table": "コーヒーテーブル", "lampshade": "ランプシェード", "table_lamp": "テーブルランプ",
    "carpet": "ラグ カーペット", "plant": "観葉植物", "chest": "サイドボード", "art": "アート ポスター",
    "floor_lamp": "フロアランプ", "mirror": "ミラー 鏡", "shelf": "シェルフ 棚",
    "cushion": "クッション ブランケット",
}


def _collect_ikea(type_: str, taste: str, count: int):
    kw = IKEA_TYPE_KW.get(type_, type_)
    q = (taste.strip() + " " + kw).strip()
    params = {"q": q, "size": max(1, min(100, count * 2)), "types": "PRODUCT", "c": "sr", "v": "20210322"}
    url = IKEA_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": IKEA_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8"))
    main = (((data.get("searchResultPage") or {}).get("products") or {}).get("main") or {})
    items, seen = [], set()
    for w in (main.get("items") or []):
        p = w.get("product") or {}
        pid = p.get("id") or p.get("itemNo")
        img = p.get("mainImageUrl") or p.get("imageUrl")
        if not pid or pid in seen or not img:
            continue
        seen.add(pid)
        # IKEAは品名(EKTORP等)に種類が出ないため typeName/説明も合わせて関連判定
        desc = " ".join(str(p.get(k) or "") for k in ("name", "typeName", "itemMeasureReferenceText", "mainImageAlt"))
        if not _relevant(desc, type_):
            continue
        price = (p.get("salesPrice") or {}).get("numeral") or 0
        items.append({
            "id": str(pid),
            "title": ((p.get("name") or "") + " " + (p.get("typeName") or "")).strip()[:80] or kw,
            "proxy": "/imgproxy?url=" + urllib.parse.quote(img, safe=""),
            "link": p.get("pipUrl") or "",
            "price": price,
            "shop": "IKEA",
        })
        if len(items) >= count:
            break
    return items


@app.get("/collect")
def collect(type: str, taste: str = "", count: int = 50, source: str = "ikea", shop: str = ""):
    """家具店の商品を種類＋テイストで検索し、画像プロキシURL＋商品ページリンク付きで返す。"""
    count = max(1, min(90, int(count)))
    try:
        if source == "artofblack":
            items = _collect_rakuten(type, taste, count, "artofblack")  # ART OF BLACK 楽天店
        elif source == "rakuten":
            items = _collect_rakuten(type, taste, count, shop)
        else:
            items = _collect_ikea(type, taste, count)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"収集に失敗: {e}")
    return {"source": source, "count": len(items), "items": items}


def _collect_rakuten(type_: str, taste: str, count: int, shop: str = ""):
    """楽天市場 商品検索API（新仕様）。applicationId(UUID) と accessKey が必要。"""
    if not RAKUTEN_APP_ID or not RAKUTEN_ACCESS_KEY:
        raise HTTPException(
            status_code=503,
            detail="RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY が必要です。https://webservice.rakuten.co.jp/ の"
                   "アプリ一覧で「アプリケーションID」と「アクセスキー」を確認し、.env に両方設定して再起動してください。",
        )
    kw, genre = TYPE_QUERY.get(type_, (type_, None))
    keyword = (taste.strip() + " " + kw).strip()
    items, seen, page = [], set(), 1
    while len(items) < count and page <= 5:  # 楽天は30件/ページ
        if page > 1:
            time.sleep(1.0)  # スロットル: API呼び出しを 1 QPS 以下に保つ（楽天の推奨/規約 第7条3項）
        params = {
            "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY, "keyword": keyword,
            "hits": 30, "page": page, "imageFlag": 1, "format": "json", "sort": "standard",
        }
        if genre and not shop.strip():
            params["genreId"] = genre  # 特定店舗指定時はジャンルで絞りすぎないよう外す
        if shop.strip():
            params["shopCode"] = shop.strip()
        if RAKUTEN_AFFILIATE_ID:
            params["affiliateId"] = RAKUTEN_AFFILIATE_ID
        url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
        # 新APIは「許可されたWebサイト」に一致する Referer と Origin が必須
        req = urllib.request.Request(url, headers={"User-Agent": "RoomStudio/1.0", "Referer": RAKUTEN_REFERER, "Origin": RAKUTEN_ORIGIN})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if items:
                break
            raise HTTPException(status_code=502, detail=f"楽天検索に失敗 (HTTP {e.code}): {body}")
        except Exception as e:  # noqa: BLE001
            if items:
                break
            raise HTTPException(status_code=502, detail=f"楽天検索に失敗: {e}")
        arr = data.get("Items", []) or []
        if not arr:
            break
        for w in arr:
            it = w.get("Item", w)
            code = it.get("itemCode")
            if not code or code in seen:
                continue
            seen.add(code)
            if not _relevant(it.get("itemName"), type_):  # 関係ないカテゴリの混入を除去
                continue
            imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
            raw = []
            for im in imgs[:3]:
                u = im.get("imageUrl") if isinstance(im, dict) else None
                if u:
                    raw.append(u.replace("?_ex=128x128", "?_ex=600x600").replace("?_ex=64x64", "?_ex=600x600"))
            if not raw:
                continue
            # Item Search は先頭3枚しか返さない。商品ページには連番画像(-1,-2,…)が多数あり、
            # その中に「単体・正面」の使いやすい1枚があることが多いので連番URLを補完して候補に加える。
            merged, seen_u = [], set()
            for u in raw + _numbered_variants(raw[0], 9):
                k = u.split("?")[0]
                if k in seen_u:
                    continue
                seen_u.add(k)
                merged.append(u)
            cands = ["/imgproxy?url=" + urllib.parse.quote(u, safe="") for u in merged[:10]]  # クライアントが最良の1枚を選ぶ
            items.append({
                "id": code,
                "title": (it.get("itemName") or kw)[:80],
                "proxy": cands[0],
                "cands": cands,
                "link": it.get("affiliateUrl") or it.get("itemUrl") or "",
                "price": it.get("itemPrice") or 0,
                "shop": it.get("shopName") or "",
            })
            if len(items) >= count:
                break
        page += 1
    return items


@app.get("/imgproxy")
def imgproxy(url: str):
    """外部画像を同一オリジンで中継（キャンバス汚染を防ぐ）。"""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="invalid url")
    req = urllib.request.Request(url, headers={"User-Agent": "RoomStudio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            ctype = r.headers.get("Content-Type", "image/jpeg")
            if "image" not in ctype:
                raise HTTPException(status_code=415, detail="not an image")
            data = r.read(14 * 1024 * 1024)  # 上限 14MB
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"画像取得に失敗: {e}")
    return Response(content=data, media_type=ctype,
                    headers={"Cache-Control": "public, max-age=86400"})


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
