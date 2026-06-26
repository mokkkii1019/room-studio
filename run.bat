@echo off
rem Room Studio - start the local server and open the app.
cd /d %~dp0
start "" http://127.0.0.1:7865
python server.py
