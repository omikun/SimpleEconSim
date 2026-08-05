# SimpleEconSim — Task Handoff

Last updated: 2026-08-04 22:23 PDT · HEAD: `01d4fee` (3 local commits ahead of origin/main; nothing pushed)

## Last results (committed)

**Commit chain** (all local, not pushed):
- `c8cdeeb` (origin/main) — Gov income decomposition (tax/tariff/inheritance per-turn logs + dashboard row + summary print)
- `1282645` — Cut tariff & inheritance: tariff 10%→3%, duty drawback 70% refunded to seller, heirless estates 30% probate→gov / 70%→charity
- `59db6e9` — Net-exports dashboard panel broken down by good
- `01d4fee` — Per-stirpes inheritance + family trust funds + gov-wealth chart fix

### Findings from the last investigation
1. **Wealth-stacked "Gov" slice is NOT a chart bug** — it reads `cash + deposits`; the gov is genuinely lean post-P8. The deposit-ledger vs `total_deposits` divergence is the bank's bad-debt forgiveness / retained interest, **not** the gov slice (don't "fix" it unless asked — see agent.md).
2. **Heirless deaths (~59%) are driven by poverty**: ~96% of the 746 deaths were agents with wealth < $20 who died before reproducing. Per-stirpes misclassification (grandparent with living grandkids) was only 13/746 (1.7%).
3. **Fix results (300 turns, seed 42):**
   - Per-stirpes: misclassified heirless deaths 13/746 → 0
   - Inheritance-to-gov cut ~⅔: A $5,947→$2,255 (−62%), B $12,623→$4,135 (−67%)
   - 30-turn trader ROI healthy: A +86%, B +293% (was +160%/+594% pre-trust; bounded trust restored)
   - 0 COMBINED LEAK / 0 SUPPLY SHIFT in all runs

### Key mechanism decisions
- **Family trust funds** (econsim_live `_handle_reproduction`): rich parents (>4× COL) endow newborns from **surplus above a liquidity floor** (trader: 10×COL + 45×food; other: 2×COL), sized 3–5× COL. Bequest-from-total-wealth was tried and **rejected** — it drained trader working capital and evicted all Region_A traders (ROI −27% at 30t). Bounded surplus funding is the correct variant.
- **Inherited mortality bridge** (`_birth_protection_until`): 50–200 turns scaled by trust size. The fade **must stay clamped to [0,1]** — an unclamped fade amplified `wealth_factor` past 1.0 on long bridges and converted protection into extra mortality.
- **Per-stirpes** `_living_descendants_recursive(agent)`: BFS children→grandchildren, used in `_handle_death` (passes list to debt/wealth inheritance) and `_handle_company_inheritance`.

## Status: PASSING
- `python3 econsim_two_region.py 30` — no LEAK/SHIFT, ROI positive both sides
- `python3 econsim_two_region.py 300` — no LEAK/SHIFT; A-trader decline at 300t is **pre-existing structural** (price convergence evicts unprofitable arbitrageurs; P8 baseline showed A at −80% too)
- Both PNGs render; gov income decomposition row present

## Potential follow-ups (not yet requested / open)
1. **Region_A long-horizon trader extinction (300t)** — pre-existing, structural: arbitrage converges so traders become unprofitable and the exit benchmark evicts them. Options if user wants traders to persist: add an import-side margin floor, reduce FX convergence, or relax `_process_trader_exits` benchmark. **Do not "fix" without being asked** — it's intended behavior.
2. **Gov deposits sit idle** — heirs/probate credit `bank.deposits[gov]` directly; `bid_food`/loan service always use hand cash so deposits are never touched. If user wants the gov to actually bank like citizens (use deposits for spending), wire `bid_food`/tax-servicing to withdraw from deposits — currently they only use hand cash (+ deposit withdrawal is supported in `bid_food` but rarely triggers).
3. **Poverty → heirless root cause** — 96% of deaths are poor (<$20). If user wants lower heirless rate, address poverty (food aid/welfare coverage, wage floors, charity distribution rate) rather than inheritance rules.
4. **Deposit-ledger divergence** — documented as bank bad-debt/interest mechanism. Only revisit if user asks about total-deposits accounting or wants per-agent attribution of forgiven debt.
5. **Charity food hoarding** — earlier runs showed charity with hundreds/thousands of food units remaining; `max_food_per_agent=1` and distribution covers ~1/3 of hungry + young only. Potential follow-up: scale distribution to stockpile.
6. **`agent.md` / `task.md`** — update both files when the next session changes behavior or commits.

## Diagnostics (tmp/)
- `tmp/gov_deposit_heirless.py [turns]` — gov bank Withdraw/Deposit tally, heirless fraction
- `tmp/heirless_bucket.py [turns]` — death buckets by wealth/profession, direct vs recursive descendants, ledger vs interest
- `tmp/verify_gov_wealth.py [turns]` — ledger invariant + gov wealth breakdown (cash/deposits/food)