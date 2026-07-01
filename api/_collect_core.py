# -*- coding: utf-8 -*-
"""Room Studio — collection facade + image-proxy (standard library only).

This is the single entry point the endpoints (server.py / api/index.py) call. It picks a
*provider* (get_provider) and adapts its normalized items into the shape the frontend wants
(proxy / cands / link / …). No collection logic lives here anymore — see:

  - _provider_base.py     … CollectError, env switch, shared category filters
  - _provider_official.py … Rakuten official API   (PUBLIC-safe, always importable)
  - _provider_crawler.py  … IKEA / Shopify scrape   (PRIVATE only; not shipped to Vercel)

Provider switch:
  COLLECT_PROVIDER = 'official' | 'crawler'   (default 'official')
  APP_MODE         = 'public'   | 'private'    (default 'public')
  In 'public' mode the crawler is NEVER imported and is refused with 403, so the public
  deployment cannot run it even if COLLECT_PROVIDER=crawler is set.

No third-party imports (runs on Vercel's stdlib Python runtime).
"""

import urllib.parse
import urllib.request

import _provider_base as base
from _provider_base import CollectError, COLLECT_PROVIDER, APP_MODE, _load_dotenv  # noqa: F401

# Backward-compat re-exports (tools/check_makers.py reads these off `core`).
# Importing the official provider at module load is safe — it is the public default and
# only reads env into constants. The crawler is NOT imported here (kept lazy + gated).
import _provider_official as _official
from _provider_official import (  # noqa: F401
    RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY, RAKUTEN_ENDPOINT, INTERIOR_GENRE,
)


def get_provider(name=None):
    """Return the active collection provider module.

    `name` (optional) explicitly requests 'official' | 'crawler'; when omitted the
    COLLECT_PROVIDER env value is used. In APP_MODE=public the crawler is refused with a
    403 and — importantly — never imported, so its code cannot run on a public build.
    """
    requested = (name or COLLECT_PROVIDER or "official").strip().lower()
    if requested not in ("official", "crawler"):
        requested = "official"
    if requested == "crawler":
        if APP_MODE == "public":
            raise CollectError(403, "クローラ収集は非公開ビルド専用です（APP_MODE=public では無効）。"
                                    "公開版では正規API（official）のみ利用できます。")
        import _provider_crawler as prov  # lazy: never imported when APP_MODE=public
        return prov
    return _official


def _to_frontend(it):
    """Normalized provider item -> the shape room-studio.html expects (proxied images)."""
    imgs = it.get("imageUrls") or ([it["imageUrl"]] if it.get("imageUrl") else [])
    cands = ["/imgproxy?url=" + urllib.parse.quote(u, safe="") for u in imgs[:10]]
    return {
        "id": it.get("itemCode") or "",
        "title": (it.get("name") or "")[:80],
        "proxy": cands[0] if cands else "",
        "cands": cands,
        "link": it.get("affiliateUrl") or it.get("productUrl") or "",
        "price": it.get("price") or 0,
        "shop": it.get("shop") or "",
        "source": it.get("source") or "",
    }


def _shop_for(prov, source, shop):
    """Map the frontend's legacy `source` into the provider's `shop` selector."""
    src = (source or "").strip().lower()
    if getattr(prov, "PROVIDER_NAME", "official") == "crawler":
        return src if src in ("ikea", "rughaus", "kanademono", "bauhaus") else (shop or "")
    # official (Rakuten): 'artofblack' is a shopCode; otherwise pass the given shopCode through.
    return "artofblack" if src == "artofblack" else (shop or "")


def collect(type_, taste="", count=50, source="", shop="", referer=None, provider=None):
    """Dispatch a collection request through the active provider. Raises CollectError.
    `referer` (the request's own origin) lets the Rakuten call match the deployed domain.
    `provider` (optional) forces 'official'|'crawler' for this request (still APP_MODE-gated)."""
    count = max(1, min(90, int(count)))
    prov = get_provider(provider)
    prov_shop = _shop_for(prov, source, shop)
    try:
        raw = prov.search(type_, taste, count, prov_shop, referer=referer)
    except CollectError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"収集に失敗: {e}")
    items = [_to_frontend(it) for it in raw if it]
    return {"source": source or getattr(prov, "PROVIDER_NAME", ""), "count": len(items), "items": items}


def fetch_item(code, source="", referer=None, provider=None):
    """Re-fetch a single item by provider id (reference-only re-hydration). Returns the
    frontend-shaped item or None. Raises CollectError."""
    prov = get_provider(provider)
    try:
        it = prov.fetch_item(code, referer=referer)
    except CollectError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CollectError(502, f"商品取得に失敗: {e}")
    return _to_frontend(it) if it else None


# ---- image relay (same-origin, avoids canvas tainting) -----------------------
def _allowed_img_hosts():
    """Allowed image host suffixes = official (always) + crawler (only when loadable)."""
    hosts = set(_official.imgproxy_hosts())
    if APP_MODE != "public":  # crawler hosts only where the crawler itself is allowed
        try:
            hosts |= set(get_provider("crawler").imgproxy_hosts())
        except CollectError:
            pass
    return hosts


def _host_allowed(url):
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return any(host == s or host.endswith("." + s) for s in _allowed_img_hosts())


def imgproxy_fetch(url):
    """Relay an external furniture image (same-origin, to avoid canvas tainting).
    Returns (bytes, content_type). Raises CollectError. Allowlisted hosts only —
    in public/official mode that means Rakuten's image CDNs only."""
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
