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
import queue
import threading

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
# Dedicated Thread-Affinity Worker for Headless ModernGL GPU Execution
# ---------------------------------------------------------------------------
GPU_TASK_QUEUE = queue.Queue()
GPU_AVAILABLE = False
_GPU_READY = threading.Event()


def _gpu_worker_loop():
    global GPU_AVAILABLE
    pipe = None
    try:
        from render_engine.gpu.mesh_brdf_pipeline import GPUMeshBRDFPipeline
        pipe = GPUMeshBRDFPipeline()
        if pipe.is_available():
            GPU_AVAILABLE = True
    except Exception as exc:
        sys.stderr.write(f"GPU ModernGL worker initialization note: {exc}\n")
    finally:
        _GPU_READY.set()

    while True:
        task = GPU_TASK_QUEUE.get()
        if task is None:
            break
        func, args, kwargs, reply_q = task
        try:
            if pipe is None or not GPU_AVAILABLE:
                raise RuntimeError("ModernGL GPU pipeline is unavailable on this system")
            res = func(pipe, *args, **kwargs)
            reply_q.put((True, res))
        except Exception as e:
            reply_q.put((False, e))
        finally:
            GPU_TASK_QUEUE.task_done()


_gpu_thread = threading.Thread(target=_gpu_worker_loop, daemon=True)
_gpu_thread.start()


def is_gpu_ready(timeout: float = 2.0) -> bool:
    _GPU_READY.wait(timeout)
    return GPU_AVAILABLE


def run_on_gpu(func, *args, **kwargs):
    is_gpu_ready()
    reply_q = queue.Queue()
    GPU_TASK_QUEUE.put((func, args, kwargs, reply_q))
    ok, res = reply_q.get()
    if ok:
        return res
    raise res


def _render_gpu_mesh_surface(
    pipe,
    gen: PolygonMapGenerator,
    triangles: list,
    width: int,
    height: int,
    uniforms: dict,
    mesh_key: Any = None,
) -> pygame.Surface:
    """Invoked inside dedicated GPU worker thread to render CPU mapgen mesh with BRDF."""
    return pipe.render_mesh(
        gen=gen,
        triangles=triangles,
        width=width,
        height=height,
        uniforms=uniforms,
        mesh_cache_key=mesh_key,
    )

# ---------------------------------------------------------------------------
# Two-Tier In-Memory Cache for Instant Interactive Response
# ---------------------------------------------------------------------------
CANONICAL_WORLD_SIZE = 1024
GRAPH_CACHE: Dict[Tuple, PolygonMapGenerator] = {}
MESH_CACHE: Dict[Tuple, Tuple[List[Tuple], int]] = {}
MAX_CACHE_ENTRIES = 12


