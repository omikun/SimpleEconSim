"""Phase 5 fix 13: supply-side scarcity into _update_price_ref.

The forest-fire test exposed that price does not spike when production
collapses: the reference update only sees demand_ratio (bids/asks), and
existing inventories keep asks normal, so scarcity is invisible until stock
hits zero.  Add a REGIONAL scarcity signal — average producer inventory vs a
target level — so price responds the same round a supply shock hits.

  scarcity = 1 - avg_inventory / (maxinv * 0.6)   (0 normal, 1 empty)
  influence = 0.25*tanh(demand_ratio-1) + 0.30*scarcity

On a forest fire: production collapses -> stock drains -> avg_inventory
falls -> scarcity > 0 -> ref rises that round (cash-rationing starts
immediately), inventory drains slower, and price settles back when
production recovers (scarcity -> 0, glut pull returns).
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """    def _update_price_ref(self, good, demand_ratio):
        \"\"\"Bounded move-toward-target price reference.

        NOT multiplicative (a multiplicative update compounds ref * step when
        demand_ratio > 1 and flies to the cap, starving everyone, killing
        exports, and preventing imports).  Instead move a fraction of the gap
        to a target, so the reference is asymptotically stable yet still reacts
        fast to real supply shocks (tanh-bounded), and eases gently on gluts.
        Also syncs recipes[g]['price'] so legacy systems (trader profitability,
        food price, cost of living, price logs) see one coherent price.
        \"\"\"
        ref = self._price_ref[good]
        # Asymmetric bounded pull: positive imbalance pulls up, glut pulls down
        influence = 0.25 * math.tanh(demand_ratio - 1.0)
        target = ref * (1.0 + influence)
        ref = ref + (target - ref) * 0.25"""
new = """    def _update_price_ref(self, good, demand_ratio):
        \"\"\"Bounded move-toward-target price reference WITH supply scarcity.

        NOT multiplicative (a multiplicative update compounds ref * step when
        demand_ratio > 1 and flies to the cap, starving everyone, killing
        exports, and preventing imports).  Instead move a fraction of the gap
        to a target, so the reference is asymptotically stable yet still reacts
        fast to real supply shocks, and eases gently on gluts.  Also syncs
        recipes[g]['price'] so legacy readers see one coherent price.

        The demand_ratio alone is blind to supply shocks while inventories
        still buffer asks, so we ADD a regional scarcity signal (average stock
        per producer vs target).  A forest fire: production collapses -> stock
        drains -> scarcity rises -> price rises that same round, cash-rationing
        preserves remaining inventory, and it settles back once production
        recovers (scarcity -> 0, glut pull returns).
        \"\"\"
        ref = self._price_ref[good]
        # Demand pull (bids/asks ratio), bounded by tanh
        inflation = 0.25 * math.tanh(demand_ratio - 1.0)

        # Supply scarcity: producers' average inventory vs a 60%-of-maxinv
        # target.  0 = normal stock, 1 = empty (prices on the ceiling).
        maxinv = self.recipes.get(good, {}).get('maxinv', 10)
        producers = [a for a in self.agents
                     if a.output == good and not getattr(a, 'is_trader', False)]
        if producers:
            avg_inv = sum(a.inv_get(good, 0) for a in producers) / len(producers)
        else:
            avg_inv = 0.0
        scarcity = max(0.0, min(1.0, 1.0 - avg_inv / max(0.1, maxinv * 0.6)))

        influence = inflation + 0.30 * scarcity
        influence = max(-0.35, min(0.50, influence))
        target = ref * (1.0 + influence)
        ref = ref + (target - ref) * 0.25"""
assert old in src, "scarcity-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("supply scarcity added to price reference")