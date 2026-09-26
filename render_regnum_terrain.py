"""
render_regnum_terrain.py — Photorealistic REGNUM Topographic Renderer for Mapgen2.

Ports all graphical shader passes from REGNUM's topographic engine onto Mapgen2
polygonal worlds, including:
1. 2D Volumetric Forest Canopy (crown stamps, dome relief, AO, drop shadows, interior clearings, riparian woods)
2. Optical Ocean Water (Beer-Lambert depth extinction, 4-octave wave ripples, sun glints, coastal surf foam)
3. Coastal Geomorphology (sheer sea cliffs, sloping ramps, terraced bluffs, expansive sand beaches with dunes)
4. Alpine Rock Strata & Glacial Snow Summits (slate & granite facings, scree slopes, specular glint)
5. Multi-Scale Ground Cover (grazing grain, tussock clump mottle, Worley soil parcels, meandering trails)
6. Hydraulic River Valleys (thalweg valley carving, feathered waterlines, delta estuary fans, riparian turf)
7. Atmospheric Post-Processing (domain-warped cloud shadows, aerial haze, split-tone grading, filmic vignette)
"""

import math
import random
from typing import Optional, Tuple, Dict, Any, List
import numpy as np
from scipy.ndimage import gaussian_filter, distance_transform_edt
import pygame
from heightmap import HeightMapGenerator
from polygon_map import PolygonMapGenerator


# Re-use HeightMapGenerator's precomputed noise table and matrix
_DEFAULT_HM = HeightMapGenerator(seed=42)
NOISE_TBL = _DEFAULT_HM.noise_table
M2 = _DEFAULT_HM.m2


