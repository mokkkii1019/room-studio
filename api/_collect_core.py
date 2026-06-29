# -*- coding: utf-8 -*-
"""
Room Studio — collection + image-proxy core (standard library only).

Single source of truth for the furniture-collection (IKEA / Rakuten / ART OF BLACK)
and same-origin image relay logic. Imported by BOTH:
  - the local FastAPI dev server (server.py, which also has the heavy LaMa /inpaint)
  - the Vercel serverless functions (api/collect.py, api/imgproxy.py)

No third-party imports here so it runs on Vercel's Python runtime with no deps.
"""

import os
import re
import json
import time
import urllib.parse
import urllib.request
import urllib.error

APP_DIR = os.path.dirname(os.path.abspath(__file__))


class CollectError(Exception):
    """Carries an HTTP status + message for the adapters to surface."""
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _load_dotenv():
    """Load KEY=VALUE from a local .env (project root or this dir) into os.environ
    without overriding already-set vars. No-op on Vercel (env vars are injected)."""
    for path in (os.path.join(APP_DIR, ".env"), os.path.join(os.path.dirname(APP_DIR), ".env")):
        if not os.path.exists(path):
            continue
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
            print(".env load failed:", e)


_load_dotenv()
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID", "").strip()          # applicationId (UUID)
RAKUTEN_ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()  # accessKey (required by new API)
RAKUTEN_AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip()
# new API requires Referer + Origin matching the registered "allowed website"
RAKUTEN_REFERER = os.environ.get("RAKUTEN_REFERER", "https://github.com/").strip()
_rp = urllib.parse.urlsplit(RAKUTEN_REFERER)
RAKUTEN_ORIGIN = os.environ.get("RAKUTEN_ORIGIN", "").strip() or (
    f"{_rp.scheme}://{_rp.netloc}" if _rp.scheme and _rp.netloc else "https://github.com")
RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
INTERIOR_GENRE = "100804"  # interior / bedding / storage (fewer people/scenery shots)

# type key -> (search keyword, genreId or None). Must match the frontend's <select>.
TYPE_QUERY = {
    "chair": ("椅子 チェア", INTERIOR_GENRE),
    "dining_table": ("ダイニングテーブル", INTERIOR_GENRE),
    "sofa": ("ソファ", INTERIOR_GENRE),
    "bed": ("ベッド フレーム", INTERIOR_GENRE),
    "coffee_table": ("ローテーブル センターテーブル", INTERIOR_GENRE),
    "lampshade": ("ランプシェード", INTERIOR_GENRE),
    "table_lamp": ("テーブルランプ", INTERIOR_GENRE),
    "carpet": ("ラグ カーペット", INTERIOR_GENRE),
    "plant": ("観葉植物", None),
    "chest": ("サイドボード キャビネット", INTERIOR_GENRE),
    "art": ("アートポスター 絵画 ウォールアート", INTERIOR_GENRE),
    "floor_lamp": ("フロアランプ スタンドライト", INTERIOR_GENRE),
    "mirror": ("鏡 ミラー", INTERIOR_GENRE),
    "shelf": ("シェルフ 棚 オープンシェルフ ラック", INTERIOR_GENRE),
    "cushion": ("クッション ブランケット スロー", INTERIOR_GENRE),
}

# type key -> title must contain ANY of these (drops off-category items).
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
# accessory/parts words to drop regardless of type (not the item itself).
TYPE_EXCLUDE = ["カバー", "ケース", "リペア", "交換用", "替えカバー", "脚のみ", "脚単品", "パーツ", "ステッカー", "シール"]

# IKEA storefront search (frontend-style product search JSON, no API key).
IKEA_ENDPOINT = "https://sik.search.blue.cdtapps.com/jp/ja/search-result-page"
IKEA_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoomStudio/1.0 (personal room-preview)"
IKEA_TYPE_KW = {
    "chair": "チェア", "dining_table": "ダイニングテーブル", "sofa": "ソファ", "bed": "ベッド",
    "coffee_table": "コーヒーテーブル", "lampshade": "ランプシェード", "table_lamp": "テーブルランプ",
    "carpet": "ラグ カーペット", "plant": "観葉植物", "chest": "サイドボード", "art": "アート ポスター",
    "floor_lamp": "フロアランプ", "mirror": "ミラー 鏡", "shelf": "シェルフ 棚",
    "cushion": "クッション ブランケット",
}

