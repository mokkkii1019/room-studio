# -*- coding: utf-8 -*-
"""Room Studio — collection provider base (standard library only).

Defines the shared pieces every collection *provider* builds on:
  - CollectError               … carries an HTTP status + message
  - env / config               … COLLECT_PROVIDER, APP_MODE, .env loading
  - category maps + filters     … TYPE_MATCH / TYPE_EXCLUDE / _relevant / _numbered_variants

A provider module (e.g. _provider_official, _provider_crawler) must expose:

    PROVIDER_NAME : str                       # 'official' | 'crawler'
    search(type_, taste, count, shop='', referer=None) -> list[item]
    fetch_item(item_code, referer=None)        -> item | None
    imgproxy_hosts()                           -> tuple[str, ...]   # allowed image host suffixes

where `item` is a normalized dict:

    {
      "name":        str,        # product title
      "price":       int,        # JPY (0 if unknown)
      "shop":        str,        # storefront / shop name
      "productUrl":  str,        # canonical product page
      "affiliateUrl":str,        # monetized link (may equal productUrl if none)
      "imageUrl":    str,        # primary image (raw, provider's own CDN)
      "imageUrls":   list[str],  # optional: extra candidate images (best-photo picking)
      "itemCode":    str,        # provider-unique id (for fetch_item re-fetch)
      "source":      str,        # 'rakuten' | 'ikea' | 'rughaus' | ...
    }

No third-party imports here (runs on Vercel's stdlib Python runtime with no deps).
"""

import os
import re

APP_DIR = os.path.dirname(os.path.abspath(__file__))


class CollectError(Exception):
    """Carries an HTTP status + message for the endpoints to surface."""
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

# ---- provider switch / deployment mode ---------------------------------------
# COLLECT_PROVIDER : which provider get_provider() returns ('official' | 'crawler').
# APP_MODE         : 'public'  → the crawler provider is never imported and is refused (403).
#                    'private' → the crawler provider may be selected (self-hosted / personal use).
COLLECT_PROVIDER = (os.environ.get("COLLECT_PROVIDER", "official") or "official").strip().lower()
APP_MODE = (os.environ.get("APP_MODE", "public") or "public").strip().lower()


# ---- shared category filtering (used by every provider) ----------------------
# type key -> title must contain ANY of these (drops off-category items).
TYPE_MATCH = {
    # --- 家具 furniture ---
    "chair": ["椅子", "チェア", "いす", "chair", "スツール", "stool", "アームチェア"],
    "dining_table": ["ダイニングテーブル", "ダイニング", "dining"],
    "sofa": ["ソファ", "ソファー", "sofa", "カウチ", "couch", "ラブソファ"],
    "bed": ["ベッド", "bed", "ベットフレーム", "ベッドフレーム"],
    "coffee_table": ["ローテーブル", "コーヒーテーブル", "センターテーブル", "リビングテーブル", "coffee table"],
    "chest": ["サイドボード", "リビングボード", "キャビネット", "チェスト", "sideboard", "cabinet", "収納棚"],
    "shelf": ["シェルフ", "棚", "ラック", "shelf", "rack", "ウォールシェルフ", "本棚"],
    "desk": ["デスク", "机", "desk", "パソコンデスク", "学習机", "ワークデスク", "pcデスク"],
    # --- 家電 home appliances ---
    "tv": ["テレビ", "液晶テレビ", "有機el", "4kテレビ", "tv", "テレビ本体"],
    "refrigerator": ["冷蔵庫", "冷凍冷蔵庫", "refrigerator", "fridge", "冷凍庫"],
    "washing_machine": ["洗濯機", "ドラム式", "全自動洗濯機", "洗濯乾燥機", "washer"],
    "air_conditioner": ["エアコン", "ルームエアコン", "クーラー", "冷房", "暖房", "air conditioner"],
    "microwave": ["電子レンジ", "オーブンレンジ", "レンジ", "スチームオーブン", "microwave"],
    "rice_cooker": ["炊飯器", "炊飯ジャー", "rice cooker", "ジャー炊飯"],
    "air_purifier": ["空気清浄機", "空気清浄", "air purifier", "加湿空気清浄"],
    "fan": ["扇風機", "サーキュレーター", "circulator", "タワーファン", "fan"],
    "humidifier": ["加湿器", "humidifier", "気化式", "超音波加湿", "加湿"],
    "vacuum": ["掃除機", "クリーナー", "vacuum", "コードレス掃除機", "ロボット掃除機", "スティッククリーナー"],
    # --- 日用品・インテリア雑貨 daily goods / accessories ---
    "carpet": ["ラグ", "カーペット", "rug", "絨毯", "じゅうたん", "ラグマット"],
    "curtain": ["カーテン", "curtain", "ドレープ", "遮光", "レースカーテン"],
    "table_lamp": ["テーブルランプ", "デスクランプ", "テーブルライト", "table lamp", "デスクライト"],
    "floor_lamp": ["フロアランプ", "フロアライト", "スタンドライト", "floor lamp", "フロアスタンド"],
    "lampshade": ["ランプシェード", "シェード", "lampshade", "ペンダントライト", "ペンダントランプ"],
    "plant": ["観葉植物", "フェイクグリーン", "人工観葉", "造花", "グリーン", "plant", "ボタニカル"],
    "art": ["アート", "ポスター", "絵画", "ウォール", "パネル", "art", "poster", "ファブリックパネル"],
    "mirror": ["ミラー", "鏡", "mirror", "姿見"],
    "cushion": ["クッション", "ブランケット", "スロー", "cushion", "blanket", "throw", "ひざ掛け", "膝掛け", "ピロー", "枕"],
    "clock": ["時計", "クロック", "clock", "掛け時計", "置き時計", "ウォールクロック"],
    "storage_box": ["収納ボックス", "収納ケース", "収納バスケット", "収納かご", "storage", "収納box", "バスケット"],
    "trash_can": ["ゴミ箱", "ごみ箱", "ダストボックス", "くずかご", "trash", "ダストbox"],
}
# accessory/parts words to drop regardless of type (not the item itself).
TYPE_EXCLUDE = ["カバー", "ケース", "リペア", "交換用", "替えカバー", "脚のみ", "脚単品", "パーツ", "ステッカー", "シール"]

