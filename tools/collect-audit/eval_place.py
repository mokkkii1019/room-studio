# Measure the placement ranking (指示016) and build the visual comparison sheet.
#
#   python eval_place.py <cache-dir>              # numbers only
#   python eval_place.py <cache-dir> --sheet ../../docs/collect-ranking-compare.html
#
# 🔴 判定は「上位3枚」で行うこと（指示019 の3項）。ユーザーが最初に見るのは3枚で、10枚の
# 合計ではない。指示018 の重み調整は @10 の合計を 31→27 に改善したが、上位3枚では sofa /
# plant / chest が悪化していたため不採用になった。この取り違えを繰り返さないよう、表は
# **@3 を左に置いてある**。@10 は参考値で、これだけを見て採否を決めないこと。
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

from imgscore import FETCH_PX, diversify_by_shop, load, place_score, score

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = "place"
SEVERE = {"text", "comp", "person"}   # 指示016 が名指しした3種
SHOP_MAX = 2                          # COLLECT_SHOP_MAX in room-studio.html

# The orderings the sheet compares, top to bottom.
#   key … which score sorts the 30 delivered images
#   div … 0 = no shop suppression, N = at most N per shop before the next pass
# ② is what production serves after 指示019 (COLLECT_RANKING='log' + suppression).
# ③④ are what flipping COLLECT_RANKING to 'on' would look like.
ORDERS = [
    ("① 指示019 の前（選別スコア順・抑制なし）", "sel", 0),
    ("② 現在の本番（選別スコア順 ＋ 同一店舗の抑制）", "sel", SHOP_MAX),
    ("③ 'on' にした場合（配置しやすさ順・抑制なし）", "place", 0),
    ("④ 'on' ＋ 同一店舗の抑制", "place", SHOP_MAX),
]


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


def positions(rows, key, div=0):
    order = sorted(rows, key=lambda r: -r[key])
    if div:
        order = diversify_by_shop(order, div)
    return order, [i for i, r in enumerate(order) if r["label"] == GOOD]


def totals(by, key, div):
    """One row of the summary: @3 first, because that is what the decision is made on."""
    t = dict(p3=0, p10=0, sev3=0, sev10=0, text10=0, room10=0, dup=[])
    for rows in by.values():
        order, pos = positions(rows, key, div)
        t["p3"] += sum(1 for i in pos if i < 3)
        t["p10"] += sum(1 for i in pos if i < 10)
        t["sev3"] += sum(1 for r in order[:3] if r["label"] in SEVERE)
        t["sev10"] += sum(1 for r in order[:10] if r["label"] in SEVERE)
        t["text10"] += sum(1 for r in order[:10] if r["label"] == "text")
        t["room10"] += sum(1 for r in order[:10] if r["label"] == "room")
        c = defaultdict(int)
        for r in order[:10]:
            c[r["shop"]] += 1
        t["dup"].append(max(c.values()))
    return t


def report(by):
    n_cat = len(by)
    print(f"\n{'順序':40} {'配置@3':>7} {'深刻@3':>7} | {'配置@10':>8} {'深刻@10':>8} "
          f"{'部屋@10':>8} {'同一店舗の最大数':>16}")
    print(f"{'':40} {'← ここで判断する（指示019）':<24}   {'← 参考値':<20}")
    for name, key, div in ORDERS:
        t = totals(by, key, div)
        print(f"{name:40} {t['p3']:4}/{n_cat*3:<3} {t['sev3']:4}/{n_cat*3:<3} | "
              f"{t['p10']:5}/{n_cat*10:<3} {t['sev10']:5}/{n_cat*10:<3} "
              f"{t['room10']:5}/{n_cat*10:<3} {t['dup']}")
    print("\nカテゴリごとの「配置しやすい画像が何番目に出るか」(0=先頭)")
    for t, rows in by.items():
        cells = [str(positions(rows, key, div)[1]) for _, key, div in ORDERS]
        print(f"  {t:14} " + "  ->  ".join(f"{c:<16}" for c in cells))


LAB = {"place": ("配置しやすい", "#12833a"), "room": ("部屋の中", "#a1651a"),
       "text": ("文字入り", "#b3261e"), "comp": ("合成物", "#b3261e"),
       "person": ("人物", "#b3261e"), "close": ("接写", "#6b5bd2")}


