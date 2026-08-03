"""Phase 5 fix 11: traders keep buying power in cash, deposit only excess.

Current _deposit_excess locks 10% of TOTAL liquid into deposits, which can
leave too little usable cash for export buying.  New policy for traders:
  cash_floor = 5 * cost_of_living + 15 * all_goods_price
Deposit only the portion ABOVE the floor (still capped by the 10% deposit
target).  Non-traders keep the existing 30-70% wealth-based behavior.

Conservation: pure cash <-> deposit re-allocation, both counted in the
per-currency audit -> no SUPPLY SHIFT / LEAK.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """    def _deposit_excess(self, agent, all_goods_price):
        mult = agent.consumption_multiplier
        total_liquid = agent.cash + self.bank.deposits.get(agent, 0)
        current_deposits = self.bank.deposits.get(agent, 0)
        # Traders keep most of their capital liquid for buying opportunities
        if agent.is_trader:
            deposit_fraction = 0.10  # only lock 10%
        else:
            deposit_fraction = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
        cash_floor = int(all_goods_price * (100 / max(1.0, mult)))
        max_deposits = total_liquid * deposit_fraction
        excess = max(0, max_deposits - current_deposits)
        if agent.cash > cash_floor and excess > 0:
            self.bank.Deposit(agent, min(agent.cash - cash_floor, excess))"""
new = """    def _deposit_excess(self, agent, all_goods_price):
        mult = agent.consumption_multiplier
        total_liquid = agent.cash + self.bank.deposits.get(agent, 0)
        current_deposits = self.bank.deposits.get(agent, 0)
        if agent.is_trader:
            # Traders keep EVERYTHING they need for buying in cash; deposit
            # only excess above a working-capital floor (5x cost of living +
            # 15x goods price — matches the trade-financing borrow target).
            deposit_fraction = 0.10  # applied to above-floor portion
            cash_floor = int(self.cost_of_living * 5) + int(all_goods_price * 15)
        else:
            deposit_fraction = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
            cash_floor = int(all_goods_price * (100 / max(1.0, mult)))
        max_deposits = max(0.0, total_liquid - cash_floor) * deposit_fraction
        excess = max(0, max_deposits - current_deposits)
        if agent.cash > cash_floor and excess > 0:
            self.bank.Deposit(agent, min(agent.cash - cash_floor, excess))"""
assert old in src, "deposit-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("trader deposit policy applied (cash floor for buying power)")