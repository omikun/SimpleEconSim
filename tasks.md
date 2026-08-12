# REGNUM — Task Handoff (2026-08-11)

HEAD: f627d5f (T1 committed; never push). M1 committed on top (never push).
Invariant: 0 LEAK / 0 SUPPLY SHIFT / no BANK INSOLVENCY.

## DONE — T1 transport (f627d5f, 9 files, +528/-28)
- In-flight cargo is FINAL: _repoint_traders no longer reclaims on dest
  switch (reclaim stays at death/exit).
- Route.advance parks old-dest deliveries in trader.parked_foreign;
  Route.post_parked re-ships parked lots.
- Parked lots sell in place at the abandoned tile's auction (is_parked
  flag; settlement decrements parked_foreign; unsold stays parked).
- resolve_parked re-routes only after dest change + strictly-better net.
- Death escheats parked goods; exit liquidation folds parked in.
- Verified: sim_ring 300, sim_nation 100, two-region 30 all 0 LEAK/SHIFT;
  tmp/probe_t1_parked.py PASS (241 switches, 5 parked checks).

## DONE — M1 People (committed; never push)
- [x] M1.1 Traits: agent.py __slots__ ambition/loyalty/charisma/
  risk_tolerance/bigotry(dict)/productivity/fertility/religiousness;
  seeded at birth via seed_traits(); heritable +/- mutation
  (child = clamp(parent + gauss(0,0.15))); orphans/immigrants random.
  All Agent(t) creation points seed traits (population, traders,
  immigrants, births, companies).
- [x] M1.2 Identity tags (ethnicity/religion/politics) inherited with
  2% mutation; per-tile mix probe in tmp/behavior_drift.py.
- [x] M1.3 Bounded memory buffers (cap 32) + mem_push/mem_last/mem_avg/
  mem_recent; mem_hunger + mem_wages wired.
- [x] M1.4 Career-switch learning (_learned_switch_choice: bottleneck
  weights + demand_ratio history + mem_hunger + ambition).
- [x] M1.5 Migration intent stub (score-only, per-tile migration_intent_log).
- [x] M1 gate: tmp/behavior_drift.py 300t x 3 seeds — 0 LEAK/SHIFT,
  no insolvency; memory <= 32; identity all seeded.

## DONE — V1 Pygame hex viewer (committed; never push)
- [x] hexmap.py: axial pointy-top hex geometry (axial_to_pixel, hex_corners,
  pixel_to_axial with cube rounding, hex_distance/adjacent) + LAYOUT_2X3 —
  the M0 2x3 grid maps 1:1 onto hex adjacency, so all wired edges share
  full hex edges like Civilization (verified: 0 non-adjacent).
- [x] hexview.py: pygame app — hexes tinted by owner nation (same palette as
  tile_map.png), name + pop/food-price/trader text, vector terrain glyphs
  (wheat wedge / forest wedge / cold snow-dot), play/pause (Space), step
  (S/->), Esc/Q quit, hover tooltip (nation/regime/legitimacy/treasury/
  prices/pop/traders/migration-intent), live per-currency audit readout with
  red-flag on >5.0 SUPPLY SHIFT / CASH LEAK.
- [x] Step loop mirrors sim_nation.main() exactly (tiles -> routes ->
  resolve_parked -> settle_trade -> cycle markets -> PPP desks -> audit).
- [x] Verified: tmp/probe_hex.py — 4 wired edges all hex-adjacent; pixel<->
  axial round-trip PASS; SDL-dummy render after 10 steps, 0 violations,
  1200x800 screenshot. M1 gate + sim_nation 100 still clean.
- [x] **V2a** hover chart dashboard: hovering a hex shows a 2x3 grid of six
  pure-pygame mini-charts (prices, population/hunger, production, trade
  flow bars, gov-income stacked, gini/migration), Tab=grid / 1-6=zoom,
  live-updating each turn.
- [x] **V2b** on-map indicators: animated trade-flow arrows on wired edges
  (width/direction from export/import value), population-heat hex fill,
  activity badges (demand alert, hunger, trader count, gini dot, migration
  arrow, hot/cold food-price arbitrage ring), +B/-D per-turn pop deltas.
- [x] **V2c** national HUD strip (N toggle): per-nation regime/legitimacy/pop
  header + treasury sparkline + export/import bars over the window.
- [x] V2 gate: tmp/probe_hex.py renders map + hover charts + HUD headlessly
  (0 audit violations, screenshots); M1 behavior-drift gate still clean.

