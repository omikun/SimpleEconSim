"""Add import-tariff collection to the Phase-5 auction clear.

When the destination government has import_tariff_enabled, the import sale is
split: buyer pays full cost; trader wallet receives cost*(1-tau); destination
gov receives cost*tau.  Conservation: buyer_out + seller_in + gov_in = 0.
"""
p = "/Users/sli/Code/region.py"
src = open(p).read()

old = """                cost = take * ask
                buyer.cash -= cost
                if is_import:
                    _fx.fx_add(seller, self.home_currency, cost)
                    seller.inventory_foreign[good.value] -= take
                    imp_units += take
                    imp_value += cost"""
new = """                cost = take * ask
                buyer.cash -= cost
                if is_import:
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
                    imp_value += cost"""
assert old in src, "tariff-anchor"
src = src.replace(old, new)

open(p, "w").write(src)
print("import tariff collection added to auction clear")