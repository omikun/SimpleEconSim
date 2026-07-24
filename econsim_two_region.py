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

from goods import Goods, profession
from region import Region, get_total_cash
from econsim_states import starvation_limit, max_career_switches, probability_birth, birth_gap
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
            self.inventory_foreign[entry['good']] += entry['quantity']
        else:
            new_pipeline.append(entry)
    self.transport_pipeline = new_pipeline
    for good, qty in list(self.inventory_export.items()):
        if qty > 0:
            self.transport_pipeline.append({
                'turns_left': self.transport_delay,
                'good': good,
                'quantity': qty,
            })
            self.inventory_export[good] = 0


from agent import Agent
Agent._process_pipeline = _agent_process_pipeline


def foreign_sell(t, destination_region, source_region):
    traders = [a for a in source_region.agents
               if getattr(a, 'is_trader', False) and getattr(a, 'home_region', None) == source_region.name]
    total_sold_value = 0.0
    total_sold_quantity = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    total_trader_profit = 0.0
    total_bank_recycle = 0.0
    total_tariff = 0.0

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furniture]:
            qty = trader.inventory_foreign.get(good, 0)
            if qty <= 0:
                continue
            price = destination_region.recipes[good]['price']
            ask_price = price * 0.95
            fx_rate = getattr(source_region, 'exchange_rate', 1.0)
            if fx_rate != 1.0 and getattr(source_region.gov, 'floating_exchange_rate_enabled', True):
                ask_price = ask_price / fx_rate
            buyers = [a for a in destination_region.agents
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

                if getattr(destination_region.gov, 'trader_recycling_enabled', True):
                    bank_share = cash * 0.20
                    trader_share -= bank_share
                if getattr(destination_region.gov, 'import_tariff_enabled', True):
                    tariff_share = cash * 0.10
                    trader_share -= tariff_share

                trader.cash += trader_share
                if bank_share > 0:
                    destination_region.bank.total_deposits += bank_share
                if tariff_share > 0:
                    destination_region.gov.agent.cash += tariff_share
                total_trader_profit += trader_share
                total_bank_recycle += bank_share
                total_tariff += tariff_share
                old_quantity = buyer.inventory.get(good, 0)
                old_cost = buyer.cost_basis.get(good, 0)
                buyer.cost_basis[good] = ((old_quantity * old_cost + bought * ask_price) / (old_quantity + bought)) if (old_quantity + bought) > 0 else ask_price
                buyer.inventory[good] += bought
                remaining -= bought
                total_sold_quantity += bought
                total_sold_value += cash
                trade_volumes[good] += bought
                trade_values[good] += cash
            trader.inventory_foreign[good] = remaining

    if total_sold_value > 0:
        print(f"  TRADE {source_region.name}->{destination_region.name}: "
              f"sold {total_sold_quantity} units worth ${total_sold_value:.2f} "
              f"({dict(trade_volumes)})"
              f"  trader ${total_trader_profit:.2f}"
              f"  bank recycle ${total_bank_recycle:.2f}"
              f"  tariff ${total_tariff:.2f}")

    for good in [Goods.food, Goods.wood, Goods.furniture]:
        volume_sold = trade_volumes[good]
        value_sold = trade_values[good]
        if volume_sold > 0:
            source_region.export_vol[good].append(volume_sold)
            source_region.export_val[good].append(value_sold)
            destination_region.import_vol[good].append(volume_sold)
            destination_region.import_val[good].append(value_sold)
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            destination_region.import_vol[good].append(0)
            destination_region.import_val[good].append(0.0)

    return total_sold_quantity, total_sold_value


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Two-Region Simulation: {time_steps} time steps per region\n")

    random.seed(42)

    region_a = Region("Region_A", t=0, number_of_agents=110,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
    region_b = Region("Region_B", t=0, number_of_agents=110,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05})

    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2

    region_a.destination_region = region_b
    region_b.destination_region = region_a
    for trader in region_a.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_b
    for trader in region_b.agents:
        if getattr(trader, 'is_trader', False):
            trader.destination_region = region_a

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    for t in range(1, time_steps + 1):
        cash_before = get_total_cash(region_a.agents, region_a.bank) + get_total_cash(region_b.agents, region_b.bank)
        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        cash_after = get_total_cash(region_a.agents, region_a.bank) + get_total_cash(region_b.agents, region_b.bank)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")

        for region, other in [(region_a, region_b), (region_b, region_a)]:
            turn_export = sum(region.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.export_val[g])
            turn_import = sum(region.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.import_val[g])
            region.cumulative_trade_balance += (turn_export - turn_import)
            if getattr(region.gov, 'floating_exchange_rate_enabled', True):
                adj = region.cumulative_trade_balance * 0.000005
                region.exchange_rate *= (1 + adj)
                region.exchange_rate = max(0.1, min(10.0, region.exchange_rate))

        for g in [Goods.food, Goods.wood, Goods.furniture]:
            price_a = region_a.recipes[g]['price']
            price_b = region_b.recipes[g]['price']
            spread = abs(price_a - price_b)
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
        labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture', Goods.gov: 'Gov'}
        for g in region.goods:
            pop = region.population_log.get(g, [0])[-1] if region.population_log.get(g) else 0
            price = (region.price_log.get(g, [1.0])[-1] if g != Goods.gov and region.price_log.get(g) else 1.0)
            inv = (region.inventory_log.get(g, [0])[-1] if g != Goods.gov and region.inventory_log.get(g) else 0)
            cash = region.cash_log.get(g, [0])[-1] if region.cash_log.get(g) else 0
            print(f"  {labels[g]}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
        total_population = region.total_population[-1] if region.total_population else 0
        dead_starved = region.dead_starved_population[-1] if region.dead_starved_population else 0
        print(f"  Total Pop: {total_population}, Dead/Starved: {dead_starved}")
        gdp_value = region.gdp_log[-1] if region.gdp_log else 0
        print(f"  Final GDP/turn: ${gdp_value:.2f}")

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
        for g in [Goods.food, Goods.wood, Goods.furniture]:
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
        print(f"  Trader ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}->${final_trader_cash:.0f})")

    print("\nDone.")


if __name__ == "__main__":
    main()