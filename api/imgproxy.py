# -*- coding: utf-8 -*-
"""Vercel serverless function: GET /api/imgproxy (rewritten from /imgproxy).
Same-origin relay for furniture images (avoids canvas tainting). Allowlisted hosts only."""
import os
import sys
import json
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
import _collect_core as core  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = parse_qs(urlsplit(self.path).query).get("url", [""])[0]
        try:
            data, ctype = core.imgproxy_fetch(url)
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except core.CollectError as e:
            self._err(e.status, e.detail)
        except Exception as e:  # noqa: BLE001
            self._err(502, str(e))

    def _err(self, status, detail):
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
