# SimpleEconSim — Agent Guide

Multi-region agent-based economy sim. Money & goods must be **conserved** — no sinks
or free creation (except explicit design decisions, which must be documented).

## Hard rules (from .clinerules)
1. **Never run scripts from inline strings** — always write the file first, then run it.
2. Commit messages go to a file (`tmp/commit_msgN.txt`), commit with `git commit -F <file>`.
3. **Commit, never push.** Regenerate-and-revert test PNGs before committing
   (`git checkout -- region_a_output.png region_b_output.png wealth_stacked.png`).
4. Short sanity runs ~15s (30 turns), full runs ~2-3 min (100 turns).

## Run & verify
```bash
python3 econsim_two_region.py 30     # ~15s; driver + plots + final summary
python3 econsim_two_region.py 300    # ~2-3min; long-horizon behavior
python3 trade_dashboard.py 60        # standalone dashboard
python3 wealth_diagnostic.py 200     # wealth stacked chart + inequality
python3 wealth_lineage.py 200        # intergenerational wealth transfer
python3 sim_ring.py 300              # M0.3: 3-tile ring (A-B-C-A), byte-clean conservation
python3 sim_nation.py 100            # M0.5/M0.6: 3 nations x 2 tiles + tile-map PNG
```
Acceptance checks: **no "COMBINED LEAK" / "SUPPLY SHIFT"** lines; trader ROI positive
on meaningful horizons; dashboard PNGs render. M0 scripts additionally require
**0 per-currency LEAK / 0 SUPPLY SHIFT** for every nation currency every turn
(`sim_nation.py` alerts above the 5.0 audit threshold), and `sim_ring.py` prints
"SUPPLY SHIFT: 0" / "CASH LEAK: 0" / "BANK INSOLVENCY: 0".

## M1 — People: traits, memory, learning (committed 2026-08-11)
- `agent.py` — M1.1 traits (`ambition`, `loyalty`, `charisma`, `risk_tolerance`,
  `bigotry` {group→[0,1]}, `productivity`, `fertility`, `religiousness`) seeded by
  the leaf helper `seed_traits(agent, parent=None)` (heritable `clamp(parent +
  gauss(0,0.15))`; orphans/immigrants uniform-random).  M1.2 identity tags
  (`ethnicity`/`religion`/`politics`) inherit with 2% mutation.  M1.3 bounded
  memory ring buffers via `mem_push/mem_last/mem_avg/mem_recent` (cap 32).
- `econsim_live.py` — `seed_traits(new_agent, parent=agent)` in `_handle_reproduction`;
  `_consume_daily_food` pushes `mem_hunger`; M1.4 `_learned_switch_choice` blends
  bottleneck weights + demand_ratio history + `mem_hunger` + `ambition` into the
  poor-agent career-switch draw.
- `region.py` — `_pay_wages` pushes `mem_wages`; `_migration_intent_score()` /
  `migration_intent_log` is the M1.5 score-only stub (no agents move yet).
- Companies (region.py `_incorporate` + econsim.py `_handle_incorporation`) also
  seed traits so dissolved-company remnants never lose identity.
- Gate: `tmp/behavior_drift.py` — 3-tile ring, 300 turns x 3 seeds,
  0 LEAK / 0 SUPPLY SHIFT / no insolvency, memory ≤ 32, identities present.

## V1 — Pygame hex viewer (committed 2026-08-11)
- `hexmap.py` — pure axial pointy-top hex geometry (`axial_to_pixel`,
  `hex_corners`, `pixel_to_axial` with cube rounding, `hex_distance` /
  `adjacent`) plus `LAYOUT_2X3` mapping the M0 2x3 tile grid onto hex
  coordinates.  Every edge `sim_nation` wires is hex-adjacent (0 non-adjacent
  verified), so hexes share full edges like Civilization with no engine change.
- `hexview.py` — pygame presentation layer (thin, per gdd.md): builds the
  world with `sim_nation.build_world()`, steps the engine turn
  (tiles → routes → `resolve_parked` → `settle_trade` → `fx.cycle_all_markets`
  → PPP desk updates) and audits every nation currency each turn.
  Hexes tint by owner nation; each hex shows name + pop/food price/trader
  count and vector terrain glyphs (wheat/forest/cold).  `Space` play/pause,
  `S`/`→` step, `Esc`/`Q` quit, hover shows a tile tooltip panel
  (nation, regime, legitimacy, treasury, prices, pop, traders, migration
  intent).  Run: `python3 hexview.py`.
