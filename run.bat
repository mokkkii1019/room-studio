@echo off
rem Room Studio - start the local server, then open the app once the server is up.
cd /d %~dp0
rem open the browser a few seconds later (server needs a moment to start)
start "" cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:7865"
echo Room Studio サーバーを起動します... ( http://127.0.0.1:7865 )
echo （このウィンドウは開いたままにしてください。閉じるとサーバーが止まります）
python server.py
echo.
echo === サーバーが終了しました ===
echo 上にエラーが出ている場合は、先に setup.bat を実行してください。
pause
