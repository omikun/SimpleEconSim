"""
sim_server/web_server.py — Pure-Python HTTP & REST Server for REGNUM Mobile Web Client.

Serves static assets for iPhone/browser client and provides REST API endpoints
for real-time world inspection, turn advancement, and policy commands.
Prints a scannable ANSI QR code directly to the terminal on startup.
"""

import os
import sys
import json
import time
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
from typing import Optional, Dict, Any

# Ensure project root is available
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sim_server.sim_server import SimServer
from sim_server.protocol import CommandType, CommandMessage
from sim_server.qr_code import generate_terminal_qr, generate_svg_qr

WEB_ASSETS_DIR = os.path.join(project_root, 'web_client')


def get_local_ip() -> str:
    """Determine the LAN IP address of this machine for local mobile access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 8.8.8.8:80 route lookup (does not actually send packets)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'


class RegnumHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for REGNUM Web Client and REST API."""

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: World State Snapshot
        if path == '/api/state':
            try:
                state = self.server.sim_server.serialize_world()
                state['lan_url'] = self.server.base_url
                body = json.dumps(state).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error serializing world state: {e}")
            return

        # 2. API: Single Tile Details
        elif path == '/api/tile':
            tile_name = query.get('name', [None])[0]
            if not tile_name:
                self._send_error_json(400, "Missing 'name' query parameter")
                return

            tile_obj = self.server.sim_server.by_name.get(tile_name)
            if not tile_obj:
                self._send_error_json(404, f"Tile '{tile_name}' not found")
                return

            try:
                tile_data = self.server.sim_server.serialize_tile(tile_obj, layout=self.server.sim_server.layout)
                body = json.dumps(tile_data).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error serializing tile: {e}")
            return

        # 3. API: QR Code SVG
        elif path == '/api/qr.svg':
            try:
                svg_content = generate_svg_qr(self.server.base_url, size=280)
                body = svg_content.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'image/svg+xml; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error generating QR SVG: {e}")
            return

        # 4. API: Photorealistic Topographic Terrain Image
        elif path in ('/api/terrain.png', '/api/terrain', '/api/terrain.jpg'):
            format_type = query.get('format', ['jpg' if path.endswith('.jpg') else 'png'])[0].lower()
            try:
                if hasattr(self.server, 'get_terrain_image'):
                    body, mime_type = self.server.get_terrain_image(format_type)
                elif hasattr(self.server, 'web_server') and hasattr(self.server.web_server, 'get_terrain_image'):
                    body, mime_type = self.server.web_server.get_terrain_image(format_type)
                else:
                    from render_engine.terrain import TerrainRenderer
                    import io
                    import pygame
                    from PIL import Image

                    renderer = getattr(self.server, 'terrain_renderer', None)
                    if renderer is None:
                        renderer = TerrainRenderer()
                        self.server.terrain_renderer = renderer

                    sim = self.server.sim_server
                    surf = renderer.get_or_generate_surface(
                        seed=sim.terrain_seed,
                        bbox=sim.bbox,
                        tiles=sim.tiles,
                        layout=sim.layout
                    )
                    raw = pygame.image.tostring(surf, 'RGBA')
                    img = Image.frombytes('RGBA', surf.get_size(), raw)
                    bio = io.BytesIO()
                    if format_type in ('jpg', 'jpeg'):
                        img.convert('RGB').save(bio, format='JPEG', quality=85)
                        mime_type = 'image/jpeg'
                    elif format_type == 'webp':
                        img.save(bio, format='WEBP', quality=85)
                        mime_type = 'image/webp'
                    else:
                        img.save(bio, format='PNG', compress_level=3)
                        mime_type = 'image/png'
                    body = bio.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'public, max-age=3600')
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error generating terrain image: {e}")
            return

        # 5. Static Web Assets
        asset_map = {
            '/': ('index.html', 'text/html; charset=utf-8'),
            '/index.html': ('index.html', 'text/html; charset=utf-8'),
            '/style.css': ('style.css', 'text/css; charset=utf-8'),
            '/client.js': ('client.js', 'application/javascript; charset=utf-8'),
            '/favicon.ico': (None, None),
        }

        if path in asset_map:
            file_name, content_type = asset_map[path]
            if file_name is None:
                self.send_response(204)
                self.end_headers()
                return

            file_path = os.path.join(WEB_ASSETS_DIR, file_name)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self._send_error_json(404, f"Asset file '{file_name}' not found on server")
                return

        self._send_error_json(404, "Path not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/command':
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw_body = self.rfile.read(length)
                data = json.loads(raw_body.decode('utf-8'))

                cmd_type_str = data.get('cmd_type', '').upper()
                payload = data.get('payload', {})

                # Validate command type
                try:
                    cmd_type = CommandType(cmd_type_str)
                except ValueError:
                    self._send_error_json(400, f"Invalid cmd_type '{cmd_type_str}'")
                    return

                res = self.server.sim_server.execute_command(CommandMessage(cmd_type, payload))
                resp_body = json.dumps(res).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(resp_body)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(resp_body)
            except Exception as e:
                self._send_error_json(500, f"Error processing command: {e}")
            return

        self._send_error_json(404, "Endpoint not found")

    def _send_error_json(self, status_code: int, message: str):
        body = json.dumps({'error': message, 'success': False}).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence default access logging to avoid terminal clutter while playing
        pass


class RegnumWebServer:
    """Threaded web server container managing simulation loop and HTTP server."""

    def __init__(self, sim_server: SimServer, host: str = '0.0.0.0', port: int = 8080):
        self.sim_server = sim_server
        self.host = host
        self.port = port
        self.local_ip = get_local_ip()
        self.base_url = f"http://{self.local_ip}:{self.port}"

        self.httpd: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._sim_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self.terrain_renderer = None
        self._cached_terrain_bytes: Optional[bytes] = None
        self._cached_terrain_mime: str = "image/png"
        self._cached_terrain_key = None
        self._terrain_lock = threading.Lock()

    def get_terrain_image(self, format_type: str = 'png') -> tuple[bytes, str]:
        """Fetch or render photorealistic topographic terrain PNG/JPEG/WEBP image."""
        with self._terrain_lock:
            if self.terrain_renderer is None:
                from render_engine.terrain import TerrainRenderer
                self.terrain_renderer = TerrainRenderer()

            sim = self.sim_server
            from render_engine.gpu import load_gpu_settings
            try:
                gpu_settings = tuple(sorted(load_gpu_settings().items()))
            except Exception:
                gpu_settings = ()

            cache_key = (sim.terrain_seed, tuple(sim.bbox), gpu_settings, format_type)
            if self._cached_terrain_key == cache_key and self._cached_terrain_bytes is not None:
                return self._cached_terrain_bytes, self._cached_terrain_mime

            surf = self.terrain_renderer.get_or_generate_surface(
                seed=sim.terrain_seed,
                bbox=sim.bbox,
                tiles=sim.tiles,
                layout=sim.layout
            )
            import io
            import pygame
            from PIL import Image

            raw = pygame.image.tostring(surf, 'RGBA')
            img = Image.frombytes('RGBA', surf.get_size(), raw)
            bio = io.BytesIO()

            if format_type in ('jpg', 'jpeg'):
                rgb_img = img.convert('RGB')
                rgb_img.save(bio, format='JPEG', quality=85)
                mime = 'image/jpeg'
            elif format_type == 'webp':
                img.save(bio, format='WEBP', quality=85)
                mime = 'image/webp'
            else:
                img.save(bio, format='PNG', compress_level=3)
                mime = 'image/png'

            data = bio.getvalue()
            self._cached_terrain_bytes = data
            self._cached_terrain_mime = mime
            self._cached_terrain_key = cache_key
            return data, mime

    def start(self, wait_forever: bool = False):
        """Start the HTTP server and simulation background loop."""
        self._stop_event.clear()

        # 1. Bind HTTP Server
        self.httpd = ThreadingHTTPServer((self.host, self.port), RegnumHTTPRequestHandler)
        # Attach references for handler access
        self.httpd.sim_server = self.sim_server
        self.httpd.base_url = self.base_url
        self.httpd.web_server = self
        self.httpd.get_terrain_image = self.get_terrain_image

        # 2. Print scannable QR Code to terminal
        self.print_banner()

        # 3. Pre-warm terrain caches in background so client requests respond in 0ms
        threading.Thread(target=self._prewarm_terrain, name="TerrainPrewarm", daemon=True).start()

        # 4. Start Sim loop thread (advances turns automatically when playing is True)
        self._sim_thread = threading.Thread(target=self._sim_loop, name="WebSimLoop", daemon=True)
        self._sim_thread.start()

        # 5. Start HTTP Server thread
        if wait_forever:
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._http_thread = threading.Thread(target=self.httpd.serve_forever, name="WebHttpServer", daemon=True)
            self._http_thread.start()

    def _prewarm_terrain(self):
        """Asynchronously pre-generate terrain surfaces into RAM cache."""
        try:
            self.get_terrain_image('jpg')
            self.get_terrain_image('png')
        except Exception as e:
            print(f"[WebServer] Prewarm note: {e}")

    def _sim_loop(self):
        """Background thread advancing simulation when server.playing is True."""
        while not self._stop_event.is_set():
            try:
                if self.sim_server.playing:
                    self.sim_server.step()
                time.sleep(self.sim_server.turn_interval_sec)
            except Exception as e:
                print(f"[WebServer SimLoop] Error: {e}")
                time.sleep(0.5)

    def stop(self):
        """Gracefully shutdown web server and background simulation loop."""
        self._stop_event.set()
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self._http_thread and self._http_thread.is_alive():
            self._http_thread.join(timeout=2.0)
        print("[WebServer] Shutdown complete.")

    def print_banner(self):
        """Render ANSI QR code and LAN access instructions."""
        print("\n" + "=" * 56)
        print("  👑 REGNUM MOBILE WEB SERVER ONLINE")
        print("=" * 56)
        print(f"  Access on your iPhone (same Wi-Fi):")
        print(f"  👉  \033[1;36m{self.base_url}\033[0m")
        print("  Scan this QR Code with your iPhone Camera:")
        print("=" * 56)
        try:
            print(generate_terminal_qr(self.base_url))
        except Exception as e:
            print(f"  [QR generation note: {e}]")
        print("=" * 56)
        print("  Controls on phone: 1-finger pan, pinch-zoom, tap hex to inspect.")
        print("=" * 56 + "\n")


def run_web_server(sim_server: Optional[SimServer] = None, host: str = '0.0.0.0', port: int = 8080,
                   wait_forever: bool = True) -> RegnumWebServer:
    """Convenience helper to create and start the web server."""
    if sim_server is None:
        sim_server = SimServer()
    server = RegnumWebServer(sim_server=sim_server, host=host, port=port)
    server.start(wait_forever=wait_forever)
    return server


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="REGNUM Mobile Web Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help="Host address to bind (default 0.0.0.0)")
    parser.add_argument('--port', type=int, default=8080, help="Port to listen on (default 8080)")
    parser.add_argument('--seed', type=int, default=4242, help="Simulation seed")
    parser.add_argument('--terrain-seed', type=int, default=None, help="Terrain seed")
    parser.add_argument('--nation-seed', type=int, default=None, help="Nation seed")
    args = parser.parse_args()

    sim = SimServer(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed)
    run_web_server(sim_server=sim, host=args.host, port=args.port, wait_forever=True)
