# Build numbered contact sheets so the sample can be labelled by eye.
import json
import os
import sys

from PIL import Image, ImageDraw

d = sys.argv[1]
per = int(sys.argv[2]) if len(sys.argv) > 2 else 24
idx = json.load(open(os.path.join(d, "index.json"), encoding="utf-8"))
S, COLS = 170, 6
for page in range((len(idx) + per - 1) // per):
    chunk = idx[page * per:(page + 1) * per]
    rows = (len(chunk) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * S, rows * (S + 18)), (245, 245, 245))
    dr = ImageDraw.Draw(sheet)
    for i, rec in enumerate(chunk):
        r, c = divmod(i, COLS)
        y = r * (S + 18)
        try:
            im = Image.open(os.path.join(d, rec["file"])).convert("RGB").resize((S, S))
            sheet.paste(im, (c * S, y + 18))
        except Exception:  # noqa: BLE001
            pass
        dr.rectangle([c * S, y, c * S + S, y + 17], fill=(30, 30, 30))
        dr.text((c * S + 4, y + 4), f"{page*per+i:02d} {rec['type']}", fill=(255, 255, 255))
    out = os.path.join(d, f"sheet{page}.png")
    sheet.save(out)
    print(out, len(chunk), "cells")