- Verified: `tmp/probe_hex.py` (adjacency + pixel↔axial round-trip + SDL-dummy
  render after 10 steps with 0 violations); M1 gate + `sim_nation 100` still clean.
- **V2 (committed separately: V2a `e5e0a6f`, V2b `84f8d19`, V2c `09a0bd2`)**
  — hover chart dashboard (6 live mini-charts per hex: prices, pop/hunger,
  production, trade flow, gov income, gini/migration; Tab grid / 1-6 zoom),
  on-map economic indicators (animated trade-flow arrows scaled by
  export/import value, population-heat fill, activity badges: demand alert,
  hunger, trader count, gini dot, migration arrow, hot/cold food-price
  arbitrage ring, +B/-D pop deltas), and an `N`-toggle national HUD strip
  (per-nation treasury sparkline + export/import bars + regime/legitimacy).
  All drawn in pure pygame; probe renders map + charts + HUD headlessly.
- **V2e (committed `help-menu`)**: `H`/`?` toggles a full-screen help overlay
  explaining every keyboard control and every map/panel/HUD element, with
  Up/Down scrolling and Esc-to-close.
- **NOTE (interpreter)**: `hexview.py` must be run with the project venv that
  has pygame+matplotlib: `source venv/bin/activate` (or
  `/Users/sli/Code/venv/bin/python hexview.py`).  The system `python3` (3.14)
  lacks pygame, so the viewer would silently show only sim logs.

## M2 — Factions & Unrest (2026-08-12; committed through face804, fixes pending)
- `faction.py` — leaf-level `Demand`/`Faction`/`FactionSystem` (no sim imports):
  overlapping membership by agent id, ranked policy demands, source-keyed
  grievances (hunger/tax/gini/unemployment/repression), live `compute_support`,
  per-turn `decay_grievances`.
- `region.py` wiring — per-tile identity factions built from M1 tags
  (ethnicity Yor/Kest/Veln/Omar, religion Sol/Luna/Terra, politics
  Conservative/Liberal/Populist); `_apply_policy_satisfaction` maps Government
  knobs (tax_rate, UBI, import_tariff, immigration) to each faction's demand
  `satisfied`; `_step_factions` refreshes membership from live tags, logs
  `faction_support_log`, accumulates grievances from tile distress + M1
  `mem_hunger`/`mem_wages` and (M2.6) `mem_casualties`/`mem_promises` trauma,
  and appends rate-driven `protest_energy_log`.
- `unrest.py` — `step_unrest(region, t)` escalation ladder with thresholds
  (UNREST 2.0 / PROTEST 4.0 / MOB 6.5 / COMPROMISE 8.0 / TAKEOVER 9.5);
  mob loot/burn, forced compromise (flips the largest faction's top demand +
  legitimacy −0.1), popular-front takeover (legitimacy 0 + regime flip); all
  effects are conserved transfers.  `apply_repression(cost_legitimacy)` —
  quells fresh grievance × 0.6 and seeds `mem_casualties`/`mem_promises`
  (delayed future grievance via `_accumulate_grievances`).
- Runs in `Region.step` after `_step_factions`, before `gov.seal_income`.
- **Conservation fix #1 (`region.py` `_buy`)**: `a.cash = max(0.0, a.cash - cash)`
  erased pre-existing negative cash (debt) when `bought==0` — a mint.  Cash now
  moves only when `bought > 0`; debt is serviced by loan/wage flows.
- **Conservation fix #2 (`econsim_trade_money.py` `PayDepositInterest`)**:
  payout funded out of bank `capital` (not deposits) and capped to
  `min(loan_interest*0.6, max(0, capital))`, so `total_deposits` stays in
  lockstep with the per-agent dict.
- **Conservation fix #3 (`econsim_live.py` / `econsim_trade_money.py`)**:
  heirless bad-debt forgiveness previously wrote down only `total_deposits`
  (scalar), never the per-agent deposit dict — the scalar drained negative
  (~−299 at ring seed-1337 T=293).  `_forgive_bad_debt` now absorbs the loss
  in strict seniority order — bank `capital` first, then the per-agent dict
  pro-rata (floored per depositor), then tile-treasury `_recapitalize` — and
  `RequestBailout` keeps the gov's dict entry in sync.  M1 gate (3 seeds ×
  300t) now PASSES.
