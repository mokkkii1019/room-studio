# Measure the placement ranking (指示016) and build the visual before/after sheet.
#
#   python eval_place.py <cache-dir>              # numbers only
#   python eval_place.py <cache-dir> --sheet out.html
#
# eval-sets/place.json is one row per *delivered* image: the 30 images the shipped
# pipeline actually hands a user for each of 7 categories, in the order it hands them
# over, hand-labelled by eye. Reordering that set is exactly what 指示016 asks for, so
# this is the set that tracks what changes on screen.
#
# Labels (指示016 の severity に合わせてある。既存の dev/holdout とは別基準):
#   place  無地に近い背景・被写体ひとつ・重畳文字なし  ← これだけが「配置しやすい」
#   room   部屋に置かれた状態の写真                    ← 指示016では深刻
#   text   見出し・バッジ・仕様図など重畳文字が主      ← 深刻
#   comp   複数アングル/カラーバリエーションの合成物    ← 深刻
#   person 人物が写っている                            ← 深刻
#   close  接写・素材アップ（商品ではあるが使えない）
#
# Rakuten's terms forbid storing their images, so the set holds URLs and labels only and
# the images are re-fetched into <cache-dir> each run. Delete the cache afterwards.
import html as _html
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

from imgscore import FETCH_PX, load, place_score, score

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = "place"
SEVERE = {"text", "comp", "person"}   # 指示016 が名指しした3種


def cached(cache, rec):
    p = os.path.join(cache, rec["file"])
    if not os.path.exists(p):
        url = re.sub(r"_ex=\d+x\d+", f"_ex={FETCH_PX}x{FETCH_PX}", rec["url"])
        req = urllib.request.Request(url, headers={"User-Agent": "RoomStudio-audit/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            open(p, "wb").write(r.read())
    return p


def load_scored(cache):
    recs = json.load(open(os.path.join(HERE, "eval-sets", "place.json"), encoding="utf-8"))
    by = defaultdict(list)
    missing = 0
    for rec in recs:
        try:
            a = load(cached(cache, rec))
        except Exception as e:  # noqa: BLE001 — a delisted image must not stop the run
            print(f"  ! {rec['file']} unavailable ({e})")
            missing += 1
            continue
        sel = score(a)
        by[rec["type"]].append({**rec, "sel": sel, "place": place_score(a, sel)})
    if missing:
        print(f"  ({missing} images no longer available; excluded)")
    return by


def positions(rows, key):
    order = sorted(rows, key=lambda r: -r[key])
    return order, [i for i, r in enumerate(order) if r["label"] == GOOD]


def report(by):
    tot = {"p5": [0, 0], "p10": [0, 0], "n": 0, "sev": [0, 0]}
    print(f"\n{'category':14} {'配置しやすい画像の位置 (0=先頭)':<44} {'深刻な画像 @10':>14}")
    for t, rows in by.items():
        (_, a), (_, b) = positions(rows, "sel"), positions(rows, "place")
        sa = sum(1 for r in sorted(rows, key=lambda r: -r["sel"])[:10] if r["label"] in SEVERE)
        sb = sum(1 for r in sorted(rows, key=lambda r: -r["place"])[:10] if r["label"] in SEVERE)
        print(f"{t:14} {str(a):>20} -> {str(b):<20} {sa:>6}/10 -> {sb}/10")
        tot["p5"][0] += sum(1 for i in a if i < 5)
        tot["p5"][1] += sum(1 for i in b if i < 5)
        tot["p10"][0] += sum(1 for i in a if i < 10)
        tot["p10"][1] += sum(1 for i in b if i < 10)
        tot["sev"][0] += sa
        tot["sev"][1] += sb
        tot["n"] += len(a)
    print(f"\n  上位5件に入った数   {tot['p5'][0]:2} -> {tot['p5'][1]:2}  (全 {tot['n']} 枚中)")
    print(f"  上位10件に入った数  {tot['p10'][0]:2} -> {tot['p10'][1]:2}")
    print(f"  上位10件の深刻な枚数 {tot['sev'][0]:3} -> {tot['sev'][1]:3}  (7カテゴリ×10=70枚中)")


LAB = {"place": ("配置しやすい", "#12833a"), "room": ("部屋の中", "#a1651a"),
       "text": ("文字入り", "#b3261e"), "comp": ("合成物", "#b3261e"),
       "person": ("人物", "#b3261e"), "close": ("接写", "#6b5bd2")}


def sheet(by, out, top=10):
    """Side-by-side of the first `top` images, before and after. The images are hot-linked
    to Rakuten's CDN, never copied into the repo (their terms forbid storing them), so
    this page needs a network connection and shows whatever is live today."""
    css = """body{font:14px/1.6 system-ui,sans-serif;margin:24px;background:#fafafa;color:#1a1a1a}
h1{font-size:20px} h2{font-size:16px;margin:32px 0 8px;border-bottom:2px solid #ddd;padding-bottom:4px}
.row{display:flex;gap:10px;overflow-x:auto;padding:6px 0}
.c{width:132px;flex:0 0 132px}
.c img{width:132px;height:132px;object-fit:contain;background:#fff;border:1px solid #e2e2e2;border-radius:6px}
.n{font-size:11px;color:#666} .t{font-size:11px;font-weight:600}
.side{font-size:13px;font-weight:700;margin-top:10px}
.moved{outline:3px solid #12833a;outline-offset:1px}
.legend span{display:inline-block;margin-right:12px;font-size:12px}
@media (prefers-color-scheme:dark){body{background:#141414;color:#eee}.c img{background:#fff;border-color:#333}h2{border-color:#333}}"""
    p = ['<!doctype html><meta charset="utf-8"><title>収集画像の並び替え 前後比較</title>',
         f"<style>{css}</style>",
         "<h1>収集画像の並び替え — 前後比較（指示016）</h1>",
         "<p>各カテゴリの上位10件。<b>上段=現行（選別スコア順）／下段=配置しやすさ順</b>。"
         "緑の枠は「無地背景・被写体ひとつ・文字なし」と目視で判定した画像。<br>"
         "画像は楽天のCDNを直接参照している（規約により保存しない）ので、"
         "表示にはネットワークが要り、内容は現時点のものになる。</p>",
         '<p class="legend">' + "".join(
             f'<span style="color:{c}">■ {n}</span>' for n, c in LAB.values()) + "</p>"]
    for t, rows in by.items():
        p.append(f"<h2>{_html.escape(t)}</h2>")
        for side, key in (("現行（選別スコア順）", "sel"), ("配置しやすさ順", "place")):
            order, _ = positions(rows, key)
            p.append(f'<div class="side">{side}</div><div class="row">')
            for i, r in enumerate(order[:top]):
                name, col = LAB.get(r["label"], (r["label"], "#666"))
                cls = "c"
                img = f'<img class="{"moved" if r["label"] == GOOD else ""}" loading="lazy" ' \
                      f'src="{_html.escape(r["url"])}" alt="">'
                p.append(f'<div class="{cls}">{img}'
                         f'<div class="t" style="color:{col}">{i}. {name}</div>'
                         f'<div class="n">{r[key]:.2f} / {_html.escape(r["shop"][:18])}</div></div>')
            p.append("</div>")
    open(out, "w", encoding="utf-8").write("\n".join(p))
    print("\nsheet ->", out)


if __name__ == "__main__":
    cache = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, ".cache")
    os.makedirs(cache, exist_ok=True)
    by = load_scored(cache)
    report(by)
    if "--sheet" in sys.argv:
        sheet(by, sys.argv[sys.argv.index("--sheet") + 1])
