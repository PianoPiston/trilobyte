"""Standalone demo server. Serves this site and proxies only the two Trilobyte API calls it uses."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
import os

ROOT = Path(__file__).parent
UPSTREAM = os.getenv("TRILOBYTE_API", "http://127.0.0.1:8090")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        if self.path.startswith("/api/") or self.path.endswith((".html", ".css", ".js")) or self.path == "/":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def proxy(self, body=None):
        path = self.path
        allowed = path == "/api/ask" or (path.startswith("/api/drawings/") and path.endswith("/image"))
        if not allowed:
            self.send_error(404)
            return
        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        req = Request(UPSTREAM + path, data=body, headers=headers, method=self.command)
        try:
            with urlopen(req, timeout=90) as response:
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", response.headers.get("Content-Length", "0"))
                self.end_headers()
                self.wfile.write(response.read())
        except Exception:
            self.send_error(502, "Trilobyte API unavailable")

    def do_POST(self):
        self.proxy(self.rfile.read(int(self.headers.get("Content-Length", 0))))

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.proxy()
        else:
            super().do_GET()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8102), Handler).serve_forever()
