# -*- coding: utf-8 -*-
"""Room Studio — OFFICIAL collection provider (public-safe, standard library only).

Uses the Rakuten Ichiba Item Search API (official, keyed). This is the ONLY provider
allowed in a public deployment: search / display / affiliate purchase links are free
and login-free for everyone (Rakuten TOS art.10(10)); monetization is affiliate-only;
displayed data is fetched live (never stored on our servers).

Amazon / Moshimo etc. can be added later as sibling functions; this phase ships Rakuten only.
"""

import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error

import _provider_base as base
from _provider_base import CollectError, _relevant, _numbered_variants

PROVIDER_NAME = "official"

# ---- Rakuten config (env; loaded via _provider_base._load_dotenv) ------------
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
    "coffee_table": ("ローテーブル リビングテーブル センターテーブル", INTERIOR_GENRE),
    "lampshade": ("ランプシェード", INTERIOR_GENRE),
    "table_lamp": ("テーブルランプ", INTERIOR_GENRE),
    "carpet": ("ラグ カーペット", INTERIOR_GENRE),
    "plant": ("観葉植物", None),
    "chest": ("サイドボード リビングボード キャビネット", INTERIOR_GENRE),
    "art": ("アートポスター 絵画 ウォールアート", INTERIOR_GENRE),
    "floor_lamp": ("フロアランプ スタンドライト", INTERIOR_GENRE),
    "mirror": ("鏡 ミラー", INTERIOR_GENRE),
    "shelf": ("シェルフ 棚 オープンシェルフ ラック", INTERIOR_GENRE),
    "cushion": ("クッション ブランケット スロー", INTERIOR_GENRE),
}


def imgproxy_hosts():
    """Allowed image host suffixes for /imgproxy — Rakuten's own image CDNs only."""
    return ("rakuten.co.jp", "r10s.jp")


def _require_keys():
    if not RAKUTEN_APP_ID or not RAKUTEN_ACCESS_KEY:
        raise CollectError(503,
            "RAKUTEN_APP_ID と RAKUTEN_ACCESS_KEY が必要です。https://webservice.rakuten.co.jp/ の"
            "アプリ一覧で「アプリケーションID」と「アクセスキー」を確認し設定してください。")


def _headers(referer):
    ref = (referer or RAKUTEN_REFERER)
    _u = urllib.parse.urlsplit(ref)
    origin = f"{_u.scheme}://{_u.netloc}" if _u.scheme and _u.netloc else RAKUTEN_ORIGIN
    return {"User-Agent": "RoomStudio/1.0", "Referer": ref, "Origin": origin}


def _raw_images(it):
    """Rakuten item -> ordered list of raw candidate image URLs (600x600, deduped)."""
    imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
    raw = []
    for im in imgs[:3]:
        u = im.get("imageUrl") if isinstance(im, dict) else None
        if u:
            raw.append(u.replace("?_ex=128x128", "?_ex=600x600").replace("?_ex=64x64", "?_ex=600x600"))
    if not raw:
        return []
    merged, seen_u = [], set()
    for u in raw + _numbered_variants(raw[0], 9):
        k = u.split("?")[0]
        if k in seen_u:
            continue
        seen_u.add(k)
        merged.append(u)
    return merged[:10]


def _normalize(it, kw=""):
    imgs = _raw_images(it)
    if not imgs:
        return None
    return {
        "name": (it.get("itemName") or kw)[:80],
        "price": it.get("itemPrice") or 0,
        "shop": it.get("shopName") or "",
        "productUrl": it.get("itemUrl") or "",
        "affiliateUrl": it.get("affiliateUrl") or it.get("itemUrl") or "",
        "imageUrl": imgs[0],
        "imageUrls": imgs,
        "itemCode": it.get("itemCode") or "",
        "source": "rakuten",
    }


def search(type_, taste="", count=50, shop="", referer=None):
    """Rakuten Ichiba Item Search. `shop` = optional Rakuten shopCode (e.g. a maker,
    'artofblack', …); empty = interior-genre keyword search."""
    _require_keys()
    kw, genre = TYPE_QUERY.get(type_, (type_, None))
    keyword = (taste.strip() + " " + kw).strip()
    headers = _headers(referer)
    items, seen, page = [], set(), 1
    while len(items) < count and page <= 3:  # 30 items/page; capped for serverless time limits
        if page > 1:
            time.sleep(1.0)  # throttle to <= 1 QPS (Rakuten guideline)
        params = {
            "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY, "keyword": keyword,
            "hits": 30, "page": page, "imageFlag": 1, "format": "json", "sort": "standard",
        }
        if genre and not (shop or "").strip():
            params["genreId"] = genre
        if (shop or "").strip():
            params["shopCode"] = shop.strip()
        if RAKUTEN_AFFILIATE_ID:
            params["affiliateId"] = RAKUTEN_AFFILIATE_ID
        url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
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
            norm = _normalize(it, kw)
            if not norm:
                continue
            items.append(norm)
            if len(items) >= count:
                break
        page += 1
    return items


def fetch_item(item_code, referer=None):
    """Re-fetch a single item by its Rakuten itemCode (for 'reference-only' re-hydration).
    Returns a normalized item or None."""
    _require_keys()
    if not item_code:
        return None
    params = {
        "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY,
        "itemCode": item_code, "hits": 1, "imageFlag": 1, "format": "json",
    }
    if RAKUTEN_AFFILIATE_ID:
        params["affiliateId"] = RAKUTEN_AFFILIATE_ID
    url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers(referer))
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"楽天商品取得に失敗: {e}")
    arr = data.get("Items", []) or []
    if not arr:
        return None
    return _normalize(arr[0].get("Item", arr[0]))
