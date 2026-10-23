"""
sim_server/web_server.py — Pure-Python HTTP & REST Server for Call of Capital (CoC) Mobile Web Client.

Serves static assets for iPhone/browser client and provides REST API endpoints
for real-time world inspection, turn advancement, and policy commands.
Prints a scannable ANSI QR code directly to the terminal on startup.
"""

from __future__ import annotations

import os
import sys
import json
import time
import socket
import secrets
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sim_server.sim_server import SimServer
from sim_server.protocol import CommandType, CommandMessage
from sim_server.qr_code import generate_terminal_qr, generate_svg_qr

curr_dir = os.path.dirname(os.path.abspath(__file__))
project_root = curr_dir
while project_root and project_root != '/':
    if os.path.exists(os.path.join(project_root, 'sim_engine.py')):
        break
    project_root = os.path.dirname(project_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

_client_web_static = os.path.join(project_root, 'client', 'web', 'static')
_web_client_assets = os.path.join(project_root, 'web_client')
WEB_ASSETS_DIR = (
    _client_web_static
    if os.path.isfile(os.path.join(_client_web_static, 'index.html'))
    else _web_client_assets
)


def get_local_ip() -> str:
    """Determine the LAN IP address of this machine for local mobile access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 8.8.8.8:80 route lookup (does not actually send packets)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'


class CoCHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Call of Capital (CoC) Web Client and REST API."""

    def do_OPTIONS(self):
        # The client is served from this origin. Do not enable cross-origin API access.
        self.send_response(405)
        self.send_header('Allow', 'GET, POST')
        self.end_headers()

    def _authorized_mutation(self) -> bool:
        expected = getattr(self.server, 'api_token', '')
        provided = self.headers.get('X-COC-Token', '')
        if expected and secrets.compare_digest(provided, expected):
            return True
        self._send_error_json(403, 'Missing or invalid API token')
        return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: World State Snapshot
        if path == '/api/state':
            try:
                sim = self.server.sim_server
                compact = query.get('compact', ['0'])[0] == '1'
                with sim._lock:
                    version = f"{sim.instance_id}:{sim.world_generation}:{sim.turn}:{sim.state_revision}:{int(sim.playing)}"
                    if query.get('since', [None])[0] == version:
                        self.send_response(304)
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        return
                    state = sim.serialize_world(compact=compact)
                    state['version'] = version
                state['lan_url'] = self.server.base_url
                body = json.dumps(state).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error serializing world state: {e}")
            return

        elif path == '/api/trace':
            try:
                sim = self.server.sim_server
                turn_text = query.get('turn', [None])[0]
                turn = int(turn_text) if turn_text is not None else None
                offset = max(0, int(query.get('offset', ['0'])[0]))
                limit = max(1, min(200, int(query.get('limit', ['50'])[0])))
                entity = query.get('entity', [None])[0]
                subject = None
                if entity:
                    entity_type, separator, entity_id = entity.partition(':')
                    if not separator or entity_type not in ('tile', 'nation') or not entity_id:
                        self._send_error_json(400, 'Entity must be tile:name or nation:name')
                        return
                    subject = {'type': entity_type, 'id': entity_id}
                base_currency = query.get('base', [None])[0]
                quote_currency = query.get('quote', [None])[0]
                if base_currency or quote_currency:
                    subject = dict(subject or {})
                    subject['type'] = 'fx_desk'
                    if base_currency:
                        subject['base_currency'] = base_currency
                    if quote_currency:
                        subject['quote_currency'] = quote_currency
                metric_id = query.get('metric', [None])[0]
                kind = query.get('kind', [None])[0]
                event_id = query.get('event_id', [None])[0]
                good = query.get('good', [None])[0]
                if good:
                    subject = dict(subject or {})
                    subject['good'] = good
                disease = query.get('disease', [None])[0]
                if disease:
                    subject = dict(subject or {})
                    subject['disease'] = disease
                class_group = query.get('class_group', [None])[0]
                if class_group:
                    subject = dict(subject or {})
                    subject['class_group'] = class_group
                with sim._lock:
                    result = sim.run_trace.query(turn=turn, subject=subject,
                                                 metric_id=metric_id,
                                                 kind=kind,
                                                 event_id=event_id,
                                                 offset=offset, limit=limit,
                                                 boundary=int(query['boundary'][0]) if 'boundary' in query else None)
                body = json.dumps(result, allow_nan=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, TypeError) as exc:
                self._send_error_json(400, f'Invalid trace query: {exc}')
            except Exception as exc:
                self._send_error_json(500, f'Error querying trace: {exc}')
            return

        elif path == '/api/trace/download':
            try:
                from trace_codec import decoded_size, iter_payloads
                sim = self.server.sim_server
                with sim._lock:
                    trace_path = sim.run_trace.path
                    run_id = sim.run_trace.run_id
                    boundary = sim.run_trace._compact_writer.end_offset
                compact = query.get('format', ['jsonl'])[0] == 'compact'
                download_extension = 'ctr' if compact else 'jsonl'
                body_size = (boundary if compact
                             else decoded_size(trace_path, end_offset=boundary))
                self.send_response(200)
                self.send_header('Content-Type',
                                 'application/octet-stream' if compact
                                 else 'application/x-ndjson; charset=utf-8')
                self.send_header('Content-Disposition',
                                 f'attachment; filename="run-{run_id}.{download_extension}"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(body_size))
                self.end_headers()
                if compact:
                    with trace_path.open('rb') as stream:
                        remaining = body_size
                        while remaining > 0:
                            chunk = stream.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                else:
                    for payload in iter_payloads(trace_path, end_offset=boundary):
                        self.wfile.write(payload.encode('utf-8') + b'\n')
            except Exception as exc:
                self._send_error_json(500, f'Error exporting trace: {exc}')
            return

        # Download the complete evidence trail of this live run.
        elif path == '/api/collective-trace':
            try:
                from collective_report import current_trace_text
                sim = self.server.sim_server
                with sim._lock:
                    body = current_trace_text(sim.get_world_dict(), seed=sim.seed,
                                              scenario=sim.scenario_id).encode('utf-8')
                    turn = sim.turn
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
                self.send_header('Content-Disposition',
                                 f'attachment; filename="collective-run-turn-{turn}.jsonl"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f'Error exporting collective trace: {e}')
            return

        # 2. API: Single Tile Details
        elif path == '/api/tile':
            tile_name = query.get('name', [None])[0]
            if not tile_name:
                self._send_error_json(400, "Missing 'name' query parameter")
                return

            try:
                sim = self.server.sim_server
                with sim._lock:
                    tile_obj = sim.by_name.get(tile_name)
                    if not tile_obj:
                        self._send_error_json(404, f"Tile '{tile_name}' not found")
                        return
                    tile_data = sim.serialize_tile(tile_obj, layout=sim.layout, turn=sim.turn)
                body = json.dumps(tile_data).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
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
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error generating QR SVG: {e}")
            return

        # State changes must not be triggerable through a cross-site GET.
        elif path == '/api/shutdown':
            self._send_error_json(405, 'Shutdown requires an authenticated POST request')
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
                    body, mime_type = render_terrain_image(
                        sim=self.server.sim_server,
                        terrain_renderer=getattr(self.server, 'terrain_renderer', None),
                        format_type=format_type
                    )

                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error generating terrain image: {e}")
            return

        elif path == '/api/terrain-mesh.bin':
            try:
                body = self.server.web_server.get_terrain_mesh()
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self._send_error_json(500, f"Error rendering 3D terrain: {e}")
            return

        # 5. Static Web Assets
        content_type_map = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml; charset=utf-8',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.ico': 'image/x-icon',
        }

        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        rel_path = 'index.html' if path in ('/', '') else path.lstrip('/')
        safe_path = os.path.normpath(os.path.join(WEB_ASSETS_DIR, rel_path))
        if safe_path.startswith(os.path.abspath(WEB_ASSETS_DIR)) and os.path.isfile(safe_path):
            _, ext = os.path.splitext(safe_path)
            content_type = content_type_map.get(ext.lower(), 'application/octet-stream')
            with open(safe_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            if os.path.basename(safe_path) == 'index.html':
                token = getattr(self.server, 'api_token', '')
                content = content.replace(
                    b'</head>',
                    f'<script>window.COC_API_TOKEN="{token}";</script></head>'.encode('ascii'),
                    1,
                )
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(content)
            return

        self._send_error_json(404, "Path not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/command':
            if not self._authorized_mutation():
                return
            try:
                try:
                    length = int(self.headers.get('Content-Length', 0))
                except (TypeError, ValueError):
                    self._send_error_json(400, 'Content-Length must be an integer')
                    return
                if length < 0 or length > 1024 * 1024:
                    self._send_error_json(413, 'Command body must be between 0 and 1 MiB')
                    return
                raw_body = self.rfile.read(length)
                try:
                    data = json.loads(raw_body.decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_error_json(400, 'Command body must contain valid UTF-8 JSON')
                    return
                if not isinstance(data, dict):
                    self._send_error_json(400, 'Command body must be a JSON object')
                    return
                cmd_type_str = (data.get('cmd_type') or data.get('type') or data.get('cmd') or '').upper()
                payload = data.get('payload', {})
                if not isinstance(payload, dict):
                    self._send_error_json(400, 'Command payload must be a JSON object')
                    return

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
                self.end_headers()
                self.wfile.write(resp_body)
            except Exception as e:
                self._send_error_json(500, f"Error processing command: {e}")
            return

        elif parsed.path == '/api/shutdown':
            if not self._authorized_mutation():
                return
            resp_body = json.dumps({"success": True, "message": "Call of Capital (CoC) server is shutting down..."}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            if hasattr(self.server, 'web_server') and self.server.web_server:
                threading.Thread(target=self.server.web_server.stop, daemon=True).start()
            return

        elif parsed.path == '/api/restart':
            if not self._authorized_mutation():
                return
            web_server = getattr(self.server, 'web_server', None)
            if web_server is None:
                self._send_error_json(503, 'Web server restart is unavailable')
                return
            resp_body = json.dumps({'success': True, 'message': 'Web server is restarting.'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            threading.Timer(0.25, web_server.restart).start()
            return

        self._send_error_json(404, "Endpoint not found")

    def _send_error_json(self, status_code: int, message: str):
        body = json.dumps({'error': message, 'success': False}).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence default access logging to avoid terminal clutter while playing
        pass


def render_terrain_pil(sim: SimServer) -> Any:
    """Pure-Python / NumPy / PIL terrain fallback when Pygame/ModernGL is unavailable."""
    from PIL import Image, ImageDraw
    import numpy as np
    import math
    from hexmap import axial_to_pixel

    w, h = 1200, 900
    x0, y0, x1, y1 = sim.bbox
    pad_x = (x1 - x0) * 0.2
    pad_y = (y1 - y0) * 0.2
    min_wx = x0 - pad_x
    min_wy = y0 - pad_y
    world_w = (x1 - x0) + 2.0 * pad_x
    world_h = (y1 - y0) + 2.0 * pad_y

    scale_x = w / max(1.0, world_w)
    scale_y = h / max(1.0, world_h)

    # Base ocean with procedural water noise
    try:
        rng = np.random.default_rng(sim.terrain_seed or 4242)
        noise = rng.integers(-8, 8, (h, w, 3), dtype=np.int16)
        base_ocean = np.full((h, w, 3), [13, 30, 51], dtype=np.int16)
        ocean_arr = np.clip(base_ocean + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(ocean_arr, 'RGB')
    except Exception:
        img = Image.new('RGB', (w, h), (13, 30, 51))

    draw = ImageDraw.Draw(img)

    biome_colors = {
        'ocean': (13, 30, 51),
        'shelf': (22, 49, 79),
        'plains': (61, 92, 49),
        'forest': (33, 66, 30),
        'mountain': (97, 95, 90),
        'hill': (78, 89, 59),
        'desert': (125, 111, 67),
        'snow': (220, 230, 238),
        'tundra': (90, 104, 107),
    }

    hex_size = getattr(sim, 'hex_size', 50.0)
    for t in sim.tiles:
        coords = sim.layout.get(t.name)
        if not coords:
            continue
        cx, cy = axial_to_pixel(coords[0], coords[1], hex_size)
        px = (cx - min_wx) * scale_x
        py = (cy - min_wy) * scale_y
        size_px = hex_size * scale_x

        pts = []
        for i in range(6):
            ang = math.pi / 180.0 * (60.0 * i - 30.0)
            pts.append((px + size_px * 1.05 * math.cos(ang), py + size_px * 1.05 * math.sin(ang)))

        col = biome_colors.get(t.biome, (61, 92, 49))
        if getattr(t, 'is_ocean', False):
            col = (13, 30, 51) if getattr(t, 'elevation', 0) < -0.4 else (22, 49, 79)
        draw.polygon(pts, fill=col)

    return img


def render_terrain_image(sim: SimServer, terrain_renderer=None, format_type: str = 'png') -> tuple[bytes, str]:
    """Render photorealistic Mapgen2 terrain image matching the desktop client render."""
    import io
    import json
    import numpy as np
    from PIL import Image

    img = None
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slot_cache_path = os.path.join(project_dir, 'saved_slots', 'slot_1_terrain.png')

    # 1. Primary: Load cached Mapgen2 3D micropoly terrain image (matching desktop client)
    if os.path.exists(slot_cache_path):
        try:
            img = Image.open(slot_cache_path)
            # Verify valid image dimensions
            if img.width < 100 or img.height < 100:
                img = None
        except Exception as e:
            print(f"[WebServer] Could not load Mapgen2 slot cache {slot_cache_path}: {e}")
            img = None

    # 2. Secondary: Dynamically synthesize Mapgen2 micropoly terrain if cache missing
    if img is None:
        try:
            import pygame
            from mapgen_web import get_cached_graph, get_cached_micropolys, build_micropoly_trees, build_coastal_surf_ribbon
            from render_island_micropolys import render_mesh
            from scipy.spatial import cKDTree

            slot_json_path = os.path.join(project_dir, 'saved_slots', 'slot_1.json')
            slot_state = {}
            if os.path.exists(slot_json_path):
                with open(slot_json_path, 'r', encoding='utf-8') as f:
                    slot_state = json.load(f).get('state', {})

            seed = int(slot_state.get('seed', sim.terrain_seed or 777))
            shape = slot_state.get('shape', 'radial')
            points = int(slot_state.get('points', 1000))
            rivers = int(slot_state.get('rivers', 25))
            sharpness = float(slot_state.get('sharpness', 1.9))

            gen = get_cached_graph(seed=seed, shape=shape, points=points, rivers=rivers, sharpness=sharpness)

            graph_key = (
                seed, shape, points, rivers, round(sharpness, 2),
                0.0, 0.0, 0.0, 0.0,
                round(float(slot_state.get('canyon_depth', 2.7)), 2),
                round(float(slot_state.get('valley_width', 1.4)), 2)
            )

            triangles, _ = get_cached_micropolys(
                gen, graph_key,
                int(slot_state.get('polys', 16000)),
                float(slot_state.get('roughness', 3.0)),
                float(slot_state.get('jitter', 0.22)),
                float(slot_state.get('alpha', 0.0)),
                float(slot_state.get('height_scale', 48.0)),
                float(slot_state.get('smooth', 0.7)),
                quad_fold=slot_state.get('quad_fold', True),
                ridge_noise=float(slot_state.get('ridge_noise', 0.35)),
                erosion_strength=float(slot_state.get('erosion_strength', 0.3)),
                erosion_droplets=int(slot_state.get('erosion_droplets', 15000)),
            )

            mesh_pts = np.asarray([v for t in triangles for v in (t[0], t[1], t[2])], dtype=np.float32)
            mesh_tree = cKDTree(mesh_pts[:, :2])

            def sample_elevation(pts_xy):
                dists, idxs = mesh_tree.query(pts_xy, k=min(3, len(mesh_pts)))
                if dists.ndim == 1:
                    z = mesh_pts[idxs.flatten(), 2]
                else:
                    w = 1.0 / np.maximum(dists, 1e-4)
                    w /= np.sum(w, axis=1, keepdims=True)
                    z = np.sum(mesh_pts[idxs, 2] * w, axis=1)
                return np.maximum(0.0, z) + 0.08

            all_triangles = list(triangles)
            if slot_state.get('micropoly_trees', True):
                tree_arr = build_micropoly_trees(
                    gen, sample_elevation,
                    height_scale=float(slot_state.get('height_scale', 48.0)),
                    tree_density=float(slot_state.get('tree_density', 1.28)),
                    subdivided_triangles=triangles
                )
                for i in range(0, len(tree_arr), 30):
                    p0 = np.array([tree_arr[i], tree_arr[i+1], tree_arr[i+2]], dtype=np.float64)
                    p1 = np.array([tree_arr[i+10], tree_arr[i+11], tree_arr[i+12]], dtype=np.float64)
                    p2 = np.array([tree_arr[i+20], tree_arr[i+21], tree_arr[i+22]], dtype=np.float64)
                    norm = np.array([tree_arr[i+3], tree_arr[i+4], tree_arr[i+5]], dtype=np.float64)
                    col = np.array([tree_arr[i+6]*255, tree_arr[i+7]*255, tree_arr[i+8]*255], dtype=np.float64)
                    elev = float(tree_arr[i+9])
                    all_triangles.append((p0, p1, p2, col, elev, False, 0, norm))

            if slot_state.get('micropoly_waves', True):
                surf_arr = build_coastal_surf_ribbon(
                    gen, ribbon_width=32.0 * float(slot_state.get('wave_intensity', 1.4))
                )
                for i in range(0, len(surf_arr), 30):
                    p0 = np.array([surf_arr[i], surf_arr[i+1], surf_arr[i+2]], dtype=np.float64)
                    p1 = np.array([surf_arr[i+10], surf_arr[i+11], surf_arr[i+12]], dtype=np.float64)
                    p2 = np.array([surf_arr[i+20], surf_arr[i+21], surf_arr[i+22]], dtype=np.float64)
                    norm = np.array([0.0, 0.0, 1.0], dtype=np.float64)
                    dist = float(surf_arr[i+9])
                    if dist < 0.25:
                        col = np.array([245.0, 252.0, 255.0])
                    elif dist < 0.55:
                        col = np.array([55.0, 185.0, 215.0])
                    else:
                        col = np.array([28.0, 120.0, 180.0])
                    all_triangles.append((p0, p1, p2, col, 0.0, False, 0, norm))

            topo_surf = render_mesh(
                gen, all_triangles,
                width=2048, height=2048,
                sun_azimuth=float(slot_state.get('sun_azimuth', -45.0)),
                sun_elevation=float(slot_state.get('sun_elevation', 24.0)),
                sun_intensity=float(slot_state.get('sun_intensity', 1.15)),
                ambient_intensity=float(slot_state.get('ambient_intensity', 0.45)),
                rot_pitch=0.0, rot_yaw=0.0,
            )
            raw = pygame.image.tostring(topo_surf, 'RGBA')
            img = Image.frombytes('RGBA', topo_surf.get_size(), raw)
            try:
                img.save(slot_cache_path)
            except Exception:
                pass
        except Exception as e:
            print(f"[WebServer] Mapgen2 render pipeline fallback note: {e}")
            img = None

    # 3. Tertiary: Fallback to procedural terrain renderer
    if img is None:
        try:
            import pygame
            if terrain_renderer is None:
                from render_engine.terrain import TerrainRenderer
                terrain_renderer = TerrainRenderer()

            surf = terrain_renderer.get_or_generate_surface(
                seed=sim.terrain_seed,
                bbox=sim.bbox,
                tiles=sim.tiles,
                layout=sim.layout
            )
            raw = pygame.image.tostring(surf, 'RGBA')
            img = Image.frombytes('RGBA', surf.get_size(), raw)
        except Exception as e:
            print(f"[WebServer] Pygame terrain pipeline note: {e}. Using PIL fallback.")
            img = None

    # 4. Emergency: pure PIL fallback
    if img is None:
        img = render_terrain_pil(sim)

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

    return bio.getvalue(), mime


class CoCWebServer:
    """Threaded web server container managing simulation loop and HTTP server."""

    def __init__(self, sim_server: SimServer, host: str = '0.0.0.0', port: int = 8080):
        self.sim_server = sim_server
        self.host = host
        self.port = port
        self.local_ip = get_local_ip()
        self.base_url = f"http://{self.local_ip}:{self.port}"
        self.api_token = secrets.token_urlsafe(32)

        self.httpd: Optional[ThreadingHTTPServer] = None
        self._http_thread: Optional[threading.Thread] = None
        self._sim_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._restart_event = threading.Event()

        self.terrain_renderer = None
        self._cached_terrain_bytes: Optional[bytes] = None
        self._cached_terrain_mime: str = "image/png"
        self._cached_terrain_key = None
        self._terrain_lock = threading.Lock()
        self._terrain_mesh_lock = threading.Lock()
        self._terrain_mesh_generation = None
        self._terrain_mesh_bytes = None
        self._restart_lock = threading.Lock()

    def get_terrain_image(self, format_type: str = 'png') -> tuple[bytes, str]:
        """Fetch or render photorealistic topographic terrain PNG/JPEG/WEBP image."""
        with self._terrain_lock:
            sim = self.sim_server
            try:
                from render_engine.gpu import load_gpu_settings
                gpu_settings = tuple(sorted(load_gpu_settings().items()))
            except Exception:
                gpu_settings = ()

            cache_key = (sim.terrain_seed, tuple(sim.bbox), gpu_settings, format_type)
            if self._cached_terrain_key == cache_key and self._cached_terrain_bytes is not None:
                return self._cached_terrain_bytes, self._cached_terrain_mime

            data, mime = render_terrain_image(
                sim=sim,
                terrain_renderer=self.terrain_renderer,
                format_type=format_type
            )
            self._cached_terrain_bytes = data
            self._cached_terrain_mime = mime
            self._cached_terrain_key = cache_key
            return data, mime

    def get_terrain_mesh(self) -> bytes:
        """Return desktop terrain, tree, river, and coastal mesh buffers for WebGL."""
        import struct
        import numpy as np
        sim = self.sim_server
        with sim._lock:
            generation = sim.world_generation
            gen = sim.gen
            slot_state = dict(getattr(gen, 'slot_1_state', None) or {})
        if gen is None:
            raise RuntimeError('3D Mapgen terrain is unavailable for this world')
        if not slot_state:
            from world_config import load_mapgen_slot_one
            slot_state = load_mapgen_slot_one()
        with self._terrain_mesh_lock:
            if generation == self._terrain_mesh_generation and self._terrain_mesh_bytes is not None:
                return self._terrain_mesh_bytes

            from mapgen_web import (
                get_cached_micropolys, build_micropoly_trees,
                build_hydro_river_ribbons, build_coastal_surf_ribbon,
            )
            from world_config import mapgen_mesh_graph_key
            graph_key = mapgen_mesh_graph_key(gen)
            triangles, _ = get_cached_micropolys(
                gen, graph_key, int(slot_state.get('polys', 16000)),
                float(slot_state.get('roughness', 3.0)), float(slot_state.get('jitter', 0.22)),
                float(slot_state.get('alpha', 0.0)), float(slot_state.get('height_scale', 48.0)),
                float(slot_state.get('smooth', 0.7)), quad_fold=slot_state.get('quad_fold', True),
                ridge_noise=float(slot_state.get('ridge_noise', 0.35)),
                erosion_strength=float(slot_state.get('erosion_strength', 0.3)),
                erosion_droplets=int(slot_state.get('erosion_droplets', 15000)),
                persistent_cache=slot_state.get('scenario_id', 'slot_1_mesh_v3'),
            )
            from scipy.spatial import cKDTree
            vertices = np.asarray([point for triangle in triangles for point in triangle[:3]], dtype=np.float32)
            vertex_tree = cKDTree(vertices[:, :2])

            def sample_elevation(points):
                distances, indices = vertex_tree.query(points, k=min(3, len(vertices)))
                if distances.ndim == 1:
                    return np.maximum(0.0, vertices[indices.flatten(), 2]) + 0.08
                weights = 1.0 / np.maximum(distances, 1e-4)
                weights /= np.sum(weights, axis=1, keepdims=True)
                return np.maximum(0.0, np.sum(vertices[indices, 2] * weights, axis=1)) + 0.08

            mesh = []
            for p0, p1, p2, color, elev, _is_river, _poly, normal in triangles:
                values = [*normal, *(float(c) / 255.0 for c in color), float(elev)]
                for point in (p0, p1, p2):
                    mesh.extend([*point, *values])
            mesh = np.asarray(mesh, dtype='<f4')

            trees = np.empty(0, dtype='<f4')
            if slot_state.get('micropoly_trees', True):
                trees = np.asarray(build_micropoly_trees(
                    gen, sample_elevation,
                    height_scale=float(slot_state.get('height_scale', 48.0)),
                    tree_density=float(slot_state.get('tree_density', 1.28)),
                    subdivided_triangles=triangles,
                ), dtype='<f4')
            rivers = np.asarray(build_hydro_river_ribbons(
                gen, sample_mesh_elevation=sample_elevation,
                height_scale=float(slot_state.get('height_scale', 48.0)),
                river_width_mult=float(slot_state.get('river_width', 1.0)),
                river_count=int(slot_state.get('rivers', 25)),
            ), dtype='<f4') if int(slot_state.get('rivers', 25)) > 0 else np.empty(0, dtype='<f4')
            surf = np.asarray(build_coastal_surf_ribbon(
                gen, ribbon_width=32.0 * float(slot_state.get('wave_intensity', 1.4)),
            ), dtype='<f4') if slot_state.get('micropoly_waves', True) else np.empty(0, dtype='<f4')
            buffers = (mesh, trees, rivers, surf)
            flags = (
                (1 if slot_state.get('micropoly_strata', True) else 0)
                | (2 if slot_state.get('shadows', True) else 0)
                | (4 if slot_state.get('micropoly_waves', True) else 0)
            )
            render_settings = (
                float(slot_state.get('sun_azimuth', -45.0)),
                float(slot_state.get('sun_elevation', 24.0)),
                float(slot_state.get('sun_intensity', 1.15)),
                float(slot_state.get('ambient_intensity', 0.45)),
                float(slot_state.get('mountain_roughness', 1.0)),
                float(slot_state.get('snow_altitude', 0.70)),
                float(slot_state.get('shadow_darkness', 1.0)),
                float(slot_state.get('wave_intensity', 1.4)),
                float(slot_state.get('wave_speed', 0.65)),
                float(slot_state.get('wave_period', 1.2)),
                float(slot_state.get('foam_coverage', 0.85)),
                float(slot_state.get('wave_desync', 0.60)),
            )
            header = struct.pack('<5I12f', *(len(values) for values in buffers), flags, *render_settings)
            body = header + b''.join(values.tobytes() for values in buffers)
            self._terrain_mesh_generation = generation
            self._terrain_mesh_bytes = body
            return body


    def start(self, wait_forever: bool = False):
        """Start the HTTP server and simulation background loop."""
        self._stop_event.clear()

        # 1. Bind HTTP Server
        self.httpd = self._create_http_server()

        # 2. Print scannable QR Code to terminal
        self.print_banner()

        # 3. Pre-warm terrain caches in background so client requests respond in 0ms
        threading.Thread(target=self._prewarm_terrain, name="TerrainPrewarm", daemon=True).start()

        # 4. Start Sim loop thread (advances turns automatically when playing is True)
        self._sim_thread = threading.Thread(target=self._sim_loop, name="WebSimLoop", daemon=True)
        self._sim_thread.start()

        # 5. Serve on a managed thread so a listener restart can preserve the process.
        self._http_thread = threading.Thread(
            target=self._serve_http,
            name='WebHttpServer',
            daemon=not wait_forever,
        )
        self._http_thread.start()
        if wait_forever:
            try:
                self._http_thread.join()
            except KeyboardInterrupt:
                self.stop()

    def _create_http_server(self):
        httpd = ThreadingHTTPServer((self.host, self.port), CoCHTTPRequestHandler)
        httpd.sim_server = self.sim_server
        httpd.base_url = self.base_url
        httpd.api_token = self.api_token
        httpd.web_server = self
        httpd.get_terrain_image = self.get_terrain_image
        return httpd

    def _serve_http(self):
        while not self._stop_event.is_set():
            httpd = self.httpd
            if httpd is None:
                return
            httpd.serve_forever()
            httpd.server_close()
            if self._stop_event.is_set() or not self._restart_event.is_set():
                return
            self._restart_event.clear()
            try:
                self.httpd = self._create_http_server()
                threading.Thread(target=self._prewarm_terrain, name='TerrainPrewarm', daemon=True).start()
                print('[WebServer] HTTP listener restarted.')
            except OSError as exc:
                self.httpd = None
                print(f'[WebServer] Could not restart HTTP listener: {exc}')
                return

    def restart(self):
        """Restart the HTTP listener while preserving the simulation and terrain caches."""
        current = self.httpd
        if current is None or self._stop_event.is_set():
            return False
        with self._restart_lock:
            if self._restart_event.is_set():
                return True
            self._restart_event.set()
            threading.Thread(target=current.shutdown, name='WebHttpRestart', daemon=True).start()
        return True

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
        print("  👑 CALL OF CAPITAL (CoC) WEB SERVER ONLINE")
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


def run_web_server(sim_server: Optional['SimServer'] = None, host: str = '0.0.0.0', port: int = 8080,
                   wait_forever: bool = True) -> CoCWebServer:
    """Convenience helper to create and start the web server."""
    if sim_server is None:
        from sim_server.sim_server import SimServer
        sim_server = SimServer()
    server = CoCWebServer(sim_server=sim_server, host=host, port=port)
    server.start(wait_forever=wait_forever)
    return server


if __name__ == '__main__':
    from sim_server.sim_server import SimServer
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Call of Capital (CoC) Mobile Web Server")
    parser.add_argument('--host', type=str, default='0.0.0.0', help="Host address to bind (default 0.0.0.0)")
    parser.add_argument('--port', type=int, default=8080, help="Port to listen on (default 8080)")
    parser.add_argument('--restore-checkpoint', type=Path, default=None, help='Resume a trusted local full simulation checkpoint into a new branch')
    parser.add_argument('--checkpoint-branches', type=Path, default=Path('tmp/checkpoint-branches'))
    parser.add_argument('--seed', type=int, default=None, help="Simulation seed (default: Mapgen2 slot one)")
    parser.add_argument('--terrain-seed', type=int, default=None, help="Terrain seed")
    parser.add_argument('--nation-seed', type=int, default=None, help="Nation seed")
    parser.add_argument('--topology', type=str, default='voronoi', choices=['voronoi', 'hex'],
                        help="World topology: 'voronoi' (irregular polygons) or 'hex' (honeycomb)")
    parser.add_argument('--scenario', choices=['labor-frontier-rivalry'], default=None)
    args = parser.parse_args()

    if args.restore_checkpoint:
        sim = SimServer.restore_checkpoint(args.restore_checkpoint, args.checkpoint_branches)
    else:
        sim = SimServer(seed=args.seed, terrain_seed=args.terrain_seed, nation_seed=args.nation_seed,
                        topology=args.topology,
                        scenario_id='labor_frontier_rivalry' if args.scenario else None)
    run_web_server(sim_server=sim, host=args.host, port=args.port, wait_forever=True)
