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
- Deposit ledger can diverge from `bank.total_deposits` — that's the bank's
  bad-debt forgiveness / retained interest, **not** the gov slice. Don't "fix" unless asked.
- **FX conservation (M0.5 audit, commit `f222b71`)** — `fx.audit_currency_total(regions, currency)`
  sums home-tile cash + bank equity (deposits−liabilities) + fx_pool + charity cash +
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