## DONE — M2 Factions & Unrest (committed; never push)
- [x] M2.1 `faction.py`: Demand/Faction/FactionSystem — overlapping membership
  by agent id, ranked demands, source-keyed grievances, live support.
- [x] M2.2 identity factions wired per tile (ethnicity/religion/politics from
  M1 tags) + Government policy knobs -> demand satisfaction + per-turn
  faction_support_log.
- [x] M2.3+M2.4 grievance accumulation (hunger/gini/tax/unemployment via M1
  mem_*) + per-tile protest_energy_log (rate-driven, no saturation).
- [x] M2.5+M2.6 `unrest.py` escalation ladder (unrest->protest->mob->
  compromise->takeover, conserved `_loot_and_burn`/`_forced_compromise`/
  `_takeover`) + `apply_repression` (legitimacy cost + mem_casualties /
  mem_promises seeds -> delayed TRAUMA grievance).
- [x] M2 gate: tmp/probe_m2.py PASS — famine -> unrest -> protest -> mob ->
  compromise, 0 conservation violations, legitimacy 0.0.
- [x] CONSERVATION FIX #1: Region._buy `a.cash = max(0.0, a.cash - cash)`
  silently erased pre-existing negative agent cash (debt) when bought==0 —
  minted $6.66 C (7 agents summed to exactly 6.6553) only in the gate's
  one-process multi-seed run.  Now cash moves only when bought > 0; the
  seed-7 post-42 supply shift is gone.
- [x] CONSERVATION FIX #2: Bank.PayDepositInterest payout capped at the
  available deposit pool (`max_total_payout = min(loan_interest*0.6,
  max(0, total_deposits))`) so deposit-ledger can never overflow.

## DONE — M2 conservation gate: seed-1337 BANK INSOLVENCY FIXED
Root cause (from tmp/probe_all_deposits.py user run at T=293):
`sum_deposits_dict=17492.50` while `total_deposits=-299.23` → the per-agent
deposit DICT and the scalar had diverged by ~$17.8k.  Heirless bad-debt
forgiveness only wrote down `total_deposits` (scalar), never the per-agent
dict, so depositors never absorbed losses while the scalar drained negative.
- Fix (econsim_live.py): `_forgive_bad_debt` + `_deposit_pool` — forgiveness
  now writes down BOTH the scalar and the per-agent dict **pro-rata** (floored
  per depositor), with government bailout cushioned against the real dict pool
  and insolvency raised only when the TRUE pool is genuinely insufficient.
- Fix (econsim_trade_money.py): `RequestBailout` also credits the government's
  per-agent dict entry, keeping dict/scalar in sync.
- Result: **`tmp/behavior_drift.py` GATE PASS — 3 seeds × 300t, 0 LEAK /
  0 SUPPLY SHIFT / no insolvency**; `tmp/probe_m2.py` GATE PASS.

## IN PROGRESS — sim_nation 100: genuine bank insolvency at T=74
With the honest forfeiture now in place (no phantom-scalar absorption),
sim_nation 100 aborts:
```
turn=74 shortfall=$116.92  bank: total_deposits=2076.56
  total_liabilities=2652.99 equity=-576.44 deposit_dict_pool=1.43
  bank loans outstanding=$2652.99 (319 loans)  gov cash=0.0
```
- The real deposit pool is only $1.43 and the government has $0 cash — a
  **genuinely insolvent tile bank** (real depositor money + gov capital cannot
  cover a dying agent's $116.92 bad debt).  Pre-M2 this was silently absorbed
  from the phantom 2000-base scalar (the same bug class that broke the ring).
- The exception is the engine refusing to destroy money — conservation-safe.
  It needs an economic-tune fix (larger bank capital, lender-of-last-resort,
  or gov treasury-backed bailout), NOT a silent write-off.

## NEXT — M2 finish
1. Resolve sim_nation's genuine insolvency (T=74): give banks a real capital/equity
   buffer or a government treasury-backed lender-of-last-resort so bad debt is
   absorbed against countable capital — never phantom scalar, never silent.
2. Re-verify: sim_nation 100 (PASS), probe_hex (headless render), sim_ring 300.
3. Docs: update agent.md + task.md + tasks.md.  Commit (no push).

## FINAL
- Docs: update agent.md + task.md + tasks.md.
- Commits: T1 done -> M1 -> V1 -> M2 (in progress). No push.

## Known quirks (don't fix unless asked)
- Long commands with '&' fail to transmit; write tmp/*.sh and bash it.
- pending_imports emits 3-tuples (trader, qty, is_parked).
- two-region plot needs `pip install adjustText`.