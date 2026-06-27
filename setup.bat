@echo off
rem Room Studio - one-time setup (Windows). Requires Python 3.10+ installed (python on PATH).
cd /d %~dp0
echo === Room Studio setup ===
python --version
if errorlevel 1 (
  echo.
  echo [NG] Python が見つかりません。https://www.python.org/ からインストールしてください。
  echo      インストール時に「Add python.exe to PATH」に必ずチェックしてください。
  pause & exit /b 1
)
echo.
echo [1/3] CPU版 PyTorch を入れます（数百MB・数分かかります）...
python -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cpu
echo.
echo [2/3] 必要パッケージを入れます...
python -m pip install --disable-pip-version-check fastapi "uvicorn[standard]" pillow numpy opencv-python fire
echo.
echo [3/3] LaMa (simple-lama-inpainting) を依存なしで入れます（numpyの不要な再ビルドを回避）...
python -m pip install --disable-pip-version-check --no-deps simple-lama-inpainting
echo.
if not exist .env if exist .env.example ( copy .env.example .env >nul & echo [i] .env を作成しました。ART OF BLACK 等の楽天収集を使う場合は .env を編集して RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY を記入してください。 )
echo.
echo === インストール確認 ===
python -c "import fastapi,uvicorn,PIL,numpy,cv2,torch,simple_lama_inpainting; print('[OK] すべての依存を読み込めました。run.bat で起動できます。')"
if errorlevel 1 (
  echo [NG] 依存の読み込みに失敗しました。上のエラー（赤字）を確認してください。
  echo      よくある原因: 途中のpipエラー / ネット未接続 / 別のPythonが使われている。
)
echo.
pause
