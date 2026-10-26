#!/bin/bash
# Phase 3 commit script — writes everything to /tmp/p3_commit.log
exec > /tmp/p3_commit.log 2>&1
set -x
cd /Users/sli/Code || exit 1

echo "=== git status before ==="
git status --short | head -30

# Revert regenerated PNG artifacts (not part of the code change)
git checkout -- region_a_output.png region_b_output.png wealth_stacked.png

# Stage the 5 source files modified for Phase 3
git add econsim_live.py econsim_trade_money.py econsim_two_region.py forex.py region.py

echo "=== git status after stage ==="
git status --short | head -30

# Commit
git commit -m "Phase 3: interbank order book + fix core conservation leaks

FX:
- ForexDesk order book (post_order/clear_book) matching bids/asks inside
  the band; wallet-to-wallet foreign settlement + home cash trader-to-trader
- fx.cycle_market: posts working-capital bids, clears book cross, desk as
  last resort (fx_pool-capped repatriate + reserve-capped buy), drops stale
  asks so the book can't bloat O(T^2)
- foreign_sell posts trader foreign earnings as asks; repatriation deferred
  to the market cycle
- clear_book matches on actual wallet balances and has a heartbeat guard

Core conservation fixes (pre-existing leaks, unrelated to FX):
- Region._trade: imports inflate supply only for price discovery; local
  market clears against local asks only (killed -178/turn money destruction)
- Region._trade transport clear: pass real buyer cash to _sell so sellers
  are paid (killed -20.56/turn)
- Bank.Borrow returns actual amount lent; _incorporate funds company.cash
  from the real loan (killed phantom +403 money creation)
- econsim_live debt forgiveness: conservation-safe full-R write-down with
  gov bailout first + logwarning, and negative deposits raise a diagnostic
  insolvency error instead of silently destroying money

Validation: fx_conserv_test ALL PASS; 30-turn (3.1s) and 100-turn (5.9s)
with ZERO SUPPLY SHIFT / COMBINED LEAK lines; both FX desks stay funded."

echo "=== git log after ==="
git log --oneline -3

echo "=== git status after ==="
git status --short | head -30

echo "DONE"