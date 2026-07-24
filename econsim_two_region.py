#!/usr/bin/env python3
"""
Two-region economic simulation.

Initializes two independent regions, each with its own Government, bank, agent
population, and logging state.  Trade flows between regions via trader agents
with transport delay.  Supports per-government policy toggles and floating
exchange rates.

Usage:
    python3 econsim_two_region.py [time_steps]
"""

import sys
import random
from collections import defaultdict

from goods import Goods
from region import Region
from econsim_states import profession, starve_limit, max_career_switches, p_birth, birthGap
from logger import loginfo, logInit


# =============================================================================
# Trader constant
# =============================================================================
TRADER_GOOD = Goods.none
profession[Goods.none] = 'T'  # traders show as 'T'

MAX_TRADER_FRACTION = 0.2
TRANSPORT_DELAY = 1


# =============================================================================
# Inter-region transport & foreign-sell
# =============================================================================

def process_transport(t, region_a, region_b):
    """Process transport pipelines for all traders in both regions."""
    for trader in region_a.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()
    for trader in region_b.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()


def _agent_process_pipeline(self):
    new_pipeline = []
    for entry in self.transport_pipeline:
        entry['turns_left'] -= 1
        if entry['turns_left'] <= 0:
            self.inv_foreign[entry['good']] += entry['qty']
        else:
            new_pipeline.append(entry)
    self.transport_pipeline = new_pipeline
    for good, qty in list(self.inv_export.items()):
        if qty > 0:
            self.transport_pipeline.append({
                'turns_left': self.transport_delay,
                'good': good,
                'qty': qty,
            })
            self.inv_export[good] = 0


from agent import Agent
Agent._process_pipeline = _agent_process_pipeline


