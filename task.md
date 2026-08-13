# SimpleEconSim — Task Handoff

Last updated: 2026-08-11 09:16 PDT · HEAD: `f627d5f` + M1 (4+ local commits ahead of origin/main; nothing pushed)

## M0 — Nation & Tiles (committed, PASSING)

**Commit chain** (all local, not pushed):
- `ecbc772` — GDD + `priority_tasks.md` (REGNUM strategy game design)
- `f222b71` — **M0: Nation & Tiles** — nation.py, terrain hooks, adjacency + multi-route,
  ownership, sim_ring.py + sim_nation.py, tile-map sketch, **FX conservation audit fixes**
  (9 files, +1101/−57)
- `be8de3a` — Docs: record M0 completion in agent.md + task.md (agent guide + handoff)

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

## M1 — People: traits, memory, learning (committed, PASSING)
- `agent.py`: M1.1 traits (ambition/loyalty/charisma/risk_tolerance/bigotry dict/
  productivity/fertility/religiousness) via `seed_traits(agent, parent=None)`;
  M1.2 identity tags (ethnicity/religion/politics, 2% mutation);
  M1.3 bounded memory rings (cap 32) `mem_push/mem_last/mem_avg/mem_recent`.
- `econsim_live.py`: heritable seeding in `_handle_reproduction`; `mem_hunger` on
  consumption; M1.4 `_learned_switch_choice` (bottleneck + demand history +
  hunger memory + ambition) for poor-agent career switches.
- `region.py`: `mem_wages` on wage payment; M1.5 `_migration_intent_score()` +
  `migration_intent_log` (score-only stub, no movement).
- Companies seed traits (region.py + econsim.py) so dissolved remnants keep identity.
- **M1 gate** `tmp/behavior_drift.py`: 3-tile ring, 300t × 3 seeds — 0 LEAK /
  0 SUPPLY SHIFT / no insolvency; memory ≤ 32; identities present.

## V1 — Pygame hex viewer (committed, PASSING)
- `hexmap.py` — axial pointy-top hex geometry (`axial_to_pixel`/`hex_corners`/
  `pixel_to_axial` with cube rounding/`hex_distance`/`adjacent`) + `LAYOUT_2X3`
  mapping the M0 2×3 grid onto hex coordinates.  All sim-wired edges are
  hex-adjacent (0 non-adjacent verified), so hexes share full edges like Civ.
- `hexview.py` — pygame viewer: hexes tinted by owner nation, name + pop/food/
  trader text, vector terrain glyphs (wheat/forest/cold), Space play/pause,
  S/→ step, Esc/Q quit, hover tooltip (nation/regime/legitimacy/treasury/
  prices/pop/traders/migration-intent), live per-currency audit readout with
  red-flag on >5.0 violation.  Run: `python3 hexview.py`.
- Step loop mirrors `sim_nation.main()`; verified by `tmp/probe_hex.py`
  (adjacency + pixel↔axial round-trip + SDL-dummy render after 10 steps,
  0 violations).  M1 gate + `sim_nation 100` still clean.
- **V2a** hover chart dashboard (6 pure-pygame mini-charts per hex: prices,
  pop/hunger, production, trade flow, gov income, gini/migration; Tab grid /
  1–6 zoom, live per turn).
- **V2b** on-map indicators: animated trade-flow arrows (width/direction from
  export/import value), population-heat fill, activity badges (demand alert,
  hunger, trader count, gini dot, migration arrow, hot/cold food-price ring),
  +B/−D per-turn pop deltas.
- **V2c** national HUD strip (`N` toggle): per-nation regime/legitimacy/pop
  header + treasury sparkline + export/import bars over the window.
- V2 commits: `e5e0a6f` (V2a), `84f8d19` (V2b), `09a0bd2` (V2c); probe now
  renders map + hover charts + HUD headlessly (0 violations) and the M1
  behavior-drift gate stays clean.

## M2 — Factions & Unrest (committed except conservation fixes; gate in progress)
- `faction.py` — `Demand`/`Faction`/`FactionSystem`: overlapping membership by
  agent id, ranked demands, source-keyed grievances, live support measure.
- `region.py` wiring: per-tile identity factions (ethnicity/religion/politics
  from M1 tags), Government policy knobs → demand `satisfied` + per-turn
  `faction_support_log`; M2.3/M2.4 grievance accumulation (hunger/gini/tax/
  unemployment via M1 `mem_*`) + rate-driven `protest_energy_log`.
- `unrest.py` (M2.5/M2.6) — escalation ladder (calm→unrest→protest→mob→
  compromise→takeover, all transfers conserved: `_loot_and_burn`,
  `_forced_compromise`, `_takeover`) + `apply_repression` (legitimacy cost +
  `mem_casualties`/`mem_promises` seeds → delayed TRAUMA grievance in M2.6
  closure commit `face804`).
