# -*- coding: utf-8 -*-
"""Room Studio — server-side background removal core for /bgcut.

Runs ISNet (DIS, Apache-2.0 — quantized to quint8 by tools/quantize_isnet.py) via
onnxruntime on CPU and returns a transparent PNG. The frontend uses the result as an
alpha mask only (destination-in onto its own full-res canvas), so the returned image is
capped at 1024px on the long side to keep transfers small.

Storage policy (Rakuten TOS): input and output images are NEVER persisted — the only
thing written to disk is the model weights, cached under /tmp (Vercel) or ~/.cache.
Same transient posture as /imgproxy.

Heavy deps (onnxruntime / numpy / PIL) are imported lazily inside functions so the
other routes' cold start doesn't pay for them; this module itself imports stdlib only.
`available()` never imports them at all (keeps /health cheap and honest).

Env:
  BGCUT_MODEL_URL  … where to download the .onnx from on first use
                     (default: this repo's GitHub Release asset)
  BGCUT_MODEL_PATH … local .onnx path override (skips download; handy for dev)
  BGCUT_CACHE_DIR  … where to cache the downloaded model (default: /tmp on Vercel)
"""

import importlib.util
import os
import tempfile
import threading
import urllib.request

from _provider_base import CollectError, _load_dotenv

_load_dotenv()

MODEL_URL = (os.environ.get("BGCUT_MODEL_URL", "") or
             "https://github.com/mokkkii1019/room-studio/releases/download/bgcut-model-v1/isnet-general-use.quint8.onnx").strip()
MODEL_PATH = (os.environ.get("BGCUT_MODEL_PATH", "") or "").strip()
_DEFAULT_CACHE = tempfile.gettempdir() if os.environ.get("VERCEL") else os.path.expanduser("~/.cache/roomstudio")
CACHE_DIR = (os.environ.get("BGCUT_CACHE_DIR", "") or _DEFAULT_CACHE).strip()

_INFER_SIDE = 1024   # ISNet standard input (square)
_OUT_MAX = 1024      # returned PNG long-side cap (client only uses the alpha)

_lock = threading.Lock()
_sem = threading.Semaphore(2)  # cap concurrent inferences per instance (OOM guard)
_session = None


def available():
    """Can /bgcut work here? onnxruntime installed + a model source configured.
    Deliberately avoids importing onnxruntime (slow) — /health stays cheap."""
    if importlib.util.find_spec("onnxruntime") is None:
        return False
    if MODEL_PATH:  # explicit local override: honest check (no URL fallthrough — _model_file won't either)
        return os.path.isfile(MODEL_PATH)
    return bool(MODEL_URL)


def _model_file():
    """Resolve the model path, downloading to the cache dir on first use.
    Atomic (tmp file + os.replace) so concurrent cold starts can't see a torn file."""
    if MODEL_PATH:
        if os.path.isfile(MODEL_PATH):
            return MODEL_PATH
        raise CollectError(503, f"model not found: {MODEL_PATH}")
    dst = os.path.join(CACHE_DIR, "bgcut-" + os.path.basename(MODEL_URL))
    if os.path.isfile(dst):
        return dst
    if not MODEL_URL:
        raise CollectError(503, "bgcut model is not configured (BGCUT_MODEL_URL)")
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = dst + f".part-{os.getpid()}"
    try:
        req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "RoomStudio/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(tmp, dst)
    except Exception as e:  # noqa: BLE001
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise CollectError(503, f"model download failed: {e}")
    return dst


def _get_session():
    """Lazy singleton InferenceSession (model DL + session build happen once)."""
    global _session
    if _session is not None:
        return _session
    with _lock:
        if _session is not None:
            return _session
        if importlib.util.find_spec("onnxruntime") is None:
            raise CollectError(503, "onnxruntime is not installed on this deployment")
        path = _model_file()
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _session = ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])
        return _session


def cut_png(img_bytes):
    """image bytes (JPEG/PNG…) -> transparent RGBA PNG bytes (long side <= 1024).
    Raises CollectError(415) on non-image input, 500 on inference failure."""
    import io

    import numpy as np
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:  # noqa: BLE001
        raise CollectError(415, "not a decodable image")

    sess = _get_session()
    # ISNet preprocessing (rembg-compatible): square 1024 resize, x/255 then (x-0.5)/1.0, CHW.
    small = im.resize((_INFER_SIDE, _INFER_SIDE), Image.BILINEAR)
    x = np.asarray(small, dtype=np.float32) / 255.0
    x = (x - 0.5) / 1.0
    x = np.transpose(x, (2, 0, 1))[np.newaxis, ...]  # 1x3xHxW
    try:
        with _sem:
            outs = sess.run(None, {sess.get_inputs()[0].name: x})
        pred = outs[0][0, 0]  # HxW float
    except CollectError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CollectError(500, f"inference failed: {e}")
    lo, hi = float(pred.min()), float(pred.max())
    if hi - lo > 1e-6:
        pred = (pred - lo) / (hi - lo)
    alpha = Image.fromarray((np.clip(pred, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L")

    # Compose: RGB (capped at _OUT_MAX) + soft alpha, back at the image's aspect ratio.
    out = im
    if max(out.size) > _OUT_MAX:
        s = _OUT_MAX / max(out.size)
        out = out.resize((max(1, round(out.width * s)), max(1, round(out.height * s))), Image.BILINEAR)
    out = out.convert("RGBA")
    out.putalpha(alpha.resize(out.size, Image.BILINEAR))
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
