# Python mirror of the candidate scorer shipped in room-studio.html
# (candTextScore / candGutterScore / candVividScore / scoreCandidate).
#
# The browser is the thing that actually runs this, but tuning a scorer by reloading a
# web page is hopeless, so the rule lives here too and the two are kept in lockstep:
# eval_imgscore.py --parity dumps identical pixel buffers and diffs the numbers.
#
# Any change to a threshold here must be mirrored in room-studio.html and re-measured
# with eval_imgscore.py before it ships.
import numpy as np
from PIL import Image
from scipy import ndimage

SIDE = 256      # analysis resolution (the canvas the features are computed on)
FETCH_PX = 300  # what the client downloads to score with — keep in sync with
#                 CAND_FETCH_PX in room-studio.html.
#
# FETCH_PX is not a free parameter. Scoring started at 128px to save bandwidth; measured
# against the `delivered` set that was wrong in a way the earlier item-level metric was
# too coarse to show — downscaling destroys the fine glyph structure text detection
# relies on, so overlay text stopped being detected at all:
#
#   source | 1 image | precision@24 | mean(usable) - mean(text)
#    128px |   4.8KB |     46%      |  -0.02   <- text scored *better* than usable
#    200px |   9.6KB |     54%      |  +0.38
#    300px |  18.8KB |     62%      |  +0.46
#    600px |  58.1KB |     62%      |  +0.41
#
# 300px matches full size at a third of the bytes. Do not lower it without re-running
# eval_imgscore.py on the `delivered` set.


def load(path, side=SIDE):
    return np.asarray(Image.open(path).convert("RGB")
                      .resize((side, side), Image.BILINEAR)).astype(np.float32)


def _edges(g):
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    return np.hypot(gx, gy)


def text_score(a):
    """(covered fraction, blob count) for small dense text-like components.

    Glyphs are small, high-contrast and of limited stroke width. Product outlines are
    long and thin (filtered by the fill test), photo texture is low contrast (filtered
    by the percentile threshold).
    """
    e = _edges(a.mean(axis=2))
    strong = e > max(28.0, np.percentile(e, 92))
    lab, n = ndimage.label(strong, structure=np.ones((3, 3)))
    if n == 0:
        return 0.0, 0
    areas = ndimage.sum(strong, lab, range(1, n + 1))
    glyph_px, glyphs = 0.0, 0
    for area, sl in zip(areas, ndimage.find_objects(lab)):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if h < 3 or w < 3 or h > 40 or w > 40:
            continue
        if area < 8 or area > 400:
            continue
        if area / max(1, h * w) < 0.08:
            continue
        glyphs += 1
        glyph_px += h * w
    return glyph_px / (a.shape[0] * a.shape[1]), glyphs


def gutter_score(a):
    """Count of flat interior row/column bands — the separators in a collage."""
    g = a.mean(axis=2)
    n = g.shape[0]
    inner = slice(int(n * 0.12), int(n * 0.88))

    def bands(flat):
        out, cur = 0, 0
        for v in flat:
            if v:
                cur += 1
            else:
                if cur >= 3:
                    out += 1
                cur = 0
        return out + (1 if cur >= 3 else 0)

    return bands(g.std(axis=1)[inner] < 4.0) + bands(g.std(axis=0)[inner] < 4.0)


def vivid_score(a):
    """Fraction of vividly saturated pixels — ranking ribbons and coupon badges."""
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    return float(((sat > 0.55) & (mx / 255.0 > 0.45)).mean())


def seam_score(a, thr=18.0, frac=0.80):
    """(count, strongest) of interior rows/columns that are almost entirely an edge.

    gutter_score() only finds collages separated by FLAT whitespace. Measured over 120
    live deliveries, collages are the largest remaining failure class and most of them
    butt photographs straight against each other, so no flat gap exists — but the seam
    still runs the full width of the frame, which a real photograph essentially never
    does. Catches 7 of 14 collages for 2 false positives out of 39 usable images.
    """
    g = a.mean(axis=2)
    n = g.shape[0]
    lo, hi = int(n * 0.10), int(n * 0.90)
    rows = (np.abs(np.diff(g, axis=0)) > thr).mean(axis=1)[lo:hi]
    cols = (np.abs(np.diff(g, axis=1)) > thr).mean(axis=0)[lo:hi]
    seams = int((rows > frac).sum() + (cols > frac).sum())
    return seams, float(max(rows.max(initial=0.0), cols.max(initial=0.0)))


def score(a):
    """Higher = more usable as a cut-out. Deductions only.

    Nothing rewards a plain bright background: colour-variation tables have the
    whitest, most uniform borders in the whole corpus, and the previous scorer — which
    did reward exactly that — ranked them top of the list.

    This is the *selection* score: which candidate of an item to take, and which items
    survive the over-fetch. place_score() below is a different question — see there.
    """
    tpx, tn = text_score(a)
    seams, seam_max = seam_score(a)
    return (-min(1.6, tn / 60.0)
            - min(1.0, tpx * 6.0)
            - 0.8 * min(2, gutter_score(a))
            - min(0.8, vivid_score(a) * 12.0)
            - 1.0 * min(2, seams)
            - (0.8 if seam_max >= 0.80 else 0.0))


