"""Fix the Phase-5 reference runaway + price-desync.

1. _update_price_ref compounded multiplicatively (ref * 1.08 * shock) every
   turn demand_ratio > 1, flying to the 50 cap in ~6 turns and pricing
   everyone (including traders) out of the market -> zero exports -> zero
   imports ever arrive.  Replace with a bounded "move toward target" update
   (asymptotic, stable, still fast on shocks):
       target = ref * (1 + 0.25 * tanh(demand_ratio - 1))
       ref   += (target - ref) * 0.25
   Demand_ratio < 1 pulls the same way with tanh negative -> gentle decline.

2. Legacy systems (trader bid profitability, food_price, cost_of_living,
   price logs) still read recipes[g]['price'], which froze since _set_price is
   no longer called in Phase A.  Sync recipes[g]['price'] = ref each turn so
   the whole sim sees one coherent price.
"""
import math

p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """    def _update_price_ref(self, good, demand_ratio):
        \"\"\"Slow anchor: VWAP-of-trades + demand/supply, asymmetric step.

        Positive imbalance (fires / scarcity) moves ref UP fast — bounded per
        round so no runaway — while gluts ease gently.  Blends recent realized
        trade prices so the anchor tracks actuals.
        \"\"\"
        ref = self._price_ref[good]
        base_step = 1.0 + 0.08  # ~8% normal move
        if demand_ratio > 1.0:
            shock = 1.0 + 0.25 * min(5.0, (demand_ratio - 1.0) ** 2)
            ref = ref * base_step * shock
        else:
            ref = ref / base_step
        recent = self._trade_prices.get(good, [])[-12:]
        if recent:
            vwap = sum(recent) / len(recent)
            ref = 0.7 * ref + 0.3 * vwap
        r = self.recipes.get(good, {})
        cost_floor = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            cost_floor = max(0.1, (r['numInput'] * self.recipes[r['input']]['price'])
                             / r['production'])
        ref = max(cost_floor, ref)
        self._price_ref[good] = max(0.1, min(50.0, ref))"""
new = """    def _update_price_ref(self, good, demand_ratio):
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
        ref = ref + (target - ref) * 0.25
        # Blend recent realized trade prices (VWAP) so ref tracks actuals
        recent = self._trade_prices.get(good, [])[-12:]
        if recent:
            vwap = sum(recent) / len(recent)
            ref = 0.7 * ref + 0.3 * vwap
        # Cost floor keeps prices from collapsing below production cost
        r = self.recipes.get(good, {})
        cost_floor = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            cost_floor = max(0.1, (r['numInput'] * self.recipes[r['input']]['price'])
                             / r['production'])
        ref = max(cost_floor, ref)
        ref = max(0.1, min(50.0, ref))
        self._price_ref[good] = ref
        # Sync the legacy recipe price so all readers see the same number
        if good in self.recipes:
            self.recipes[good]['price'] = ref"""
assert old in src, "ref-update-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("bounded price-ref + recipes sync applied")