#!/usr/bin/env python3
"""
mapgen_web.py — High-Performance Mobile-Ready Web Server for Mapgen2 Terrain Explorer.

Serves an interactive web application optimized for iPhone (and desktop), providing
instant visual map updates, touch cell inspection, and native Apple AR Quick Look
3D USDZ streaming over Tailscale.

Usage:
    python3 mapgen_web.py [--port 8080] [--host 0.0.0.0]
"""

import sys
import os
import io
import time
import json
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Tuple, Any, Optional, List

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from polygon_map import PolygonMapGenerator
from render_island_micropolys import (
    build_island_mesh,
    render_mesh,
    export_island_wireframe_usdz,
)

# ---------------------------------------------------------------------------
# Two-Tier In-Memory Cache for Instant Interactive Response
# ---------------------------------------------------------------------------
GRAPH_CACHE: Dict[Tuple, PolygonMapGenerator] = {}
MESH_CACHE: Dict[Tuple, Tuple[List[Tuple], int]] = {}
MAX_CACHE_ENTRIES = 12


def get_cached_graph(seed: int, shape: str, points: int, rivers: int, sharpness: float, size: int) -> PolygonMapGenerator:
    key = (seed, shape, points, rivers, round(sharpness, 2), size)
    if key in GRAPH_CACHE:
        return GRAPH_CACHE[key]

    gen = PolygonMapGenerator(
        seed=seed,
        width=size,
        height=size,
        num_points=points,
        island_shape=shape,
        river_count=rivers,
        mountain_sharpness=sharpness,
        enable_corner_improvement=True,
        enable_roads=True,
        enable_lava=True,
        enable_noisy_edges=True,
    )

    if len(GRAPH_CACHE) >= MAX_CACHE_ENTRIES:
        GRAPH_CACHE.pop(next(iter(GRAPH_CACHE)))
    GRAPH_CACHE[key] = gen
    return gen