def _ss(lo: float, hi: float, x: np.ndarray) -> np.ndarray:
    """Vectorized Hermite smoothstep."""
    t = np.clip((x - lo) / (hi - lo + 1e-7), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _iq_noised(px_arr: np.ndarray, py_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Inigo Quilez value noise with analytical spatial derivatives."""
    ix = np.floor(px_arr).astype(np.int32)
    iy = np.floor(py_arr).astype(np.int32)
    fx = px_arr - ix
    fy = py_arr - iy

    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    dux = 6.0 * fx * (1.0 - fx)
    duy = 6.0 * fy * (1.0 - fy)

    ix0 = ix & 255
    iy0 = iy & 255
    ix1 = (ix + 1) & 255
    iy1 = (iy + 1) & 255

    c_a = NOISE_TBL[iy0, ix0]
    c_b = NOISE_TBL[iy0, ix1]
    c_c = NOISE_TBL[iy1, ix0]
    c_d = NOISE_TBL[iy1, ix1]

    k0 = c_a
    k1 = c_b - c_a
    k2 = c_c - c_a
    k3 = c_a - c_b - c_c + c_d

    val = k0 + k1 * ux + k2 * uy + k3 * ux * uy
    dx = dux * (k1 + k3 * uy)
    dy = duy * (k2 + k3 * ux)
    return val, dx, dy


def _cellhash(ai: np.ndarray, bi: np.ndarray, salt: int, seed: int) -> np.ndarray:
    """Integer hash for random Voronoi scatter without regular lattice artifacts."""
    h = (ai * np.int64(374761393)) ^ (bi * np.int64(668265263)) ^ np.int64(salt * 2246822519 + seed)
    h = (h ^ (h >> np.int64(13))) * np.int64(1274126177)
    h = (h ^ (h >> np.int64(16))) & np.int64(0xFFFF)
    return NOISE_TBL[(h >> np.int64(8)).astype(np.int64), (h & np.int64(255)).astype(np.int64)]


def render_regnum_terrain(
    gen: PolygonMapGenerator,
    width: int = 512,
    height: int = 512,
    # Volumetric Forest Canopy Knobs
    show_canopy: bool = True,
    canopy_density: float = 0.85,
    crown_size: float = 5.0,
    forest_shadows: bool = True,
    forest_clearings: bool = True,
    riparian_trees: bool = True,
    # Optical Ocean Water & Waves Knobs
    show_ocean_fx: bool = True,
    show_wave_ripples: bool = True,
    wave_ripples: float = 1.0,
    show_specular_glints: bool = True,
    specular_glints: float = 1.0,
    show_coastal_surf: bool = True,
    coastal_surf: float = 1.0,
    shelf_width: float = 1.0,
    # Coastal Geomorphology & Beaches Knobs
    show_beaches: bool = True,
    beach_width: float = 1.0,
    sand_dunes: bool = True,
    show_coastal_cliffs: bool = True,
    coastal_cliffs: float = 1.0,
    # Alpine Rock Strata & Glacial Snow Knobs
    show_rock_strata: bool = True,
    rock_strata: float = 1.0,
    show_snow_peaks: bool = True,
    snow_peaks: float = 1.0,
    snow_altitude: float = 0.70,
    # Ground Cover & Soil Parcels Knobs
    show_ground_grain: bool = True,
    ground_grain: float = 1.0,
    show_soil_parcels: bool = True,
    soil_parcels: float = 1.0,
    field_filaments: bool = True,
    # Hydraulic River Valleys Knobs
    carve_rivers: bool = True,
    river_width: float = 1.0,
    estuary_fan: bool = True,
    riparian_turf: bool = True,
    # Atmospheric Post-Processing & Lighting Knobs
    show_atmosphere: bool = True,
    show_cloud_shadows: bool = True,
    cloud_shadows: float = 0.55,
    show_aerial_haze: bool = True,
    aerial_haze: float = 0.50,
    show_split_tone: bool = True,
    split_tone: float = 0.60,
    vignette: bool = True,
    sun_azimuth: float = -135.0,
    sun_elevation: float = 42.0,
    frame: int = 0,
) -> pygame.Surface:
    """Render a Mapgen2 polygonal world using the photorealistic REGNUM topographic rendering pipeline."""
    # 1. World Mesh Coordinates
    seed = getattr(gen, "seed", 42)
    world_w, world_h = float(gen.width), float(gen.height)

    x_vals = np.linspace(0.0, world_w, width, dtype=np.float32)
    y_vals = np.linspace(0.0, world_h, height, dtype=np.float32)
    WX, WY = np.meshgrid(x_vals, y_vals)

    # 2. Sample Mapgen2 Centers onto Canvas Grid
    pts = np.column_stack([WX.ravel(), WY.ravel()])
    _, idxs = gen._center_kdtree.query(pts)
    grid_idxs = idxs.reshape(height, width)

    c_elevs = np.array([float(c.elevation) for c in gen.centers], dtype=np.float32)
    c_ocean = np.array([bool(c.ocean) for c in gen.centers], dtype=bool)
    c_water = np.array([bool(c.water) for c in gen.centers], dtype=bool)
    c_moist = np.array([float(getattr(c, "moisture", 0.5)) for c in gen.centers], dtype=np.float32)

    raw_elev = c_elevs[grid_idxs]
    is_ocean = c_ocean[grid_idxs]
    is_water = c_water[grid_idxs]
    is_land = ~is_water
    moisture = c_moist[grid_idxs]

    # Forest, Mountain, and Snow probabilities based on Whittaker biomes and geography
    c_biomes = [str(c.biome).upper() for c in gen.centers]
    forest_biomes = {
        "TEMPERATE_DECIDUOUS_FOREST", "TEMPERATE_RAIN_FOREST",
        "TROPICAL_RAIN_FOREST", "TROPICAL_SEASONAL_FOREST", "TAIGA", "FOREST"
    }
    c_is_forest = np.array([b in forest_biomes for b in c_biomes], dtype=np.float32)
    c_is_mountain = np.array([
        (e >= 0.55) or (b in ("SNOW", "TUNDRA", "BARE", "SCORCHED", "MOUNTAINS", "SNOW_PEAKS"))
        for e, b in zip(c_elevs, c_biomes)
    ], dtype=np.float32)
    c_is_snow = np.array([
        (e >= snow_altitude) or (b in ("SNOW", "SNOW_PEAKS"))
        for e, b in zip(c_elevs, c_biomes)
    ], dtype=np.float32)
    c_is_hills = np.array([0.35 <= e < 0.60 for e in c_elevs], dtype=np.float32)

    H_forest_prob = gaussian_filter(c_is_forest[grid_idxs], sigma=width * 0.015)
    H_mount_prob = gaussian_filter(c_is_mountain[grid_idxs], sigma=width * 0.012)
    H_snow_prob = gaussian_filter(c_is_snow[grid_idxs], sigma=width * 0.010)
    H_hills_prob = gaussian_filter(c_is_hills[grid_idxs], sigma=width * 0.015)
    H_land_prob = gaussian_filter(is_land.astype(np.float32), sigma=width * 0.012)

    # 3. Distance Fields for Coast & Bathymetry
    _ocean_mask = H_land_prob < 0.32
    if _ocean_mask.any() and (~_ocean_mask).any():
        sea_dist_px = distance_transform_edt(~_ocean_mask).astype(np.float32)
        ocean_dist_px = distance_transform_edt(_ocean_mask).astype(np.float32)
    else:
        sea_dist_px = np.full((height, width), 1e6, dtype=np.float32)
        ocean_dist_px = np.full((height, width), 1e6, dtype=np.float32)

    hex_ref = width / 18.0
    sea_dist_tiles = ocean_dist_px / hex_ref
    inland_dist_tiles = sea_dist_px / hex_ref

    # 4. Multi-Fractal Inigo Quilez Terrain & Relief
    scale = 3.2 / world_w
    NX = (WX - world_w * 0.5) * scale
    NY = (WY - world_h * 0.5) * scale

    PX, PY = NX * 3.0, NY * 3.0
    fbm_a = np.zeros_like(WX, dtype=np.float32)
    fbm_b = 1.0
    dx_accum = np.zeros_like(WX, dtype=np.float32)
    dy_accum = np.zeros_like(WY, dtype=np.float32)

    for _ in range(6):
        n_val, ndx, ndy = _iq_noised(PX, PY)
        dx_accum += ndx
        dy_accum += ndy
        erosion_term = 1.0 + (dx_accum**2 + dy_accum**2) * 0.75
        fbm_a += fbm_b * n_val / erosion_term
        fbm_b *= 0.52
        PX, PY = 2.0 * (M2[0, 0] * PX + M2[0, 1] * PY), 2.0 * (M2[1, 0] * PX + M2[1, 1] * PY)

    # Domain Warp for organic geomorphology
    qw_val, qw_dx, qw_dy = _iq_noised(WX * (1.0 / (hex_ref * 3.5)), WY * (1.0 / (hex_ref * 3.5)))
    WX_warped = WX + qw_dx * (hex_ref * 0.35)
    WY_warped = WY + qw_dy * (hex_ref * 0.35)

    # Ridged alpine mountain relief
    mount_px = WX_warped / (hex_ref * 2.2)
    mount_py = WY_warped / (hex_ref * 2.2)
    mount_relief = np.zeros_like(WX, dtype=np.float32)
    mount_amp = 1.0
    mount_freq = 1.0
    m_dx_acc = np.zeros_like(WX, dtype=np.float32)
    m_dy_acc = np.zeros_like(WY, dtype=np.float32)

    for _ in range(5):
        n_val, ndx, ndy = _iq_noised(mount_px * mount_freq, mount_py * mount_freq)
        ridge = 1.0 - np.abs(2.0 * n_val - 1.0)
        ridge = ridge * ridge
        m_dx_acc += ndx * mount_freq
        m_dy_acc += ndy * mount_freq
        mount_relief += mount_amp * (ridge / (1.0 + (m_dx_acc**2 + m_dy_acc**2) * 0.35))
        mount_amp *= 0.52
        mount_freq *= 2.05

    mount_relief = np.maximum(0.0, (mount_relief - 0.45) * 1.35)
    eff_rock_strata = rock_strata if show_rock_strata else 0.0
    mountain_ridge = H_mount_prob * (0.16 + 0.88 * mount_relief) * eff_rock_strata

    # Plains & Hills micro-relief
    hill_fbm, _, _ = _iq_noised(WX_warped / (hex_ref * 1.8), WY_warped / (hex_ref * 1.8))
    hill_ridge = H_hills_prob * (0.24 + 0.14 * hill_fbm)

    plains_fbm, _, _ = _iq_noised(WX_warped / (hex_ref * 0.5), WY_warped / (hex_ref * 0.5))
    plains_details = (plains_fbm - 0.50) * 0.035

    # 5. Coastal Profiles & Shelf Bathymetry
    _rp = hill_ridge + mountain_ridge
    _gpx = np.gradient(_rp, axis=1)
    _gpy = np.gradient(_rp, axis=0)
    coast_steep = gaussian_filter(np.sqrt(_gpx * _gpx + _gpy * _gpy), sigma=hex_ref * 0.6)
    coast_steep = np.clip(coast_steep / 0.010, 0.0, 1.0) ** 0.75

    c_morph1, _, _ = _iq_noised(WX / (hex_ref * 3.6) + 41.2, WY / (hex_ref * 3.6) - 17.8)
    c_morph2, _, _ = _iq_noised(WX / (hex_ref * 1.5) - 73.1, WY / (hex_ref * 1.5) + 62.4)
    coast_morph = c_morph1 * 0.60 + c_morph2 * 0.40

    eff_coastal_cliffs = coastal_cliffs if (show_beaches and show_coastal_cliffs) else 0.0
    w_cliff = np.clip(coast_steep * 1.35 * eff_coastal_cliffs + (coast_morph - 0.52) * 1.8 * (1.0 if show_coastal_cliffs else 0.0), 0.0, 1.0) ** 1.3
    w_ramp = np.clip((1.0 - coast_steep * 1.5) * np.clip((0.52 - coast_morph) * 2.5, 0.0, 1.0), 0.0, 1.0) ** 1.2
    _w_sum = w_cliff + w_ramp + 1e-4
    w_cliff = np.where(_w_sum > 1.0, w_cliff / _w_sum, w_cliff)
    w_ramp = np.where(_w_sum > 1.0, w_ramp / _w_sum, w_ramp)
    w_terrace = np.clip(1.0 - w_cliff - w_ramp, 0.0, 1.0)

    cliff_coast_H = (0.09 + 0.16 * coast_steep) * _ss(0.0, 0.16, inland_dist_tiles)
    ramp_coast_H = 0.085 * (np.clip(inland_dist_tiles / 1.8, 0.0, 1.0) ** 1.1)
    terrace_coast_H = 0.035 * (np.clip(inland_dist_tiles / 1.1, 0.0, 1.0) ** 0.4) + 0.05 * (np.clip(inland_dist_tiles / 1.1, 0.0, 1.0) ** 1.5)

    land_shelf_above = (cliff_coast_H * w_cliff + ramp_coast_H * w_ramp + terrace_coast_H * w_terrace)
    land_shelf_above += np.clip(H_land_prob - 0.46, 0.0, 1.0) * 0.04

    # Continental shelf depth & abyssal plunge
    base_shelf_tiles = (w_cliff * 0.15 + w_terrace * 1.60 + w_ramp * 4.60) * shelf_width
    shelf_target_tiles = np.clip(base_shelf_tiles, 0.12, 6.0)
    t_shelf = np.clip(sea_dist_tiles / np.maximum(shelf_target_tiles, 0.05), 0.0, 1.0)
    shelf_depth = (0.001 + 0.016 * t_shelf) * w_ramp + (0.035 + 0.160 * (t_shelf ** 2.4)) * w_cliff + (0.005 + 0.060 * (t_shelf ** 1.3)) * w_terrace

    plunge_rate = (w_cliff * 0.14 + w_terrace * 0.95 + w_ramp * 3.60) * shelf_width
    t_plunge = np.clip((sea_dist_tiles - shelf_target_tiles) / np.maximum(plunge_rate, 0.06), 0.0, 1.0)
    s_plunge = _ss(0.0, 1.0, t_plunge)
    seabed_H = -(shelf_depth + s_plunge * 0.35 + (s_plunge ** 2) * 0.28)

    wsea_width = w_cliff * 0.012 + w_terrace * 0.024 + w_ramp * 0.035
    _wsea = _ss(0.32 - wsea_width, 0.32 + wsea_width, 1.0 - H_land_prob)
    land_shelf = land_shelf_above * (1.0 - _wsea) + seabed_H * _wsea

    # Continuous Base Elevation H
    smooth_mapgen_elev = gaussian_filter(raw_elev, sigma=width * 0.008)
    base_ground_H = land_shelf + mountain_ridge + hill_ridge + plains_details * (1.0 - H_mount_prob)
    base_ground_H = np.where(is_land, np.maximum(base_ground_H, smooth_mapgen_elev * 0.75), base_ground_H)

    # 6. River Thalweg Valley Carving & Water
    carved_ground_H = base_ground_H.copy()
    river_alpha = np.zeros((height, width), dtype=np.float32)
    riparian = np.zeros((height, width), dtype=np.float32)
    mouth_zone = np.zeros((height, width), dtype=np.float32)

    # Extract river lines from Mapgen2 edges
    river_edges = [e for e in getattr(gen, "edges", []) if getattr(e, "river", 0) > 0 and e.v0 and e.v1]
    if carve_rivers and river_edges:
        scale_x = width / world_w
        scale_y = height / world_h

        # Build rasterized river mask using Pygame line drawing
        riv_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        riv_surf.fill((0, 0, 0, 0))
        for e in river_edges:
            lw = max(1, int(round(math.sqrt(e.river) * 1.5 * river_width)))
            if hasattr(gen, "noisy_edges") and gen.noisy_edges:
                pts = gen.noisy_edges.get_edge_path(e, start_corner=e.v0)
                if len(pts) >= 2:
                    arr = np.array(pts, dtype=np.float64)
                    prev_p = np.roll(arr, 1, axis=0)
                    next_p = np.roll(arr, -1, axis=0)
                    sm = 0.20 * prev_p + 0.60 * arr + 0.20 * next_p
                    sm[0] = arr[0]
                    sm[-1] = arr[-1]
                    line_pts = [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in sm]
                    pygame.draw.lines(riv_surf, (255, 255, 255, 255), False, line_pts, lw)
            else:
                p0 = (int(e.v0.x * scale_x), int(e.v0.y * scale_y))
                p1 = (int(e.v1.x * scale_x), int(e.v1.y * scale_y))
                pygame.draw.line(riv_surf, (255, 255, 255, 255), p0, p1, lw)

        riv_arr = pygame.surfarray.pixels_alpha(riv_surf)
        riv_mask = (np.transpose(riv_arr) > 10)
        del riv_arr

        if riv_mask.any():
            dist_to_riv = distance_transform_edt(~riv_mask).astype(np.float32)
            w_chan = max(1.5, 2.2 * river_width)
            v_reach = max(8.0, 16.0 * river_width)
            chan_depth = 0.015 * river_width

            t_reach = np.clip((dist_to_riv - w_chan) / v_reach, 0.0, 1.0)
            s_reach = _ss(0.0, 1.0, t_reach)
            carve_raw = (1.0 - s_reach) * chan_depth
            carve_amt = gaussian_filter(carve_raw, sigma=1.5)
            carved_ground_H = carved_ground_H - carve_amt

            # Water alpha and riparian margin
            edge_soft = 1.8 * river_width
            river_alpha = np.clip((w_chan - dist_to_riv) / edge_soft, 0.0, 1.0) * is_land.astype(np.float32)
            if riparian_turf:
                riparian = np.clip(1.0 - dist_to_riv / (v_reach * 1.5), 0.0, 1.0) * (1.0 - river_alpha) * is_land.astype(np.float32)

            if estuary_fan:
                mouth_zone = np.clip(1.0 - dist_to_riv / 25.0, 0.0, 1.0) * np.clip(1.0 - sea_dist_tiles / 0.8, 0.0, 1.0)

    is_river_water = river_alpha > 0.15
    raw_H = carved_ground_H
    is_ocean_water = H_land_prob < 0.30
    raw_H = np.where(is_ocean_water, seabed_H, raw_H)
    H = raw_H

    # 7. Surface Normals & Sun/Sky Lighting
    # Light angles
    sun_az = math.radians(sun_azimuth)
    sun_el = math.radians(sun_elevation)
    sun_x = math.cos(sun_el) * math.cos(sun_az)
    sun_y = math.cos(sun_el) * math.sin(sun_az)
    sun_z = math.sin(sun_el)
    sun_len = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2) + 1e-6
    sun_x, sun_y, sun_z = sun_x / sun_len, sun_y / sun_len, sun_z / sun_len

    half_x, half_y, half_z = sun_x, sun_y, sun_z + 1.0
    half_len = math.sqrt(half_x**2 + half_y**2 + half_z**2) + 1e-6
    half_x, half_y, half_z = half_x / half_len, half_y / half_len, half_z / half_len

    h_exag = 0.14
    dHx = np.gradient(H, axis=1) * (width * 0.5) * h_exag
    dHy = np.gradient(H, axis=0) * (height * 0.5) * h_exag
    Nz = np.ones_like(H, dtype=np.float32)
    norm = np.sqrt(dHx**2 + dHy**2 + Nz**2) + 1e-6
    Nx, Ny, Nz = -dHx / norm, -dHy / norm, Nz / norm

    # Flatten normals over river water
    Nx = Nx * (1.0 - river_alpha)
    Ny = Ny * (1.0 - river_alpha)
    Nz = Nz * (1.0 - river_alpha) + river_alpha
    n_len = np.sqrt(Nx**2 + Ny**2 + Nz**2) + 1e-6
    Nx, Ny, Nz = Nx / n_len, Ny / n_len, Nz / n_len
    slope = 1.0 - Nz

    NdotL = np.clip(Nx * sun_x + Ny * sun_y + Nz * sun_z, 0.0, 1.0)
    diffuse_sun = np.power(NdotL, 1.05)
    sky_light = Nz * 0.60 + 0.40

    # Raymarched soft shadows
    shadow_mask = np.ones((height, width), dtype=np.float32)
    step_dx, step_dy = int(round(-sun_x * 4.0)), int(round(-sun_y * 4.0))
    if step_dx != 0 or step_dy != 0:
        for s in range(1, 10):
            ox = s * step_dx
            oy = s * step_dy
            if abs(ox) >= width or abs(oy) >= height:
                break
            occ = np.full_like(H, -1.0)
            if oy > 0 and ox > 0:
                occ[oy:, ox:] = H[:-oy, :-ox]
            elif oy > 0 and ox < 0:
                occ[oy:, :ox] = H[:-oy, -ox:]
            elif oy < 0 and ox > 0:
                occ[:oy, ox:] = H[-oy:, :-ox]
            elif oy < 0 and ox < 0:
                occ[:oy, :ox] = H[-oy:, -ox:]
            diff = occ - (H + s * 0.04)
            shadow_mask = np.where(diff > 0.008, np.minimum(shadow_mask, np.clip(1.0 - diff * 3.5, 0.50, 1.0)), shadow_mask)

    direct_sun = diffuse_sun * shadow_mask

    # 8. Optical Ocean Water, Wave Ripples & Coastal Surf
    depth = np.clip(-H, 0.0, 5.0)
    coastal_turquoise = np.array([0.25, 0.62, 0.65], dtype=np.float32)
    shallow_shelf = np.array([0.15, 0.44, 0.55], dtype=np.float32)
    mid_ocean = np.array([0.10, 0.26, 0.44], dtype=np.float32)
    deep_ocean = np.array([0.05, 0.14, 0.32], dtype=np.float32)

    t_shallow = np.clip(depth / 0.055, 0.0, 1.0)[:, :, None]
    t_mid = np.clip((depth - 0.055) / 0.15, 0.0, 1.0)[:, :, None]
    t_deep = np.clip((depth - 0.18) / 0.16, 0.0, 1.0)[:, :, None]

    c_shelf = coastal_turquoise * (1.0 - t_shallow) + shallow_shelf * t_shallow
    c_water = c_shelf * (1.0 - t_mid) + mid_ocean * t_mid
    w_col = c_water * (1.0 - t_deep) + deep_ocean * t_deep

    # 4-octave wave ripples & capillary chop
    eff_wave_ripples = wave_ripples if (show_ocean_fx and show_wave_ripples) else 0.0
    eff_specular_glints = specular_glints if (show_ocean_fx and show_specular_glints) else 0.0
    eff_coastal_surf = coastal_surf if (show_ocean_fx and show_coastal_surf) else 0.0

    _wv = np.array([0.72, -0.69], dtype=np.float32)
    _wv /= np.linalg.norm(_wv)
    _wp = np.array([-_wv[1], _wv[0]], dtype=np.float32)
    _along = WX * _wv[0] + WY * _wv[1]
    _acr = WX * _wp[0] + WY * _wp[1]

    # Time frame offset for wave motion
    w_time = frame * 0.06
    _sv, _sdx, _sdy = _iq_noised(_along / (hex_ref * 1.5) + w_time, _acr / (hex_ref * 3.0) + 11.0)
    _cv, _cdx, _cdy = _iq_noised(WX / (hex_ref * 0.45) - w_time * 1.4, WY / (hex_ref * 0.45) - 38.7)
    _rv, _rdx, _rdy = _iq_noised(WX / 8.0 + _sdx * 0.5 + w_time * 2.0, WY / 8.0 + _sdy * 0.5)
    _mv, _mdx, _mdy = _iq_noised(WX / 3.0, WY / 3.0)

    _gx = (_sdx * 0.25 + _cdx * 0.35 + _rdx * 0.32 + _mdx * 0.18) * 0.24 * eff_wave_ripples
    _gy = (_sdy * 0.25 + _cdy * 0.35 + _rdy * 0.32 + _mdy * 0.18) * 0.24 * eff_wave_ripples

    _wnx, _wny = -_gx, -_gy
    _wn_inv = 1.0 / np.sqrt(_wnx**2 + _wny**2 + 1.0)
    _wnx, _wny, _wnz = _wnx * _wn_inv, _wny * _wn_inv, _wn_inv

    _w_NdotL = np.clip(_wnx * sun_x + _wny * sun_y + _wnz * sun_z, 0.0, 1.0)
    _w_diffuse = 0.65 + 0.35 * (np.power(_w_NdotL, 1.2) * (0.75 + 0.25 * shadow_mask))
    _w_NdotH = np.clip(_wnx * half_x + _wny * half_y + _wnz * half_z, 0.0, 1.0)
    _spec_crisp = ((_w_NdotH ** 36) * 0.18 + (_w_NdotH ** 90) * 0.30) * direct_sun * eff_specular_glints

    ocean_lit = w_col * _w_diffuse[:, :, None] + _spec_crisp[:, :, None]

    # Coastal surf & whitecap foam
    _fn0, _, _ = _iq_noised(WX * 0.13 + 3.0, WY * 0.13 - 7.0)
    _fn1, _, _ = _iq_noised(WX * 0.40 - 11.0, WY * 0.40 + 5.0)
    _fbreak = _ss(0.30, 0.66, _fn0 * 0.65 + _fn1 * 0.35)
    _szone = np.clip((0.15 - sea_dist_tiles) / 0.15, 0.0, 1.0) * is_ocean_water.astype(np.float32)
    foam = np.clip((_szone ** 1.3) * _fbreak * 0.95 * eff_coastal_surf, 0.0, 0.90)
    foam_col = np.array([0.94, 0.965, 0.975], dtype=np.float32)
    ocean_lit = ocean_lit * (1.0 - foam[:, :, None]) + foam_col * foam[:, :, None]

    # 9. Ground Cover Albedo, Grazing Grain & Worley Soil Parcels
    grass_sage = np.array([0.40, 0.46, 0.34], dtype=np.float32)
    grass_mid = np.array([0.37, 0.45, 0.27], dtype=np.float32)
    grass_dry = np.array([0.55, 0.52, 0.30], dtype=np.float32)

    eff_ground_grain = ground_grain if show_ground_grain else 0.0
    eff_soil_parcels = soil_parcels if show_soil_parcels else 0.0

    # Sub-hex clump mottle & high-frequency grain
    clump_v, _, _ = _iq_noised(WX / 20.0 + 40.0, WY / 20.0 - 12.0)
    clump = np.clip((clump_v - 0.5) * 2.2 * eff_ground_grain, -1.0, 1.0)

    grain_v, _, _ = _iq_noised(WX / 6.0, WY / 6.0)
    grain = np.clip((grain_v - 0.5) * 2.4 * eff_ground_grain, -1.0, 1.0)

    # Worley soil parcels
    parcel_dry = np.zeros_like(WX, dtype=np.float32)
    parcel_edge = np.ones_like(WX, dtype=np.float32)
    if show_soil_parcels and eff_soil_parcels > 0.05:
        parcel_cell = hex_ref * 0.72
        pcx, pcy = WX / parcel_cell, WY / parcel_cell
        p_nu, p_nv = np.floor(pcx), np.floor(pcy)
        f1 = np.full_like(WX, 1e6, dtype=np.float32)
        f2 = np.full_like(WX, 1e6, dtype=np.float32)
        pid = np.zeros_like(WX, dtype=np.float32)

        for _jj in (-1.0, 0.0, 1.0):
            for _ii in (-1.0, 0.0, 1.0):
                cu, cv = p_nu + _ii, p_nv + _jj
                ox = _cellhash(cu.astype(np.int64), cv.astype(np.int64), 1, seed)
                oy = _cellhash(cu.astype(np.int64), cv.astype(np.int64), 2, seed)
                featx, featy = cu + 0.15 + 0.70 * ox, cv + 0.15 + 0.70 * oy
                pd2 = (pcx - featx)**2 + (pcy - featy)**2
                closer = pd2 < f1
                f2 = np.where(closer, f1, np.minimum(f2, pd2))
                f1 = np.where(closer, pd2, f1)
                cid = _cellhash(cu.astype(np.int64), cv.astype(np.int64), 3, seed)
                pid = np.where(closer, cid, pid)

        parcel_edge = np.clip((np.sqrt(f2) - np.sqrt(f1)) / 0.14, 0.0, 1.0)
        parcel_dry = np.clip((pid - 0.58) / 0.22, 0.0, 1.0) * parcel_edge * eff_soil_parcels

    # Meandering filaments (trails and hedge shadow hairlines)
    fil_dark = np.zeros_like(WX, dtype=np.float32)
    if field_filaments:
        fa0, _, _ = _iq_noised(WX / (hex_ref * 1.25), WY / (hex_ref * 1.25) * 1.5)
        ridgeA = 1.0 - np.abs(2.0 * fa0 - 1.0)
        fil_dark = _ss(0.90, 0.98, ridgeA) * 0.25

    dryness = np.clip(0.50 + 0.16 * parcel_dry + 0.05 * clump + 0.05 * grain + 0.22 * H_hills_prob, 0.18, 0.86)
    d = dryness[:, :, None]
    plains_col = np.where(
        d < 0.5,
        grass_sage * (1.0 - d / 0.5) + grass_mid * (d / 0.5),
        grass_mid * (1.0 - (d - 0.5) / 0.5) + grass_dry * ((d - 0.5) / 0.5),
    )
    val_mott = np.clip(1.0 - 0.045 * parcel_dry + 0.11 * clump + 0.26 * grain - fil_dark, 0.65, 1.35)
    plains_col = plains_col * val_mott[:, :, None]

    ground_c = plains_col.copy()

    # Riparian turf blend
    if riparian_turf and riparian.any():
        rip_turf_col = np.array([0.17, 0.40, 0.15], dtype=np.float32)
        ground_c = ground_c * (1.0 - riparian[:, :, None] * 0.80) + rip_turf_col * (riparian[:, :, None] * 0.80)

    # Hills and mountain rock strata
    hills_col = np.array([0.46, 0.43, 0.30], dtype=np.float32)
    ground_c = ground_c * (1.0 - (H_hills_prob * 0.22)[:, :, None]) + hills_col * ((H_hills_prob * 0.22)[:, :, None])

    rock_slate = np.array([0.38, 0.37, 0.41], dtype=np.float32)
    rock_granite = np.array([0.52, 0.51, 0.55], dtype=np.float32)
    rock_scree = np.array([0.44, 0.42, 0.40], dtype=np.float32)
    m_weight = np.clip(H_mount_prob * 1.5 + np.clip((H - 0.30) / 0.25, 0.0, 1.0), 0.0, 1.0)[:, :, None] * eff_rock_strata
    m_rock = rock_slate * 0.5 + rock_granite * 0.5
    m_rock = np.where(slope[:, :, None] < 0.12, rock_scree, m_rock)
    ground_c = ground_c * (1.0 - m_weight) + m_rock * m_weight

    # Coastal cliffs and steep rock face
    cliff_factor = np.clip((slope - 0.14) / 0.18, 0.0, 1.0)[:, :, None] * np.clip(H_mount_prob * 1.5 + w_cliff * 2.0, 0.0, 1.0)[:, :, None] * (1.0 if (show_beaches and show_coastal_cliffs) else 0.0)
    ground_c = ground_c * (1.0 - cliff_factor * 0.70) + rock_slate * (cliff_factor * 0.70)

    # 10. Expansive Beaches & Dune Ripples
    if show_beaches:
        wet_sand = np.array([0.72, 0.66, 0.50], dtype=np.float32)
        gold_sand = np.array([0.88, 0.82, 0.60], dtype=np.float32)
        dune_sand = np.array([0.94, 0.89, 0.72], dtype=np.float32)

        if sand_dunes:
            sand_ripple = (np.sin((WX * 0.6 + WY * 0.8) / 10.0) * 0.5 + 0.5)[:, :, None]
        else:
            sand_ripple = 0.5
        t_beach = np.clip(H / 0.065, 0.0, 1.0)[:, :, None]
        beach_col = wet_sand * (1.0 - t_beach) + gold_sand * t_beach
        beach_col = beach_col * (0.94 + 0.06 * sand_ripple)
        beach_col = beach_col * (1.0 - np.clip((H - 0.04) / 0.035, 0.0, 1.0)[:, :, None]) + dune_sand * np.clip((H - 0.04) / 0.035, 0.0, 1.0)[:, :, None]

        beach_hi = 0.055 * beach_width * np.clip(1.0 - w_cliff * 0.85, 0.10, 1.5)
        beach_mask = np.clip((beach_hi - H) / np.maximum(beach_hi, 1e-3), 0.0, 1.0)[:, :, None] * (1.0 - np.clip(cliff_factor * 1.6, 0.0, 1.0)) * is_land.astype(np.float32)[:, :, None]
        ground_c = ground_c * (1.0 - beach_mask) + beach_col * beach_mask

    # 11. Glacial Snow Peaks
    eff_snow_peaks = snow_peaks if show_snow_peaks else 0.0
    snow_base = np.array([0.92, 0.95, 0.98], dtype=np.float32)
    snow_summit = np.array([1.00, 1.00, 1.00], dtype=np.float32)
    snow_weight = np.clip(H_snow_prob * 1.6, 0.0, 1.0) * np.clip((H - (snow_altitude - 0.08)) / 0.15, 0.0, 1.0) * eff_snow_peaks
    snow_col = snow_base * (1.0 - np.clip((H - 0.82) / 0.12, 0.0, 1.0)[:, :, None]) + snow_summit * np.clip((H - 0.82) / 0.12, 0.0, 1.0)[:, :, None]
    ground_c = ground_c * (1.0 - snow_weight[:, :, None]) + snow_col * snow_weight[:, :, None]

    # 12. 2D Volumetric Forest Canopy
    canopy_a = np.zeros((height, width, 1), dtype=np.float32)
    if show_canopy:
        # Treeline factor: trees do not climb into alpine rock
        elev_treeline = np.clip(1.0 - (H - 0.25) / 0.20, 0.0, 1.0)
        treeline_factor = elev_treeline * np.clip(1.0 - H_mount_prob * 2.0, 0.0, 1.0)

        # Crown stamps Voronoi scatter
        cc = max(2.5, crown_size)
        u, vv = WX / cc, WY / cc
        nu, nv = np.floor(u), np.floor(vv)
        fu, fv = (u - nu).astype(np.float32), (vv - nv).astype(np.float32)

        wsum = np.full_like(WX, 1e-4, dtype=np.float32)
        tone_ws = np.zeros_like(WX, dtype=np.float32)
        relief_ws = np.zeros_like(WX, dtype=np.float32)
        canopy_cov = np.zeros_like(WX, dtype=np.float32)
        canopy_hi = np.zeros_like(WX, dtype=np.float32)
        canopy_sh = np.zeros_like(WX, dtype=np.float32)

        for gv in (-1, 0, 1):
            for gu in (-1, 0, 1):
                cellu = (nu + gu).astype(np.int64)
                cellv = (nv + gv).astype(np.int64)
                ox = _cellhash(cellu, cellv, 11, seed)
                oy = _cellhash(cellu, cellv, 12, seed)
                hr = _cellhash(cellu, cellv, 13, seed)
                hv = _cellhash(cellu, cellv, 14, seed)

                ru = (gu - fu + ox) * cc
                rv = (gv - fv + oy) * cc
                rad = cc * (0.70 + 0.55 * hr)
                d = np.sqrt(ru * ru + rv * rv)
                qn = d / np.maximum(rad, 1e-4)
                prof = np.where(qn < 1.35, np.maximum(0.0, 1.0 - qn * qn), 0.0)
                tone = np.where(hv < 0.42, -0.55, np.where(hv < 0.80, 0.05, 0.55))
                sunlit = -(ru * sun_x + rv * sun_y) / np.maximum(d, 1e-4)

                wsum += prof
                tone_ws += prof * tone
                relief_ws += prof * sunlit
                canopy_cov = np.maximum(canopy_cov, prof)
                canopy_hi = np.maximum(canopy_hi, np.clip(sunlit, 0.0, 1.0) * prof)
                ring = _ss(1.0, 1.35, qn) * _ss(1.85, 1.35, qn)
                canopy_sh = np.where(sunlit < -0.10, np.maximum(canopy_sh, ring * (-sunlit)), canopy_sh)

        tone_blend = tone_ws / wsum
        relief_blend = relief_ws / wsum
        canopy_tex = np.clip(0.55 * tone_blend + 0.50 * (canopy_cov - 0.62) + 0.22 * relief_blend, -0.80, 0.60)

        # Ragged boundary noise
        cbn, _, _ = _iq_noised(WX_warped / (hex_ref * 4.2), WY_warped / (hex_ref * 4.2))
        cbn = (cbn - 0.5) * 2.0

        fprob = gaussian_filter(H_forest_prob * canopy_density, sigma=width * 0.01)
        if riparian_trees and riparian.any():
            fprob = fprob + 0.25 * riparian

        edge = fprob + 0.32 * cbn + 0.07 * (canopy_cov - 0.55)
        canopy_density_field = _ss(0.28, 0.50, edge)

        if forest_clearings:
            cl, _, _ = _iq_noised(WX_warped / (hex_ref * 1.7) + 71.0, WY_warped / (hex_ref * 1.7) - 33.0)
            clearing = _ss(0.54, 0.82, cl)
            canopy_density_field = canopy_density_field * (1.0 - 0.85 * clearing)

        canopy_density_field = canopy_density_field * treeline_factor * is_land.astype(np.float32)

        # Forest AO and drop shadow
        if forest_shadows:
            canopy_ao = np.clip(gaussian_filter(canopy_density_field, sigma=4.0) * 1.15, 0.0, 1.0)
            ground_c = ground_c * (1.0 - 0.30 * canopy_ao[:, :, None])

            shp = 4
            src = np.zeros_like(canopy_density_field)
            src[shp:, shp:] = canopy_density_field[:-shp, :-shp]
            canopy_drop = np.clip(gaussian_filter(src, sigma=1.5) - canopy_density_field, 0.0, 1.0)
            ground_c = ground_c * (1.0 - 0.34 * canopy_drop[:, :, None])

        canopy_deep = np.array([0.060, 0.140, 0.075], dtype=np.float32)
        canopy_core = np.array([0.130, 0.270, 0.120], dtype=np.float32)
        canopy_olive = np.array([0.300, 0.380, 0.170], dtype=np.float32)
        canopy_under_col = canopy_deep * 0.5 + canopy_core * 0.5

        canopy_rgb = canopy_under_col * (1.0 + np.clip(canopy_tex, -0.75, 0.60)[:, :, None] * 1.35)
        canopy_rgb = canopy_rgb + (canopy_olive - canopy_rgb) * (0.60 * canopy_hi[:, :, None])
        canopy_rgb = canopy_rgb * (1.0 - 0.34 * canopy_sh[:, :, None])
        canopy_rgb = np.clip(canopy_rgb, 0.0, 1.0)

        canopy_a = np.clip(_ss(0.14, 0.42, canopy_density_field) + 0.40 * canopy_cov * _ss(0.04, 0.22, canopy_density_field), 0.0, 1.0)[:, :, None]
        ground_c = ground_c * (1.0 - canopy_a) + canopy_rgb * canopy_a

    # 13. Lighting Pass over Land
    sun_color = np.array([1.18, 1.10, 0.96], dtype=np.float32)
    sky_color = np.array([0.22, 0.28, 0.40], dtype=np.float32)
    total_light = direct_sun[:, :, None] * sun_color + sky_light[:, :, None] * sky_color + 0.12

    snow_spec = (np.clip(Nx * half_x + Ny * half_y + Nz * half_z, 0.0, 1.0)**20 * 0.25)[:, :, None] * direct_sun[:, :, None]
    land_lit = ground_c * total_light + snow_weight[:, :, None] * snow_spec

    # Composite Ocean and Land
    final_rgb = np.where(is_ocean_water[:, :, None], ocean_lit, land_lit)

    # River water surface compositing
    if is_river_water.any():
        river_water_col = np.array([0.15, 0.38, 0.52], dtype=np.float32)
        if estuary_fan and mouth_zone.any():
            estuary_col = np.array([0.15, 0.33, 0.40], dtype=np.float32)
            river_water_col = river_water_col * (1.0 - 0.55 * mouth_zone[:, :, None]) + estuary_col * (0.55 * mouth_zone[:, :, None])
        river_spec = (np.clip(half_z, 0.0, 1.0)**32 * 0.35) * direct_sun[:, :, None]
        river_lit = river_water_col * (0.65 + 0.35 * direct_sun[:, :, None]) + river_spec
        iw_a = river_alpha[:, :, None]
        final_rgb = final_rgb * (1.0 - iw_a) + river_lit * iw_a

    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    final_rgb = np.power(final_rgb, 1.0 / 1.15)

    # 14. Atmospheric Post-Processing & Grading
    if show_atmosphere:
        lc = np.array([0.299, 0.587, 0.114], dtype=np.float32)
        rad = np.sqrt(NX**2 + NY**2)

        # Split-tone warm sun / cool ambient
        eff_split_tone = split_tone if show_split_tone else 0.0
        if eff_split_tone > 0.05:
            warm_col = np.array([1.00, 0.955, 0.86], dtype=np.float32)
            cool_col = np.array([0.66, 0.74, 0.90], dtype=np.float32)
            warm_norm = warm_col / float(warm_col @ lc)
            cool_norm = cool_col / float(cool_col @ lc)

            lum = final_rgb @ lc
            lum_mean = gaussian_filter(lum, sigma=width * 0.12)
            st_t = np.clip(0.5 + (lum - lum_mean) * 3.6, 0.0, 1.0)
            st_tint = cool_norm[None, None, :] * (1.0 - st_t)[:, :, None] + warm_norm[None, None, :] * st_t[:, :, None]
            st_tint = np.clip(1.0 + (st_tint - 1.0) * (0.48 * eff_split_tone), 0.92, 1.08)
            final_rgb = final_rgb * st_tint

        # Aerial Haze
        eff_aerial_haze = aerial_haze if show_aerial_haze else 0.0
        if eff_aerial_haze > 0.05:
            h_norm = np.clip(H / 0.80, 0.0, 1.0)
            haze_f = (0.02 + (0.08 - 0.02) * (1.0 - h_norm)**1.5) * eff_aerial_haze
            haze_col = np.array([0.72, 0.77, 0.86], dtype=np.float32)
            final_rgb = final_rgb * (1.0 - haze_f[:, :, None]) + haze_col * haze_f[:, :, None]

        # Drifting Cloud Shadows
        eff_cloud_shadows = cloud_shadows if show_cloud_shadows else 0.0
        if eff_cloud_shadows > 0.05:
            c_time = frame * 0.03
            cs_scale = 1.0 / (hex_ref * 4.5)
            cw1_v, cw1_dx, _ = _iq_noised(WX * cs_scale + c_time, WY * cs_scale - c_time)
            CWX = WX + cw1_dx * (hex_ref * 0.5)
            CWY = WY
            cl0, _, _ = _iq_noised(CWX * cs_scale + 12.0 + c_time, CWY * cs_scale - 12.0)
            cl1, _, _ = _iq_noised(CWX * cs_scale * 3.5, CWY * cs_scale * 3.5)
            cloud_field = cl0 * 0.60 + cl1 * 0.40
            cl_sh = _ss(0.55, 0.72, cloud_field) * eff_cloud_shadows
            final_rgb = final_rgb * (1.0 - 0.22 * cl_sh[:, :, None])

        # Filmic Vignette & S-Curve Knee
        if vignette:
            p, s, knee = 0.45, 1.12, 0.86
            y = p + (final_rgb - p) * s
            over = np.maximum(0.0, y - knee)
            y = np.where(y > knee, knee + over / (1.0 + over / (1.0 - knee) * 1.20), y)
            final_rgb = np.maximum(y, 0.0)

            vig = np.clip((rad - 0.90) / 0.90, 0.0, 1.0)**2
            final_rgb = final_rgb * (1.0 - 0.05 * vig)[:, :, None]

    final_rgb = np.clip(final_rgb, 0.0, 1.0)
    img_uint8 = (final_rgb * 255).astype(np.uint8)
    # Pygame expects (width, height, 3) where array is indexed (x, y)
    surf = pygame.surfarray.make_surface(np.transpose(img_uint8, (1, 0, 2)))
    return surf
