#!/usr/bin/env python3
# Phase 6A: record trader cost basis in _clear_discriminatory
TARGET = 'region.py'
src = open(TARGET).read()

old = """                if getattr(buyer, 'is_trader', False):
                    if good == Goods.transport:
                        buyer.inv_add(good, take)
                    elif good != Goods.food:
                        buyer.inventory_export[good.value] += take
                    else:
                        food_needed = max(0, 8 - buyer.inv_get(good, 0))
                        keep = min(food_needed, take)
                        buyer.inv_add(good, keep)
                        if take - keep > 0:
                            buyer.inventory_export[good.value] += take - keep"""

new = """                if getattr(buyer, 'is_trader', False):
                    if good == Goods.transport:
                        buyer.inv_add(good, take)
                    elif good != Goods.food:
                        old_q = buyer.inv_get(good, 0)
                        old_c = buyer.cost_get(good, 0)
                        total_q = old_q + take
                        buyer.cost_set(good, ((old_q * old_c + take * ask)
                                              / total_q) if total_q > 0 else ask)
                        buyer.inventory_export[good.value] += take
                    else:
                        food_needed = max(0, 8 - buyer.inv_get(good, 0))
                        keep = min(food_needed, take)
                        buyer.inv_add(good, keep)
                        if take - keep > 0:
                            export = take - keep
                            old_q = buyer.inv_get(good, 0)
                            old_c = buyer.cost_get(good, 0)
                            total_q = old_q + export
                            buyer.cost_set(good, ((old_q * old_c + export * ask)
                                                  / total_q) if total_q > 0 else ask)
                            buyer.inventory_export[good.value] += export"""

assert src.count(old) == 1, "deliver block not found"
src = src.replace(old, new)
open(TARGET, 'w').write(src)
print("patch_p6a.py applied OK")
