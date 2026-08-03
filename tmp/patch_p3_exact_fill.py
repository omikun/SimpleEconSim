"""Phase 3: fix clear_book over-transfer — match by ACTUAL wallet balance.

Unfilled asks persist across turns; the trader's wallet can shrink (e.g. food
purchases in destination), so the posted ask qty may exceed the current
balance.  clear_book then credits the bidder the full qty while fx_sub floors
the asker at zero — foreign created from nothing.

Fix: compute actual foreign transferred as (before - after) of fx_sub, and cap
the match qty by the bidder's home cash too, transferring exactly that.
"""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

old = """        while i < len(bids) and j < len(asks):
            b = bids[i]
            a = asks[j]
            if b['rate'] < a['rate']:
                i += 1
                continue  # no cross; move to next bid
            qty = min(b['qty'], a['qty'])
            price = a['rate']  # match at ask rate
            # Bidder pays home cash to asker; foreign transfers wallet-to-wallet
            btrader = b['trader']
            atrader = a['trader']
            home = qty * price
            if btrader.cash < home:
                home = btrader.cash
                qty = home / price if price > 0 else 0.0
            if qty <= 0:
                i += 1
                continue
            # Home leg (both are home-region traders)
            btrader.cash -= home
            atrader.cash += home
            # Foreign leg: asker sells foreign to bidder (wallet-to-wallet)
            fx_sub(atrader, self.other, qty)
            fx_add(btrader, self.other, qty)
            total_home += home
            b['qty'] -= qty
            a['qty'] -= qty
            if a['qty'] <= 0:
                j += 1
            if b['qty'] <= 0:
                i += 1"""
new = """        while i < len(bids) and j < len(asks):
            b = bids[i]
            a = asks[j]
            if b['rate'] < a['rate']:
                i += 1
                continue  # no cross; move to next bid
            price = a['rate']  # match at ask rate
            btrader = b['trader']
            atrader = a['trader']
            # Cap the match by the asker's ACTUAL wallet balance (the posted
            # qty may exceed it if the ask persisted across turns while the
            # trader's wallet shrank).  Also cap by the bidder's home cash.
            avail_foreign = fx_balance(atrader, self.other)
            qty = min(b['qty'], a['qty'], avail_foreign)
            if qty <= 0:
                j += 1
                continue
            home = qty * price
            if btrader.cash < home:
                home = btrader.cash
                qty = home / price if price > 0 else 0.0
            if qty <= 0:
                i += 1
                continue
            # Home leg (both are home-region traders)
            btrader.cash -= home
            atrader.cash += home
            # Foreign leg: transfer exactly what fx_sub actually removes
            before = fx_balance(atrader, self.other)
            fx_sub(atrader, self.other, qty)
            moved = before - fx_balance(atrader, self.other)
            fx_add(btrader, self.other, moved)
            total_home += moved * price
            b['qty'] -= moved
            a['qty'] -= moved
            if a['qty'] <= 0 or fx_balance(atrader, self.other) <= 0:
                j += 1
            if b['qty'] <= 0:
                i += 1"""
assert old in src, "clear-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("clear_book now matches on actual wallet balances")