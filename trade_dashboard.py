#!/usr/bin/env python3
"""
Trade dashboard: macro view of a two-region economy.

Generates a single multi-panel PNG (trade_dashboard.png) describing the
state and execution of the two-region sim from the trade-economist's
perspective:

  Row 1 — Trade balance & integration:
    (A) Net exports  = export_val - import_val per turn per region
    (B) Trade openness = (exports + imports) / GDP per turn per region
    (C) Import composition per region (stacked area, by good)

  Row 2 — Prices & FX:
    (D) Law-of-one-price convergence: |price_A - price_B| per good
    (E) Nominal vs real exchange rate, per region
    (F) Terms of trade index = export price idx / import price idx

  Row 3 — External financing & real health:
    (G) Balance of payments: foreign reserves + net trader FX wallets
    (H) Pipeline depth & unsold foreign inventory (supply-chain stress)
    (I) Real per-capita GDP overlay (region A vs B)

All panels read from the Region logs already produced by the sim; no
new simulation logging is required.  Uses the 10-turn rolling average
convention from region._smooth where trends matter.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from goods import Goods

OUTPUT_FILE = "trade_dashboard.png"

# Standard economist colors
COLORS = {
    'A': '#1f77b4',
    'B': '#d62728',
}


def _smooth(data, window=10):
    """10-turn rolling average, matching region._smooth."""
    if len(data) < window:
        return data
    result = list(data[:window - 1])
    for i in range(window - 1, len(data)):
        result.append(sum(data[i - window + 1:i + 1]) / window)
    return result


def _export_val(region, good):
    return region.export_val.get(good, [0])


def _import_val(region, good):
    return region.import_val.get(good, [0])


def _gdp_series(region):
    return region.gdp_log or [0] * len(region.total_cash_log)


def _exports_total(region):
    """Per-turn total export value across trade goods."""
    n = max(len(region.export_val[g]) for g in [Goods.food, Goods.wood, Goods.furniture])
    out = []
    for i in range(n):
        out.append(sum(region.export_val[g][i] for g in [Goods.food, Goods.wood, Goods.furniture]
                       if i < len(region.export_val[g])))
    return out


def _imports_total(region):
    """Per-turn total import value across trade goods."""
    n = max(len(region.import_val[g]) for g in [Goods.food, Goods.wood, Goods.furniture])
    out = []
    for i in range(n):
        out.append(sum(region.import_val[g][i] for g in [Goods.food, Goods.wood, Goods.furniture]
                       if i < len(region.import_val[g])))
    return out


def _net_exports(region):
    ex = _exports_total(region)
    im = _imports_total(region)
    return [e - i for e, i in zip(ex, im)]


def _real_exchange_rate(region, other):
    """Nominal rate adjusted for price levels (CPI proxy = cost of living).

    real = nominal * (home_CPI / foreign_CPI).  A value > 1 means home goods
    are expensive relative to foreign after conversion.  Uses the per-turn
    cost_of_living_log when available so the real rate tracks inflation.
    """
    nominal = region.exchange_rate_log or [region.exchange_rate]
    home_col = region.cost_of_living_log or [region.cost_of_living]
    other_col = other.cost_of_living_log or [other.cost_of_living]
    real = []
    for i, rate in enumerate(nominal):
        h = home_col[i] if i < len(home_col) else home_col[-1]
        o = other_col[i] if i < len(other_col) else other_col[-1]
        real.append(rate * (max(0.1, h) / max(0.1, o)))
    return real


def _terms_of_trade(region, other):
    """Export price index / import price index per turn.

    Using each good's recipe price and the region's export/import mix as
    weights.  Rising ToT = each unit of exports buys more imports.
    """
    goods = [Goods.food, Goods.wood, Goods.furniture]
    n = max(len(region.export_val[g]) for g in goods)
    tot = []
    for i in range(n):
        export_weight = sum(region.export_val[g][i] for g in goods if i < len(region.export_val[g]))
        import_weight = sum(region.import_val[g][i] for g in goods if i < len(region.import_val[g]))
        if export_weight <= 0 or import_weight <= 0:
            tot.append(1.0)
            continue
        # Value-weighted average price of what is exported vs imported
        exp_price = sum(region.export_val[g][i] for g in goods if i < len(region.export_val[g])) / max(1, export_weight)
        imp_price = sum(region.import_val[g][i] for g in goods if i < len(region.import_val[g])) / max(1, import_weight)
        tot.append(exp_price / max(0.01, imp_price))
    return tot


def generate_dashboard(region_a, region_b, filename=OUTPUT_FILE):
    """Produce trade_dashboard.png from two Region objects."""
    goods = [Goods.food, Goods.wood, Goods.furniture]
    color_map = {Goods.food: 'green', Goods.wood: 'red', Goods.furniture: 'blue'}

    fig, axes = plt.subplots(3, 3, figsize=(18, 13))
    fig.suptitle("Two-Region Trade Dashboard", fontsize=16, y=0.98)

    # ---------- A: Net exports ----------
    ax = axes[0, 0]
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
    ax.plot(_smooth(_net_exports(region_a)), label='Region A', color=COLORS['A'])
    ax.plot(_smooth(_net_exports(region_b)), label='Region B', color=COLORS['B'])
    ax.set_title("Net Exports (export val - import val)")
    ax.set_ylabel("Value / turn")
    ax.legend()

    # ---------- B: Trade openness ----------
    ax = axes[0, 1]
    for region, label, col in [(region_a, 'Region A', COLORS['A']),
                               (region_b, 'Region B', COLORS['B'])]:
        gdp = _gdp_series(region)
        open_ = [(e + i) / max(1.0, g) for e, i, g in zip(_exports_total(region),
                                                          _imports_total(region), gdp)]
        ax.plot(_smooth(open_), label=label, color=col)
    ax.set_title("Trade Openness (exports + imports) / GDP")
    ax.set_ylabel("Ratio")
    ax.legend()

    # ---------- C: Import composition stacked ----------
    ax = axes[0, 2]
    for region, label, col in [(region_a, 'Region A', COLORS['A']),
                               (region_b, 'Region B', COLORS['B'])]:
        x = list(range(len(_imports_total(region))))
        bottom = [0] * len(x)
        for g in goods:
            vals = region.import_val.get(g, [0])
            vals = vals + [0] * (len(x) - len(vals))
            ax.bar(x, vals, bottom=bottom, width=1.0, label=f"{label} {Goods(g).name}",
                   color=color_map[g], alpha=0.6 if label == 'Region A' else 0.35)
            bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("Import Composition (value, stacked)")
    ax.set_ylabel("Value / turn")
    ax.legend(fontsize='small', ncol=2)

    # ---------- D: Law of one price ----------
    ax = axes[1, 0]
    for g in goods:
        spread = region_a.price_spread_log.get(g, [])
        ax.plot(_smooth(spread), label=Goods(g).name, color=color_map[g])
    ax.set_yscale('log', base=2)
    ax.set_title("Price Convergence |price A - price B| (log2)")
    ax.set_ylabel("Spread $")
    ax.legend()

    # ---------- E: Nominal vs real exchange rate ----------
    ax = axes[1, 1]
    ax.plot(_smooth(region_a.exchange_rate_log), label='Nominal A', color=COLORS['A'], linestyle='--')
    ax.plot(_smooth(region_b.exchange_rate_log), label='Nominal B', color=COLORS['B'], linestyle='--')
    ax.plot(_smooth(_real_exchange_rate(region_a, region_b)), label='Real A', color=COLORS['A'])
    ax.plot(_smooth(_real_exchange_rate(region_b, region_a)), label='Real B', color=COLORS['B'])
    ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=0.5)
    ax.set_title("Exchange Rate: Nominal (--) vs Real")
    ax.set_ylabel("Rate")
    ax.legend()

    # ---------- F: Terms of trade ----------
    ax = axes[1, 2]
    ax.plot(_smooth(_terms_of_trade(region_a, region_b)), label='Region A', color=COLORS['A'])
    ax.plot(_smooth(_terms_of_trade(region_b, region_a)), label='Region B', color=COLORS['B'])
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.5)
    ax.set_title("Terms of Trade (export px / import px)")
    ax.set_ylabel("Index")
    ax.legend()

    # ---------- G: Balance of payments / reserves ----------
    ax = axes[2, 0]
    for region, label, col in [(region_a, 'Region A', COLORS['A']),
                               (region_b, 'Region B', COLORS['B'])]:
        partner_cur = region_a.name if region is region_b else region_b.name
        # Per-turn snapshots (list of {currency: amount}) when available;
        # otherwise fall back to the current balance repeated.
        if region.foreign_reserves_log:
            reserves = [snap.get(partner_cur, 0.0) for snap in region.foreign_reserves_log]
        else:
            reserves = [region.bank.foreign_reserves.get(partner_cur, 0.0)] * len(region.total_cash_log)
        ax.plot(_smooth(reserves), label=f"{label} reserves", color=col)
    ax.set_title("Foreign Reserves (partner currency)")
    ax.set_ylabel("Reserve units")
    ax.legend()

    # ---------- H: Pipeline / unsold foreign inventory ----------
    ax = axes[2, 1]
    for region, label, col in [(region_a, 'Region A', COLORS['A']),
                               (region_b, 'Region B', COLORS['B'])]:
        ax.plot(_smooth(region.pipeline_depth_log), label=f"{label} in-transit", color=col)
        stuck = []
        for i in range(len(region.total_cash_log)):
            stuck.append(sum(a.inventory_foreign[g.value] for a in region.trader_agents
                             for g in [Goods.food, Goods.wood, Goods.furniture]))
        ax.plot(_smooth(stuck), label=f"{label} unsold-foreign", color=col, linestyle='--')
    ax.set_title("Supply-chain stress: in-transit vs unsold imports")
    ax.set_ylabel("Units")
    ax.legend()

    # ---------- I: Real per-capita GDP overlay ----------
    ax = axes[2, 2]
    for region, label, col in [(region_a, 'Region A', COLORS['A']),
                               (region_b, 'Region B', COLORS['B'])]:
        pop = region.total_population or [1] * len(region.gdp_log)
        per_cap = [g / max(1, p) for g, p in zip(region.gdp_log, pop)]
        # Deflate by food price (proxy for purchasing power)
        price = region.price_log.get(Goods.food, [1.0])
        real = [v / max(0.1, (price[i] if i < len(price) else price[-1])) for i, v in enumerate(per_cap)]
        ax.plot(_smooth(real), label=label, color=col)
    ax.set_title("Real per-capita GDP (deflated by food price)")
    ax.set_ylabel("Units / agent")
    ax.legend()

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(filename)
    plt.close(fig)
    print(f"  Trade dashboard saved to {filename}")


def main(time_steps=60):
    """Standalone driver: build two regions, run, and produce the dashboard."""
    import random
    import econsim_two_region as sim
    from transporter import Route

    random.seed(42)
    region_a = sim.Region("Region_A", t=0, number_of_agents=200,
                          profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furniture: 0.037},
                          number_of_traders=3)
    region_b = sim.Region("Region_B", t=0, number_of_agents=200,
                          profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furniture: 0.05},
                          number_of_traders=3)
    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2
    region_a.destination_region = region_b
    region_b.destination_region = region_a
    for tr in region_a.agents:
        if getattr(tr, 'is_trader', False):
            tr.destination_region = region_b
    for tr in region_b.agents:
        if getattr(tr, 'is_trader', False):
            tr.destination_region = region_a
    region_a.route = Route("A->B", region_a, region_b, base_delay=sim.TRANSPORT_DELAY)
    region_b.route = Route("B->A", region_b, region_a, base_delay=sim.TRANSPORT_DELAY)
    sim.fx.connect_regions(region_a, region_b, t=0)

    for t in range(1, time_steps + 1):
        region_a.pending_imports = sim._pending_imports(region_a, region_b)
        region_b.pending_imports = sim._pending_imports(region_b, region_a)
        region_a._auction_import_sales = {}
        region_b._auction_import_sales = {}
        region_a.step(t)
        region_b.step(t)
        region_a.route.advance()
        region_a.route.deliver_pending()
        region_b.route.advance()
        region_b.route.deliver_pending()
        sim.settle_trade(t, region_a, region_b)
        sim.settle_trade(t, region_b, region_a)
        sim.fx.cycle_market(region_a, region_b, t)
        # Mirror the two-region driver: update FX so exchange_rate_log fills.
        sim.update_exchange_rate(region_a)
        sim.update_exchange_rate(region_b)
        region_a.foreign_reserves_log.append(dict(region_a.bank.foreign_reserves))
        region_b.foreign_reserves_log.append(dict(region_b.bank.foreign_reserves))

    generate_dashboard(region_a, region_b)


if __name__ == "__main__":
    import sys
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    main(steps)