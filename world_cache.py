"""world_cache.py — Persistent Map & Configuration Caching System.

Caches the last generated map, initial configuration, and 4x pre-rendered topographic
elevation surface to disk. On application startup, loads the cached map instantly (0.05s)
without procedural generation or loading modals.

A fresh map is only generated from scratch with the progress load screen when:
1. Reload is triggered (Cmd+R / Ctrl+R, or native Restart Game menu action).
2. The cache files are missing or invalidated.
3. Explicit CLI seed overrides differ from the cached configuration.
"""

from __future__ import annotations
import json
import os
import pickle
import time
from typing import Any
import pygame

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_cache")
CONFIG_PATH = os.path.join(CACHE_DIR, "map_config.json")
WORLD_STATE_PATH = os.path.join(CACHE_DIR, "world_state.pkl")
TOPO_SURF_PATH = os.path.join(CACHE_DIR, "topo_surface.png")


def has_valid_cache(
    seed: int | None = None,
    terrain_seed: int | None = None,
    nation_seed: int | None = None,
) -> bool:
    """Return True if a complete, valid map cache exists matching requested seeds."""
    if not (os.path.isfile(CONFIG_PATH) and os.path.isfile(WORLD_STATE_PATH) and os.path.isfile(TOPO_SURF_PATH)):
        return False

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # If user explicitly passed specific seeds on CLI, verify they match the cache
        if seed is not None and cfg.get("seed") != seed:
            return False
        if terrain_seed is not None and cfg.get("terrain_seed") != terrain_seed:
            return False
        if nation_seed is not None and cfg.get("nation_seed") != nation_seed:
            return False

        return True
    except Exception:
        return False


def load_map_cache() -> dict | None:
    """Load cached map state and pre-rendered topographic surface from disk.

    Returns the populated world dictionary, or None if loading fails.
    """
    if not (os.path.isfile(CONFIG_PATH) and os.path.isfile(WORLD_STATE_PATH) and os.path.isfile(TOPO_SURF_PATH)):
        return None

    try:
        t0 = time.time()
        # 1. Unpickle world state
        with open(WORLD_STATE_PATH, "rb") as f:
            world = pickle.load(f)

        # 2. Load pre-rendered topographic elevation surface
        topo_surf = pygame.image.load(TOPO_SURF_PATH)
        disp = pygame.display.get_surface()
        if disp is not None:
            try:
                topo_surf = topo_surf.convert_alpha()
            except Exception:
                pass

        # 3. Register surface in memory cache for the seed / bbox
        seed = world.get("terrain_seed", world.get("seed", 42))
        bbox = world.get("bbox")
        tiles = world.get("tiles")
        tile_sig = (
            tuple((t.name, round(getattr(t, "elevation", 0.0), 3), bool(getattr(t, "is_ocean", False))) for t in tiles)
            if tiles
            else None
        )
        cache_key = (seed, bbox, 2400, 1800, tile_sig)

        from heightmap import _TOPOGRAPHIC_SURFACE_CACHE
        _TOPOGRAPHIC_SURFACE_CACHE[cache_key] = topo_surf

        # 4. Attach to world dictionary and flag as ready
        world["_cached_topo_surface"] = topo_surf
        world["_cached_from_disk"] = True
        world["_map_generation_done"] = True
        world["loading_modal"] = None
        world["needs_redraw"] = True
        world["turn"] = 0
        world["playing"] = False
        world["selected_region"] = None
        world["hover_region"] = None

        from worldview_camera import clamp_cam, get_min_zoom
        if world.get("cam"):
            if world["cam"].get("zoom", 1.0) < get_min_zoom(world):
                from worldview_camera import reset_cam
                reset_cam(world)
            else:
                clamp_cam(world)

        t_elapsed = time.time() - t0
        print(f"[world_cache] Successfully loaded cached map in {t_elapsed:.3f}s (Seed: {seed})")
        return world
    except Exception as e:
        print(f"[world_cache] Warning: Failed to load map cache: {e}. Falling back to generation.")
        return None


def save_map_cache(world: dict, topo_surf: pygame.Surface | None = None) -> bool:
    """Save generated map state and topographic surface to disk."""
    if not world or not isinstance(world, dict):
        return False

    try:
        os.makedirs(CACHE_DIR, exist_ok=True)

        seed = world.get("seed")
        t_seed = world.get("terrain_seed", seed)
        n_seed = world.get("nation_seed")

        # 1. Save config JSON
        cfg = {
            "seed": seed,
            "terrain_seed": t_seed,
            "nation_seed": n_seed,
            "canvas_w": 2400,
            "canvas_h": 1800,
            "timestamp": time.time(),
            "version": 1,
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        # 2. Save topographic surface PNG if available
        surf_to_save = topo_surf or world.get("_cached_topo_surface")
        if surf_to_save is None:
            bbox = world.get("bbox")
            tiles = world.get("tiles")
            tile_sig = (
                tuple((t.name, round(getattr(t, "elevation", 0.0), 3), bool(getattr(t, "is_ocean", False))) for t in tiles)
                if tiles
                else None
            )
            cache_key = (t_seed, bbox, 2400, 1800, tile_sig)
            from heightmap import _TOPOGRAPHIC_SURFACE_CACHE
            surf_to_save = _TOPOGRAPHIC_SURFACE_CACHE.get(cache_key)

        if surf_to_save is not None:
            pygame.image.save(surf_to_save, TOPO_SURF_PATH)

        # 3. Clean transient runtime properties before pickling
        world_to_pickle = dict(world)
        world_to_pickle.pop("_ui_targets", None)
        world_to_pickle.pop("_hovered_left_tooltip", None)
        world_to_pickle.pop("_cached_topo_surface", None)
        world_to_pickle["loading_modal"] = None
        world_to_pickle["_map_generation_done"] = True
        world_to_pickle["_cached_from_disk"] = True
        world_to_pickle["needs_redraw"] = True

        with open(WORLD_STATE_PATH, "wb") as f:
            pickle.dump(world_to_pickle, f, protocol=pickle.HIGHEST_PROTOCOL)

        print(f"[world_cache] Cached map state & topographic surface to {CACHE_DIR} (Seed: {t_seed})")
        return True
    except Exception as e:
        print(f"[world_cache] Error saving map cache: {e}")
        return False


def invalidate_map_cache() -> None:
    """Remove cache files so the next build generates a new map from scratch."""
    for p in (CONFIG_PATH, WORLD_STATE_PATH, TOPO_SURF_PATH):
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    print("[world_cache] Invalidated map cache.")
