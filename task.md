# SimpleEconSim — Task Handoff

Last updated: 2026-08-10 21:30 PDT · HEAD: `791ada4` (3 local commits ahead of origin/main; nothing pushed)

## M0 — Nation & Tiles (committed, PASSING)

**Commit chain** (all local, not pushed):
- `ecbc772` — GDD + `priority_tasks.md` (REGNUM strategy game design)
- `f222b71` — **M0: Nation & Tiles** — nation.py, terrain hooks, adjacency + multi-route,
  ownership, sim_ring.py + sim_nation.py, tile-map sketch, **FX conservation audit fixes**
  (9 files, +1101/−57)
- `791ada4` — Docs: record M0 completion in agent.md + task.md (agent guide + handoff)

### M0 milestone contents
- **M0.1 `nation.py`** — `Nation`: owns one or more tiles (Regions), `treasury()`,
  **currency seam** (each nation has its own home currency; same-nation tiles share it),
  regime_type (autocracy/oligarchy/democracy), tile-graph ops
  (add/remove/claim/transfer/_reparent_tile).
- **M0.2 terrain** — `Region(terrain=, climate=)` hooks: terrain advantages on tile.
- **M0.3 adjacency + multi-route** — per-neighbor `forex_desks[name]`/`routes[name]`,
  `connect_desks`/`cycle_all_markets`; `Route` gains `location`, `delivered_this_turn`,
  `reclaim(trader)`; traders re-point to best-margin neighbour. 3-tile ring
  `sim_ring.py` (A–B–C–A) byte-clean at 300t.
- **M0.4 ownership** — `Nation` tile transfers with `_reparent_tile`.
- **M0.5 3 nations × 2 tiles** — `sim_nation.py`: 200 agents / 2 traders per tile,
  cross-nation routes only (intra-nation **deferred to the currency-union milestone**),
  per-turn per-currency audit with 5.0 alert threshold.
- **M0.6 tile map** — `draw_map` → `tile_map.png` sketch.

### FX conservation audit (the big finding)
The 6-tile grid showed ~$5–45/turn cross-currency round-off. Two root causes found by
phase-bisect / event-ledger probes (untracked: `tmp/probe_ga*.py`, `tmp/probe_be*.py`,
`tmp/fx_p2_audit_core.py`):
1. **Negative `Loan.pay` (~−0.379/turn, G2, T=290–295)** — an overdrawn agent produced a
   negative "payment"; `Loan.pay(-0.379)` gave `interest_paid = min(0.131, -0.379) = -0.379`
   and `bank.pay_interest(-0.379)` **reduced total_deposits (destroyed currency) with no
   cash transfer**. Fixed in `econsim_trade_money.py`: `Loan.pay` and `PayLoans` reject
   `amount <= 0`.
2. **Corpse-sale to invisible wallet (−982.33 one-shot, B2, T=70)** — a trader died
   mid-turn while cargo was already in B2's import pool; the sale credited +982 BE to its
   cleared corpse wallet, invisible to `audit_currency_total` (dead agents aren't in any
   region's living-agents list). Fixed: `Route.reclaim(trader)` at death via
   `LiveContext.source_region` (returns in-transit + pending cargo, drops stranded), and
   destination-government **import_escheat** for dead sellers in `_clear_discriminatory`.

### M0 verification (100 turns — per user request, not 300)
- `sim_nation.py 100`: **0 SUPPLY SHIFT / 0 CASH LEAK** for AL / BE / GA; trader ROI
  **+62.6% / +90.1% / +37.9%**
- `sim_ring.py` — clean (3-tile ring remains byte-clean)
- `econsim_two_region.py 30` — no LEAK/SHIFT/INSOLVENCY regression
- `tile_map.png` renders

## Earlier status (pre-M0, still PASSING)
- `python3 econsim_two_region.py 30` — no LEAK/SHIFT, ROI positive both sides
- `python3 econsim_two_region.py 300` — no LEAK/SHIFT; A-trader decline at 300t is
  **pre-existing structural** (price convergence evicts unprofitable arbitrageurs)
- Both PNGs render; gov income decomposition row present

## Potential follow-ups (not yet requested / open)
1. **M1? (next milestone)** — see `priority_tasks.md` / `gdd.md` for REGNUM roadmap.
   Natural continuations: **currency-union / intra-nation trade** (M0 deferred it),
   more tile shapes (non-grid), nation-level AI vs regime_type, war/conquest, tech tree.
2. **Region_A long-horizon trader extinction (300t)** — pre-existing, structural:
   arbitrage converges so traders become unprofitable and the exit benchmark evicts them.
   **Do not "fix" without being asked** — it's intended behavior.
3. **Gov deposits sit idle** — heirs/probate credit `bank.deposits[gov]` directly;
   `bid_food`/loan service always use hand cash so deposits are never touched.
4. **Poverty → heirless root cause** — 96% of deaths are poor (<$20). Address poverty
   (food aid/welfare, wage floors, charity rate) rather than inheritance rules.
5. **Deposit-ledger divergence** — bank bad-debt/interest mechanism; only revisit if the
   user asks about total-deposits accounting.
6. **Charity food hoarding** — charity can hold hundreds of food units; `max_food_per_agent=1`
   and distribution covers ~1/3 of hungry + young only.
7. **`agent.md` / `task.md`** — update both when the next session changes behavior or commits.

## Diagnostics (tmp/)
- `tmp/gov_deposit_heirless.py [turns]` — gov bank Withdraw/Deposit tally, heirless fraction
- `tmp/heirless_bucket.py [turns]` — death buckets by wealth/profession, direct vs recursive descendants, ledger vs interest
- `tmp/verify_gov_wealth.py [turns]` — ledger invariant + gov wealth breakdown
- `tmp/probe_ga*.py`, `tmp/probe_be*.py`, `tmp/fx_p2_audit_core.py` — M0.5 FX audit probes (untracked debug)