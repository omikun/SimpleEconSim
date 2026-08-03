"""Phase 3: fix sim hang — stale-ask book bloat + clear_book heartbeat.

1. Book bloat: foreign_sell posts a NEW ask each turn for the trader's full
   wallet balance.  cycle_market's cleanup keeps ALL unfilled asks, but
   repatriate_traders already drains those wallets to 0 the same turn, so
   stale asks linger forever -> book grows O(traders/turn) -> O(T^2) work.

   Fix: at cleanup, drop any ask whose trader's actual wallet balance is 0.

2. clear_book heartbeat: a successful match should always advance at least
   one pointer (b/a qty or asker balance hits 0), but add a defensive
   iteration cap so a pathological pair can never deadlock the loop.
"""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

# ---- 1. cycle_market cleanup: drop stale asks (trader wallet drained) ----
old = """        # Drop fully-filled bids; leave unfilled asks for next turn
        desk.book = [o for o in desk.book
                     if o['qty'] > 0 and o['kind'] == 'ask']"""
new = """        # Drop fully-filled bids and STALE asks (trader's wallet was drained
        # by repatriation this same turn, so those asks can never fill).
        # Without this, foreign_sell stacks a fresh ask per turn and the book
        # grows without bound -> O(T^2) hang.
        desk.book = [o for o in desk.book
                     if o['qty'] > 0 and o['kind'] == 'ask'
                     and fx_balance(o['trader'], other) > 0]"""
assert old in src, "cleanup-anchor"
src = src.replace(old, new)

# ---- 2. clear_book heartbeat guard ----
old = """        i = j = 0
        while i < len(bids) and j < len(asks):"""
new = """        i = j = 0
        _heartbeat = len(bids) + len(asks) + 1  # defensive: every iteration
        # must advance at least one pointer; cap anyway to avoid deadlock
        while i < len(bids) and j < len(asks) and _heartbeat > 0:
            _heartbeat -= 1"""
assert old in src, "heartbeat-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("hang fix applied: stale-ask cleanup + clear_book heartbeat")