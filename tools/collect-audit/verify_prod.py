# Verify the deployed /collect: accessory leakage, candidate counts, and that the
# categories we deliberately left alone are unchanged.
import json
import sys
import time
import urllib.parse
import urllib.request

CASES = [
    ("tv", ["フィルム", "保護パネル"], 0),
    ("washing_machine", ["毛ごみ", "糸くず", "枚入"], 0),
    ("vacuum", ["掃除機スタンド", "クリーナースタンド"], 0),
    ("sofa", [], 0),
    ("carpet", [], 0),
]
w = sys.stdout.buffer.write
w(b"%-17s %-6s %-10s %-9s %s\n" % (b"type", b"items", b"accessory", b"cands/it", b"max"))
for t, bad, _ in CASES:
    u = "https://roomstudio.jp/collect?" + urllib.parse.urlencode({"type": t, "count": 30})
    with urllib.request.urlopen(u, timeout=90) as r:
        its = json.loads(r.read().decode("utf-8")).get("items", [])
    leak = [i["title"] for i in its if any(k in i.get("title", "") for k in bad)]
    c = [len(i.get("cands") or []) for i in its] or [0]
    w(("%-17s %-6d %-10d %-9.1f %d\n" % (t, len(its), len(leak), sum(c) / len(c), max(c))).encode())
    for x in leak[:2]:
        w(("    LEAK: " + x[:64] + "\n").encode())
    time.sleep(1)

# mirror must still keep its legitimate film mirrors
u = "https://roomstudio.jp/collect?" + urllib.parse.urlencode({"type": "mirror", "count": 30})
with urllib.request.urlopen(u, timeout=90) as r:
    its = json.loads(r.read().decode("utf-8")).get("items", [])
keep = [i["title"] for i in its if "フィルム" in i.get("title", "")]
w(("\nmirror: %d items, %d contain フィルム (must be > 0)\n" % (len(its), len(keep))).encode())
for x in keep[:2]:
    w(("    KEPT: " + x[:64] + "\n").encode())
