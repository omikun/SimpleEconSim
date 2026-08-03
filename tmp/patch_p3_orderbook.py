"""Phase 3: interbank order-book engine inside the band.

Layers on the existing ForexDesk (mid/spread/band) without restructuring:
  * Each region's desk hosts a book of bid orders (buy foreign) and ask
    orders (sell foreign) for its other currency.
  * The book clears at crossing prices.  Unmatched asks/bids flow to the
    desk at its quote (market-maker of last resort, still reserve-capped).
  * Matching is conservation-safe: buyer pays home cash; seller receives
    home cash; foreign currency moves wallet-to-wallet (reserves untouched).
"""
p = "/Users/sli/Code/forex.py"
src = open(p).read()

# ---- 1. ForexDesk: add book fields + clear_book method ----
old = """        self.log = []  # (t, mid, reserves) history
        if bank is not None:
            self._seed_bank(bank, initial_reserves)"""
new = """        self.log = []  # (t, mid, reserves) history
        # Interbank order book (Phase 3): entries are
        #   {'kind': 'bid'|'ask', 'trader': trader, 'qty': float, 'rate': float}
        self.book = []
        if bank is not None:
            self._seed_bank(bank, initial_reserves)

    def post_order(self, kind, trader, qty, rate):
        \"\"\"Post a bid (buy foreign) or ask (sell foreign) to this desk's book.\"\"\"
        if qty <= 0 or rate <= 0:
            return 0.0
        self.book.append({'kind': kind, 'trader': trader, 'qty': qty,
                          'rate': rate})
        return qty

    def clear_book(self):
        \"\"\"Match crossed orders inside the bank's rate band.

        A bid (buy foreign) at rate B crosses an ask (sell foreign) at rate A
        when B >= A.  Matching transfers foreign between the two traders'
        wallets bilaterally, and home cash between them:  the bidder pays
        (qty * A) home cash to the asker, both in home currency.  This is
        conservation-safe (home cash moves home-cash; foreign wallet moves
        foreign wallet).  Uses the ASK's rate A as the trade price so the
        bidder gets the more favorable fill for the market maker.
        Returns total home value matched.
        \"\"\"
        total_home = 0.0
        bids = [o for o in self.book if o['kind'] == 'bid']
        asks = [o for o in self.book if o['kind'] == 'ask']
        # Sort: highest bids first, lowest asks first (best price)
        bids.sort(key=lambda o: -o['rate'])
        asks.sort(key=lambda o: o['rate'])
        i = j = 0
        while i < len(bids) and j < len(asks):
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
                i += 1
        self.book = [o for o in self.book if o['qty'] > 0]
        return total_home"""
assert old in src, "book-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("order-book engine added to ForexDesk")