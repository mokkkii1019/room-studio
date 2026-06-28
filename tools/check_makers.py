# -*- coding: utf-8 -*-
"""家具メーカー一覧（room-studio.html の MAKERS）の定期メンテ用ツール。

やること:
  1) 現在のリストの各 shopCode がまだ生きているか（商品が返るか）を確認
  2) 楽天の人気家具ショップをサンプリングし、リスト未収載の候補を提示

使い方（プロジェクト直下で）:
    python tools/check_makers.py
必要: RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY（.env か環境変数）。
楽天の新APIは Referer 必須なので、登録済みの公開ドメインを使う:
    RAKUTEN_REFERER=https://room-studio-fawn.vercel.app/  （既定値・env で上書き可）
"""
import os
import re
import sys
import json
import time
import urllib.parse
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
import _collect_core as core  # APP_ID / ACCESS_KEY / ENDPOINT / INTERIOR_GENRE / _load_dotenv

REFERER = os.environ.get("RAKUTEN_REFERER", "").strip() or "https://room-studio-fawn.vercel.app/"
_u = urllib.parse.urlsplit(REFERER)
ORIGIN = f"{_u.scheme}://{_u.netloc}"


def _api(params):
    p = {"applicationId": core.RAKUTEN_APP_ID, "accessKey": core.RAKUTEN_ACCESS_KEY,
         "format": "json", "hits": 30, **params}
    url = core.RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "RoomStudio/1.0", "Referer": REFERER, "Origin": ORIGIN})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def current_makers():
    """room-studio.html の MAKERS=[...] から {code: name} を抽出。"""
    html = open(os.path.join(ROOT, "room-studio.html"), encoding="utf-8").read()
    m = re.search(r"const MAKERS=\[(.*?)\]\.sort", html, re.S)
    block = m.group(1) if m else ""
    out = {}
    for mm in re.finditer(r"code:'([^']+)'\s*,\s*name:'([^']+)'", block):
        out[mm.group(1)] = mm.group(2)
    return out


def verify(codes):
    print("=== 生存確認（現リスト） ===")
    dead = []
    for code, name in codes.items():
        try:
            d = _api({"keyword": "家具", "shopCode": code, "hits": 3})
            n = len(d.get("Items", []))
            print(f"  {'OK ' if n else 'EMPTY':6} {code:18} {name}  ({n})")
            if not n:
                dead.append(code)
        except urllib.error.HTTPError as e:
            print(f"  NG{e.code:>4} {code:18} {name}")
            dead.append(code)
        except Exception as e:  # noqa: BLE001
            print(f"  ERR    {code:18} {name}  {e}")
        time.sleep(1.0)
    if dead:
        print("  → 要確認/削除候補:", ", ".join(dead))


def discover(known):
    print("\n=== 新規候補（人気家具ショップで未収載のもの） ===")
    from collections import Counter
    cnt, names = Counter(), {}
    for kw in ["ソファ", "ダイニングテーブル", "ベッド", "チェスト", "テレビ台", "本棚 シェルフ", "チェア", "ローテーブル"]:
        try:
            d = _api({"keyword": kw, "genreId": core.INTERIOR_GENRE, "sort": "standard"})
            for w in d.get("Items", []):
                it = w.get("Item", w)
                code = (it.get("itemCode") or "").split(":")[0]
                if code:
                    cnt[code] += 1
                    names[code] = it.get("shopName") or ""
        except Exception as e:  # noqa: BLE001
            print("  (err)", kw, e)
        time.sleep(1.0)
    shown = 0
    for code, c in cnt.most_common(40):
        if code in known:
            continue
        print(f"  +{c:>3}  {code:18} {names[code]}")
        shown += 1
        if shown >= 20:
            break
    if not shown:
        print("  （新規候補なし）")


if __name__ == "__main__":
    if not core.RAKUTEN_APP_ID or not core.RAKUTEN_ACCESS_KEY:
        print("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が未設定です（.env か環境変数）。")
        sys.exit(1)
    print("Referer:", REFERER)
    codes = current_makers()
    print(f"現リスト {len(codes)} 社\n")
    verify(codes)
    discover(set(codes))
    print("\n更新する場合は room-studio.html の MAKERS 配列を編集してください（code/name/kana）。")
