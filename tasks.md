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

## DONE — sim_nation 100: genuine bank insolvency → real bank capital (committed; never push)
The honest forfeiture (no phantom-scalar absorption) exposed a **genuinely
insolvent tile bank** at T=74:
```
turn=74 shortfall=$116.92  bank: total_deposits=2076.56
  total_liabilities=2652.99 equity=-576.44 deposit_dict_pool=1.43
  bank loans outstanding=$2652.99 (319 loans)  gov cash=0.0
```
Fixed with a proper capital structure — NOT a silent write-off:
- **`Bank.capital`** (econsim_trade_money.py): the phantom 2000-base now lives
  as explicit shareholder equity; `total_deposits` starts at 0 and stays in
  lockstep with the per-agent dict.  Loan interest → `capital` (retained
  earnings); deposit interest paid out of `capital`.  `Bank.equity` =
  `capital + total_deposits − total_liabilities`.
- **Seniority-order `_forgive_bad_debt`** (econsim_live.py): shareholders first
  (capital write-down), then depositors pro-rata (real dict pool), then tile
  treasury via new `_recapitalize` (gov cash → bank capital, state takes
  `state_equity`).  All conserved.
- **Equity readers** use `bank.equity` (forex.py audit, region.py, econsim.py,
  wealth_diagnostic.py); `Nation.add_tile` wires `bank.owner_nation`.
- **Verified**: `sim_nation 100` PASS (0 shift/leak/insolvency), `sim_ring 300`
  PASS, M1 gate `behavior_drift` PASS (3 seeds × 300t), `probe_m2` PASS,
  `probe_hex` PASS.

## DONE — Cleanup pass (M2 follow-through, committed; never push)
- Removed the dead `RequestBailout` / `gov_decide_bailout` pair and the
  write-only `Bank.owner_nation` / `Bank.region` / `Bank.state_equity`
  backrefs.  `_recapitalize` sources the tile treasury via `bank.gov` (the
  actual recap source); `_forgive_bad_debt` seniority docs corrected to
  "shareholders → depositors → tile treasury".  `Nation.add_tile` /
  `Region.__init__` no longer wire the unused backrefs.  sim_nation 100 +
  full suite still green.

## DONE — M3 Regimes (committed; never push)
- [x] M3.1 `election.py` — `Candidate` (charisma + backing faction + platform
  from faction demands); `generate_candidates` pool per election.
- [x] M3.2 campaign finance — `campaign_finance` transfers tile-treasury cash
  → candidate cash (conserved) at a charisma-diluted popularity rate.
- [x] M3.3 faction-weighted voting — `faction_weighted_vote`: adult voters
  vote their most-influential faction's candidate and DEFECT to the strongest
  rival when broken-promise memory (mem_promises > 0.5) targets the incumbent.
- [x] M3.4 legitimacy + cadence — `regime.track_legitimacy` drifts toward
  population faction support; democracies run fixed-interval elections, any
  regime snaps on legitimacy collapse; winner's platform flips the TAX knob.
- [x] M3.5 `coup.py` — `find_generals` (ambition+charisma+loyalty), per-turn
  `coup_chance` trigger, `execute_coup` (treasury seizure to the general =
  conserved transfer, regime → autocracy, deposed-faction purge as memory
  seeds).  Reuses the M2.5 takeover seam.
- [x] M3.6 player-faction continuity — engine-only opposition state:
  `Nation.ruling_faction` / `Nation.opposition` / faction `is_opposition`,
  plus `agitate(nation, faction)` and `unrest_intent(nation)` intents.
- [x] `regime.step_regime` wired into `sim_nation.main`; per-turn
  `Nation.regime_log` archives the election/coup money-trail.
- [x] **Conservation fix (immigration mint)**: `Government.spawn_immigrants`
  no longer mints $50–80 unsourced cash.  Immigrants are now chain-migrants
  derived from an existing adult citizen (parent cash split + food grant,
  traits inherited) — every agent traces to another agent.  `apply_platform`
  flips only the conserved tax knob; the UBI/tariff/immigration toggles stay
  at defaults (their money paths are not yet conservation-validated).
- [x] **M3 gate** `tmp/probe_m3.py`: scripted election (campaign $100k, leak
  $0) + betrayal flip (Yoro→Terra) + scripted coup (seizure conserved, regime
  flip) — 0 LEAK / SHIFT / INSOLVENCY.
- [x] Regression suite: sim_nation 100, sim_ring 300, M1 gate behavior_drift,
  probe_m2, probe_hex — all PASS.

## FINAL
- Docs: update agent.md + task.md + tasks.md.
- Commits: T1 → M1 → V1 → M2 → M3 (done). No push.

## Known quirks (don't fix unless asked)
- Long commands with '&' fail to transmit; write tmp/*.sh and bash it.
- pending_imports emits 3-tuples (trader, qty, is_parked).
- two-region plot needs `pip install adjustText`.