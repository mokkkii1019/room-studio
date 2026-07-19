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
import re
import time
import urllib.parse
import urllib.request
import urllib.error

import _provider_base as base
from _provider_base import CollectError, _relevant

PROVIDER_NAME = "official"

# ---- Rakuten config (env; loaded via _provider_base._load_dotenv) ------------
RAKUTEN_APP_ID = os.environ.get("RAKUTEN_APP_ID", "").strip()          # applicationId (UUID)
RAKUTEN_ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()  # accessKey (required by new API)
# 楽天アフィリエイトID。必ずリクエストに含める（未指定だと affiliateUrl が hb.afl の
# アフィリンクにならず、rafcid にアプリIDが入る＝報酬が発生しない）。既定値を埋め込み、
# 環境変数 RAKUTEN_AFFILIATE_ID で上書き可（アフィリIDは公開情報＝秘密ではない）。
RAKUTEN_AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID", "553d27b1.3fab40d2.553d27b2.4375e9f6").strip()
# new API requires Referer + Origin matching the registered "allowed website"
RAKUTEN_REFERER = os.environ.get("RAKUTEN_REFERER", "https://github.com/").strip()
_rp = urllib.parse.urlsplit(RAKUTEN_REFERER)
RAKUTEN_ORIGIN = os.environ.get("RAKUTEN_ORIGIN", "").strip() or (
    f"{_rp.scheme}://{_rp.netloc}" if _rp.scheme and _rp.netloc else "https://github.com")
RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
INTERIOR_GENRE = "100804"  # interior / bedding / storage (fewer people/scenery shots)