def get_cached_graph(
    seed: int,
    shape: str,
    points: int,
    rivers: int,
    sharpness: float,
    moisture_bias: float = 0.0,
    north_temp: float = 0.0,
    south_temp: float = 0.0,
    persistence: float = 0.0,
    size: int = CANONICAL_WORLD_SIZE,
) -> PolygonMapGenerator:
    key = (
        seed,
        shape,
        points,
        rivers,
        round(sharpness, 2),
        round(moisture_bias, 2),
        round(north_temp, 2),
        round(south_temp, 2),
        round(persistence, 2),
    )
    if key in GRAPH_CACHE:
        return GRAPH_CACHE[key]

    gen = PolygonMapGenerator(
        seed=seed,
        width=CANONICAL_WORLD_SIZE,
        height=CANONICAL_WORLD_SIZE,
        num_points=points,
        island_shape=shape,
        river_count=rivers,
        mountain_sharpness=sharpness,
        moisture_bias=moisture_bias,
        north_temperature=north_temp,
        south_temperature=south_temp,
        persistence=persistence,
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
    quad_fold: bool = True,
    ridge_noise: float = 0.35,
    erosion_strength: float = 0.30,
    erosion_droplets: int = 15000,
) -> Tuple[List[Tuple], int]:
    mesh_key = (
        graph_key,
        polys,
        round(roughness, 1),
        round(jitter, 2),
        round(alpha, 2),
        round(height_scale, 1),
        round(smooth, 2),
        quad_fold,
        round(ridge_noise, 2),
        round(erosion_strength, 2),
        int(erosion_droplets),
    )
    if mesh_key in MESH_CACHE:
        return MESH_CACHE[mesh_key]

    triangles, actual_count = build_island_mesh(
        gen,
        width=CANONICAL_WORLD_SIZE,
        height=CANONICAL_WORLD_SIZE,
        mode="fractal",
        target_polys=polys,
        roughness=roughness,
        lateral_jitter=jitter,
        elevation_alpha=alpha,
        elev_scale=height_scale,
        normal_smooth_ratio=smooth,
        quad_fold=quad_fold,
        ridge_noise=ridge_noise,
        erosion_strength=erosion_strength,
        erosion_droplets=erosion_droplets,
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

        # 2b. High-FPS Client-Side WebGL 3D Mesh API
        elif path == "/api/mesh_binary":
            self.handle_mesh_binary(query)

        # 3. Cell Inspection API
        elif path == "/api/inspect":
            self.handle_inspect(query)

        # 4. Apple Quick Look 3D USDZ Stream API
        elif path == "/api/export_usdz":
            self.handle_export_usdz(query)

        # 5. Health Check
        elif path == "/api/health":
            self.send_json({"status": "ok", "cached_graphs": len(GRAPH_CACHE), "gpu_available": is_gpu_ready(0.2)})

        # 6. Client Diagnostics Log API
        elif path == "/api/log_error":
            msg = query.get("msg", [""])[0]
            sys.stderr.write(f"[CLIENT LOG] {msg}\n")
            sys.stderr.flush()
            self.send_json({"status": "logged"})

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
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)

    def handle_render(self, q: Dict[str, list]):
        t0 = time.time()
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["perlin"])[0]
        engine = q.get("engine", ["gpu" if is_gpu_ready(0.2) else "cpu"])[0].lower()
        mode = q.get("mode", ["micropolys"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.0])[0])
        rivers = int(q.get("rivers", [25])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])
        size = int(q.get("size", [1024])[0])
        size = max(256, min(4096, size))

        # Dynamic lighting & sun angles
        sun_azimuth = float(q.get("sun_azimuth", [-135.0])[0])
        sun_elevation = float(q.get("sun_elevation", [42.0])[0])
        sun_intensity = float(q.get("sun_intensity", [1.15])[0])
        ambient_intensity = float(q.get("ambient_intensity", [0.45])[0])
        mountain_roughness = float(q.get("mountain_roughness", [1.0])[0])

        # 3D interactive mesh rotation
        rot_pitch = float(q.get("rot_pitch", [0.0])[0])
        rot_yaw = float(q.get("rot_yaw", [0.0])[0])

        graph_key = (
            seed,
            shape,
            points,
            rivers,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            rivers,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )

        surf = None
        used_engine = "cpu"

        # 1. GPU Pipeline Execution (ModernGL hardware rasterization of CPU mapgen mesh with BRDF)
        if (engine == "gpu" or mode == "gpu") and is_gpu_ready(0.2):
            uniforms = {
                "sun_azimuth": sun_azimuth,
                "sun_elevation": sun_elevation,
                "sun_intensity": sun_intensity,
                "ambient_intensity": ambient_intensity,
                "mountain_roughness": mountain_roughness,
                "rot_pitch": rot_pitch,
                "rot_yaw": rot_yaw,
            }
            try:
                triangles, _ = get_cached_micropolys(
                    gen,
                    graph_key,
                    polys,
                    roughness,
                    jitter,
                    alpha,
                    height_scale,
                    smooth,
                    quad_fold=quad_fold,
                    ridge_noise=ridge_noise,
                    erosion_strength=erosion_strength,
                    erosion_droplets=erosion_droplets,
                )
                mesh_key = (
                    graph_key,
                    polys,
                    round(roughness, 1),
                    round(jitter, 2),
                    round(alpha, 2),
                    round(height_scale, 1),
                    round(smooth, 2),
                    quad_fold,
                    ridge_noise,
                    erosion_strength,
                    int(erosion_droplets),
                )
                surf = run_on_gpu(
                    _render_gpu_mesh_surface,
                    gen,
                    triangles,
                    size,
                    size,
                    uniforms,
                    mesh_key=mesh_key,
                )
                used_engine = "gpu"
            except Exception as e:
                sys.stderr.write(f"GPU render error, fallback to CPU: {e}\n")
                surf = None

        # 2. CPU Fallback / Alternative Modes (Only execute if surf was not already rendered by GPU)
        if surf is None:
            used_engine = "cpu"
            if mode in ("micropolys", "gpu") or engine == "cpu":
                triangles, _ = get_cached_micropolys(
                    gen,
                    graph_key,
                    polys,
                    roughness,
                    jitter,
                    alpha,
                    height_scale,
                    smooth,
                    quad_fold=quad_fold,
                    ridge_noise=ridge_noise,
                    erosion_strength=erosion_strength,
                    erosion_droplets=erosion_droplets,
                )
                surf = render_mesh(
                    gen,
                    triangles,
                    width=size,
                    height=size,
                    sun_azimuth=sun_azimuth,
                    sun_elevation=sun_elevation,
                    sun_intensity=sun_intensity,
                    ambient_intensity=ambient_intensity,
                    rot_pitch=rot_pitch,
                    rot_yaw=rot_yaw,
                )

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
                # Guaranteed non-black fallback for any unknown mode
                surf = gen.render_to_surface(width=size, height=size, use_brdf=True)

        # 3. Permanent Failsafe Guard: Verify the surface has non-zero pixels
        if surf is None:
            sys.stderr.write("WARNING: surf is None, invoking guaranteed CPU emergency fallback.\n")
            used_engine = "cpu-emergency"
            surf = gen.render_to_surface(width=size, height=size, use_brdf=True)
        else:
            # Check center and quarter pixels
            test_pts = [(size // 2, size // 2), (size // 4, size // 4), (3 * size // 4, 3 * size // 4)]
            if all(sum(surf.get_at(pt)[:3]) == 0 for pt in test_pts):
                raw_test = pygame.image.tobytes(surf, "RGB")
                if max(raw_test) == 0:
                    sys.stderr.write("WARNING: Render produced an all-black surface! Triggering guaranteed CPU fallback.\n")
                    used_engine = "cpu-failsafe"
                    surf = gen.render_to_surface(width=size, height=size, use_brdf=True)

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
        self.send_header("X-Render-Engine", used_engine)
        self.send_header("X-Render-Resolution", f"{size}x{size}")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(payload)

    def handle_mesh_binary(self, q: Dict[str, list]):
        """Streams compact binary 3D mesh + river lines for 60-120 FPS client WebGL rendering."""
        import struct
        import gzip
        t0 = time.time()
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["perlin"])[0]
        points = int(q.get("points", [1000])[0])
        polys = int(q.get("polys", [16000])[0])
        height_scale = float(q.get("height_scale", [70.0])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        roughness = float(q.get("roughness", [3.0])[0])
        jitter = float(q.get("jitter", [0.22])[0])
        smooth = float(q.get("smooth", [0.70])[0])
        alpha = float(q.get("alpha", [0.0])[0])
        rivers = int(q.get("rivers", [25])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])
        size = int(q.get("size", [1024])[0])

        graph_key = (
            seed,
            shape,
            points,
            rivers,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            rivers,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )

        triangles, _ = get_cached_micropolys(
            gen,
            graph_key,
            polys,
            roughness,
            jitter,
            alpha,
            height_scale,
            smooth,
            quad_fold=quad_fold,
            ridge_noise=ridge_noise,
            erosion_strength=erosion_strength,
            erosion_droplets=erosion_droplets,
        )

        from render_engine.gpu.mesh_brdf_pipeline import build_vbo_data
        vbo_data, max_z = build_vbo_data(triangles)

        # Extract river vector lines in canonical world coordinates
        river_coords = []
        if hasattr(gen, "edges") and gen.noisy_edges:
            scale_x = CANONICAL_WORLD_SIZE / gen.width
            scale_y = CANONICAL_WORLD_SIZE / gen.height
            for e in gen.edges:
                if e.river > 0 and e.v0 and e.v1:
                    if (e.d0 and e.d1 and e.d0.water and e.d1.water):
                        continue
                    if (getattr(e.v0, "ocean", False) and getattr(e.v1, "ocean", False)):
                        continue
                    pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                    n_p = len(pts)
                    if n_p >= 2:
                        z0 = float(getattr(e.v0, "elevation", 0.0) * height_scale)
                        z1 = float(getattr(e.v1, "elevation", 0.0) * height_scale)
                        for i in range(n_p - 1):
                            t_a = i / (n_p - 1)
                            t_b = (i + 1) / (n_p - 1)
                            za = z0 * (1.0 - t_a) + z1 * t_a + 0.35
                            zb = z0 * (1.0 - t_b) + z1 * t_b + 0.35
                            river_coords.extend([pts[i][0] * scale_x, pts[i][1] * scale_y, za,
                                                pts[i+1][0] * scale_x, pts[i+1][1] * scale_y, zb])
        river_arr = np.array(river_coords, dtype=np.float32)

        # Extract lava fissure lines in canonical world coordinates
        lava_coords = []
        if hasattr(gen, "edges"):
            scale_x = CANONICAL_WORLD_SIZE / gen.width
            scale_y = CANONICAL_WORLD_SIZE / gen.height
            for e in gen.edges:
                if getattr(e, "lava", False) and e.v0 and e.v1:
                    z0 = float(getattr(e.v0, "elevation", 0.0) * height_scale) + 0.35
                    z1 = float(getattr(e.v1, "elevation", 0.0) * height_scale) + 0.35
                    lava_coords.extend([e.v0.x * scale_x, e.v0.y * scale_y, z0,
                                        e.v1.x * scale_x, e.v1.y * scale_y, z1])
        lava_arr = np.array(lava_coords, dtype=np.float32)

        n_verts = len(vbo_data)
        n_river = len(river_arr) // 3
        n_lava = len(lava_arr) // 3

        hdr = struct.pack('<4sIIfII', b'MMSH', 1, n_verts, float(max_z), n_river, n_lava)
        raw_payload = hdr + vbo_data.tobytes() + river_arr.tobytes() + lava_arr.tobytes()

        accept_enc = self.headers.get("Accept-Encoding", "")
        dur_ms = (time.time() - t0) * 1000.0

        if "gzip" in accept_enc:
            compressed = gzip.compress(raw_payload, compresslevel=1)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(compressed)))
            self.send_header("X-Mesh-Vertices", str(n_verts))
            self.send_header("X-Mesh-Time-Ms", f"{dur_ms:.1f}")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(raw_payload)))
            self.send_header("X-Mesh-Vertices", str(n_verts))
            self.send_header("X-Mesh-Time-Ms", f"{dur_ms:.1f}")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(raw_payload)

    def handle_inspect(self, q: Dict[str, list]):
        seed = int(q.get("seed", [777])[0])
        shape = q.get("shape", ["radial"])[0]
        points = int(q.get("points", [1000])[0])
        sharpness = float(q.get("sharpness", [1.0])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        nx = float(q.get("nx", [0.5])[0])
        ny = float(q.get("ny", [0.5])[0])
        size = int(q.get("size", [1024])[0])

        gen = get_cached_graph(
            seed,
            shape,
            points,
            25,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )
        cx = nx * CANONICAL_WORLD_SIZE
        cy = ny * CANONICAL_WORLD_SIZE

        center = gen.get_center_at(cx, cy)
        if not center:
            self.send_json({"error": "not found"}, status=404)
            return

        res = {
            "index": center.index,
            "biome": center.biome,
            "elevation": round(center.elevation, 3),
            "moisture": round(center.moisture, 3),
            "temperature": round(center.temperature, 3),
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
        alpha = float(q.get("alpha", [0.0])[0])
        moisture_bias = float(q.get("moisture_bias", [0.0])[0])
        north_temp = float(q.get("north_temp", [0.0])[0])
        south_temp = float(q.get("south_temp", [0.0])[0])
        persistence = float(q.get("persistence", [0.0])[0])
        quad_fold = q.get("quad_fold", ["true"])[0].lower() in ("true", "1", "yes")
        ridge_noise = float(q.get("ridge_noise", [0.35])[0])
        erosion_strength = float(q.get("erosion_strength", [0.30])[0])
        erosion_droplets = int(q.get("erosion_droplets", [15000])[0])

        graph_key = (
            seed,
            shape,
            points,
            25,
            round(sharpness, 2),
            round(moisture_bias, 2),
            round(north_temp, 2),
            round(south_temp, 2),
            round(persistence, 2),
        )
        gen = get_cached_graph(
            seed,
            shape,
            points,
            25,
            sharpness,
            moisture_bias=moisture_bias,
            north_temp=north_temp,
            south_temp=south_temp,
            persistence=persistence,
        )
        triangles, _ = get_cached_micropolys(
            gen,
            graph_key,
            polys,
            roughness,
            jitter,
            alpha,
            height_scale,
            smooth,
            quad_fold=quad_fold,
            ridge_noise=ridge_noise,
            erosion_strength=erosion_strength,
            erosion_droplets=erosion_droplets,
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
