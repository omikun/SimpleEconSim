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
import wealth_lineage
import wealth_diagnostic
import forex as fx


# =============================================================================
# Trader constant
# =============================================================================
TRADER_GOOD = Goods.none
profession[Goods.none] = 'T'  # traders show as 'T'

MAX_TRADER_FRACTION = 0.2
TRANSPORT_DELAY = 1

# Floating exchange rate tuning: recent net trade flows (rolling window, not
# cumulative stock) drive the rate; a gentle reversion pulls toward parity.
FX_WINDOW = 40            # rolling window (turns) of net flows used
FX_SENSITIVITY = 0.00005  # rate change per $ of average recent flow
FX_REVERT = 0.01          # per-turn pull toward parity (1.0)


def update_exchange_rate(region):
    """Adjust the region's exchange rate.

    Phase 1: delegates to the region's ForexDesk (central-bank quote with
    reserve constraints) when wired.  Falls back to the legacy trade-flow
    heuristic when no desk exists (e.g. single-region or external scripts).
    """
    desk = getattr(region, 'forex', None)
    if desk is not None:
        desk.update(0, bank=getattr(region, 'bank', None),
                    fx_regime=getattr(region.gov, 'fx_regime', 'managed'))
        desk.save_rate(region)
        return region.exchange_rate
    if not getattr(region.gov, 'floating_exchange_rate_enabled', True):
        region.exchange_rate_log.append(region.exchange_rate)
        return
    recent = region.trade_flow_log[-FX_WINDOW:]
    flow = sum(recent) / len(recent) if recent else 0.0
    region.exchange_rate *= (1 + flow * FX_SENSITIVITY)
    region.exchange_rate += (1.0 - region.exchange_rate) * FX_REVERT
    region.exchange_rate = max(0.5, min(2.0, region.exchange_rate))
    region.exchange_rate_log.append(region.exchange_rate)


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
    # ---- Step 1: arrive expired pipeline entries ----
    new_pipeline = []
    for entry in self.transport_pipeline:
        entry['turns_left'] -= 1
        if entry['turns_left'] <= 0:
            good = entry['good']
            self.inventory_foreign[good.value] += entry['quantity']
        else:
            new_pipeline.append(entry)
    self.transport_pipeline = new_pipeline

    # ---- Step 2: consume transport units to move export goods ----
    transport_units = self.inventory[Goods.transport.value]
    transport_capacity = _transport_capacity_per_unit()
    max_movable = transport_units * transport_capacity
    total_moved = 0

    for good in list(Goods):
        if good == Goods.none or good == Goods.transport:
            continue
        qty = self.inventory_export[good.value]
        if qty <= 0:
            continue
        movable = min(qty, max_movable - total_moved)
        if movable <= 0:
            continue
        self.transport_pipeline.append({
            'turns_left': self.transport_delay,
            'good': good,
            'quantity': movable,
        })
        self.inventory_export[good.value] -= movable
        total_moved += movable

    # Consume transport units: ceil(total_moved / capacity)
    if total_moved > 0:
        consumed = _div_ceil(total_moved, transport_capacity)
        self.inventory[Goods.transport.value] -= min(consumed, self.inventory[Goods.transport.value])

    # Transport is a perishable service: any leftover decays each turn
    self.inventory[Goods.transport.value] = 0

def _transport_capacity_per_unit():
    """Goods moved per transport unit (from recipe). Returns 10 as default."""
    from econsim_states import recipes
    return recipes.get(Goods.transport, {}).get('capacity', 10)

def _div_ceil(a, b):
    """Integer ceiling division: ceil(a / b)."""
    return (a + b - 1) // b


from agent import Agent
Agent._process_pipeline = _agent_process_pipeline


