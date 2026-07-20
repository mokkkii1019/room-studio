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

SIDE = 256  # analysis resolution; results barely move down to a 128px source


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


def score(a):
    """Higher = more usable as a cut-out. Deductions only.

    Nothing rewards a plain bright background: colour-variation tables have the
    whitest, most uniform borders in the whole corpus, and the previous scorer — which
    did reward exactly that — ranked them top of the list.
    """
    tpx, tn = text_score(a)
    return (-min(1.6, tn / 60.0)
            - min(1.0, tpx * 6.0)
            - 0.8 * min(2, gutter_score(a))
            - min(0.8, vivid_score(a) * 12.0))


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
