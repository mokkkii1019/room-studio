# Pull item titles per category from the live /collect and dump them for a relevance
# audit. Titles only -- no images fetched.
import json
import sys
import time
import urllib.parse
import urllib.request

TYPES = sys.argv[1].split(",")
OUT = sys.argv[2]
res = {}
for t in TYPES:
    u = "https://roomstudio.jp/collect?" + urllib.parse.urlencode({"type": t, "count": 30})
    try:
        with urllib.request.urlopen(u, timeout=90) as r:
            items = json.loads(r.read().decode("utf-8")).get("items", [])
        res[t] = [i.get("title", "") for i in items]
        print(t, len(res[t]))
    except Exception as e:  # noqa: BLE001
        print(t, "FAILED", e)
        res[t] = []
    time.sleep(0.5)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
