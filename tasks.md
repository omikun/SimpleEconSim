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

---

# v3_wilderness — PLAN (parked; do NOT implement yet)

Goal: 10×8 (80-tile) "wilderness" map — 3 nations with 2–3 owned tiles (100
agents/tile), the rest unclaimed frontier homesteaded by migrating agents, with
trade, claims, and a turn ticker.  Decisions locked in with the user below;
no code has been written for this section yet.

## Locked-in rulings (user decisions, 2026-08-13)

- **Headless first.** Implement `sim_world.py` + engines and validate with a
  probe BEFORE touching the pygame viewer.
- **Wilderness pop is a scalar, not agents.** Each unclaimed tile gets a
  random `wilderness_pop` in 0–50 at world build.  No agent objects are
  spawned for these "natives"; they never tick (no births/deaths/consumption/
  production) and exist ONLY as a pop-count denominator for the claim rule.
- **Unclaimed tiles are currency-less.** `home_currency = None`, no bank, no
  government, no charity, no factions, no tariffs.  Subsistence-only.
- **Homesteaders carry their money in their wallet.** On migrating to an
  unclaimed tile, `agent.cash` moves into `agent.wallets[agent.home_currency]`
  so the per-currency audit (`audit_currency_total` sums all agents' FX
  wallets regardless of residence) stays leak-free.  On unclaimed tiles,
  agents hold only wallet money.
