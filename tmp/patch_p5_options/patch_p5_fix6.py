"""Fix two real Phase-5 bugs:

1. Import purchases never delivered the good to the buyer (buyer.inv_add only
   ran for locals).  Buyers paid cash and got nothing.
2. _buy never recorded trader cost_basis, so _import_ask_price floor (0.05)
   made ALL imports sell at ~$0.05 -> Net Trade $0.00 + negative trader ROI.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

# ---- 1. Deliver goods to buyer on import purchases ----
old = """                if is_import:
                    _fx.fx_add(seller, self.home_currency, cost)
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost
                else:
                    seller.cash += cost
                    seller.inventory[good.value] -= take
                    buyer.inv_add(good, take)
                cash_collected += cost"""
new = """                if is_import:
                    _fx.fx_add(seller, self.home_currency, cost)
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost
                else:
                    seller.cash += cost
                    seller.inventory[good.value] -= take
                buyer.inv_add(good, take)   # buyer always receives the good
                cash_collected += cost"""
assert old in src, "deliver-anchor"
src = src.replace(old, new)

# ---- 2. Record trader cost_basis for export goods in _buy ----
old = """                if bought > 0:
                    if a.is_trader:
                        # Transport goes to personal inventory (consumed locally
                        # to move goods), not exported
                        if good == Goods.transport:
                            a.inv_add(good, bought)
                        elif good != Goods.food:
                            a.inventory_export[good.value] += bought
                        else:
                            food_needed = max(0, 8 - a.inv_get(good, 0))
                            keep = min(food_needed, bought)
                            export = bought - keep
                            a.inv_add(good, keep)
                            if export > 0:
                                a.inventory_export[good.value] += export
                    else:"""
new = """                if bought > 0:
                    if a.is_trader:
                        # Transport goes to personal inventory (consumed locally
                        # to move goods), not exported
                        if good == Goods.transport:
                            a.inv_add(good, bought)
                        elif good != Goods.food:
                            # Record cost basis for export goods so imports are
                            # priced at cost+margin, not a floor
                            old_q = a.inv_get(good, 0)
                            old_c = a.cost_get(good, 0)
                            total_q = old_q + bought
                            a.cost_set(good, ((old_q * old_c + bought * price)
                                              / total_q) if total_q > 0 else price)
                            a.inventory_export[good.value] += bought
                        else:
                            food_needed = max(0, 8 - a.inv_get(good, 0))
                            keep = min(food_needed, bought)
                            export = bought - keep
                            a.inv_add(good, keep)
                            if export > 0:
                                old_q = a.inv_get(good, 0)
                                old_c = a.cost_get(good, 0)
                                total_q = old_q + export
                                a.cost_set(good, ((old_q * old_c + export * price)
                                                  / total_q) if total_q > 0 else price)
                                a.inventory_export[good.value] += export
                    else:"""
assert old in src, "cost-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("delivery + trader cost-basis fixes applied")