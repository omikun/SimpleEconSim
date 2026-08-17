#!/usr/bin/env python3
"""Check nation cluster claims: sizes (3/4/5) + hex adjacency contiguity."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hexmap import rectangular_hex_layout, offset_to_axial, hex_distance
from sim_world import build_world, GRID_ROWS, GRID_COLS

tiles, nations, grid = build_world()
layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)


def name_to_rc(name):
    return int(name[1:name.index('c')]), int(name[name.index('c') + 1:])


ok = True
for n in nations:
    cells = [layout[t.name] for t in n.tiles]
    names = [t.name for t in n.tiles]
    # 1. size
    expect = {'Alpha': 3, 'Beta': 4, 'Gamma': 5}[n.name]
    size_ok = len(cells) == expect
    ok &= size_ok
    # 2. contiguity: every tile reachable from the first via hex-adjacency
    #    staying inside the set
    reach = {cells[0]}
    stack = [cells[0]]
    while stack:
        cur = stack.pop()
        for other in cells:
            if other in reach:
                continue
            if hex_distance(cur, other) == 1:
                reach.add(other)
                stack.append(other)
    contig_ok = len(reach) == len(cells)
    ok &= contig_ok
    print(f"{n.name}: size={len(cells)} (expect {expect} {'OK' if size_ok else 'FAIL'}), "
          f"contiguous={'PASS' if contig_ok else 'FAIL'}, tiles={names}")

print("\nCLUSTER CHECK " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)