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


def edge_list_from_tiles(tiles, layout=LAYOUT_2X3):
    """Extract the unique undirected neighbor edges actually wired by the sim.

    Each Region carries ``neighbors`` (set when routes/desks were wired), so
    this is the ground truth of connectivity — same edges sim_nation used.
    *layout* maps region name -> axial (q, r); it defaults to the legacy 2x3
    map so existing callers (probe_hex) are byte-identical.
    Returns a list of ((q1,r1),(q2,r2)) hex pairs.
    """
    edges = []
    seen = set()
    for t in tiles:
        coords_a = layout.get(t.name)
        if coords_a is None:
            continue
        for other_name in getattr(t, 'neighbors', {}):
            key = tuple(sorted((t.name, other_name)))
            if key in seen:
                continue
            seen.add(key)
            coords_b = layout.get(other_name)
            if coords_b is not None:
                edges.append((coords_a, coords_b))
    return edges


def assert_edges_are_hex_adjacent(tiles, layout=LAYOUT_2X3):
    """Return the list of edges that are NOT hex-adjacent (should be empty).

    This is the "all hexes connect like Civilization" proof: every edge the
    simulation wired must map to two hexes sharing a full edge.  *layout*
    defaults to the legacy 2x3 map.
    """
    bad = []
    for a, b in edge_list_from_tiles(tiles, layout=layout):
        if not adjacent(a, b):
            bad.append((a, b))
    return bad


# ---------------------------------------------------------------------------
# v3_wilderness: offset rectangular hex layout (real 6-neighbor honeycomb)
# ---------------------------------------------------------------------------

#: The six axial unit-step directions of a pointy-top hex lattice.
HEX_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))


def offset_to_axial(col, row):
    """Odd-r offset (col, row) -> axial (q, r) for a pointy-top hex grid.

    Odd rows are shifted right by half a hex (standard odd-r offset), which
    lets a rectangular (row, col) region grid map 1:1 onto a honeycomb where
    interior tiles have exactly six edge-adjacent neighbors.
    """
    return col - row // 2, row


def axial_to_offset(q, r):
    """Axial (q, r) -> odd-r offset (col, row) (pointy-top, odd rows right)."""
    return q + r // 2, r


def rectangular_hex_layout(rows, cols):
    """Rectangular odd-r hex map: grid (row, col) -> axial (q, r).

    *rows* x *cols* tiles named ``r{row}c{col}`` (matches sim_world grid
    addressing).  Interior tiles have all six axial neighbors edge-adjacent,
    so the "all hexes connect like Civilization" proof holds for the world.
    """
    return {f"r{r}c{c}": offset_to_axial(c, r)
            for r in range(rows) for c in range(cols)}


def axial_neighbors(q, r):
    """The six axial coordinates adjacent to (q, r)."""
    return [(q + dq, r + dr) for dq, dr in HEX_DIRS]


def hex_bbox(layout, size):
    """Bounding box (x0, y0, x1, y1) in pixels covering *layout* at *size*.

    Includes the hex radius padding so a camera clamp keeps every hex fully
    on screen (used by worldview for centering + pan limits).
    """
    xs, ys = [], []
    for q, r in layout.values():
        x, y = axial_to_pixel(q, r, size)
        xs.append(x)
        ys.append(y)
    return (min(xs) - size, min(ys) - size,
            max(xs) + size, max(ys) + size)
