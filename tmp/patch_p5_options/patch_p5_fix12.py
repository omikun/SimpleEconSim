"""Phase 5 fix 12: _clear_discriminatory must route trader purchases to
inventory_export (the phase-1 _buy logic it replaced did this).

B traders were bidding ~20 wood every other turn, but `_clear_discriminatory`
delivered goods via buyer.inv_add -> PERSONAL inventory, so inventory_export
never grew -> _pending_imports found nothing -> imports never reached the
auction.  Replicate _buy's routing for trader buyers:
  - transport -> personal inventory
  - non-food -> inventory_export
  - food -> keep up to 8, rest -> inventory_export
  - non-traders -> personal inventory (unchanged)
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """                if is_import:
                    # Split buyer payment between trader (in dest-currency
                    # wallet) and the destination government's import tariff
                    tau = getattr(self.gov, 'import_tariff_rate', 0.0) \\
                        if getattr(self.gov, 'import_tariff_enabled', False) \\
                        else 0.0
                    trader_share = cost * (1.0 - tau)
                    tariff_share = cost * tau
                    _fx.fx_add(seller, self.home_currency, trader_share)
                    if tariff_share > 0:
                        self.gov.agent.cash += tariff_share
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost
                else:
                    seller.cash += cost
                    seller.inventory[good.value] -= take
                buyer.inv_add(good, take)   # buyer always receives the good
                cash_collected += cost"""
new = """                if is_import:
                    # Split buyer payment between trader (in dest-currency
                    # wallet) and the destination government's import tariff
                    tau = getattr(self.gov, 'import_tariff_rate', 0.0) \\
                        if getattr(self.gov, 'import_tariff_enabled', False) \\
                        else 0.0
                    trader_share = cost * (1.0 - tau)
                    tariff_share = cost * tau
                    _fx.fx_add(seller, self.home_currency, trader_share)
                    if tariff_share > 0:
                        self.gov.agent.cash += tariff_share
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost
                else:
                    seller.cash += cost
                    seller.inventory[good.value] -= take
                # Deliver to buyer — traders route exports like _buy did
                if getattr(buyer, 'is_trader', False):
                    if good == Goods.transport:
                        buyer.inv_add(good, take)
                    elif good != Goods.food:
                        buyer.inventory_export[good.value] += take
                    else:
                        food_needed = max(0, 8 - buyer.inv_get(good, 0))
                        keep = min(food_needed, take)
                        buyer.inv_add(good, keep)
                        if take - keep > 0:
                            buyer.inventory_export[good.value] += take - keep
                else:
                    buyer.inv_add(good, take)   # non-trader: personal stock
                cash_collected += cost"""
assert old in src, "deliver-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("trader purchase routing restored in _clear_discriminatory")