# -*- coding: utf-8 -*-
"""Vercel serverless function: GET /api/health (rewritten from /health).
On the hosted site there is no LaMa server, so inpaint=false → the app uses
the in-browser PatchMatch eraser. `ok`/`collect` signal the API is reachable."""
import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "inpaint": False, "collect": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