- **origin_nation is set once and NEVER updated.** `origin_nation` is the
  persistent homeland: inherited from the parent at birth (else seeded from
  the birth tile's nation).  It does not change when an agent moves.
  Citizenship (`government._add_citizen`) is what changes on move.  The
  claim rule counts `origin_nation == X` — if we kept re-pointing origin on
  every move, the fraction would trivially be 100% and claims would be
  meaningless.  This is the point of keeping it stable.
- **Traders are a no-interest wilderness bank.** A trader sells goods to
  homesteaders ALWAYS at `(market price + transport) × 1.20`, credited to the
  homesteader's wallet in the trader's home currency (homesteader "owes").
  The trader collects the homesteader's outputs; each leg is a real
  inventory/cash transfer — nothing is created.  It tracks the differential
  (value of goods collected minus value of goods loaned), and when positive
  pays HALF the differential to the homesteader at market rate in the
  trader's home currency.
- **Foreign homesteaders are NOT skipped.** Wallets are multi-currency;
  homesteaders never pay cash — they only receive money from traders when
  they have surplus.  No FX conversion ever happens.
- **Two-resource rule dropped.** Only `food` and `wood` exist, so no
  profession/resource gating is needed beyond homesteading-is-universal.

## Mechanism spec

1. **Model foundation**
   - `Agent.origin_nation` (persistent homeland; seed at birth; never update).
   - `agent.is_homesteader` flag.
   - `Region.unclaimed` / `Region.wilderness_pop` (scalar) fields; unclaimed
     tiles get `home_currency=None` + no bank/gov/charity/factions.
   - Wallet portability helper: move `cash` → `wallets[home_currency]` when
     entering an unclaimed tile (reversable on claim).

2. **`sim_world.py` (new)** — 10×8 world builder
   - 3 nations × 2–3 random claimed tiles, 100 agents each (normal seeding).
   - Remaining 62± tiles unclaimed; `wilderness_pop = randint(0, 50)`.
   - Wire adjacency (rectangular/grid neighboring) + trader routes owned →
     owned and owned → adjacent unclaimed tiles.

3. **`migration.py` (new)**
   - Real movement (M1.5 was score-only): on per-tile immigration pressure
     threshold, move a bounded number of agents to the best adjacent tile.
   - Conserved: cash → wallet, inventory moves with the agent; cooldown to
     avoid ping-pong; on landing unclaimed → `is_homesteader=True`.

4. **Homesteading**
   - `is_homesteader` agents on unclaimed tiles forage `+1 food` every 3
     turns; must be LOGGED (production_log or a homestead ledger) else GDP
     and the supply audit drift.

5. **Trader wilderness settlement (extend transporter/world_trade)**
   - `settle_wilderness(trader, tile, t)`: sell at `(price+transport)×1.20`
     (wallet credit in trader currency); collect homesteader outputs; track
     per-(trader, tile) value differential; when collected > loaned, pay
     `0.5 × diff` at market rate to the homesteader's wallet.  All legs are
     transfers — no mint.

6. **`claims.py` (new)** — each turn, for each unclaimed tile:
   - `pop = homesteader_agents_count + wilderness_pop` (natives count).
   - If `pop > 0` and `max_X count(origin_nation==X) / pop ≥ 0.5`: X claims.
   - On claim: `home_currency = X.currency`; convert X-origin homesteaders'
     wallets back into hand cash/deposits (others stay foreign wallets);
     build bank/gov/charity/factions normally; append to `nation.claim_log`.

7. **Ticker (viewer later)**
   - `nation.claim_log` + migration events; render a scrolling strip.

8. **Generalize `hexmap` / `hexview` (LAST, after engines green)**
   - Dynamic axial layout for 10×8; dynamic `NATION_COLORS`; camera/scroll;
     top bar already follows `_selected_nation` (keep 3-nation defaults for
     the 6-tile legacy layout — parameterize by world).
   - Pinned-panel + top bar need `home_currency=None` -> "Unclaimed" handling.

### v3 file layout (new features in new files)
- **wilderness.py** (NEW) — ALL unclaimed-tile behavior: FORAGE_INTERVAL,
  enter_wilderness (walletize cash + is_homesteader=True), enter_claimed
  (de-cash + homesteader status LOST), forage, step_wilderness.  region.py
  only holds construction flags + a one-line step() delegate.
- **migration.py** (NEW, later) — real conserved movement.
- **claims.py** (NEW, later) — 50% rule + currency backfill + claim_log.
- Trader wilderness settlement gets its own module later.

### New locked rulings (2026-08-14)
- **Foraging ONLY on unclaimed tiles.** Homesteaders forage +1 food / 3
  turns ONLY while on an unclaimed tile; claimed tiles never forage.
- **Homesteader status is lost on claimed tiles.** A homesteader who moves
  to any claimed tile immediately clears is_homesteader + homestead_since.

## Order of work (correctness first)

1. Model foundation: `origin_nation` + `is_homesteader` + wallet portability +
   unclaimed-tile fields (audit-safe by construction).
2. `sim_world.py` 10×8 builder (headless).
3. `migration.py` + homestead foraging.
4. Trader wilderness settlement.
5. `claims.py` + claim_log.
6. Probe: 0 LEAK / 0 SUPPLY SHIFT across all nation currencies; claims fire;
   migration happens; trader settlement conserved.  Perf smoke: 80 tiles.
7. Generalize `hexmap`/`hexview` + ticker.
8. Docs (agent.md / task.md / tasks.md / priority_tasks.md) + commit (no push).

## Risks still to validate
- `audit_currency_total` on `home_currency=None` tiles must skip them for home
  sums (wallets already counted globally).
- Trader wallet denom: every sell is in trader currency — multi-currency
  wallets must never reconcile to a single currency.
- Claim-time wallet→cash conversion must be reversed exactly on claim.
- Perf: 80 `Region.step()` per turn ≈ 13× current cost; cython only speeds
  production — smoke test early and consider stepping only "active" tiles
  (owned or homesteader-populated).

### New locked ruling (2026-08-14, v3)
- **Only the poor homestead.** Company owners (founder/owner of a corporation)
  and wealthy agents (`wealth() > 60`) NEVER become homesteaders — only the
  poor go the homesteader route.  They may still migrate between CLAIMED tiles.

### v3 residual (tracked)
- Long 120-turn runs still show occasional rare GA/BE/BE offsets (e.g.
  T=54 GA -41).  Root class: RNG-dependent cross-tile birth/death events strand
  hand cash on wilderness agents (ghost-cash).  Harden by enforcing "wilderness
  agents never hold hand cash" centrally in enter_wilderness.

## v3 progress checkpoint (2026-08-16) — CONTINUE HERE (conservation fixes landed)

### Done in this session (all local, uncommitted since b9c9ee7)
- Model foundation: Agent.origin_nation (set once, never re-pointed) + is_homesteader/homestead_since/last_forage_turn/last_migration_turn; cash portability via fx.walletize/decash_wallet.
- region.py narrowed: wilderness construction (no bank/gov/charity/factions, EMPTY start); step() delegates to wilderness.step_wilderness.
- wilderness.py: forage (1 food/3 turns, wild only), enter_wilderness (walletize + flag), enter_claimed (homestead status LOST + de-cash), step_wilderness (logged).
- sim_world.py: 10x8 builder (3 nations x 2-3 tiles, 100 agents/tile; 72 wilderness tiles, wilderness_pop 0-50), full adjacency, ForexDesks only between claimed; loop = pending->step->routes->parked->settle(claimed)->FX->migrate->settle_wilderness->regime->PPP->audit.
- migration.py: real conserved move (pressure>=0.2, max 3/tile, cooldown 20); homesteading ONLY for poor (owners/wealth>60 never wild); origin-tile currency walletized BEFORE wilderness entry (ghost-safe).
- trade_settle.py: no-interest wilderness bank, sell (price+transport)*1.20 funded from trader cash, collect outputs, half-diff paid from trader cash; settlement_log.
- world_trade.settle_trade: wilderness destinations skipped (None-currency leak); commerce pairs claimed-only.
- ledger.py: heirless-no-state cash/wallet/deposit destruction RECORDED; sim_world alarm EXEMPTS recorded destruction + prints DESTROY lines; goods-at-sea accounted-tolerated (future cargo milestone).
- econsim_live: cross-tile heir/owner payouts walletized; heirless-no-state records.

### Verified state (2026-08-16 rerun on current tree)
- **claims.py now FIRES end-to-end** — the old "no claims" world120*.out files were stale
  (pre-claims).  40-turn gate: Gamma r0c7 (T=24), Alpha r4c5/r3c1/r2c0, Beta r1c2/r4c1...
- **Fix A (claims.py)**: fresh-claim Government agent is now appended to tile.agents with
  region/_bank_ref/home_currency wired (region._create_agents does this for normal tiles).
  Without it, every $ the new gov collects (taxes/probate/import-escheat) left the audit =
  the step-phase GA sink (-84.18 -> -0.02 at T=34).
- **Fix B (claims.py)**: frontier banks get a conserved founding charter — residents pool
  5% of their just-de-cashed cash (capped $10) into bank.capital.  Kills the zero-capital
  instant-insolvency.
- **Fix C (econsim_live._handle_debt_inheritance)**: debt groups by issuing bank (loan.bank),
  not ctx.bank — a homesteader dying at a frontier tile was writing total_liabilities down
  for another bank's loans (-$216 phantom at T=55).
- **Fix D (econsim_live._forgive_bad_debt)**: genuine-failure tier — after shareholders/
  depositors/treasury, the shortfall writes capital negative (conserved; caller already
  removed the loan from liabilities; audit sees negative equity).  No more RuntimeError abort.
- Regression suite STILL GREEN: sim_nation 100 / sim_ring 300 / behavior_drift / probe_m2 /
  probe_hex all PASS.
- world120 now RUNS to T=119+ (was T=55 crash) but REMAINING cross-currency shifts
  (mostly BE+/GA- pairs ~$5-65: T=60, 70-78, 81-91) and one T=91 $65 swing are UNRESOLVED.

### PARTIAL FIX (2026-08-16) — death-path cross-currency settlement
Phase-bisect probes (tmp/dbg_bega_shifts.py, tmp/dbg_stepper_tile.py,
tmp/dbg_subphase2.py, tmp/dbg_live_fine.py, tmp/dbg_death_sub.py) traced the
AL-/BE+ SUPPLY SHIFTs to the DEATH path:

1. **Foreign-bank loans paid from death-tile cash** (T=60 AL -12.48 / BE
   +11.97).  `Loan.pay()` credits the ISSUING bank (audited under its tile's
   currency), but `_handle_debt_inheritance` funded it from the death-tile's
   ctx.bank cash.  Fix: foreign loans settle FIRST from the agent's FX wallet
   in the loan bank's currency; same-tile cash now services only ctx.bank
   loans; the rest flows to per-bank split/forgive at the ISSUING bank.
   Result: T=60 now AL -0.01 / BE -0.13 / GA +0.14.
2. **Wealth-inheritance denomination**: bequests now pay out in the RESIDENCE
   tile's currency (what the audit counts), not the corpse's attribute.
3. **Newborn home_currency**: child inherits the RESIDENCE tile currency first.

Legacy regression GREEN: sim_nation 100 / sim_ring 300 / behavior_drift PASS.

### Still open (resume here)
1. **Late-run BE-/GA+ second class** (T=77-90, ~6-14/turn: T=85 r1c8 BE -11.19
   / GA +11.19, T=89 BE -11.04 / GA +13.87).  Per-tile attribution points at
   the frontier-bank bad-debt / burial path: `_forgive_bad_debt` + per-bank
   loan inheritance writing non-issuing banks' ledgers.  Phase-bisect T=85
   r1c8 with a loan-bank == ctx.bank sanity dump, then route forgiveness
   strictly by `loan.bank`.
2. Re-run 40/120 gate to 0 unaccounted once the GA+ class is fixed.
3. Perf smoke (80 tiles) + generalize hexmap/hexview + ticker (migrate/claims/
   DESTROY events).
4. Docs (agent.md/task.md/tasks.md/priority_tasks.md) + commit (no push) once
   gate green.

---

## DONE — Region Modular Refactor
Extracted monolithic `region.py` (2,768 lines) into clean, single-responsibility sub-modules while preserving 100% backward compatibility and exact conservation invariants:
- `region_plotting.py`: Matplotlib subplot rendering (`plot_region`, `smooth`, 19 subplot functions); eliminates heavy matplotlib overhead from headless runs.
- `region_factions.py`: Identity faction registration, policy satisfaction, grievance accumulation, and protest energy calculation (`step_factions`).
- `region_labor.py`: Labor market cleanup, firm incorporation, worker hiring/poaching, layoffs, dynamic wage adjustments (`run_labour`).
- `region_production.py`: Corporation synergies, active slot execution with Cython acceleration fallback, independent crafting, and terrain bonuses (`produce`).
- `region_finance.py`: Corporate wage payouts, dividend profit sharing, cross-currency owner bailouts, deficit-balanced progressive taxation (`distribute_profits`, `collect_tax`).
- `region_logistics.py`: Multi-neighbor route management, trader arbitrage repointing, export posting, migration intent scoring, and trader exit/liquidation (`repoint_traders`, `exit_trader`, `process_trader_exits`).
- `region_market.py`: 2-phase discriminatory pay-as-bid double auction clearing, price reference & supply scarcity updating, liquidity deposits/borrows, import pools, and transport bids (`trade`).
- `region.py`: Slimmed down to an orchestrator class delegating to sub-modules with backward-compatible method aliases.

### Verification
- `sim_world.py 80`: PASS (80 turns across 81 hex tiles, clean execution).
- `sim_ring.py 100`: PASS (100 turns, 3-region ring, 0 errors).
- `sim_nation.py 50`: PASS (50 turns, 3 nations x 2 tiles, 0 errors).
- `econsim_two_region.py 30`: PASS (30 turns, wealth diagnostics & trade balance clean).

---

## DONE — Worldview Modular Refactor
Extracted monolithic `worldview.py` (1,159 lines) into clean, extensible sub-modules while preserving 100% backward compatibility and test verification with `tmp/probe_worldview.py`:
- `worldview_camera.py`: Viewport bounds clamping, axial-to-screen projection with pan/zoom, screen-to-axial hex tile picking (`clamp_cam`, `hex_px`, `tile_at`).
- `worldview_charts.py`: Pygame time-series chart rendering (polylines, paired bar charts, stacked bar charts) and 2x3 grid / large zoom dashboard layouts (`tile_charts`, `draw_chart_grid`, `draw_chart_large`).
- `worldview_map.py`: Hex polygons, terrain glyphs, population heatmap, trade animation arrows, activity badges, population delta tags, and province highlight grouping (`draw_hex_map`).
- `worldview_ui.py`: Civ-style top stats bar, right panel with currency audit readouts, regime status, event ticker feed, and controls help modal (`draw_top_bar`, `draw_panel`, `draw_ticker`, `draw_help`).
- `worldview_engine.py`: 81-hex world state initialization, simulation turn step runner, and event ticker queue management (`build_world_view`, `step_world`).
- `worldview.py`: Slim orchestrator, frame renderer, event loop, and public exports.

### Verification
- `tmp/probe_worldview.py`: PASS (5/5 checks: adjacency, pixel roundtrip, nation contiguity, headless dummy render, ticker events).
- `sim_world.py 40`: PASS (40 turns, 81 hex tiles, clean execution).

---

## DONE — System-Wide Modular Pipeline & Extensibility Refactor
Consolidated duplicate simulation loops, decomposed the 1,225-line demographic monolith, unified wealth diagnostics, and consolidated viewers:
- `sim_engine.py`: Canonical, multi-level simulation engine implementing the 12-phase pipeline (inter-tile logistics, trade settlement, forex cycle, migration, claims, national regimes, and audits). Unifies `sim_world.py`, `sim_nation.py`, `sim_ring.py`, and `worldview_engine.py`.
- `demographics_consumption.py`: Daily food consumption, luxury goods intake, and bottleneck analysis.
- `demographics_career.py`: M1 memory-driven career switches, apprenticeship subsidies, and job matching.
- `demographics_reproduction.py`: Agent births, fertility scaling, and heritable traits.
- `demographics_estate.py`: Mortality, corporate succession, debt resolution, bad debt write-downs, wealth inheritance, and escheat.
- `econsim_live.py`: Slim orchestrator class preserving `LiveContext` and `Live()`.
- `hexview.py`: Refactored to reuse `worldview_*` modules and `sim_engine`, eliminating 800+ lines of duplicate rendering and stepping code.
- `wealth_collector.py`: Unified snapshot recorder for agent wealth, debt, and demographic transitions.

### Verification
- `sim_world.py 80`: PASS (80 turns, 81 hex tiles, 0 leaks).
- `sim_nation.py 50`: PASS (50 turns, 3 nations x 2 tiles, 0 errors).
- `sim_ring.py 100`: PASS (100 turns, 3-region ring, 0 errors).
- `econsim_two_region.py 30`: PASS (30 turns, wealth diagnostics clean).
- `tmp/probe_worldview.py`: PASS (5/5 headless checks).
- `tmp/probe_hex.py`: PASS (3/3 checks).
- `tmp/probe_hex_m3.py`: PASS (0 leaks, legitimacy drift confirmed).

---

# v3_bank_network — PLAN (approved 2026-08-16; DO NOT implement yet)

Goal: per-Nation bank network so a distressed tile bank is rescued by stronger
nation banks + the national government. Every leg is an intra-nation
SAME-CURRENCY transfer, so `audit_currency_total` (sums `bank.equity` across
all banks of that currency) sees no net change. Legacy drivers stay
byte-identical when the master switch is OFF.

## Locked-in rulings (user, 2026-08-16)
1. `Nation.bank_network_enabled` — master switch (default OFF for legacy
   sim_nation/sim_ring; ON for sim_world). When ON it enables BOTH bank-to-bank
   swaps AND the national-government backstop (one switch, per user).
2. `Nation.founder_dividends_enabled` — separate per-nation switch, DEFAULT ON.
3. `Nation.swap_interest_enabled` — separate per-nation switch, DEFAULT ON.

## Spec
1. Registry: `Nation.banks: list[Bank]`; populated in `Nation.add_tile`
   (auto-onboards future claims.py banks); unregister in remove/_reparent.
2. Founder shares: `claims.py` founding charter records `bank.founders[agent]`;
   every DIVIDEND_INTERVAL (10) pay pro-rata dividend from `bank.capital`
   capped to a safety floor (capital down, founder cash up = transfer). Founder
   death: stake inherits per-stirpes else escheats (stake cancelled, funds stay
   in capital). Honors founder_dividends_enabled.
3. Swap: distress = `equity < equity_floor`; contributors = same-nation banks
   above a participation threshold, largest-capital-first, exposure-capped.
   Swap is an inter-bank liability: source `capital -= X`,
   `swap_assets[target] += X`; target `capital += X`,
   `swap_liabilities[source] += X` (audit-flat). Repay principal (+ interest if
   swap_interest_enabled) once recovered above a repayment floor.
4. National backstop (same switch as #3): extend `_recapitalize` to try tile gov
   then sovereign Nation.government; fund via optional federal remittance
   (tile govs remit a fraction of tax/tariff/probate to national gov).
5. Ticker: `Nation.bank_event_log` entries {t, kind: swap|swap_repay|recap|
   bank_failure|dividend, from_bank, to_bank, amount}; wire into sim_world
   world_events archive with MIGRATE/CLAIM/DESTROY.

## Order of work
1 registry -> 2 founder shares+dividend -> 3 swap+interest -> 4 backstop+
remittance -> 5 scripted probe (force distress; audit flat across legs; other
nations untouched) -> 6 sim_world 40/120 network ON 0 SHIFT -> 7 legacy suite
network OFF unchanged -> 8 viewer ticker.

## Risks
- Swap/recap only within one nation's currency. Never cross-nation.
- Dividend must never push capital below the safety floor.
- Exposure cap + seniority prevent one strong bank being drained by many weak.