def get_cached_micropolys(
    gen: PolygonMapGenerator,
    graph_key: Tuple,
    polys: int,
    roughness: float,
    jitter: float,
    alpha: float,
    height_scale: float,
    smooth: float,
    size: int,
) -> Tuple[List[Tuple], int]:
    mesh_key = (
        graph_key,
        polys,
        round(roughness, 1),
        round(jitter, 2),
        round(alpha, 2),
        round(height_scale, 1),
        round(smooth, 2),
    )
    if mesh_key in MESH_CACHE:
        return MESH_CACHE[mesh_key]

    triangles, actual_count = build_island_mesh(
        gen,
        width=size,
        height=size,
        mode="fractal",
        target_polys=polys,
        roughness=roughness,
        lateral_jitter=jitter,
        elevation_alpha=alpha,
        elev_scale=height_scale,
        normal_smooth_ratio=smooth,
    )

    if len(MESH_CACHE) >= MAX_CACHE_ENTRIES:
        MESH_CACHE.pop(next(iter(MESH_CACHE)))
    MESH_CACHE[mesh_key] = (triangles, actual_count)
    return triangles, actual_count


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------
class MapgenHTTPHandler(BaseHTTPRequestHandler):
    """Processes static assets, map rasterization, inspection, and USDZ exports."""

    def log_message(self, format, *args):
        # Concise single-line request logging
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {format % args}\n")
        sys.stdout.flush()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Root / UI Client
        if path == "/" or path == "/index.html":
            self.serve_index()

        # 2. Map Render API
        elif path == "/api/render":
            self.handle_render(query)

        # 3. Cell Inspection API
        elif path == "/api/inspect":
            self.handle_inspect(query)

        # 4. Apple Quick Look 3D USDZ Stream API
        elif path == "/api/export_usdz":
            self.handle_export_usdz(query)

        # 5. Health Check
        elif path == "/api/health":
            self.send_json({"status": "ok", "cached_graphs": len(GRAPH_CACHE)})

        else:
            self.send_error(404, "Not Found")

    def serve_index(self):
        html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
        if not os.path.exists(html_path):
            self.send_error(404, "index.html not found")
            return

        with open(html_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def handle_render(self, q: Dict[str, list]):
        t0 = time.time()
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        mode = q.get("mode", ["micropolys"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.25])[0])
        rivers = int(q.get("rivers", [25])[0])
        size = int(q.get("size", [720])[0])

        graph_key = (seed, shape, points, rivers, round(sharpness, 2), size)
        gen = get_cached_graph(seed, shape, points, rivers, sharpness, size)

        # Render chosen view mode
        if mode == "micropolys":
            triangles, _ = get_cached_micropolys(
                gen, graph_key, polys, roughness, jitter, alpha, height_scale, smooth, size
            )
            surf = render_mesh(gen, triangles, width=size, height=size)

        elif mode == "biomes":
            surf = gen.render_to_surface(
                width=size,
                height=size,
                use_brdf=True,
                use_noisy_edges=True,
                show_roads=True,
                show_lava=True,
                render_micropolys=False,
            )

        elif mode == "elevation":
            surf = pygame.Surface((size, size))
            surf.fill((18, 48, 100))
            for c in gen.centers:
                if c.ocean:
                    col = (18, 48, 100)
                elif c.water:
                    col = (40, 110, 175)
                else:
                    e = min(1.0, max(0.0, c.elevation))
                    if e < 0.25:
                        t = e / 0.25
                        col = (int(50 + 60 * t), int(140 + 40 * t), int(50 + 30 * t))
                    elif e < 0.60:
                        t = (e - 0.25) / 0.35
                        col = (int(110 + 70 * t), int(180 - 40 * t), int(80 - 20 * t))
                    elif e < 0.82:
                        t = (e - 0.60) / 0.22
                        col = (int(180 - 40 * t), int(140 - 20 * t), int(60 + 40 * t))
                    else:
                        t = (e - 0.82) / 0.18
                        col = (int(140 + 110 * t), int(120 + 130 * t), int(100 + 155 * t))

                poly = gen.get_polygon_noisy_boundary(c)
                if len(poly) >= 3:
                    pygame.draw.polygon(surf, col, poly)

        elif mode == "moisture":
            surf = pygame.Surface((size, size))
            surf.fill((18, 48, 100))
            for c in gen.centers:
                if c.ocean:
                    col = (18, 48, 100)
                elif c.water:
                    col = (40, 110, 175)
                else:
                    m = min(1.0, max(0.0, c.moisture))
                    col = (
                        int(210 * (1.0 - m) + 20 * m),
                        int(190 * (1.0 - m) + 160 * m),
                        int(90 * (1.0 - m) + 80 * m),
                    )
                poly = gen.get_polygon_noisy_boundary(c)
                if len(poly) >= 3:
                    pygame.draw.polygon(surf, col, poly)

        elif mode == "watersheds":
            surf = gen.render_to_surface(
                width=size,
                height=size,
                use_brdf=False,
                show_watersheds=True,
                render_micropolys=False,
            )

        elif mode == "wireframe":
            surf = pygame.Surface((size, size))
            surf.fill((22, 26, 34))
            for e in gen.edges:
                if e.v0 and e.v1:
                    col = (60, 90, 130) if (e.d0 and e.d0.water and e.d1 and e.d1.water) else (140, 160, 190)
                    pygame.draw.line(surf, col, (e.v0.x, e.v0.y), (e.v1.x, e.v1.y), 1)
                if e.d0 and e.d1:
                    pygame.draw.line(surf, (180, 80, 80), (e.d0.x, e.d0.y), (e.d1.x, e.d1.y), 1)

        else:
            surf = pygame.Surface((size, size))
            surf.fill((0, 0, 0))

        # Encode directly to fast WebP buffer
        raw_rgb = pygame.image.tobytes(surf, "RGB")
        img = Image.frombytes("RGB", (size, size), raw_rgb)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82)
        payload = buf.getvalue()

        dur_ms = (time.time() - t0) * 1000.0
        self.send_response(200)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Render-Time-Ms", f"{dur_ms:.1f}")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(payload)

    def handle_inspect(self, q: Dict[str, list]):
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        points = int(q.get("points", [1000])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        nx = float(q.get("nx", [0.5])[0])
        ny = float(q.get("ny", [0.5])[0])
        size = 720

        gen = get_cached_graph(seed, shape, points, 25, sharpness, size)
        cx = nx * size
        cy = ny * size

        center = gen.get_center_at(cx, cy)
        if not center:
            self.send_json({"error": "not found"}, status=404)
            return

        res = {
            "index": center.index,
            "biome": center.biome,
            "elevation": round(center.elevation, 3),
            "moisture": round(center.moisture, 3),
            "is_water": center.water,
            "is_ocean": center.ocean,
            "is_coast": center.coast,
        }
        self.send_json(res)

    def handle_export_usdz(self, q: Dict[str, list]):
        """Package and stream Apple Quick Look USDZ model for iOS Safari AR."""
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.25])[0])
        size = 1000

        graph_key = (seed, shape, points, 25, round(sharpness, 2), size)
        gen = get_cached_graph(seed, shape, points, 25, sharpness, size)
        triangles, _ = get_cached_micropolys(
            gen, graph_key, polys, roughness, jitter, alpha, height_scale, smooth, size
        )

        tmp_out = f"/tmp/island_web_{seed}_{os.getpid()}.usdz"
        export_island_wireframe_usdz(gen, triangles, tmp_out, wire_width=0.8)

        if not os.path.exists(tmp_out):
            self.send_error(500, "USDZ export failed")
            return

        with open(tmp_out, "rb") as f:
            data = f.read()

        try:
            os.remove(tmp_out)
        except OSError:
            pass

        self.send_response(200)
        # model/vnd.usdz+zip tells iOS Safari to activate AR Quick Look
        self.send_header("Content-Type", "model/vnd.usdz+zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'inline; filename="island_{seed}.usdz"')
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Server Launcher
# ---------------------------------------------------------------------------
def run_server(host: str = "0.0.0.0", port: int = 8080):
    server = ThreadingHTTPServer((host, port), MapgenHTTPHandler)
    print(f"\n==========================================================")
    print(f"  Mapgen2 Mobile & Web Server Running")
    print(f"==========================================================")
    print(f"  • Local URL     : http://localhost:{port}")
    print(f"  • Tailscale URL : http://100.126.125.100:{port}")
    print(f"  • iPhone URL    : http://100.126.125.100:{port}")
    print(f"==========================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mapgen2 Terrain Explorer Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port number")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
