#!/usr/bin/env python3
# Phase 6C: FX-adjusted bid gate (repatriated home value vs local price)
TARGET = 'region.py'
src = open(TARGET).read()

old = """                dest_price = destination.recipes.get(good, {}).get('price', 0)
                min_margin = self.IMPORT_MARGIN_MIN  # 5%
                if dest_price <= good_price * (1.0 + min_margin):
                    return 0"""

new = """                dest_price = destination.recipes.get(good, {}).get('price', 0)
                min_margin = self.IMPORT_MARGIN_MIN  # 5%
                # FX-adjusted parity: traders repatriate destination earnings
                # at their HOME desk's buy rate.  A raw price-spread test
                # ignores conversion (spread + managed-float drift) and lets
                # traders buy on phantom arbitrage that conversion erases.
                desk = getattr(self, 'forex', None)
                home_per_dest = desk.buy_rate() if desk is not None else 1.0
                if dest_price * home_per_dest <= good_price * (1.0 + min_margin):
                    return 0"""

assert src.count(old) == 1, "bid gate block not found"
src = src.replace(old, new)
open(TARGET, 'w').write(src)
print("patch_p6c.py applied OK")
