# REGNUM — Session Progress

**Session topic (2026-08-17):** item (3) — perf smoke + generalize hexmap/hexview + ticker, upgraded to a **real 6-neighbor hex world** per user request.

**HEAD when starting:** d4c67eb (never push).

---

## Locked plan

1. **`hexmap.py`** — add pure-geometry helpers (no sim imports):
   - `HEX_DIRS` (6 axial dirs), `offset_to_axial(row,col)` / `axial_to_offset(q,r)` (odd-r offset),
   - `rectangular_hex_layout(rows, cols)` → `{name: (q, r)}` for `r{r}c{c}` tiles,
   - `axial_neighbors(q, r)` → 6 axial neighbor coords,
   - `hex_bbox(layout, size)` → pixel extents for centering/camera clamp,
   - generalize `edge_list_from_tiles` / `assert_edges_are_hex_adjacent` with `layout=LAYOUT_2X3` default (legacy byte-identical).
2. **`sim_world.py`** — 9×9 (81 tiles) pointy-top hex topology: replace 4-neighbor orthogonal wiring with 6-neighbor axial wiring; simplify forex-desk connection to `neighbors.values()`; update strings/constants.
3. **Perf smoke** — `tmp/world_perf.py`: build hex world, a few headless turns, report turns/sec (80+ `Region.step()`/turn).
4. **`worldview.py`** (new) — hex-world viewer: `build_world_view()` + `step_world()` mirroring `sim_world.main()` exactly (migration/claims/ledger DESTROY accounting), hex grid render tinted by owner nation, "Unclaimed" grey tiles (no gov/recipes/faction readouts), camera pan/zoom, hover/pin, **ticker** strip of MIGRATE/CLAIM/DESTROY events.
5. **Probe** — `tmp/probe_worldview.py`: SDL-dummy — adjacency proof (0 bad edges), pixel↔axial round-trip (81 tiles), step ~20 turns, render screenshots (map + ticker). Report (not hard-fail) on late-run BE−/GA+ shifts (item 1 still open).
6. **Regression + commit (no push)** — sim_nation 100, sim_ring 300, tmp/behavior_drift.py, tmp/probe_hex.py, tmp/probe_worldview.py; commit message → tmp/commit_msg28.txt → `git commit -F`.

## Risks
- hexmap.py defaults must keep LAYOUT_2X3/probe_hex green.
- worldview.step_world must match sim_world.main()'s ledger.reset()/cleared() handling.
- Unclaimed tiles: guard `gov is None` / missing logs everywhere.

---

## Progress

- [x] Create progress.md with locked plan
- [x] hexmap.py helpers (layout/neighbors/bbox/adjective proof)
- [x] sim_world.py 9x9 hex topology
- [x] Perf smoke passes — tmp/verify_hex_adj.py: 81 tiles, 0 bad edges,
      interior all 6-neighbor, pixel<->axial round-trip PASS,
      10 turns in 1.14s (8.76 turns/sec), 0 SUPPLY SHIFT
- [x] worldview.py viewer + ticker — 9x9 hex map, camera pan/zoom, Unclaimed
      guards, MIGRATE/CLAIM/DESTROY ticker, audit overlay
- [x] probe_worldview.py PASS (SDL dummy) — 81 tiles, 0 bad edges,
      round-trip PASS, stepped to T=20 with 0 violations (0 shift entries),
      screenshots worldview_frame/wild/zoom.png; pygame found at
      /Users/sli/Code/venv/bin/python3
- [x] Regression suite GREEN (venv python 3.13):
      sim_nation 100 (0 LEAK/SHIFT), sim_ring 300 (0 LEAK/SHIFT),
      behavior_drift GATE PASS (3 seeds x 300t), probe_m2 PASS,
      probe_m3 PASS (via PYTHONPATH=/Users/sli/Code), probe_hex PASS
      (legacy layout unchanged), probe_worldview PASS
- [x] World 40-turn hex gate CLEAN: 527 MIGRATE, 10 CLAIM, 0 DESTROY,
      0 SUPPLY SHIFT > 5.0; 72 wilderness tiles, 48 homesteaders
- [x] Commit (no push) — hex-world viewer milestone