# ---- placeability (指示016) --------------------------------------------------
RING, NEAR, FAR = 0.08, 24.0, 32.0


def _ring_mask(n):
    b = max(2, int(round(n * RING)))
    m = np.zeros((n, n), bool)
    m[:b, :] = m[-b:, :] = m[:, :b] = m[:, -b:] = True
    return m


def _hist_median(v):
    """Lower median through a 256-bin histogram. np.median() averages the two central
    values on an even count and would then disagree with the browser; this cannot."""
    cum = np.cumsum(np.bincount(v.astype(np.uint8), minlength=256))
    return float(min(255, int(np.searchsorted(cum, (len(v) + 1) // 2))))


def place_feats(a):
    """(ring_pure, ring_edge, fg_border) — how close the frame is to 'product on a
    plain sweep'. Measured AUC against 210 hand-labelled delivered images:
    ring_pure 0.913, fg_border 0.891, ring_edge 0.838. Mirrored in room-studio.html
    as candPlaceFeat(); parity.js diffs the two.
    """
    n = a.shape[0]
    rm = _ring_mask(n)
    bg = np.array([_hist_median(a[..., c][rm]) for c in range(3)], np.float64)
    dist = np.abs(a.astype(np.float64) - bg).max(axis=2)
    fr = np.zeros((n, n), bool)
    fr[:2, :] = fr[-2:, :] = fr[:, :2] = fr[:, -2:] = True
    # Edges are measured on the RGB *sum* in integers and compared squared. Averaging
    # into float32 disagrees with the browser by 1 ULP, which flips pixels sitting exactly
    # on the threshold and breaks parity (it did). Sum => threshold 24*3=72, squared 5184.
    gs = a.astype(np.int32).sum(axis=2)
    dx = np.abs(np.diff(gs, axis=1, prepend=gs[:, :1]))
    dy = np.abs(np.diff(gs, axis=0, prepend=gs[:1, :]))
    return (float((dist[rm] < NEAR).mean()),
            float(((dx * dx + dy * dy)[rm] > 5184).mean()),
            float((dist[fr] > FAR).mean()))


def _c01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def place_score(a, sel=None):
    """Higher = easier to drop straight into a room. Built on top of score() so the
    collage/banner deductions carry over, then penalised for a busy background and for
    overlay text.

    This is used for ORDERING ONLY, never to drop or to choose between an item's
    candidates: rewarding a plain background is safe when nothing is excluded, and
    unsafe otherwise — picking candidates with it promotes review-score cards, spec
    diagrams and illustrated brand cards, all of which look like 'one object on white'.
    Weights come from a multi-start search over 210 hand labels with
    leave-one-category-out validation (docs/COLLECT_RANKING_REPORT.md).

    Re-tuning these was tried in 指示018 (text terms up, background terms down) and
    REJECTED in 指示019: it improved the 70-image @10 totals but made the first three
    slots worse in sofa / plant / chest. Judge any future change on the first three
    (docs/COLLECT_RANKING_REPORT.md §12), not on @10 sums.
    """
    if sel is None:
        sel = score(a)
    pure, edge, border = place_feats(a)
    tpx, tn = text_score(a)
    return (sel
            - 1.2 * _c01((0.75 - pure) / 0.45)
            - 0.3 * _c01((border - 0.10) / 0.35)
            - 0.6 * _c01(edge / 0.10)
            - 0.3 * _c01(tn / 45.0)
            - 2.0 * _c01(tpx / 0.09))


def diversify_by_shop(rows, per=2, key="shop"):
    """Mirror of diversifyByShop() in room-studio.html: send a shop's (per+1)th and later
    images to a later pass so one shop cannot fill the first screen. Nothing is dropped,
    and the order inside a pass is unchanged, so this is a pure reordering.
    """
    if not per or len(rows) < 3:
        return list(rows)
    seen, passes = {}, []
    for r in rows:
        k = r.get(key) or ""
        n = seen.get(k, 0)
        seen[k] = n + 1
        p = n // per
        while len(passes) <= p:
            passes.append([])
        passes[p].append(r)
    return [r for p in passes for r in p]


def score_legacy(a64):
    """The scorer this replaced, kept so the comparison can be re-run.

    Border uniformity + lightness + centre detail - skin fraction. Measured against
    hand labels it was anti-correlated with usable images, and its "skin" term fired
    on beige fabric and light wood rather than on people.
    """
    g = a64.mean(axis=2)
    s, m = 64, max(2, round(64 * 0.12))
    mask = np.zeros((s, s), bool)
    mask[:m, :] = mask[-m:, :] = mask[:, :m] = mask[:, -m:] = True
    vals = g[mask]
    lightness, uniform = vals.mean() / 255, 1 - min(1, vals.std() / 55)
    c0, c1 = round(s * 0.3), round(s * 0.7)
    center = min(1, g[c0:c1, c0:c1].std() / 35)
    R, G, B = a64[..., 0], a64[..., 1], a64[..., 2]
    skin = ((R > 95) & (G > 40) & (B > 20) & (R > G) & (R > B)
            & ((R - np.minimum(G, B)) > 15) & (np.abs(R - G) > 15)).mean()
    return uniform * 0.5 + lightness * 0.25 + center * 0.25 - (max(0, skin - 0.06) * 5)