- **Resolved (bank capital, not a mint)**: `sim_nation 100` previously aborted
  at T=74 with a genuinely insolvent tile bank (deposit pool $1.43, gov $0,
  shortfall $116.92).  Now the bank has a real capital tier: `Bank.capital`
  (explicit shareholder equity, seeded 2000 — the old phantom 2000-base moved
  out of `total_deposits`), loan interest accrues to `capital`, deposit interest
  is paid out of `capital`, and `Bank.equity = capital + total_deposits −
  total_liabilities`.  Heirless bad debt is absorbed in seniority order
  (shareholders → depositors pro-rata → tile treasury via `_recapitalize`).
   Verified: sim_nation 100 / sim_ring 300 / M1 gate / probe_m2 / probe_hex all PASS.

## M3 — Regimes: elections, coups, continuity (committed; never push)
- `election.py` — leaf-level `Candidate` (`eq=False`, identity-hashed) + election
  mechanics.  `generate_candidates(nation, t)` builds one candidate per faction
  (highest-charisma adult member) with a platform from that faction's demands.
  `campaign_finance(nation, cand, amount)` transfers tile-treasury cash → candidate
  cash (conserved; both counted in `audit_currency_total`) and accrues popularity at
  a charisma-diluted rate (`CHARISMA_DILUTION_FLOOR` + (1−floor)·charisma).  `run_election`
  records `nation._incumbent_faction` for betrayal memory.
- `faction_weighted_vote` — adult (age>20) voters support their most-influential
  faction's candidate; if that candidate is the incumbent AND the voter's
  `mem_promises` mean > 0.5, the voter **defects to the strongest rival**, which is
  what flips election outcomes (M3.3 acceptance).
- `coup.py` — `find_generals` scores adults by ambition/charisma/loyalty; `coup_chance`
  fires below `COUP_LEGITIMACY_TRIGGER` (scaled by the top general + legitimacy
  shortfall); `execute_coup` seizes tile-treasury cash → the general (conserved),
  flips regime to autocracy, purges the deposed faction via `mem_casualties` /
  `mem_promises` seeds (memory only, no wealth destruction).
- `regime.py` — `step_regime(nation, t)` is the per-turn orchestrator: coup check →
  `track_legitimacy` (legitimacy drifts toward population faction support) → election
  cadence (democracies every `ELECTION_INTERVAL`, snap on `SNAP_ELECTION_LEGITIMACY`).
  `apply_platform` flips only the conserved tax knob; UBI/tariff/immigration stay at
  defaults (their money paths are not yet conservation-validated).  `agitate` /
  `unrest_intent` are the M3.6 engine-only opposition-continuity intents.
- `nation.py` — M3 state: `ruling_faction`, `opposition` (with per-faction
  `is_opposition` flag), `_incumbent_faction`, and `regime_log` (the per-turn
  election/coup money-trail archive).
- **Conservation fix (immigration mint)**: `Government.spawn_immigrants(t, agents)`
  no longer mints $50–80 unsourced cash.  Immigrants are chain-migrants derived from
  an existing adult citizen — the parent splits off a bounded cash share + a food
  grant and the child inherits traits/identity, so **every agent traces to another
  agent** and no money/goods are created.
- **Gate** `tmp/probe_m3.py`: scripted election (campaign $100k, leak $0) + betrayal
  flip (Yoro→Terra) + scripted coup (seize conserved, regime→autocracy) — 0 LEAK /
  SHIFT / INSOLVENCY.  Full suite (sim_nation 100, sim_ring 300, M1 gate, probe_m2,
  probe_hex) passes.

## Architecture
- `region.py` — `Region`: per-region bank, Government, agents, logs; `step(t)` orders
  labour → produce → trade (priced auction `_clear_discriminatory`) → wages → profits →
  `_collect_tax` (deficit-capped) → `_live` (lifecycle) → charity → `_log_metrics` →
  `gov.seal_income(t)` (income snapshot per turn).
- `government.py` — `Government`: config toggles (tax, tariff, drawback, probate fee,
  population policy), `income_log` decomposition (`tax`/`tariff`/`inheritance` per turn).
