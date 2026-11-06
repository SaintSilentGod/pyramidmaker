"""Note Pyramid local server.

Serves the app and proxies Fragrantica note photos through /img/<id>.jpg so the
canvas can export them (fimgs.net sends no CORS headers). Photos are cached in ./cache.
"""
import http.server
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8793
SRC = "https://fimgs.net/mdimg/sastojci/{kind}.{id}.jpg"
MAX_PX = 600


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def cached_photo(note_id):
    path = os.path.join(CACHE, f"{note_id}.jpg")
    if os.path.exists(path):
        return path
    data = None
    for kind in ("o", "t"):  # o = large original, t = 120px thumbnail
        try:
            data = fetch(SRC.format(kind=kind, id=note_id))
            break
        except Exception:
            continue
    if not data:
        return None
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    subprocess.run(["sips", "-Z", str(MAX_PX), tmp], capture_output=True)  # shrinks only if larger
    os.replace(tmp, path)
    return path


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        m = re.fullmatch(r"/img/(\d{1,5})\.jpg", self.path.split("?")[0])
        if not m:
            return super().do_GET()
        path = cached_photo(m.group(1))
        if not path:
            self.send_error(404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        if not self.path.startswith("/img/"):
            self.send_header("Cache-Control", "no-cache")  # edits to the page show up on a normal reload
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    print(f"Note Pyramid on http://127.0.0.1:{PORT}/")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
