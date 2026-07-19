# Apply proposed exclusion terms to the audited titles and print exactly what each
# term removes, so false positives can be spotted before the rule ships.
import json
import sys

titles = json.load(open(sys.argv[1], encoding="utf-8"))

# NOTE: "フィルム" must NOT be generic -- "フィルムミラー" (shatterproof film mirrors)
# are legitimate `mirror` products. Scope it to the categories where it only ever
# means a screen protector.
GENERIC = []
BY_TYPE = {
    "tv": ["フィルム", "保護パネル", "保護フィルム"],
    "washing_machine": ["毛ごみ", "糸くず", "ゴミ取り", "乾燥フィルター", "枚入"],
    "vacuum": ["掃除機スタンド", "クリーナースタンド", "ツールステーション", "スタンド コードレス"],
}

w = sys.stdout.buffer.write
total_removed = 0
for t, ts in titles.items():
    terms = GENERIC + BY_TYPE.get(t, [])
    removed = [x for x in ts if any(k in x for k in terms)]
    kept = [x for x in ts if x not in removed]
    if not removed:
        continue
    total_removed += len(removed)
    w(("\n=== %s : removed %d / %d (kept %d) ===\n" % (t, len(removed), len(ts), len(kept))).encode())
    for x in removed[:12]:
        hit = [k for k in terms if k in x]
        w(("  [%s] %s\n" % (",".join(hit), x[:64])).encode())
    if len(removed) > 12:
        w(("  ... +%d more\n" % (len(removed) - 12)).encode())
    w(b"  -- survivors (sanity check) --\n")
    for x in kept[:4]:
        w(("     %s\n" % x[:64]).encode())
w(("\nTOTAL removed: %d\n" % total_removed).encode())