# /imgproxy is a same-origin relay (avoids canvas tainting). On a PUBLIC deployment it
# must NOT be an open relay, so only the furniture image hosts are allowed.
IMG_HOST_SUFFIXES = ("ikea.com", "cdtapps.com", "rakuten.co.jp", "r10s.jp", "shopify.com", "rughaus.jp", "kanademono.design")


def _numbered_variants(url, maxn):
    """Re-number a trailing image index (…-1.jpg / …-21a.jpg) to a plain 1..maxn.
    Rakuten's representative images aren't always -1..-3, so this surfaces the
    small-index main/front shots that tend to be the cleanest single-item photos."""
    m = re.match(r'^(.*[^\d])(\d+)([a-zA-Z]*)(\.\w+)(\?.*)?$', url)
    if not m:
        return []
    pre, _num, _sfx, ext, q = m.group(1), m.group(2), m.group(3), m.group(4), (m.group(5) or "")
    return [f"{pre}{n}{ext}{q}" for n in range(1, maxn + 1)]


def _relevant(title, type_):
    """Does the product title match the requested category (drops mismatches)?"""
    t = (title or "").lower()
    if not t:
        return False
    if any(x.lower() in t for x in TYPE_EXCLUDE):
        return False
    inc = TYPE_MATCH.get(type_)
    if not inc:
        return True
    return any(k.lower() in t for k in inc)


def _collect_ikea(type_, taste, count):
    kw = IKEA_TYPE_KW.get(type_, type_)
    q = (taste.strip() + " " + kw).strip()
    params = {"q": q, "size": max(1, min(100, count * 2)), "types": "PRODUCT", "c": "sr", "v": "20210322"}
    url = IKEA_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": IKEA_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
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


def _collect_rakuten(type_, taste, count, shop="", referer=None):
    """Rakuten Ichiba Item Search (new API). Needs applicationId(UUID) + accessKey.
    The new API requires Referer/Origin matching a registered 'allowed website'.
    `referer` (the request's own origin) is preferred so a public deployment works
    without a RAKUTEN_REFERER env var; falls back to the env value for local dev."""
    if not RAKUTEN_APP_ID or not RAKUTEN_ACCESS_KEY:
        raise CollectError(503,
            "RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY が必要です。https://webservice.rakuten.co.jp/ の"
            "アプリ一覧で「アプリケーションID」と「アクセスキー」を確認し設定してください。")
    ref = (referer or RAKUTEN_REFERER)
    _u = urllib.parse.urlsplit(ref)
    origin = f"{_u.scheme}://{_u.netloc}" if _u.scheme and _u.netloc else RAKUTEN_ORIGIN
    kw, genre = TYPE_QUERY.get(type_, (type_, None))
    keyword = (taste.strip() + " " + kw).strip()
    items, seen, page = [], set(), 1
    while len(items) < count and page <= 3:  # 30 items/page; capped for serverless time limits
        if page > 1:
            time.sleep(1.0)  # throttle to <= 1 QPS (Rakuten guideline)
        params = {
            "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY, "keyword": keyword,
            "hits": 30, "page": page, "imageFlag": 1, "format": "json", "sort": "standard",
        }
        if genre and not shop.strip():
            params["genreId"] = genre
        if shop.strip():
            params["shopCode"] = shop.strip()
        if RAKUTEN_AFFILIATE_ID:
            params["affiliateId"] = RAKUTEN_AFFILIATE_ID
        url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "User-Agent": "RoomStudio/1.0", "Referer": ref, "Origin": origin})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if items:
                break
            raise CollectError(502, f"楽天検索に失敗 (HTTP {e.code}): {body}")
        except Exception as e:  # noqa: BLE001
            if items:
                break
            raise CollectError(502, f"楽天検索に失敗: {e}")
        arr = data.get("Items", []) or []
        if not arr:
            break
        for w in arr:
            it = w.get("Item", w)
            code = it.get("itemCode")
            if not code or code in seen:
                continue
            seen.add(code)
            if not _relevant(it.get("itemName"), type_):
                continue
            imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
            raw = []
            for im in imgs[:3]:
                u = im.get("imageUrl") if isinstance(im, dict) else None
                if u:
                    raw.append(u.replace("?_ex=128x128", "?_ex=600x600").replace("?_ex=64x64", "?_ex=600x600"))
            if not raw:
                continue
            merged, seen_u = [], set()
            for u in raw + _numbered_variants(raw[0], 9):
                k = u.split("?")[0]
                if k in seen_u:
                    continue
                seen_u.add(k)
                merged.append(u)
            cands = ["/imgproxy?url=" + urllib.parse.quote(u, safe="") for u in merged[:10]]
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


