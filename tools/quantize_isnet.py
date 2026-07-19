# -*- coding: utf-8 -*-
"""ISNet(DIS) モデルを /bgcut 用に quint8 へ動的量子化するワンショットツール。

/bgcut（サーバ側の自動背景切り抜き）は onnxruntime + ISNet を使う。
配布元の fp32 モデル（isnet-general-use.onnx, ~170MB, Apache-2.0 — rembg 配布 /
原作 xuebinqin/DIS）は Vercel コールドスタート時の /tmp ダウンロードには大きいので、
weights を quint8 化して ~45MB に縮める。生成物は GitHub Release のアセットとして
アップロードし、環境変数 BGCUT_MODEL_URL で指す（リポジトリには同梱しない）。

使い方（プロジェクト直下で。onnxruntime / onnx / numpy が必要）:
    python tools/quantize_isnet.py [入力.onnx] [出力.onnx]
既定: isnet-general-use.onnx が無ければ rembg のリリースからダウンロードして
      isnet-general-use.quint8.onnx を生成する。
"""
import os
import sys
import urllib.request

SRC_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "isnet-general-use.onnx"
    dst = sys.argv[2] if len(sys.argv) > 2 else "isnet-general-use.quint8.onnx"
    if not os.path.isfile(src):
        print(f"download: {SRC_URL} -> {src}")
        urllib.request.urlretrieve(SRC_URL, src)
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(src, dst, weight_type=QuantType.QUInt8)
    print(f"ok: {src} ({os.path.getsize(src)/1e6:.1f}MB) -> {dst} ({os.path.getsize(dst)/1e6:.1f}MB)")


if __name__ == "__main__":
    main()
