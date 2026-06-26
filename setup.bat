@echo off
rem Room Studio - one-time setup (Windows). Requires Python 3.10+ installed (python on PATH).
cd /d %~dp0
echo === Room Studio setup ===
python --version || (echo Python が見つかりません。https://www.python.org/ からインストールしてください & pause & exit /b 1)
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
echo === 完了。run.bat を実行すると起動します。 ===
pause
