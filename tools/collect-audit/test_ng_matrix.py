# Verify NGKeyword semantics (is a space-separated list OR-of-exclusions?) and check
# the proposed per-category NG terms against live data.
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api"))
import _provider_base as base  # noqa: E402
import _provider_official as po  # noqa: E402

base._load_dotenv()


def call(keyword, ng=None, genre=None):
    p = {"applicationId": po.RAKUTEN_APP_ID, "accessKey": po.RAKUTEN_ACCESS_KEY,
         "keyword": keyword, "hits": 30, "page": 1, "imageFlag": 1,
         "format": "json", "sort": "standard"}
    if ng:
        p["NGKeyword"] = ng
    if genre:
        p["genreId"] = genre
    url = po.RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers=po._headers("https://roomstudio.jp/"))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:120]
    return [w.get("Item", w).get("itemName", "") for w in d.get("Items", [])], None


w = sys.stdout.buffer.write

w(b"--- semantics: is a multi-word NGKeyword OR-of-exclusions? ---\n")
for ng in (None, "フィルム", "保護パネル", "フィルム 保護パネル"):
    names, err = call("テレビ 液晶テレビ", ng)
    if err:
        w(("  NG=%-16s ERROR %s\n" % (ng, err)).encode())
        continue
    f = sum(1 for n in names if "フィルム" in n)
    p = sum(1 for n in names if "保護パネル" in n)
    w(("  NG=%-16s n=%2d  contains-フィルム=%2d  contains-保護パネル=%2d\n"
       % (str(ng), len(names), f, p)).encode())

w(b"\n--- proposed per-category NG terms ---\n")
CASES = [
    ("washing_machine", "洗濯機 ドラム式洗濯機", "フィルター 毛ごみ 糸くず ゴミ取り", ["フィルター", "毛ごみ", "糸くず"]),
    ("vacuum", "掃除機 クリーナー", "掃除機スタンド クリーナースタンド ツールステーション", ["掃除機スタンド", "クリーナースタンド"]),
    ("tv", "テレビ 液晶テレビ", "フィルム 保護パネル", ["フィルム", "保護パネル"]),
    ("mirror", "鏡 ミラー 姿見", None, ["フィルムミラー"]),
]
for name, kw, ng, probes in CASES:
    for label, use in (("before", None), ("after", ng)):
        if use is None and ng is None and label == "after":
            continue
        names, err = call(kw, use)
        if err:
            w(("  %-16s %-6s ERROR %s\n" % (name, label, err)).encode())
            continue
        hits = {p: sum(1 for n in names if p in n) for p in probes}
        w(("  %-16s %-6s n=%2d  %s\n" % (name, label, len(names),
           "  ".join("%s:%d" % kv for kv in hits.items()))).encode())
        if label == "after":
            w(b"     survivors: \n")
            for n in names[:3]:
                w(("       " + n[:64] + "\n").encode())
