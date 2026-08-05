# SimpleEconSim — Agent Guide

Multi-region agent-based economy sim. Money & goods must be **conserved** — no sinks
or free creation (except explicit design decisions, which must be documented).

## Hard rules (from .clinerules)
1. **Never run scripts from inline strings** — always write the file first, then run it.
2. Commit messages go to a file (`tmp/commit_msgN.txt`), commit with `git commit -F <file>`.
3. **Commit, never push.** Regenerate-and-revert test PNGs before committing
   (`git checkout -- region_a_output.png region_b_output.png wealth_stacked.png`).
4. Short sanity runs ~15s (30 turns), full runs ~2-3 min (300 turns).

## Run & verify
```bash
python3 econsim_two_region.py 30     # ~15s; driver + plots + final summary
python3 econsim_two_region.py 300    # ~2-3min; long-horizon behavior
python3 trade_dashboard.py 60        # standalone dashboard
python3 wealth_diagnostic.py 200     # wealth stacked chart + inequality
python3 wealth_lineage.py 200        # intergenerational wealth transfer
```
Acceptance checks: **no "COMBINED LEAK" / "SUPPLY SHIFT"** lines; trader ROI positive
on meaningful horizons; dashboard PNGs render.

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
- `forex.py` / `transporter.py` — FX desks + structural cargo routes.
- `trade_dashboard.py` — 4×3 dashboard (net exports by good, FX, reserves, supply-chain,
  gov income decomposition). `wealth_diagnostic.py` / `wealth_lineage.py` — diagnostics
  (Gov slice = cash + deposits + food_reserve × price).

## Key invariants / gotchas
- Tariff in `_clear_discriminatory`: `gov_share = tariff × (1 − drawback)`, rebate back to
  seller wallet. `gov.receive_tariff()` logs only the gov share.
- Heirless estates: 30% probate to gov, 70% to regional Charity (`LiveContext.charity`).
- Deposit ledger can diverge from `bank.total_deposits` — that's the bank's
  bad-debt forgiveness / retained interest, **not** the gov slice. Don't "fix" unless asked.
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