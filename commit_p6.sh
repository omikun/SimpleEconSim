#!/bin/bash
# Phase 6 commit — writes everything to /tmp/p6_commit.log
exec > /tmp/p6_commit.log 2>&1
set -x
cd /Users/sli/Code || exit 1

echo "=== git status before ==="
git status --short | head -30

# Revert regenerated PNG artifacts
git checkout -- region_a_output.png region_b_output.png wealth_stacked.png 2>/dev/null

git add region.py econsim_two_region.py forex.py

echo "=== git status after stage ==="
git status --short | head -30

git commit -m "Phase 6: trader-economics fixes — imports now clear, FX damped, ROI positive

Root cause of Phase 5's negative trader ROI: trader.cost_get() was never
recorded when traders bought export goods (the legacy _buy path did, the
priced-book path didn't), so _import_ask_price degenerated to the
DESTINATION price -> imports never cleared -> revenue ~0 -> forced exits.

Import-margin economics:
- _clear_discriminatory: weight-averaged cost basis for trader buyers so
  exports carry TRUE source cost + margin at the destination
- _import_ask_price: ask = source cost x (1+margin) / ((1-tariff) x
  repatriate_rate), capped at ~5% over the destination market so reasonably
  cheap lots clear in round 1 instead of parking working capital
- _calculate_bid: FX-adjusted parity gate (dest_price x home buy rate >
  local price x (1+margin)) — no more phantom arbitrage that conversion erases

FX:
- update(): log-space BOUNDED step (the old multiplicative update compounded
  past the band once a desk drained) + slow PPP anchor (0.5%/turn toward
  partner/home basket-cost ratio); update() accepts ppp_target from the main
  loop's update_exchange_rate
- DESK_BAND widened (0.5,2.0)->(0.4,2.5): sustained flow pinned both desks
  at the ceiling; more room lets the float express competitiveness

Trader economics:
- 110 agents/region restored (two-region had been thinned to 55)
- exit benchmark: revenue must cover col + 2%/turn on capital committed in
  goods (export + in-transit + foreign-side) — unprofitable arbitrageurs
  are evicted instead of diluting ROI
- ROI summary: wealth = cash + deposits + foreign wallet @ buy rate;
  prints the cash/deposit/wallet split so tuning is measurable

Validation (100 turns, 110 agents/region):
- 0 SUPPLY SHIFT / 0 COMBINED LEAK on 30- and 100-turn runs, fx_conserv_test
  all green
- Trader ROI positive on BOTH sides: A +363%, B +127% (was -99.5%/-53.2%)
- Trade flowing strongly both ways (952/1581 units)
- FX stable: reserves 1835/1656 (B at widened 2.5 ceiling reflects a
  structurally weaker A currency, not a machinery failure)
- Forest-fire shock: price rises within 4 turns, inventory drained -171 vs
  baseline -1091 (6.4x preservation), 0 conservation violations"

echo "=== git log after ==="
git log --oneline -6

echo "=== git status after ==="
git status --short | head -20

echo "DONE"