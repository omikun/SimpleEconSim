#!/usr/bin/env python3
# Phase 6G: trader exit benchmark — col + 2% opportunity cost on committed capital
TARGET = 'region.py'
src = open(TARGET).read()

old = """            period_revenue = agent._trader_revenue - agent._trader_revenue_check
            if period_revenue < col:
                self._exit_trader(agent)
                loginfo(t, f"{agent.name()} exited trading (revenue ${period_revenue:.0f} < col ${col:.0f})")"""

new = """            period_revenue = agent._trader_revenue - agent._trader_revenue_check
            # Opportunity-cost benchmark: cover living costs PLUS 2%/turn on
            # capital parked in tradable goods (inventory_export + in-transit +
            # foreign-side), so unprofitable arbitrageurs get evicted instead
            # of surviving forever and diluting trader ROI.
            committed = 0.0
            for g in Goods:
                if g == Goods.none or g == Goods.transport:
                    continue
                q = (agent.inventory_export[g.value]
                     + agent.inventory_foreign[g.value])
                for pipe in agent.transport_pipeline:
                    if pipe['good'] == g:
                        q += pipe['quantity']
                if q > 0:
                    committed += q * agent.cost_get(g, 0)
            benchmark = col + 0.02 * committed
            if period_revenue < benchmark:
                self._exit_trader(agent)
                loginfo(t, f"{agent.name()} exited trading "
                        f"(revenue ${period_revenue:.0f} < ${benchmark:.0f})")"""

assert src.count(old) == 1, "exit benchmark block not found"
src = src.replace(old, new)
open(TARGET, 'w').write(src)
print("patch_p6g.py applied OK")