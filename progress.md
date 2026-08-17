# REGNUM — Session Progress

**Session topic 1 (2026-08-17, DONE):** item (3) — true 6-neighbor hex world (9x9=81), perf smoke, worldview viewer + ticker.
Committed: `331b05b` (no push).

**Session topic 2 (2026-08-17, CURRENT):** user follow-up —
  1. restore the per-region GRAPH PANEL (V2a hover charts: Prices, Pop/Hunger,
     Production, Trade flow, Gov income, Gini/Migration) into worldview.py,
  2. make each nation's STARTING tiles CONTIGUOUS (cluster growth on the hex
     grid), with sizes **Alpha=3 / Beta=4 / Gamma=5** tiles.

---

## Locked plan (topic 2)

1. **sim_world.py**: cluster-growth claims — pick a random unclaimed seed cell,
   grow via BFS into unclaimed hex-adjacent cells (odd-r offset lookup, no
   dependence on already-wired Region.neighbors); sizes 3/4/5; rebuild in place
   with make_claimed; reject already-taken cells.
2. **worldview.py**: right chart panel (MAP_RIGHT=1100, PANEL_LEFT=1112):
   - port _tile_charts / _sum_turns / _plot_line_chart / _plot_bar_pairs /
     _plot_stacked_bars / _chart_labels / _draw_chart_cell / grid / large from
     hexview.py (pure pygame),
   - guard unclaimed tiles (gov None -> empty gov income; .get()-defaults for
     all logs),
   - panel shows pinned (else hovered) tile charts; Tab = grid, 1..6 = zoom,
   - fold the per-currency audit readout into the panel top (drop the old
     top-right map overlay), camera/tile_at/clamp constrained to MAP_RIGHT,
   - keep top bar, ticker, pan/zoom/help.
3. **tmp/probe_worldview.py**: add contiguity check (each nation's axial hex
   cells are BFS-connected) + render chart panel (grid view + zoom 1) for a
   claimed and an unclaimed tile; keep 20-turn step + audit + screenshots.
4. Verify: probe_worldview PASS, world 40-turn gate 0 SUPPLY SHIFT,
   sim_nation/sim_ring untouched (different builders).
5. Update progress.md + tmp/commit_msg29.txt + `git commit -F` (no push).

---

## Progress (topic 1, DONE)

- [x] hexmap.py helpers + layout generalization (legacy probe_hex green)
- [x] sim_world.py 9x9 hex topology (interior 6-neighbor)
- [x] Perf smoke: 8.76 turns/sec, 0 SUPPLY SHIFT (tmp/verify_hex_adj.py)
- [x] worldview.py viewer + ticker + camera (committed 331b05b)
- [x] probe_worldview PASS (SDL dummy T=20, 0 violations)
- [x] Regression green (sim_nation/ring/drift/m2/m3/hex/worldview)
- [x] World 40-turn gate clean (527 MIGRATE / 10 CLAIM / 0 SHIFT)

## Progress (topic 2)

- [x] sim_world.py contiguous cluster claims — BFS cluster growth on the hex
      grid; Alpha=3 / Beta=4 / Gamma=5; tmp/check_clusters.py PASS
      (all contiguous, sizes exact)
- [x] worldview.py chart panel — V2a six-chart dashboard ported (Prices,
      Pop/Hunger, Production, Trade flow, Gov income, Gini/Migration),
      Tab=grid / 1..6=zoom, audit folded into panel, unclaimed-tile guards
      (gov None safe), camera/hit-test constrained to MAP_RIGHT
- [x] probe_worldview.py — 5/5 PASS: adjacency (0 bad), round-trip,
      cluster contiguity 3/4/5, dummy render T=20 (0 violations, 0 shifts),
      ticker archived; screenshots worldview_charts/chart1/wild.png
- [x] World 40-turn gate CLEAN: 720 MIGRATE / 6 CLAIM / 0 DESTROY /
      0 SUPPLY SHIFT; nations end at 4/5/9 tiles (12 start + 6 claims)
- [x] Commit (no push) — topic 2 milestone
