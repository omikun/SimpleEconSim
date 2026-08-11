"""
HexMap — axial hex geometry + the M0 2x3 tile layout (REGNUM V1).

Pure geometry module (no pygame, no simulation imports) so it can be tested
headlessly and reused by any renderer.

Coordinate system: axial (q, r) pointy-top hexes (Civ-style full-edge
adjacency).  The 2x3 map from sim_nation.build_world():

    A1(0,0) A2(1,0)
    B1(0,1) B2(1,1)
    G1(0,2) G2(1,2)

Every edge sim_nation wires (internal + cross-border) is exactly the axial
adjacency set, so all hexes connect edge-to-edge with zero engine changes.
"""

import math

#: sqrt(3) precomputed
_SQRT3 = math.sqrt(3.0)

#: Named layout: region name -> axial (q, r) on the 2x3 map.
LAYOUT_2X3 = {
    'A1': (0, 0),
    'A2': (1, 0),
    'B1': (0, 1),
    'B2': (1, 1),
    'G1': (0, 2),
    'G2': (1, 2),
}


def axial_to_pixel(q, r, size):
    """Axial (q, r) -> pixel (x, y) center for a pointy-top hex of radius *size*."""
    x = size * _SQRT3 * (q + r / 2.0)
    y = size * 1.5 * r
    return x, y


def hex_corners(center, size):
    """Six polygon corners (screen-space) for a pointy-top hex.

    *center* is a (x, y) pixel; angle 0 points up for pointy-top.
    """
    cx, cy = center
    pts = []
    for i in range(6):
        ang = math.pi / 180.0 * (60 * i - 30)
        pts.append((cx + size * math.cos(ang),
                    cy + size * math.sin(ang)))
    return pts


def _axial_round(frac_q, frac_r):
    """Round fractional axial coords to the nearest whole hex (cube math)."""
    x, y, z = frac_q, frac_r, -frac_q - frac_r
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, ry


def pixel_to_axial(x, y, size):
    """Pixel (x, y) -> nearest axial (q, r) for a pointy-top hex of radius *size*."""
    q = (_SQRT3 / 3.0 * x - 1.0 / 3.0 * y) / size
    r = (2.0 / 3.0 * y) / size
    return _axial_round(q, r)


def hex_distance(a, b):
    """Axial hex-distance between two hexes (BFS-independent proof of adjacency)."""
    (aq, ar), (bq, br) = a, b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


def adjacent(a, b):
    """True if hexes *a* and *b* share a full edge (Civ-style connectivity)."""
    d = hex_distance(a, b)
    return d == 1


def edge_list_from_tiles(tiles):
    """Extract the unique undirected neighbor edges actually wired by the sim.

    Each Region carries ``neighbors`` (set when routes/desks were wired), so
    this is the ground truth of connectivity — same edges sim_nation used.
    Returns a list of ((q1,r1),(q2,r2)) hex pairs via LAYOUT_2X3.
    """
    edges = []
    seen = set()
    for t in tiles:
        coords_a = LAYOUT_2X3.get(t.name)
        if coords_a is None:
            continue
        for other_name in getattr(t, 'neighbors', {}):
            key = tuple(sorted((t.name, other_name)))
            if key in seen:
                continue
            seen.add(key)
            coords_b = LAYOUT_2X3.get(other_name)
            if coords_b is not None:
                edges.append((coords_a, coords_b))
    return edges


def assert_edges_are_hex_adjacent(tiles):
    """Return the list of edges that are NOT hex-adjacent (should be empty).

    This is the "all hexes connect like Civilization" proof: every edge the
    simulation wired must map to two hexes sharing a full edge.
    """
    bad = []
    for a, b in edge_list_from_tiles(tiles):
        if not adjacent(a, b):
            bad.append((a, b))
    return bad