def foreign_sell(t, destination_region, source_region):
    sname = source_region.name
    # Use cached trader list (maintained on Region) — avoid O(N) filter per call
    traders = [a for a in source_region.trader_agents
               if a.home_region == sname]
    use_fx = (getattr(source_region, 'forex', None) is not None
              and getattr(source_region, 'home_currency', None) is not None)
    dest_currency = destination_region.home_currency
    total_sold_value = 0.0
    total_sold_quantity = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    total_trader_profit = 0.0
    total_bank_recycle = 0.0
    total_tariff = 0.0

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furniture]:
            qty = trader.inventory_foreign[good.value]
            if qty <= 0:
                continue
            price = destination_region.recipes[good]['price']
            ask_price = price * 0.95
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

                if destination_region.gov.trader_recycling_enabled:
                    bank_share = cash * destination_region.gov.trader_recycling_rate
                    trader_share -= bank_share
                if destination_region.gov.import_tariff_enabled:
                    tariff_share = cash * destination_region.gov.import_tariff_rate
                    trader_share -= tariff_share

                if use_fx:
                    fx.fx_add(trader, dest_currency, trader_share)
                else:
                    trader.cash += trader_share
                trader._trader_revenue += trader_share
                if bank_share > 0:
                    destination_region.bank.total_deposits += bank_share
                if tariff_share > 0:
                    destination_region.gov.agent.cash += tariff_share
                total_trader_profit += trader_share
                total_bank_recycle += bank_share
                total_tariff += tariff_share
                old_quantity = buyer.inv_get(good, 0)
                old_cost = buyer.cost_get(good, 0)
                buyer.cost_set(good, ((old_quantity * old_cost + bought * ask_price) / (old_quantity + bought)) if (old_quantity + bought) > 0 else ask_price)
                buyer.inv_add(good, bought)
                remaining -= bought
                total_sold_quantity += bought
                total_sold_value += cash
                trade_volumes[good] += bought
                trade_values[good] += cash
            trader.inventory_foreign[good.value] = remaining

        # Traders buy food for themselves at the destination out of sales
        # proceeds (they are away from home and must eat from local markets).
        if trader.inv_get(Goods.food, 0) < 8:
            food_price = destination_region.recipes[Goods.food]['price']
            need = 8 - trader.inv_get(Goods.food, 0)
            if use_fx:
                wallet_bal = fx.fx_balance(trader, dest_currency)
                afford = int(wallet_bal / food_price) if food_price > 0 else 0
            else:
                afford = int(trader.cash / food_price) if food_price > 0 else 0
            to_buy = min(need, afford)
            if to_buy > 0:
                sellers = [a for a in destination_region.agents
                           if a.output == Goods.food
                           and a.inv_get(Goods.food, 0) > 2
                           and not getattr(a, 'is_trader', False)]
                bought = 0
                for seller in sellers:
                    if bought >= to_buy:
                        break
                    available = seller.inv_get(Goods.food, 0) - 2
                    if available <= 0:
                        continue
                    take = min(available, to_buy - bought)
                    seller.inv_add(Goods.food, -take)
                    seller.cash += take * food_price
                    if use_fx:
                        fx.fx_sub(trader, dest_currency, take * food_price)
                    else:
                        trader.cash -= take * food_price
                    trader.inv_add(Goods.food, take)
                    bought += take

    if use_fx:
        fx.repatriate_traders(traders, source_region, t)

    if total_sold_value > 0 and t % 50 == 0:
        loginfo(t, f"TRADE {source_region.name}->{destination_region.name}: "
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

    region_a = Region("Region_A", t=0, number_of_agents=55,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037})
    region_b = Region("Region_B", t=0, number_of_agents=55,
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

    fx.connect_regions(region_a, region_b, t=0)
    currencies = [region_a.home_currency, region_b.home_currency]

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    # Instrument diagnostics so they record from THIS simulation run
    wealth_lineage.init_collectors()
    wealth_diagnostic.init_collectors()

    for t in range(1, time_steps + 1):
        curr_before = {c: fx.audit_currency_total([region_a, region_b], c)
                       for c in currencies}
        cash_before = sum(curr_before.values())
        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)
        wealth_lineage.record_turn(t, region_a, region_b)
        wealth_diagnostic.record_turn(t, region_a, region_b)
        cash_after = sum(fx.audit_currency_total([region_a, region_b], c)
                         for c in currencies)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after-cash_before:.2f}")

        for c in currencies:
            delta = fx.audit_currency_total([region_a, region_b], c) - curr_before[c]
            if abs(delta) > 5.0:
                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")

        for region, other in [(region_a, region_b), (region_b, region_a)]:
            turn_export = sum(region.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.export_val[g])
            turn_import = sum(region.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if region.import_val[g])
            region.cumulative_trade_balance += (turn_export - turn_import)
            region.trade_flow_log.append(turn_export - turn_import)
            update_exchange_rate(region)

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
    wealth_lineage.generate_plots(time_steps, region_a, region_b)
    wealth_diagnostic.generate_plots(time_steps, region_a, region_b)

    print("\n" + "=" * 60)
    print("FINAL SUMMARY =")
    print("=" * 60)

    for region in (region_a, region_b):
        print(f"\n--- {region.name} ---")
        labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furniture: 'Furniture',
                  Goods.transport: 'Transport', Goods.gov: 'Gov'}
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
        # Charity summary
        c = region.charity.log
        print(f"  Charity: ${c['donations_collected']:.2f} collected, "
              f"{c['food_distributed']} food to {c['recipients']} recipients, "
              f"{c['food_purchased']} purchased")

        # Trader summary
        traders = [a for a in region.agents if a.is_trader]
        print(f"  Traders: {len(traders)} traders, "
              f"${sum(a.cash for a in traders):.2f} total cash, "
              f"ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}->${final_trader_cash:.0f})")

        desk = getattr(region, "forex", None)
        if desk is not None:
            bank = region.bank
            print(f"  FX Desk: mid={desk.mid:.4f} ({region.home_currency} per 1 "
                  f"{desk.other}), spread={desk.spread:.2%}, "
                  f"reserves={ {k: round(v, 2) for k, v in dict(bank.foreign_reserves).items()} }, "
                  f"fx_pool=${bank.fx_pool:.2f}")

    print("\nDone.")


if __name__ == "__main__":
    main()