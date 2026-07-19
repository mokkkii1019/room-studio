# Fetch real Rakuten candidate images across categories into a local sample set,
# then build labelled contact sheets. Scratchpad only — nothing is committed.
import json
import os
import sys
import urllib.parse
import urllib.request

OUT = sys.argv[1]
TYPES = sys.argv[2].split(",")
PER = int(sys.argv[3]) if len(sys.argv) > 3 else 8
os.makedirs(OUT, exist_ok=True)

index = []
for t in TYPES:
    u = "https://roomstudio.jp/collect?" + urllib.parse.urlencode({"type": t, "count": 20})
    with urllib.request.urlopen(u, timeout=90) as r:
        items = json.loads(r.read().decode("utf-8")).get("items", [])
    n = 0
    for it in items:
        if n >= PER:
            break
        cands = (it.get("cands") or [])[:3]
        got = 0
        for k, c in enumerate(cands):
            url = "https://roomstudio.jp" + c
            name = f"{t}_{n}_{k}.jpg"
            p = os.path.join(OUT, name)
            try:
                with urllib.request.urlopen(url, timeout=40) as r:
                    b = r.read()
                if len(b) < 2000:
                    continue
                open(p, "wb").write(b)
                index.append({"file": name, "type": t, "item": n, "slot": k,
                              "raw": urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["url"][0],
                              "title": (it.get("title") or "")[:60]})
                got += 1
            except Exception as e:  # noqa: BLE001
                print("  skip", name, e)
        if got:
            n += 1
    print(t, "->", n, "items")

json.dump(index, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total images:", len(index))