def sheet(by, out, top=10):
    """The first `top` images under each ordering in ORDERS, stacked so the change can be
    judged by eye. **The first three of each row are boxed** — that is where the decision
    is made (指示019). The images are hot-linked to Rakuten's CDN, never copied into the
    repo (their terms forbid storing them), so this page needs a network connection and
    shows whatever is live today.

    To look at it without a browser: split it per category and screenshot each with
    headless Chrome (see docs/COLLECT_RANKING_REPORT.md §12)."""
    css = """body{font:14px/1.6 system-ui,sans-serif;margin:24px;background:#fafafa;color:#1a1a1a}
h1{font-size:20px} h2{font-size:16px;margin:34px 0 8px;border-bottom:2px solid #ddd;padding-bottom:4px}
.row{display:flex;gap:10px;overflow-x:auto;padding:6px 0}
.c{width:132px;flex:0 0 132px}
.c img{width:132px;height:132px;object-fit:contain;background:#fff;border:1px solid #e2e2e2;border-radius:6px}
.n{font-size:11px;color:#666} .t{font-size:11px;font-weight:600}
.side{font-size:13px;font-weight:700;margin-top:12px}
.side em{font-weight:400;font-style:normal;color:#666;font-size:12px}
.first3{border-left:3px solid #1a1a1a;padding-left:7px;margin-left:-10px}
.moved{outline:3px solid #12833a;outline-offset:1px}
.dup{outline:3px solid #b3261e;outline-offset:1px}
.legend span{display:inline-block;margin-right:12px;font-size:12px}
table{border-collapse:collapse;font-size:13px;margin:10px 0}
th,td{border:1px solid #ddd;padding:4px 9px;text-align:right} th{background:#f0f0f0;text-align:left}
td:first-child,th:first-child{text-align:left} .dim{color:#888}
@media (prefers-color-scheme:dark){body{background:#141414;color:#eee}.c img{background:#fff;border-color:#333}
h2{border-color:#333}th{background:#222}th,td{border-color:#333}.first3{border-color:#eee}}"""
    n3 = len(by) * 3
    n10 = len(by) * 10
    p = ['<!doctype html><meta charset="utf-8"><title>収集画像の並び替え 比較シート</title>',
         f"<style>{css}</style>",
         "<h1>収集画像の並び替え — 比較シート</h1>",
         "<p>各カテゴリの上位10件を、順序ごとに段で並べたもの。"
         "<b>2段目が現在の本番</b>（<code>COLLECT_RANKING='log'</code> ＋ 同一店舗の抑制）。<br>"
         "<b>黒い縦線の左が上位3枚</b>＝ユーザーが最初に見る範囲で、"
         "<b>採否はここで判断する</b>（指示019）。@10 の合計は参考値。<br>"
         "<span style='color:#12833a'>■緑の枠</span>＝「無地背景・被写体ひとつ・文字なし」"
         "と目視で判定した画像（これが上に来てほしい）。"
         "<span style='color:#b3261e'>■赤の枠</span>＝その段で3件目以降に出た同一店舗の画像。<br>"
         "画像は楽天のCDNを直接参照している（規約により保存しない）ので、"
         "表示にはネットワークが要り、内容は現時点のものになる。</p>",
         '<p class="legend">' + "".join(
             f'<span style="color:{c}">■ {n}</span>' for n, c in LAB.values()) + "</p>",
         "<table><tr><th>順序</th><th>配置しやすい@3</th><th>深刻@3</th>"
         "<th class='dim'>配置しやすい@10</th><th class='dim'>深刻@10</th>"
         "<th class='dim'>部屋@10</th><th class='dim'>文字@10</th></tr>"]
    for name, key, div in ORDERS:
        t = totals(by, key, div)
        p.append(f"<tr><td>{_html.escape(name)}</td><td>{t['p3']}/{n3}</td>"
                 f"<td>{t['sev3']}/{n3}</td><td class='dim'>{t['p10']}/{n10}</td>"
                 f"<td class='dim'>{t['sev10']}/{n10}</td>"
                 f"<td class='dim'>{t['room10']}/{n10}</td>"
                 f"<td class='dim'>{t['text10']}/{n10}</td></tr>")
    p.append("</table>")
    for t, rows in by.items():
        p.append(f"<h2>{_html.escape(t)}</h2>")
        for name, key, div in ORDERS:
            order, _ = positions(rows, key, div)
            shown, n_by_shop = defaultdict(int), defaultdict(int)
            for r in order[:top]:
                n_by_shop[r["shop"]] += 1
            dup = sum(1 for n in n_by_shop.values() if n > SHOP_MAX)
            p.append(f'<div class="side">{_html.escape(name)}'
                     + (f" <em>（同一店舗が{SHOP_MAX}件を超える店: {dup}）</em>" if dup else "")
                     + '</div><div class="row">')
            for i, r in enumerate(order[:top]):
                nm, col = LAB.get(r["label"], (r["label"], "#666"))
                shown[r["shop"]] += 1
                cls = "moved" if r["label"] == GOOD else (
                    "dup" if shown[r["shop"]] > SHOP_MAX else "")
                img = (f'<img class="{cls}" loading="lazy" '
                       f'src="{_html.escape(r["url"])}" alt="">')
                p.append(f'<div class="c{" first3" if i == 3 else ""}">{img}'
                         f'<div class="t" style="color:{col}">{i}. {nm}</div>'
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