def foreign_sell(t, dest_region, source_region):
    traders = [a for a in source_region.agents
               if getattr(a, 'is_trader', False) and getattr(a, 'home_region', None) == source_region.name]
    total_sold_value = 0.0
    total_sold_qty = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    total_trader_profit = 0.0
    total_bank_recycle = 0.0
    total_tariff = 0.0

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furn]:
            qty = trader.inv_foreign.get(good, 0)
            if qty <= 0:
                continue
            price = dest_region.recipes[good]['price']
            ask_price = price * 0.95
            fx = getattr(source_region, 'exchange_rate', 1.0)
            if fx != 1.0 and getattr(source_region.gov, 'floating_exchange_rate_enabled', True):
                ask_price = ask_price / fx
            buyers = [a for a in dest_region.agents
                      if not getattr(a, 'is_trader', False) and a.cash > ask_price]
            random.shuffle(buyers)
            remaining = qty
            for buyer in buyers:
                if remaining <= 0:
                    break
                max_buy = int(buyer.cash / ask_price)
                if max_buy <= 0:
                    continue
                bought = min(remaining, max_buy, 3)
                cash = bought * ask_price
                buyer.cash -= cash
                trader_share = cash
                bank_share = 0.0
                tariff_share = 0.0

                if getattr(dest_region.gov, 'trader_recycling_enabled', True):
                    bank_share = cash * 0.20
                    trader_share -= bank_share
                if getattr(dest_region.gov, 'import_tariff_enabled', True):
                    tariff_share = cash * 0.10
                    trader_share -= tariff_share

                trader.cash += trader_share
                if bank_share > 0:
                    dest_region.bank.total_deposits += bank_share
                if tariff_share > 0:
                    dest_region.gov.agent.cash += tariff_share
                total_trader_profit += trader_share
                total_bank_recycle += bank_share
                total_tariff += tariff_share
                oq = buyer.inv.get(good, 0)
                oc = buyer.cost_basis.get(good, 0)
                buyer.cost_basis[good] = ((oq * oc + bought * ask_price) / (oq + bought)) if (oq + bought) > 0 else ask_price
                buyer.inv[good] += bought
                remaining -= bought
                total_sold_qty += bought
                total_sold_value += cash
                trade_volumes[good] += bought
                trade_values[good] += cash
            trader.inv_foreign[good] = remaining

    if total_sold_qty > 0:
        print(f"  TRADE {source_region.name}→{dest_region.name}: "
              f"sold {total_sold_qty} units worth ${total_sold_value:.2f} "
              f"({dict(trade_volumes)})"
              f"  trader ${total_trader_profit:.2f}"
              f"  bank recycle ${total_bank_recycle:.2f}"
              f"  tariff ${total_tariff:.2f}")

    for good in [Goods.food, Goods.wood, Goods.furn]:
        vol_sold = trade_volumes[good]
        val_sold = trade_values[good]
        if vol_sold > 0:
            source_region.export_vol[good].append(vol_sold)
            source_region.export_val[good].append(val_sold)
            dest_region.import_vol[good].append(vol_sold)
            dest_region.import_val[good].append(val_sold)
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            dest_region.import_vol[good].append(0)
            dest_region.import_val[good].append(0.0)

    return total_sold_qty, total_sold_value


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Two-Region Simulation: {time_steps} time steps per region\n")

    random.seed(42)

    region_a = Region("Region_A", t=0, num_agents=110,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furn: 0.037})
    region_b = Region("Region_B", t=0, num_agents=110,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furn: 0.05})

    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2

    region_a.dest_region = region_b
    region_b.dest_region = region_a
    for trader in region_a.agents:
        if getattr(trader, 'is_trader', False):
            trader.dest_region = region_b
    for trader in region_b.agents:
        if getattr(trader, 'is_trader', False):
            trader.dest_region = region_a

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)

        for region, other in [(region_a, region_b), (region_b, region_a)]:
            turn_export = sum(region.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if region.export_val[g])
            turn_import = sum(region.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if region.import_val[g])
            region.cumulative_trade_balance += (turn_export - turn_import)
            if getattr(region.gov, 'floating_exchange_rate_enabled', True):
                adj = region.cumulative_trade_balance * 0.000005
                region.exchange_rate *= (1 + adj)
                region.exchange_rate = max(0.1, min(10.0, region.exchange_rate))

        for g in [Goods.food, Goods.wood, Goods.furn]:
            pa = region_a.recipes[g]['price']
            pb = region_b.recipes[g]['price']
            spread = abs(pa - pb)
            region_a.price_spread_log[g].append(spread)
            region_b.price_spread_log[g].append(spread)

        if t % 50 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\nGenerating plots...")
    region_a.plot("region_a_output.png")
    region_b.plot("region_b_output.png")

    print("\n" + "=" * 60)
    print("FINAL SUMMARY =")
    print("=" * 60)

    for region in (region_a, region_b):
        print(f"\n--- {region.name} ---")
        lab = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furn: 'carp', Goods.gov: 'gov'}
        for g in region.goods:
            pop = region.pop_log.get(g, [0])[-1] if region.pop_log.get(g) else 0
            price = (region.price_log.get(g, [1.0])[-1] if g != Goods.gov and region.price_log.get(g) else 1.0)
            inv = (region.inv_log.get(g, [0])[-1] if g != Goods.gov and region.inv_log.get(g) else 0)
            cash = region.cash_log.get(g, [0])[-1] if region.cash_log.get(g) else 0
            print(f"  {lab[g]}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
        tp = region.total_pop[-1] if region.total_pop else 0
        ds = region.deadstarve_pop[-1] if region.deadstarve_pop else 0
        print(f"  Total Pop: {tp}, Dead/Starved: {ds}")
        gdp = region.gdp_log[-1] if region.gdp_log else 0
        print(f"  Final GDP/turn: ${gdp:.2f}")

        total_export = sum(sum(v) for v in region.export_vol.values())
        total_import = sum(sum(v) for v in region.import_vol.values())
        total_export_val = sum(sum(v) for v in region.export_val.values())
        total_import_val = sum(sum(v) for v in region.import_val.values())
        print(f"  Total Exports: {total_export} units (${total_export_val:.2f})")
        print(f"  Total Imports: {total_import} units (${total_import_val:.2f})")
        net_trade = total_export_val - total_import_val
        sign = "+" if net_trade >= 0 else ""
        print(f"  Net Trade Balance: {sign}${net_trade:.2f}")
        avg_spread = {}
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if region.price_spread_log.get(g) and len(region.price_spread_log[g]) > 0:
                avg_spread[g] = sum(region.price_spread_log[g]) / len(region.price_spread_log[g])
        if avg_spread:
            spread_str = ", ".join(f"{Goods(g).name}: ${s:.2f}" for g, s in avg_spread.items())
            print(f"  Avg Price Spread: {spread_str}")
        trader_roi = 0.0
        init_trader_cash = region.trader_cash_log[0] if region.trader_cash_log else 1
        final_trader_cash = region.trader_cash_log[-1] if region.trader_cash_log else 0
        if init_trader_cash > 0:
            trader_roi = (final_trader_cash - init_trader_cash) / init_trader_cash * 100
        print(f"  Trader ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}→${final_trader_cash:.0f})")

    print("\nDone.")


if __name__ == "__main__":
    main()