# type key -> (search keyword, genreId or None). Must match the frontend's category tree.
# 家電(appliance) は楽天の家電ジャンルIDに縛らず genre=None の全体キーワード検索にして確実に結果を返し、
# カテゴリ精度は TYPE_MATCH / TYPE_EXCLUDE_BY_TYPE の語で担保する（インテリアジャンル固定だと家電が0件になるため）。
TYPE_QUERY = {
    # --- 家具 furniture ---
    "chair": ("椅子 チェア", INTERIOR_GENRE),
    "dining_table": ("ダイニングテーブル", INTERIOR_GENRE),
    "sofa": ("ソファ", INTERIOR_GENRE),
    "bed": ("ベッド フレーム", INTERIOR_GENRE),
    "coffee_table": ("ローテーブル リビングテーブル センターテーブル", INTERIOR_GENRE),
    "chest": ("サイドボード リビングボード キャビネット", INTERIOR_GENRE),
    "shelf": ("シェルフ 棚 オープンシェルフ ラック", INTERIOR_GENRE),
    "desk": ("デスク 机 パソコンデスク 学習机", INTERIOR_GENRE),
    # --- 家電 home appliances (genre=None: 楽天全体をキーワード検索) ---
    "tv": ("テレビ 液晶テレビ", None),
    "refrigerator": ("冷蔵庫", None),
    "washing_machine": ("洗濯機 ドラム式洗濯機", None),
    "air_conditioner": ("エアコン ルームエアコン", None),
    "microwave": ("電子レンジ オーブンレンジ", None),
    "rice_cooker": ("炊飯器", None),
    "air_purifier": ("空気清浄機", None),
    "fan": ("扇風機 サーキュレーター", None),
    "humidifier": ("加湿器", None),
    "vacuum": ("掃除機 コードレスクリーナー", None),
    # --- 日用品・インテリア雑貨 daily goods / accessories ---
    "carpet": ("ラグ カーペット", INTERIOR_GENRE),
    "curtain": ("カーテン ドレープカーテン 遮光カーテン", INTERIOR_GENRE),
    "table_lamp": ("テーブルランプ", INTERIOR_GENRE),
    "floor_lamp": ("フロアランプ スタンドライト", INTERIOR_GENRE),
    "lampshade": ("ランプシェード ペンダントライト", INTERIOR_GENRE),
    "plant": ("観葉植物", None),
    "art": ("アートポスター 絵画 ウォールアート", INTERIOR_GENRE),
    "mirror": ("鏡 ミラー", INTERIOR_GENRE),
    "cushion": ("クッション ブランケット スロー", INTERIOR_GENRE),
    "clock": ("掛け時計 置き時計 ウォールクロック", None),
    "storage_box": ("収納ボックス 収納ケース 収納バスケット", INTERIOR_GENRE),
    "trash_can": ("ゴミ箱 ダストボックス くずかご", None),
    # --- 表面素材（壁紙・床）: 収集画像をシームレス素材化して塗る ---
    "wallpaper": ("壁紙 クロス", INTERIOR_GENRE),
    "floor_tile": ("フロアタイル フローリング 床材", INTERIOR_GENRE),
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
    """Rakuten item -> ordered list of raw candidate image URLs (600x600, deduped).

    Only the URLs Rakuten actually returned. We used to append _numbered_variants()
    guesses on top, hoping to surface cleaner front shots; measured against live
    Rakuten data that produced 105 guessed URLs per 20 items to find 9 that existed
    (91% 404). The client loaded every one of them before it could show anything, so
    the guesses were most of the collect-time wait and bought almost no extra choice.
    """
    imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
    merged, seen_u = [], set()
    for im in imgs:
        u = im.get("imageUrl") if isinstance(im, dict) else None
        if not u:
            continue
        u = u.replace("?_ex=128x128", "?_ex=600x600").replace("?_ex=64x64", "?_ex=600x600")
        k = u.split("?")[0]
        if k in seen_u:
            continue
        seen_u.add(k)
        merged.append(u)
    return merged[:6]


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


# Words handed to Rakuten's own NGKeyword so accessories never come back in the first
# place. Filtering them locally works too (TYPE_EXCLUDE_BY_TYPE still does, as a safety
# net) but wastes the page: a `tv` search returned 25/30 screen-protector films, so
# local-only filtering starved the result set and forced extra pages.
# Semantics verified against the live API (2026-07-19): a space-separated list is
# OR-of-exclusions — an item is dropped if it contains ANY of the words.
TYPE_NG = {
    "tv": "フィルム 保護パネル",
    "washing_machine": "毛ごみ 糸くず ゴミ取り 乾燥フィルター",
    "vacuum": "掃除機スタンド クリーナースタンド ツールステーション",
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
        ng = TYPE_NG.get(type_)
        if ng:
            params["NGKeyword"] = ng
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


def search_shops(query, type_="", referer=None):
    """楽天の全ショップから、query に一致するショップ（メーカー/店舗）を探す。

    楽天Ichibaに「店舗名検索API」は無いため、商品検索（IchibaItem/Search）の結果に含まれる
    shopCode / shopName を集計し、出現頻度の高い順に distinct なショップを返す。カテゴリ(type_)の
    ジャンルで軽く絞る。戻り値: [{code, name, count}]（最大20件）。"""
    _require_keys()
    q = (query or "").strip()
    if not q:
        return []
    _, genre = TYPE_QUERY.get(type_, ("", None))
    params = {
        "applicationId": RAKUTEN_APP_ID, "accessKey": RAKUTEN_ACCESS_KEY, "keyword": q,
        "hits": 30, "page": 1, "imageFlag": 1, "format": "json", "sort": "standard",
    }
    if genre:
        params["genreId"] = genre
    if RAKUTEN_AFFILIATE_ID:
        params["affiliateId"] = RAKUTEN_AFFILIATE_ID
    url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers(referer))
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        raise CollectError(502, f"店舗検索に失敗 (HTTP {e.code}): {body}")
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"店舗検索に失敗: {e}")
    counts = {}  # shopCode -> [shopName, count]
    for w in data.get("Items", []) or []:
        it = w.get("Item", w)
        code = it.get("shopCode")
        if not code:  # fallback: itemCode is "shopCode:itemId"
            ic = it.get("itemCode") or ""
            code = ic.split(":", 1)[0] if ":" in ic else ""
        if not code:
            continue
        name = it.get("shopName") or code
        # ふるさと納税（自治体）ショップは「メーカー選択」にそぐわないので除外
        if "納税" in name or "ふるさと" in name or re.search(r"[都道府県].*[市区町村]$", name):
            continue
        if code not in counts:
            counts[code] = [name, 0]
        counts[code][1] += 1
    shops = [{"code": c, "name": v[0], "count": v[1]} for c, v in counts.items()]
    shops.sort(key=lambda s: -s["count"])
    return shops[:20]


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
