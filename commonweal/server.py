"""server.py — thin stdlib web server over the simulation (C3: Python core + thin web UI).

Binds to 127.0.0.1 only (the old project's LAN server had no auth; this one does not
expose the sim to the network).  Mutations are POST-only.

    python server.py [port]
"""
import json
import os
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from sim.world import World
from sim.config import Params, Dials, PRESETS

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
LOCK = threading.Lock()
WORLD = World(Params())

MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/state":
            with LOCK:
                return self._json(WORLD.state())
        if u.path == "/api/person":
            with LOCK:
                p = WORLD.person(int(q.get("id", ["0"])[0]))
            return self._json(p if p else {"error": "no such person"}, 200 if p else 404)
        name = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB) or not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(os.path.splitext(path)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global WORLD
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        path = urllib.parse.urlparse(self.path).path
        with LOCK:
            if path == "/api/step":
                for _ in range(max(1, min(int(body.get("n", 1)), 400))):
                    if not WORLD.adults():
                        break
                    WORLD.step()
            elif path == "/api/reset":
                preset = body.get("preset", "endogenous")
                if preset not in PRESETS:
                    return self._json({"error": "unknown preset"}, 400)
                WORLD = World(Params(seed=int(body.get("seed", 1)), preset=preset), WORLD.dials)
            elif path == "/api/dials":
                d = WORLD.dials
                if "land_alienable" in body:
                    d.land_alienable = bool(body["land_alienable"])
                for k, lo, hi in (("hours_cap", 6.0, 16.0), ("relief_levy", 0.0, 0.5), ("usury_cap", 0.0, 1.0)):
                    if k in body:
                        setattr(d, k, max(lo, min(hi, float(body[k]))))
            else:
                return self._json({"error": "not found"}, 404)
            return self._json(WORLD.state())


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Commonweal on http://127.0.0.1:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