# 部分一致による他カテゴリ混入を防ぐ「このカテゴリではない」語（タイトルに含めば除外）。
# 例: dining_table 検索で「ダイニングチェア」が"ダイニング"にマッチしてしまうのを弾く。
# 家電/日用品は「台・ボード・スタンド・リモコン・フィルター」等の関連品を弾いて本体だけ残す。
TYPE_EXCLUDE_BY_TYPE = {
    "dining_table": ["チェア", "chair", "スツール", "stool", "ベンチ", "bench", "ソファ", "sofa", "デスク", "desk"],
    "coffee_table": ["チェア", "chair", "スツール", "stool", "デスク", "desk"],
    "shelf": ["ローテーブル", "センターテーブル", "コーヒーテーブル", "ダイニングテーブル", "デスク", "desk"],
    "chest": ["チェア", "chair", "ソファ", "sofa"],
    "desk": ["チェア", "chair", "ワゴンのみ"],
    "tv": ["テレビ台", "テレビボード", "tvスタンド", "テレビスタンド", "リモコン", "アンテナ", "壁掛け金具", "金具", "hdmi", "レコーダー"],
    "refrigerator": ["冷蔵庫マット", "マット", "シート", "トレー", "収納", "ラック"],
    "washing_machine": ["ラック", "台", "マット", "ホース", "洗濯ネット", "パン", "収納"],
    "air_conditioner": ["リモコン", "室外機", "洗浄", "フィルター", "配管", "ホース", "室外"],
    "microwave": ["ラック", "レンジ台", "ターンテーブル", "調理", "容器", "収納"],
    "rice_cooker": ["内釜", "しゃもじ", "パッキン", "収納"],
    "air_purifier": ["フィルター", "交換用"],
    "fan": ["リモコン", "羽根", "クリップ", "usb扇風機", "ハンディ"],
    "humidifier": ["フィルター", "交換用", "カートリッジ", "アロマオイル", "洗浄"],
    "vacuum": ["紙パック", "フィルター", "ノズル", "ヘッドのみ", "バッテリー", "スタンドのみ"],
    "curtain": ["カーテンレール", "レール", "タッセル", "フックのみ", "アジャスター", "クリップ"],
    "clock": ["電池", "ムーブメント", "部品"],
    "trash_can": ["ゴミ袋", "替え袋", "スタンドのみ"],
}


def _relevant(title, type_):
    """Does the product title match the requested category (drops mismatches)?"""
    t = (title or "").lower()
    if not t:
        return False
    inc = TYPE_MATCH.get(type_)
    inc_l = [k.lower() for k in inc] if inc else []
    # 汎用の除外語。ただしこのカテゴリが正規に含む語（例: storage_box の「収納ケース」に対する
    # グローバル除外語「ケース」）は落とさない（除外語がマッチ語の一部なら除外しない）。
    for x in TYPE_EXCLUDE:
        xl = x.lower()
        if xl in t and not any(xl in k for k in inc_l):
            return False
    exc = TYPE_EXCLUDE_BY_TYPE.get(type_)
    if exc and any(x.lower() in t for x in exc):
        return False  # 他カテゴリ/関連品（例: ダイニング「チェア」, 「テレビ台」）を弾く
    if not inc_l:
        return True
    return any(k in t for k in inc_l)


def _numbered_variants(url, maxn):
    """Re-number a trailing image index (…-1.jpg / …-21a.jpg) to a plain 1..maxn.
    Rakuten's representative images aren't always -1..-3, so this surfaces the
    small-index main/front shots that tend to be the cleanest single-item photos."""
    m = re.match(r'^(.*[^\d])(\d+)([a-zA-Z]*)(\.\w+)(\?.*)?$', url)
    if not m:
        return []
    pre, _num, _sfx, ext, q = m.group(1), m.group(2), m.group(3), m.group(4), (m.group(5) or "")
    return [f"{pre}{n}{ext}{q}" for n in range(1, maxn + 1)]