- M2 commits: `0d45334` (M2.1), `0d9878b` (M2.2), `f0f9142` (M2.3+M2.4),
  `7aea20f` (M2.5+M2.6), `face804` (M2.6 closure: trauma memory).  Gate
  `tmp/probe_m2.py` PASS (famine → … → compromise, 0 conservation violations).

### M2 conservation fixes (uncommitted — in this commit)
1. **`Region._buy` negative-cash mint (seed-7 C $6.66)** — `a.cash =
   max(0.0, a.cash - cash)` erased pre-existing negative balances (debt) when
   `bought==0` — minted exactly 6.6553 C at T=243 in the gate's one-process
   multi-seed run.  Fix: move cash only when `bought > 0`.
2. **`Bank.PayDepositInterest` deposit-pool overflow** — payout capped at
   `min(estimated_loan_interest*0.6, max(0, total_deposits))` so the deposit
   ledger can never go negative.

### DONE — seed-1337 BANK INSOLVENCY FIXED (scalar/dict divergence)
Root cause (from `tmp/probe_all_deposits.py` at T=293):
`sum_deposits_dict=17492.50` vs `total_deposits=-299.23` → the per-agent
deposit DICT and scalar had diverged ~$17.8k.  Heirless bad-debt forgiveness
only wrote down the scalar, never the per-agent dict → depositors never
absorbed losses while the scalar drained negative.
- Fix `econsim_live.py`: `_forgive_bad_debt` + `_deposit_pool` — heirless
  forgiveness now writes down BOTH scalar and per-agent dict pro-rata
  (floored per depositor), government bailout cushioned against the real dict
  pool, insolvency raised only when the TRUE pool is genuinely insufficient.
- Fix `econsim_trade_money.py`: `RequestBailout` also credits the gov's
  per-agent dict entry (keeps dict/scalar in sync).
- **Result: `behavior_drift.py` GATE PASS (3 seeds × 300t, 0 LEAK / 0 SUPPLY
  SHIFT / no insolvency); `probe_m2.py` GATE PASS.**

### DONE — sim_nation 100: genuine bank insolvency → real bank capital + recapitalization
The honest forfeiture exposed a **genuinely insolvent tile bank** at T=74
(`shortfall=$116.92`, deposit pool $1.43, gov cash $0) — pre-M2 this was
silently absorbed from the phantom 2000-base scalar.  Fixed with a proper
capital structure instead of any silent write-off:

- **`Bank.capital`** (econsim_trade_money.py): the old phantom 2000-base that
  lived inside `total_deposits` is now explicit shareholder equity (seeded
  2000).  `total_deposits` starts at 0 and stays in lockstep with the per-agent
  dict.  Loan interest accrues to `capital` (retained earnings); deposit
  interest is paid OUT OF `capital`, never out of deposits.  `Bank.equity`
  property = `capital + total_deposits − total_liabilities`.
- **Seniority-order bad-debt forgiveness** (econsim_live.py `_forgive_bad_debt`):
  shareholders absorb first (capital write-down), then depositors pro-rata
  (the real dict pool), then the tile treasury (lender of last resort).
- **`_recapitalize`**: tile gov cash → bank capital (state takes equity,
  `state_equity` bookkeeping); conserved because gov cash is counted in
  `r.agents` and bank capital in `bank.equity`.
- **Equity readers updated** (forex.py `audit_currency_total`, region.py,
  econsim.py, wealth_diagnostic.py) to use `bank.equity`; `Nation.add_tile`
  wires `bank.owner_nation` for treasury recall.
- **Verified**: `sim_nation 100` PASS (0 shift/leak/insolvency),
  `sim_ring 300` PASS, M1 gate `behavior_drift` PASS (3 seeds × 300t),
  `probe_m2` PASS, `probe_hex` PASS.

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
5. **Deposit-ledger divergence** — resolved: the seed-1337 scalar/dict divergence
   and the sim_nation phantom-base insolvency were fixed by the real capital tier
   + seniority forgiveness (see DONE sections above).
6. **Charity food hoarding** — charity can hold hundreds of food units; `max_food_per_agent=1`
   and distribution covers ~1/3 of hungry + young only.
7. **`agent.md` / `task.md`** — update both when the next session changes behavior or commits.

## Diagnostics (tmp/)
- `tmp/gov_deposit_heirless.py [turns]` — gov bank Withdraw/Deposit tally, heirless fraction
- `tmp/heirless_bucket.py [turns]` — death buckets by wealth/profession, direct vs recursive descendants, ledger vs interest
- `tmp/verify_gov_wealth.py [turns]` — ledger invariant + gov wealth breakdown
- `tmp/probe_ga*.py`, `tmp/probe_be*.py`, `tmp/fx_p2_audit_core.py` — M0.5 FX audit probes (untracked debug)