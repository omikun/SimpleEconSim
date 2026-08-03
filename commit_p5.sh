#!/bin/bash
# Phase 5 commit — writes everything to /tmp/p5_commit.log
exec > /tmp/p5_commit.log 2>&1
set -x
cd /Users/sli/Code || exit 1

echo "=== git status before ==="
git status --short | head -30

# Revert regenerated PNG artifacts
git checkout -- region_a_output.png region_b_output.png wealth_stacked.png 2>/dev/null

git add region.py econsim_two_region.py forex.py

echo "=== git status after stage ==="
git status --short | head -30

git commit -m "Phase 5: anchored per-agent pay-as-bid priced order book

Every seller quotes their own ask; the cheapest-first book sets the
transaction price per unit (Option C, no uniform single price):

- Locals: ask = sector ref x scarcity_urgency (bounded [0.7,1.8];
  low stock => dear, hungry/full => fire-sale)
- Imports: ask = max(cost, home price now) x (1+margin) / ((1-tariff) x
  buy_rate); margin 5-10%; opportunity-cost floor prevents below-cost sales
- Pay-as-bid clearing (_clear_discriminatory): cheapest-first, each unit
  trades at its own ask; tariff split goes to the destination gov
- Option-1 import channel: foreign_sell no longer dumps at 0.95x; ALL
  imports clear through the round-1 priced book (1-turn settlement lag,
  unsold stock re-offers until bought)

Price reference:
- Bounded move-to-target _update_price_ref (no multiplicative runaway), synced
  to recipes[good].price; adds a regional scarcity signal so supply shocks
  (forest fire) raise price the same round and cash-rationing preserves stock

Also:
- traders keep 5x cost-of-living + 15x goods-price in cash (deposit only
  excess); trader export purchases route to inventory_export
- trader bid gate: pure price-spread test (dest >= local x (1+min margin)),
  no fee/FX double-count
- FX desk reserves raised (init 3000 / target 2500): 100-turn runs had
  drained both desks to 0 and pinned the band ceiling; rates now float

Conservation: 0 SUPPLY SHIFT / 0 COMBINED LEAK on 30- and 100-turn runs;
forest-fire shock test preserves inventory 9x (165 vs 1486 units drained).
fx_conserv_test all green.  Trader ROI at 100 turns is still tuning-negative
(economics parameter pass deferred; machinery is conservation-clean)."

echo "=== git log after ==="
git log --oneline -6

echo "=== git status after ==="
git status --short | head -20

echo "DONE"