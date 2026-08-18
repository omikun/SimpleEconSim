"""
Plotting and chart visualization for Region metrics.
"""

from statistics import mean
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from goods import Goods


def smooth(data, window=10):
    """10-turn rolling average. First (window-1) points use raw values."""
    if len(data) < window:
        return data
    result = list(data[:window - 1])
    for i in range(window - 1, len(data)):
        result.append(sum(data[i - window + 1:i + 1]) / window)
    return result


def plot_population(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Population vs time")
    axis[axis_id].set_ylabel("Population")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        axis[axis_id].plot(region.population_log[g], label=labels[g],
                           color=colors[g])
    if 'trader' in region.population_log and any(v > 0 for v in region.population_log['trader']):
        axis[axis_id].plot(region.population_log['trader'], label='Trader',
                           color='orange')
    axis[axis_id].plot(region.total_population, label='total', color='black')
    axis[axis_id].plot([-x for x in region.dead_starved_population], label='dead', color='purple')


def plot_inventory(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Inventory vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Inventory")
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(smooth(region.inventory_log[g]), label=labels[g],
                               color=colors[g])
    if 'trader' in region.inventory_log and any(v > 0 for v in region.inventory_log['trader']):
        axis[axis_id].plot(smooth(region.inventory_log['trader']), label='Trader',
                           color='orange')


def plot_gini(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Gini coefficient")
    axis[axis_id].set_ylabel("Cash")
    for g in region.goods:
        axis[axis_id].plot(region.gini_log[g], label=labels[g],
                           color=colors[g])


def plot_demand_ratio(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Demand Ratio vs time")
    axis[axis_id].set_ylabel("Demand Ratio (log scale)")
    axis[axis_id].set_yscale('log')
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(region.demand_ratio_log[g], label=labels[g],
                               color=colors[g])


def plot_production(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Production vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Units/round")
    axis[axis_id].set_yscale('log')
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(smooth(region.production_log[g]), label=labels[g],
                               color=colors[g])


def plot_per_capita_inventory(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Inventory Per capita (excl producers)")
    axis[axis_id].set_ylabel("Inv per cap")
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(region.per_capita_inventory[g], label=labels[g],
                               color=colors[g])


def plot_cash(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Cash vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Cash")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        axis[axis_id].plot(smooth(region.cash_log[g]), label=labels[g],
                           color=colors[g])
    if 'trader' in region.cash_log and any(v > 0 for v in region.cash_log['trader']):
        axis[axis_id].plot(smooth(region.cash_log['trader']), label='Trader',
                           color='orange')
    axis[axis_id].plot(smooth(region.total_cash_log), label='total', color='black')
    axis[axis_id].plot(smooth(region.bank_cash_log), label='bank', color='purple')
    axis[axis_id].set_ylim(bottom=2 ** -3)


def plot_demand(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Demand vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Demand (log)")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(smooth(region.demand_log[g]), label=labels[g],
                               color=colors[g])


def plot_sold(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Sold vs time")
    axis[axis_id].set_ylabel("Sold (log)")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(region.sold_log[g], label=labels[g],
                               color=colors[g])


def plot_price(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Price vs time")
    axis[axis_id].set_ylabel("Price")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(region.price_log[g], label=labels[g],
                               color=colors[g])


def plot_hunger(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Hunger vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Num hungry")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        axis[axis_id].plot(smooth(region.hungry_log[g]), label=labels[g],
                           color=colors[g])
    if 'trader' in region.hungry_log and any(v > 0 for v in region.hungry_log['trader']):
        axis[axis_id].plot(smooth(region.hungry_log['trader']), label='Trader',
                           color='orange')


def plot_supply(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Supply vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Supply (log)")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(smooth(region.supply_log[g]), label=labels[g],
                               color=colors[g])


def plot_population_change_rate(region, axis, axis_id):
    axis[axis_id].set_title("Pop Change Rate (per 10 turns %)")
    axis[axis_id].set_ylabel("% change")
    axis[axis_id].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    axis[axis_id].plot(region.population_change_rate_log, color='black')


def plot_gdp(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("GDP vs time (10-turn avg)")
    axis[axis_id].set_ylabel("Total GDP (value)")
    axis[axis_id].set_yscale('log', base=2)
    for g in region.goods:
        if g != Goods.gov:
            axis[axis_id].plot(smooth(region.gdp_by_profession_log[g]), label=labels[g],
                               color=colors[g])
    if 'trader' in region.gdp_by_profession_log and any(v > 0 for v in region.gdp_by_profession_log['trader']):
        axis[axis_id].plot(smooth(region.gdp_by_profession_log['trader']), label='Trader',
                           color='orange')
    axis[axis_id].plot(smooth(region.gdp_log), label='All', color='black')


def plot_purchases(region, axis, axis_id, colors, labels):
    titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
    for i in range(len(titles)):
        axis[axis_id + i].set_title(titles[i] + " Purchases")
        axis[axis_id + i].set_ylabel("Bought")
    i = 0
    for prof in region.goods:
        for g in region.goods:
            axis[axis_id + i].plot(region.bought_log[prof][g], label=labels[g],
                                   color=colors[g])
        i += 1


def plot_trade_balance(region, axis, axis_id):
    axis[axis_id].set_title("Trade Balance")
    axis[axis_id].set_ylabel("Export - Import ($)")
    axis[axis_id].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    axis[axis_id].plot(region.trade_balance_log, color='black')


def plot_exchange_rate(region, axis, axis_id):
    axis[axis_id].set_title("Exchange Rate (10-turn avg)")
    axis[axis_id].set_ylabel("Rate")
    if region.exchange_rate_log:
        data = smooth(region.exchange_rate_log)
        axis[axis_id].plot(data, color='purple', marker='o', markersize=1)
    else:
        raw = [region.exchange_rate] * len(region.total_cash_log)
        axis[axis_id].plot(smooth(raw), color='purple', marker='o', markersize=1)


def plot_trader_cash(region, axis, axis_id):
    axis[axis_id].set_title("Trader Cash")
    axis[axis_id].set_ylabel("Cash")
    axis[axis_id].set_yscale('log', base=2)
    axis[axis_id].plot(region.trader_cash_log, color='orange')


def plot_pipeline_depth(region, axis, axis_id):
    axis[axis_id].set_title("Pipeline Depth")
    axis[axis_id].set_ylabel("Units in transit")
    axis[axis_id].plot(region.pipeline_depth_log, color='brown')


def plot_price_spread(region, axis, axis_id, colors, labels):
    axis[axis_id].set_title("Price Spread (A-B)")
    axis[axis_id].set_ylabel("Spread ($)")
    for g in [Goods.food, Goods.wood, Goods.furniture]:
        if region.price_spread_log.get(g):
            axis[axis_id].plot(region.price_spread_log[g], label=labels[g],
                               color=colors[g])


def plot_region(region, filename: str):
    """Generate a 5x4 grid of plots for a region."""
    figure, axis = plt.subplots(5, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(12)
    plt.subplots_adjust(top=0.95, bottom=0.04, hspace=0.35, wspace=0.25)
    colors = {
        Goods.food: 'green',
        Goods.wood: 'red',
        Goods.furniture: 'blue',
        Goods.transport: 'purple',
        Goods.gov: 'yellow',
    }
    labels = {
        Goods.food: 'Food',
        Goods.wood: 'Wood',
        Goods.furniture: 'Furniture',
        Goods.transport: 'Transport',
        Goods.gov: 'Gov',
    }
    axis_id = 0
    plot_population(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_inventory(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_gini(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_demand_ratio(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_production(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_per_capita_inventory(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_cash(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_demand(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_sold(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_price(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_hunger(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_supply(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_population_change_rate(region, axis, axis_id)
    axis_id += 1
    plot_gdp(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_purchases(region, axis, axis_id, colors, labels)
    axis_id += 1
    plot_trade_balance(region, axis, axis_id)
    axis_id += 1
    plot_exchange_rate(region, axis, axis_id)
    axis_id += 1
    plot_trader_cash(region, axis, axis_id)
    axis_id += 1
    plot_pipeline_depth(region, axis, axis_id)
    axis_id += 1
    plot_price_spread(region, axis, axis_id, colors, labels)

    handles, labels_list = [], []
    for ax in axis:
        h, l = ax.get_legend_handles_labels()
        for hi, li in zip(h, l):
            if li not in labels_list:
                handles.append(hi)
                labels_list.append(li)
    figure.legend(handles, labels_list, loc='upper right', ncol=1, fontsize='small')
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
    plt.savefig(filename)
    plt.close(figure)
    print(f"Plot saved to {filename}")
