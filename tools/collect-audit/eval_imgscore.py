# Measure the candidate scorer against hand labels, and check the shipped JS against
# this Python. Run this before changing any threshold in room-studio.html.
#
#   python eval_imgscore.py <cache-dir>              # download if needed, then score
#   python eval_imgscore.py <cache-dir> --parity     # also diff room-studio.html
#
# The eval sets in eval-sets/*.json hold URLs and labels, never images (Rakuten's terms
# forbid storing them); the images are re-fetched into <cache-dir> on demand and can be
# deleted afterwards. Labels were assigned by eye from contact sheets:
#
#   clean  single product, plain background, little or no overlay text
#   ok     product is the clear subject of a room shot, no overlay text, no person
#   text   overlay headline / ranking badge / review page / spec sheet dominates
#   grid   multi-panel collage, colour-variation table, several products
#   person a human is visible
#   swatch flat fabric or material close-up (curtain listings)
#
# acceptable = clean | ok  — the ones worth handing to a user.
import json
import os
import subprocess
import sys
import urllib.request
from collections import defaultdict

from imgscore import load, score, score_legacy

HERE = os.path.dirname(os.path.abspath(__file__))
SETS = ["dev", "holdout"]
ACCEPTABLE = {"clean", "ok"}


def cached(cache, rec):
    p = os.path.join(cache, rec["file"])
    if not os.path.exists(p):
        req = urllib.request.Request(rec["url"], headers={"User-Agent": "RoomStudio-audit/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            open(p, "wb").write(r.read())
    return p


def run_set(name, cache):
    recs = json.load(open(os.path.join(HERE, "eval-sets", f"{name}.json"), encoding="utf-8"))
    items, missing = defaultdict(list), 0
    for rec in recs:
        try:
            p = cached(cache, rec)
        except Exception as e:  # noqa: BLE001 — a delisted image should not stop the run
            print(f"  ! {rec['file']} unavailable ({e})")
            missing += 1
            continue
        items[(rec["type"], rec["item"])].append(
            (score(load(p)), score_legacy(load(p, 64)), rec["label"]))

    n = len(items)
    ceiling = sum(any(l in ACCEPTABLE for _, _, l in c) for c in items.values())
    new = sum(max(c)[2] in ACCEPTABLE for c in items.values())
    old = sum(max(c, key=lambda t: t[1])[2] in ACCEPTABLE for c in items.values())
    print(f"\n{name}: {sum(len(c) for c in items.values())} candidates, {n} items"
          + (f", {missing} unavailable" if missing else ""))
    print(f"  legacy scorer picks acceptable  {old:3}/{n} ({100*old/n:.0f}%)")
    print(f"  shipped scorer picks acceptable {new:3}/{n} ({100*new/n:.0f}%)")
    print(f"  ceiling (item has any)          {ceiling:3}/{n} ({100*ceiling/n:.0f}%)")
    print("  reject items whose best candidate scores below T:")
    for T in (-2.0, -1.6, -1.4, -1.2, -1.0):
        kept = [max(c) for c in items.values() if max(c)[0] >= T]
        good = sum(1 for k in kept if k[2] in ACCEPTABLE)
        pr = f"{100*good/len(kept):.0f}%" if kept else "-"
        print(f"    T={T:5.1f}  kept {len(kept):3}/{n}  acceptable {good:3} ({pr})")


def parity(cache):
    """Diff room-studio.html's scoring against this module on identical buffers."""
    import numpy as np
    from imgscore import gutter_score, text_score, vivid_score

    recs = json.load(open(os.path.join(HERE, "eval-sets", "dev.json"), encoding="utf-8"))[:24]
    pdir = os.path.join(cache, "_parity")
    os.makedirs(pdir, exist_ok=True)
    exp = []
    for rec in recs:
        a = load(cached(cache, rec))
        rgba = np.dstack([a.astype(np.uint8), np.full((256, 256, 1), 255, np.uint8)])
        open(os.path.join(pdir, rec["file"] + ".raw"), "wb").write(rgba.tobytes())
        tpx, tn = text_score(a)
        exp.append({"file": rec["file"] + ".raw", "text_px": float(tpx), "glyphs": int(tn),
                    "gutter": int(gutter_score(a)), "vivid": float(vivid_score(a))})
    json.dump(exp, open(os.path.join(pdir, "expected.json"), "w"), indent=1)
    html = os.path.join(HERE, "..", "..", "room-studio.html")
    r = subprocess.run(["node", os.path.join(HERE, "parity.js"), html, pdir])
    if r.returncode:
        sys.exit(r.returncode)


if __name__ == "__main__":
    cache = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".cache")
    os.makedirs(cache, exist_ok=True)
    for s in SETS:
        run_set(s, cache)
    if "--parity" in sys.argv:
        print()
        parity(cache)
