#!/usr/bin/env bash
# Room Studio - one-time setup (macOS / Linux). Run:  bash setup.sh
cd "$(dirname "$0")"
echo "=== Room Studio setup ==="
if ! command -v python3 >/dev/null 2>&1; then
  echo "[NG] python3 が見つかりません。https://www.python.org/downloads/ から Python3 を入れてください。"
  exit 1
fi
python3 --version
echo "[*] 仮想環境 .venv を作成..."
python3 -m venv .venv || { echo "[NG] venv の作成に失敗しました"; exit 1; }
source .venv/bin/activate
python -m pip install --upgrade pip
echo "[1/3] PyTorch（CPU）..."
python -m pip install torch
echo "[2/3] 必要パッケージ..."
python -m pip install fastapi "uvicorn[standard]" pillow numpy opencv-python fire
echo "[3/3] LaMa (simple-lama-inpainting) を依存なしで..."
python -m pip install --no-deps simple-lama-inpainting
echo "=== インストール確認 ==="
python -c "import fastapi,uvicorn,PIL,numpy,cv2,torch,simple_lama_inpainting; print('[OK] すべて読み込めました。次は:  bash run.sh')" \
  || echo "[NG] 依存の読み込みに失敗しました。上のエラーを確認してください。"
