#!/bin/bash
# Phase 4 commit — writes everything to /tmp/p4_commit.log
exec > /tmp/p4_commit.log 2>&1
set -x
cd /Users/sli/Code || exit 1

echo "=== git status before ==="
git status --short | head -20

# Revert regenerated PNG artifacts
git checkout -- region_a_output.png region_b_output.png wealth_stacked.png 2>/dev/null

git add region.py econsim_two_region.py

echo "=== git status after stage ==="
git status --short | head -20

git commit -m "Phase 4: imports compete in the destination's round-1 auction

- Main loop computes pending import pools per destination from source
  traders' arrived inventory_foreign before each step
- Region._trade folds import asks into the round-1 auction supply (price
  discovery + clearing) so imports can genuinely displace local goods;
  locals sell first, imports absorb residual demand, crediting source
  traders in destination-currency wallets (conservation-safe)
- inventory_foreign decremented for auction sales; foreign_sell only sells
  the leftover; trade-balance logs include auction-sold amounts

Conservation: buyers pay dest cash; locals get cash; import owners get
dest-currency wallets — all counted in the per-currency audit.  Verified
0 SUPPLY SHIFT / 0 COMBINED LEAK on 30- and 100-turn runs (5.7s); total
trade roughly doubled vs Phase 3 as imports now really compete."

echo "=== git log after ==="
git log --oneline -4

echo "=== git status after ==="
git status --short | head -20

echo "DONE"