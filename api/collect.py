# -*- coding: utf-8 -*-
"""Vercel serverless function: GET /api/collect (rewritten from /collect)."""
import os
import sys
import json
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
import _collect_core as core  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlsplit(self.path).query)
        g = lambda k, d="": (q.get(k, [d])[0] or d)
        try:
            count = int(g("count", "50") or 50)
        except ValueError:
            count = 50
        try:
            out = core.collect(g("type"), g("taste"), count, g("source", "ikea"), g("shop"))
            self._json(200, out)
        except core.CollectError as e:
            self._json(e.status, {"detail": e.detail})
        except Exception as e:  # noqa: BLE001
            self._json(502, {"detail": f"collect failed: {e}"})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
