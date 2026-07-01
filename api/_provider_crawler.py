# -*- coding: utf-8 -*-
"""Room Studio — CRAWLER collection provider (PRIVATE / self-hosted use only).

Scrapes public storefront endpoints that have NO official API key:
  - IKEA storefront search JSON
  - Shopify stores' public /products.json (RUGHAUS / KANADEMONO / BAUHAUS)

⚠️  This file must NOT be shipped to / run on the public (Vercel) deployment:
      1) it is excluded via .vercelignore, and
      2) get_provider() refuses to import it when APP_MODE=public (returns 403).
    It exists so the operator can collect for their own private use.

Standard library only (no third-party imports).
"""

import json
import urllib.parse
import urllib.request

import _provider_base as base
from _provider_base import CollectError, _relevant, TYPE_MATCH

PROVIDER_NAME = "crawler"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RoomStudio/1.0 (personal room-preview)"

# ---- IKEA storefront search (frontend-style product search JSON, no API key) --
IKEA_ENDPOINT = "https://sik.search.blue.cdtapps.com/jp/ja/search-result-page"
IKEA_TYPE_KW = {
    "chair": "チェア", "dining_table": "ダイニングテーブル", "sofa": "ソファ", "bed": "ベッド",
    "coffee_table": "コーヒーテーブル", "lampshade": "ランプシェード", "table_lamp": "テーブルランプ",
    "carpet": "ラグ カーペット", "plant": "観葉植物", "chest": "サイドボード", "art": "アート ポスター",
    "floor_lamp": "フロアランプ", "mirror": "ミラー 鏡", "shelf": "シェルフ 棚",
    "cushion": "クッション ブランケット",
}

# shop id -> (base url, display name) for the Shopify storefronts.
SHOPIFY_STORES = {
    "rughaus": ("https://rughaus.jp", "RUGHAUS"),
    "kanademono": ("https://kanademono.design", "KANADEMONO"),
    "bauhaus": ("https://officialbauhaus.jp", "BAUHAUS"),
}


def imgproxy_hosts():
    """Allowed image host suffixes for /imgproxy in private mode."""
    return ("ikea.com", "cdtapps.com", "shopify.com",
            "rughaus.jp", "kanademono.design", "officialbauhaus.jp")


def _ikea(type_, taste, count):
    kw = IKEA_TYPE_KW.get(type_, type_)
    q = (taste.strip() + " " + kw).strip()
    params = {"q": q, "size": max(1, min(100, count * 2)), "types": "PRODUCT", "c": "sr", "v": "20210322"}
    url = IKEA_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
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
            "name": ((p.get("name") or "") + " " + (p.get("typeName") or "")).strip()[:80] or kw,
            "price": price,
            "shop": "IKEA",
            "productUrl": p.get("pipUrl") or "",
            "affiliateUrl": p.get("pipUrl") or "",
            "imageUrl": img,
            "imageUrls": [img],
            "itemCode": str(pid),
            "source": "ikea",
        })
        if len(items) >= count:
            break
    return items


def _shopify(type_, taste, count, base_url, shop_name, source):
    """Shopify storefront: public /products.json (no key). No keyword search, so fetch
    pages and filter by category (TYPE_MATCH) + taste keyword."""
    inc = TYPE_MATCH.get(type_)
    tl = (taste or "").strip().lower()
    items, seen, page = [], set(), 1
    while len(items) < count and page <= 6:
        url = base_url.rstrip("/") + "/products.json?limit=250&page=" + str(page)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
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
            items.append({
                "name": title[:80] or type_,
                "price": price,
                "shop": shop_name,
                "productUrl": base_url.rstrip("/") + "/products/" + (p.get("handle") or ""),
                "affiliateUrl": base_url.rstrip("/") + "/products/" + (p.get("handle") or ""),
                "imageUrl": cand_urls[0],
                "imageUrls": cand_urls[:10],
                "itemCode": str(pid),
                "source": source,
            })
            if len(items) >= count:
                break
        page += 1
    return items


def search(type_, taste="", count=50, shop="", referer=None):
    """`shop` selects the storefront: 'ikea' (default) | 'rughaus' | 'kanademono' | 'bauhaus'."""
    store = (shop or "ikea").strip().lower()
    if store in SHOPIFY_STORES:
        base_url, name = SHOPIFY_STORES[store]
        return _shopify(type_, taste, count, base_url, name, store)
    return _ikea(type_, taste, count)


def fetch_item(item_code, referer=None):
    """Re-fetch a single item by bare id. Not supported for crawler storefronts in this
    phase (no stable per-id endpoint without the store context); returns None."""
    return None
