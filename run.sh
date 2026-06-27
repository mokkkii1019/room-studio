#!/usr/bin/env bash
# Room Studio - start the local server, then open the app (macOS / Linux). Run:  bash run.sh
cd "$(dirname "$0")"
PY=python3
if [ -d .venv ]; then source .venv/bin/activate; PY=python; fi
# .env があれば server.py が自動で読み込みます（楽天キー等）。
# open the browser a few seconds later (server needs a moment to start)
( sleep 3; (command -v open >/dev/null && open "http://127.0.0.1:7865") || (command -v xdg-open >/dev/null && xdg-open "http://127.0.0.1:7865") ) >/dev/null 2>&1 &
echo "Room Studio: http://127.0.0.1:7865  （このターミナルは開いたままにしてください）"
$PY server.py