def _collect_shopify(type_, taste, count, base, shop_name):
    """Shopify storefront (e.g. RUGHAUS = rughaus.jp). Uses the public /products.json
    (no key). Shopify has no keyword search, so fetch pages and filter by category/taste."""
    inc = TYPE_MATCH.get(type_)
    tl = (taste or "").strip().lower()
    items, seen, page = [], set(), 1
    while len(items) < count and page <= 6:
        url = base.rstrip("/") + "/products.json?limit=250&page=" + str(page)
        req = urllib.request.Request(url, headers={"User-Agent": IKEA_UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if items:
                break
            raise CollectError(502, f"{shop_name}取得に失敗: {e}")
        prods = data.get("products") or []
        if not prods:
            break
        for p in prods:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            title = p.get("title") or ""
            tags = p.get("tags") or []
            tagstr = " ".join(tags) if isinstance(tags, list) else str(tags)
            hay = (title + " " + (p.get("product_type") or "") + " " + tagstr).lower()
            if inc and not any(k.lower() in hay for k in inc):
                continue  # not this category
            if tl and tl not in hay and tl not in (p.get("body_html") or "").lower():
                continue  # taste keyword not matched
            cand_urls = []
            for im in (p.get("images") or [])[:8]:
                u = im.get("src") if isinstance(im, dict) else None
                if u:
                    cand_urls.append(u)
            if not cand_urls:
                continue
            price = 0
            vs = p.get("variants") or []
            if vs:
                try:
                    price = int(float(vs[0].get("price") or 0))
                except Exception:  # noqa: BLE001
                    price = 0
            cands = ["/imgproxy?url=" + urllib.parse.quote(u, safe="") for u in cand_urls[:10]]
            items.append({
                "id": str(pid),
                "title": title[:80] or type_,
                "proxy": cands[0], "cands": cands,
                "link": base.rstrip("/") + "/products/" + (p.get("handle") or ""),
                "price": price,
                "shop": shop_name,
            })
            if len(items) >= count:
                break
        page += 1
    return items


def collect(type_, taste="", count=50, source="ikea", shop="", referer=None):
    """Dispatch a collection request. Returns the response dict. Raises CollectError.
    `referer` (the request's own origin) lets the Rakuten call match the deployed domain."""
    count = max(1, min(90, int(count)))
    try:
        if source == "rughaus":
            items = _collect_shopify(type_, taste, count, "https://rughaus.jp", "RUGHAUS")
        elif source == "kanademono":
            items = _collect_shopify(type_, taste, count, "https://kanademono.design", "KANADEMONO")
        elif source == "artofblack":
            items = _collect_rakuten(type_, taste, count, "artofblack", referer)
        elif source == "rakuten":
            items = _collect_rakuten(type_, taste, count, shop, referer)
        else:
            items = _collect_ikea(type_, taste, count)
    except CollectError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"収集に失敗: {e}")
    return {"source": source, "count": len(items), "items": items}


def _host_allowed(url):
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(host == s or host.endswith("." + s) for s in IMG_HOST_SUFFIXES)


def imgproxy_fetch(url):
    """Relay an external furniture image (same-origin, to avoid canvas tainting).
    Returns (bytes, content_type). Raises CollectError. Allowlisted hosts only."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise CollectError(400, "invalid url")
    if not _host_allowed(url):
        raise CollectError(400, "host not allowed")
    req = urllib.request.Request(url, headers={"User-Agent": "RoomStudio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            ctype = r.headers.get("Content-Type", "image/jpeg")
            if "image" not in ctype:
                raise CollectError(415, "not an image")
            data = r.read(14 * 1024 * 1024)  # 14 MB cap
    except CollectError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"画像取得に失敗: {e}")
    return data, ctype
