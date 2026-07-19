# End-to-end check of the patched provider: run search() for the affected categories
# and report how many accessory items survive, plus how many candidate images per item.
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api"))
import _provider_base as base  # noqa: E402
import _provider_official as po  # noqa: E402

base._load_dotenv()
w = sys.stdout.buffer.write

CASES = [
    ("tv", ["フィルム", "保護パネル"]),
    ("washing_machine", ["毛ごみ", "糸くず", "枚入"]),
    ("vacuum", ["掃除機スタンド", "クリーナースタンド"]),
    ("mirror", ["フィルムミラー"]),   # must NOT be filtered
    ("sofa", []),
]
for t, bad_words in CASES:
    try:
        items = po.search(t, count=30, referer="https://roomstudio.jp/")
    except Exception as e:  # noqa: BLE001
        w(("%-16s ERROR %s\n" % (t, str(e)[:90])).encode())
        time.sleep(3)
        continue
    bad = [i["name"] for i in items if any(k in i["name"] for k in bad_words)]
    cands = [len(i.get("imageUrls") or []) for i in items] or [0]
    w(("%-16s items=%2d  accessory=%d  cands/item avg=%.1f max=%d\n"
       % (t, len(items), len(bad), sum(cands) / len(cands), max(cands))).encode())
    for b in bad[:3]:
        w(("    LEAK: " + b[:64] + "\n").encode())
    if t == "mirror":
        keep = [i["name"] for i in items if "フィルム" in i["name"]]
        w(("    mirror keeps %d フィルム items (expected >0): %s\n"
           % (len(keep), keep[0][:50] if keep else "-")).encode())
    time.sleep(3)   # respect Rakuten's ~1 QPS guideline
