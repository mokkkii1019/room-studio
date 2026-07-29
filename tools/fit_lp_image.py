#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LP画像を配信仕様に合わせる（トリミング・リサイズ・WebP圧縮・改名）。

Room Studio の書き出しや撮って出しの写真をそのまま `lp-assets/` に置くと、
実寸・容量・ファイル名が仕様から外れて表示が崩れたり 404 になったりする。
このスクリプトを通せば、その場で仕様どおりのファイルが出来る。

使い方:
    python tools/fit_lp_image.py <元画像> <スロット名>

    # 例: Room Studio の書き出しを LP の after にする
    python tools/fit_lp_image.py ~/Downloads/room-studio.png moyougae-simulation-after

    # 例: /try のサンプル部屋にする
    python tools/fit_lp_image.py ~/Downloads/heya.jpg try-room-1

やること:
  1. スロットごとの規定比率へトリミング（`--crop-top/--crop-bottom` で位置を指定可）
  2. 規定の実寸へリサイズ
  3. 上限KB以下になる品質で WebP 保存
  4. `lp-assets/<スロット名>.webp` として配置（半角英数字のみ）
  5. 元データを `docs/src/` へ退避（`docs/` は .vercelignore 対象なので本番に載らない）

before と after で**同じトリミング**を使うこと。ずれるとLPの比較スライダーが
ガタつく。既定値は現行の before と同じ（上89px・下26px／1100x733 基準）。
"""

import argparse
import os
import shutil
import sys

try:
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit("Pillow が必要です:  pip install pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# スロット名 -> (幅, 高さ, 上限KB)。docs/LP_IMAGE_GUIDE.md と docs/BUZZ_ASSET_GUIDE.md に対応。
SLOTS = {
    "moyougae-simulation-hero":   (2400, 1350, 400),
    "moyougae-simulation-before": (1600,  900, 250),
    "moyougae-simulation-after":  (1600,  900, 250),
    "try-room-1":                 (1100,  733, 250),
    "try-furni-1":                (700,   700, 150),
}
# before/after を揃えるための既定トリミング（1100x733 の元画像に対する上下の削り量）
DEFAULT_CROP = {"moyougae-simulation-before": (89, 26),
                "moyougae-simulation-after":  (89, 26)}


def main():
    ap = argparse.ArgumentParser(description="LP画像を配信仕様に合わせる")
    ap.add_argument("src", help="元画像（どんな実寸・形式でも可。日本語ファイル名でも可）")
    ap.add_argument("slot", help="スロット名: " + " / ".join(sorted(SLOTS)))
    ap.add_argument("--crop-top", type=int, default=None, help="上から削るpx（元画像基準）")
    ap.add_argument("--crop-bottom", type=int, default=None, help="下から削るpx（元画像基準）")
    ap.add_argument("--no-archive", action="store_true", help="docs/src/ への退避をしない")
    ap.add_argument("--also-2x", action="store_true",
                    help="高DPR用に <スロット名>-2x.webp（1.5倍）も書き出す。"
                         "before/after のように全幅で大きく出す画像に付ける")
    a = ap.parse_args()

    if a.slot not in SLOTS:
        sys.exit("未知のスロット: %s\n使えるのは: %s" % (a.slot, ", ".join(sorted(SLOTS))))
    if not os.path.isfile(a.src):
        sys.exit("元画像が見つかりません: %s" % a.src)

    W, H, MAXKB = SLOTS[a.slot]
    im = Image.open(a.src)
    print("元画像 : %s  %dx%d  %s  %.0f KB" %
          (os.path.basename(a.src), im.size[0], im.size[1], im.mode,
           os.path.getsize(a.src) / 1024))

    # アルファは配信に不要。全面不透明ならそのまま落とし、透過があるなら白で敷く。
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        opaque = im.getchannel("A").getextrema() == (255, 255)
        if opaque:
            im = im.convert("RGB")
        else:
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.getchannel("A"))
            im = bg
            print("  ! 透過部分があったので白で敷きました")
    else:
        im = im.convert("RGB")

    top, bot = DEFAULT_CROP.get(a.slot, (0, 0))
    if a.crop_top is not None:
        top = a.crop_top
    if a.crop_bottom is not None:
        bot = a.crop_bottom
    if top or bot:
        sw, sh = im.size
        if top + bot >= sh:
            sys.exit("トリミングが元画像の高さを超えています")
        im = im.crop((0, top, sw, sh - bot))
        print("トリミング: 上%dpx 下%dpx -> %dx%d" % (top, bot, im.size[0], im.size[1]))

    src_ratio, dst_ratio = im.size[0] / im.size[1], W / H
    if abs(src_ratio - dst_ratio) > 0.02:
        print("  ! 比率が %.3f で規定の %.3f と違います。--crop-top/--crop-bottom で調整してください"
              % (src_ratio, dst_ratio))
    if im.size[0] < W:
        print("  ! 元が %dpx 幅しかないため %dpx へ拡大します（%.2f倍・眠くなります）"
              % (im.size[0], W, W / im.size[0]))

    _write(im, a.slot, W, H, MAXKB, (90, 86, 80, 74, 68))
    if a.also_2x:
        # 高DPR（Retina）用の 1.5倍。全幅バンドで出す before/after は、DPR2 の
        # デスクトップだと 1600px 素材が 1.8〜2.4倍に引き伸ばされて粗が出る。
        # 画素数が増えるぶん圧縮アラは目立たないので、品質は 86 から始めて
        # 同じ上限KBに収める（＝1x とほぼ同じ重さで倍の密度になる）。
        _write(im, a.slot + "-2x", W * 3 // 2, H * 3 // 2, MAXKB, (86, 82, 78, 72, 66))

    if not a.no_archive:
        os.makedirs(os.path.join(ROOT, "docs", "src"), exist_ok=True)
        ext = os.path.splitext(a.src)[1].lower() or ".png"
        arch = os.path.join(ROOT, "docs", "src", a.slot + "-master" + ext)
        # 退避済みの原本を入力に指定して作り直す使い方もあるので、自己コピーは黙って飛ばす
        if os.path.abspath(a.src) == os.path.abspath(arch):
            print("退避   : 入力が退避済みの原本と同じなのでスキップ")
        else:
            shutil.copy(a.src, arch)
            print("退避   : docs/src/%s" % os.path.basename(arch))

    print("\n次: git add lp-assets/ docs/src/ && git commit && git push（mainで本番反映）")


def _write(im, slot, W, H, MAXKB, ladder):
    """<slot>.webp を W×H で書き出す。拡大になる場合だけ軽くシャープを掛ける。"""
    out = im.resize((W, H), Image.LANCZOS)
    if im.size[0] < W:
        # 拡大は必ず眠くなる。等倍以下に縮小するときは掛けない（輪郭が硬くなるだけ）。
        # radius 1.0 / 70% はハローが出ない範囲で最も効く値を、窓枠と葉の実寸で見て決めた。
        out = out.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=3))
    dst = os.path.join(ROOT, "lp-assets", slot + ".webp")
    chosen = None
    # 上限ぎりぎりまで品質を上げても写真では見分けがつかず、ページが重くなるだけ。
    for q in ladder:
        out.save(dst, "WEBP", quality=q, method=6)
        if os.path.getsize(dst) / 1024 <= MAXKB:
            chosen = q
            break
    if chosen is None:
        print("  ! 上限 %dKB に収まりませんでした（quality %d で %.0f KB）" %
              (MAXKB, ladder[-1], os.path.getsize(dst) / 1024))
    print("出力   : lp-assets/%s.webp  %dx%d  quality=%s  %.0f KB（上限 %dKB）%s" %
          (slot, W, H, chosen or ladder[-1], os.path.getsize(dst) / 1024, MAXKB,
           "  ※拡大のためシャープ適用" if im.size[0] < W else ""))


if __name__ == "__main__":
    main()