- `econsim_live.py` — life/death/reproduction/inheritance. **Key**: `_living_descendants_recursive`
  (per-stirpes BFS) used by death/company inheritance; family trust funds at birth
  (surplus above liquidity floor → child cash); inherited mortality bridge
  `_birth_protection_until` with **fade clamped to [0,1]**.
- `nation.py` — `Nation` (M0.1): owns one or more tiles (Regions), treasury(), the
  **currency seam** (each Nation has its own home currency; same-nation tiles share it),
  regime_type (autocracy/oligarchy/democracy), and tile-graph ops
  (add/remove/claim/transfer/_reparent_tile).
- `forex.py` / `transporter.py` — FX desks + structural cargo routes. Multi-neighbor
  (M0.3): each Region holds `forex_desks[name]` and `routes[name]`, one per neighbor pair;
  `connect_desks` / `cycle_all_markets` cycle every desk; `Route` carries a `location`
  field, `delivered_this_turn`, and `reclaim(trader)` (returns pending/in-transit cargo).
- `world_trade.py` — helper seam M0.3+ uses (`desk_for`, `route_for`, `pending_imports`,
  `settle_trade`); `settle_trade(t, dest, src)` posts leftover foreign currency as ASKs.
- `trade_dashboard.py` — 4×3 dashboard (net exports by good, FX, reserves, supply-chain,
  gov income decomposition). `wealth_diagnostic.py` / `wealth_lineage.py` — diagnostics
  (Gov slice = cash + deposits + food_reserve × price).
- `sim_ring.py` / `sim_nation.py` — M0 driver harnesses (3-tile ring; 3 nations × 2 tiles
  wired cross-nation only, intra-nation deferred to the currency-union milestone).

## Key invariants / gotchas
- Tariff in `_clear_discriminatory`: `gov_share = tariff × (1 − drawback)`, rebate back to
  seller wallet. `gov.receive_tariff()` logs only the gov share.
- Heirless estates: 30% probate to gov, 70% to regional Charity (`LiveContext.charity`).
- `bank.total_deposits` now stays in lockstep with the per-agent dict (the old
  scalar/dict divergence is fixed); bank net worth is `bank.equity` =
  `capital + total_deposits − total_liabilities`.
- **FX conservation (M0.5 audit, commit `f222b71`)** — `fx.audit_currency_total(regions, currency)`
  sums home-tile cash + bank equity (`bank.equity`) + fx_pool + charity cash +
  all agents' FX wallets + all banks' foreign reserves. Two leaks were found and fixed:
  - **Negative `Loan.pay`** (`econsim_trade_money.py`): an overdrawn agent made the
    "payment" negative; `min(interest, negative)` destroyed bank deposits with no cash
    transfer (leak ~−0.379/turn). Fixed: `Loan.pay` / `PayLoans` reject `amount <= 0`.
  - **Corpse-sale to invisible wallet** (`region._clear_discriminatory` + `econsim_live`):
    a trader that died mid-turn left cargo in the destination import pool; the sale
    credited its cleared corpse wallet, outside every region's living-agents list
    (one-shot leak −982.33). Fixed: `Route.reclaim(trader)` at death
    (`LiveContext.source_region`) + destination-government escheat for dead sellers.
  - Guard: `sim_nation.py` audits every nation currency every turn with a **5.0 alert
    threshold**; sub-dollar FP round-off is absorbed by the bank's bad-debt ledger.
- Gov deposits are only credited via the direct `bank.deposits[gov]` dict-transfer in
  heirless probate; `bid_food`/loan service always use hand cash first, so gov deposits
  sit idle (gov looks rich only on paper).
- Wealth-mortality discount: `wealth_factor = (COL/wealth)²`; the inherited-bridge fade
  must stay clamped — an unclamped fade on >50-turn bridges inverts protection.
- `set_ylim(bottom=...)` must come AFTER plot calls (autoscale freeze bug).

## Diagnostics in tmp/
- `tmp/gov_deposit_heirless.py` — gov Withdraw/Deposit tally + heirless fraction.
- `tmp/heirless_bucket.py` — death bucketing by wealth/profession, direct vs recursive
  descendants, deposit-ledger vs interest.
- `tmp/verify_gov_wealth.py` — ledger invariant + gov wealth breakdown.
- `tmp/fx_p2_audit_core.py`, `tmp/probe_ga*.py`, `tmp/probe_be*.py` — M0.5 audit
  instrumentation (phase-bisect / event-ledger / per-helper probes; untracked debug).
