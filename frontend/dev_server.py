#!/usr/bin/env python3
"""Local development server for the PawConnect frontend (standard library only).

Serves the static files in this folder and forwards /api/* to the Flask backend, so the
browser sees a single origin. The backend has no CORS configuration, and this avoids
changing it. NOT for production.

Usage:  python frontend/dev_server.py [--port 8080] [--backend http://127.0.0.1:5000]
"""
import argparse
import json
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FORWARD_HEADERS = ("Authorization", "Content-Type", "Accept")


class Handler(SimpleHTTPRequestHandler):
    backend = "http://127.0.0.1:5000"

    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(self.backend + self.path, data=body, method=self.command)
        for name in FORWARD_HEADERS:
            if self.headers.get(name):
                req.add_header(name, self.headers[name])
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._reply(resp.status, resp.read(), resp.headers.get("Content-Type"))
        except urllib.error.HTTPError as e:
            self._reply(e.code, e.read(), e.headers.get("Content-Type"))
        except Exception as e:  # backend down / unreachable
            msg = json.dumps({"status": "error", "message": f"Backend unreachable at {self.backend}: {e}"}).encode()
            self._reply(502, msg, "application/json")

    def _reply(self, status, data, ctype):
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD" and status != 204:
            self.wfile.write(data)

    def _route(self, static):
        if self.path.startswith("/api/") or self.path == "/api":
            self._proxy()
        else:
            static()

    def do_GET(self): self._route(super().do_GET)
    def do_HEAD(self): self._route(super().do_HEAD)

    def do_POST(self):  # API writes are proxied; static paths reject writes
        self._route(lambda: self.send_error(405))

    do_PATCH = do_PUT = do_DELETE = do_POST


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--backend", default="http://127.0.0.1:5000")
    args = ap.parse_args()
    Handler.backend = args.backend.rstrip("/")
    handler = partial(Handler, directory=str(Path(__file__).resolve().parent))
    print(f"PawConnect frontend: http://127.0.0.1:{args.port}  ->  API proxied to {Handler.backend}")
    ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
