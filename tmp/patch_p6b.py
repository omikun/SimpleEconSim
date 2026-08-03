#!/usr/bin/env python3
# Phase 6B: _import_ask_price true source cost + market cap
TARGET = 'region.py'
src = open(TARGET).read()

old = """        home_price_now = self.recipes.get(good, {}).get('price', 0)
        cost_home = max(0.05, trader.cost_get(good, 0), home_price_now)
        margin = self.IMPORT_MARGIN_MIN + (
            self.IMPORT_MARGIN_MAX - self.IMPORT_MARGIN_MIN) * (
                abs(hash((trader.id, good))) % 1000) / 1000.0
        tariff = getattr(self.gov, 'import_tariff_rate', 0.0)
        dest_desk = getattr(self.destination_region, 'forex', None)
        buy_rate = dest_desk.buy_rate() if dest_desk is not None else 1.0
        denom = max(0.05, (1.0 - tariff) * buy_rate)
        return cost_home * (1.0 + margin) / denom"""

new = """        cost_home = max(0.05, trader.cost_get(good, 0))
        src_region = getattr(self, 'destination_region', None)
        if cost_home <= 0.05 + 1e-9 and src_region is not None:
            cost_home = max(0.05, src_region.recipes.get(good, {}).get('price', 0.0))
        margin = self.IMPORT_MARGIN_MIN + (
            self.IMPORT_MARGIN_MAX - self.IMPORT_MARGIN_MIN) * (
                abs(hash((trader.id, good))) % 1000) / 1000.0
        tariff = getattr(self.gov, 'import_tariff_rate', 0.0)
        dest_desk = getattr(src_region, 'forex', None) if src_region is not None else None
        buy_rate = dest_desk.buy_rate() if dest_desk is not None else 1.0
        denom = max(0.05, (1.0 - tariff) * buy_rate)
        ask = cost_home * (1.0 + margin) / denom
        dest_price = self.recipes.get(good, {}).get('price', 0.0)
        if dest_price > 0:
            cap = dest_price * (1.0 + self.IMPORT_MARGIN_MIN)
            ask = min(ask, cap)
        return max(0.05, ask)"""

assert src.count(old) == 1, "_import_ask_price block not found"
src = src.replace(old, new)
open(TARGET, 'w').write(src)
print("patch_p6b.py applied OK")
