#!/usr/bin/env python3
"""
3-nation x 2-tile simulation (M0.5).

Three Nations each own two tiles (Regions) on a 2x3 map.  Same-nation tiles
share the nation's currency (Nation.currency seam).  Each tile has terrain
advantages; tiles are neighbors in a grid.  One Route + one ForexDesk per
neighbor pair.  Runs `time_steps` turns, audits every nation currency every
turn, and emits a tile-map sketch (M0.6).

Usage:
    python3 sim_nation.py [time_steps]
"""

import sys
import random

from goods import Goods
from region import Region
from nation import Nation
from logger import logInit
import forex as fx
from world_trade import (pending_imports, resolve_parked, settle_trade,
                         trader_wealth)
from regime import step_regime


def make_tile(name, prof, terrain=None, climate='temperate'):
    # 200 agents / 2 traders per tile: proven-stable population with fewer
    # concurrent FX-book positions, so the engine's per-turn FX round-off
    # stays below the 5.0 audit alert threshold at 6-tile scale.
    return Region(name, t=0, number_of_agents=200,
                  profession_distribution=prof,
                  number_of_traders=2,
                  terrain=terrain, climate=climate)


def wire_neighbors(tiles, edges):
    """Register directed neighbor/route relationships from undirected edges.

    M0.5 wires ONLY cross-nation trade routes.  A nation may own several
    tiles (provinces), but intra-nation trade is DEFERRED to the currency-
    union money phase: same-currency internal trade needs reserve-disciplined
    settlement (like the FX desks that keep the ring solvent), which is the
    documented seam behind Nation.currency.  This keeps M0.5 on the proven
    per-currency machinery: every wired route settles through a real desk.
    """
    for a, b in edges:
        if a.owner_nation is not b.owner_nation:
            a.add_neighbor(b)
            b.add_neighbor(a)
            fx.connect_desks(a, b, t=0)


def build_world():
    profs = {Goods.food: 0.60, Goods.wood: 0.25, Goods.furniture: 0.08}
    alpha_food = make_tile("A1", profs, terrain={Goods.food: 1.6})
    alpha_plain = make_tile("A2", profs)
    beta_wood = make_tile("B1", profs, terrain={Goods.wood: 1.6})
    beta_plain = make_tile("B2", profs)
    gamma_plain = make_tile("G1", profs)
    gamma_cold = make_tile("G2", profs, climate='cold')

    tiles = [alpha_food, alpha_plain, beta_wood, beta_plain,
             gamma_plain, gamma_cold]

    # 2x3 grid: row0 A1 A2; row1 B1 B2; row2 G1 G2
    edges = [
        (alpha_food, alpha_plain),        # A internal
        (beta_wood, beta_plain),          # B internal
        (gamma_plain, gamma_cold),        # G internal
        (alpha_food, beta_wood),          # A-B border
        (alpha_plain, beta_plain),        # A-B border
        (beta_wood, gamma_plain),         # B-G border
        (beta_plain, gamma_cold),         # B-G border
    ]

    # Nations wrap tiles BEFORE FX wiring so home_currency is the nation's.
    alpha = Nation("Alpha", currency="AL", regime_type="autocracy")
    beta = Nation("Beta", currency="BE", regime_type="oligarchy")
    gamma = Nation("Gamma", currency="GA", regime_type="democracy")

    alpha.add_tile(alpha_food)
    alpha.add_tile(alpha_plain)
    beta.add_tile(beta_wood)
    beta.add_tile(beta_plain)
    gamma.add_tile(gamma_plain)
    gamma.add_tile(gamma_cold)

    wire_neighbors(tiles, edges)

    for r in tiles:
        r._init_trader_wealth = trader_wealth(r)
    return tiles, [alpha, beta, gamma]


def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    logInit()
    print(f"Nation Simulation (3 nations x 2 tiles): {time_steps} turns\n")
    random.seed(42)

    tiles, nations = build_world()
    currencies = [n.currency for n in nations]
    pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                   and r.neighbors.get(o.name) is not None]

    print("Nations:", ", ".join(f"{n.name}({n.currency})" for n in nations))
    for n in nations:
        print(f"  {n.name}: tiles={[t.name for t in n.tiles]}, "
              f"legitimacy={n.legitimacy}")

    for t in range(1, time_steps + 1):
        curr_before = {c: fx.audit_currency_total(tiles, c) for c in currencies}
        cash_before = sum(curr_before.values())

        for r in tiles:
            pending = {}
            for other in tiles:
                if other is r or other not in r.neighbors.values():
                    continue
                for g, entries in pending_imports(r, other).items():
                    pending.setdefault(g, []).extend(entries)
            r.pending_imports = pending
            r._auction_import_sales = {}

        for r in tiles:
            r.step(t)

        for r in tiles:
            for rt in r._all_routes():
                rt.advance()
                rt.deliver_pending()

        resolve_parked(tiles)

        for r, other in pair_orders:
            settle_trade(t, other, r)

        fx.cycle_all_markets(tiles, t)

        # M3: regime bookkeeping per nation (elections / coups / legitimacy).
        for n in nations:
            step_regime(n, t)

        for r, other in pair_orders:
            desk = r.forex_desks.get(other.name)
            if desk is not None:
                ppp = max(0.1, other.cost_of_living) / max(0.1, r.cost_of_living)
                desk.update(0, bank=r.bank, fx_regime='managed', ppp_target=ppp)
                if getattr(r, 'destination_region', None) is other:
                    desk.save_rate(r)

        for c in currencies:
            delta = fx.audit_currency_total(tiles, c) - curr_before[c]
            if abs(delta) > 5.0:
                print(f"  T={t}: CURRENCY {c!r} SUPPLY SHIFT ${delta:.2f}")
        cash_after = sum(fx.audit_currency_total(tiles, c) for c in currencies)
        if abs(cash_after - cash_before) > 5.0:
            print(f"  T={t}: COMBINED CASH LEAK ${cash_after - cash_before:.2f}")

        for r in tiles:
            for other in tiles:
                if other is r or other not in r.neighbors.values():
                    continue
                turn_export = sum(r.export_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.export_val[g])
                turn_import = sum(r.import_val[g][-1]
                                  for g in [Goods.food, Goods.wood, Goods.furniture]
                                  if r.import_val[g])
                r.cumulative_trade_balance += (turn_export - turn_import)
                r.trade_flow_log.append(turn_export - turn_import)

        if t % 50 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\n" + "=" * 60)
    print("NATION FINAL SUMMARY")
    print("=" * 60)
    for n in nations:
        print(f"\n--- Nation {n.name} ({n.currency}) ---")
        gdp = 0.0
        exports = 0.0
        imports = 0.0
        pop = 0
        food_prices = []
        for r in n.tiles:
            gdp += r.gdp_log[-1] if r.gdp_log else 0
            exports += sum(sum(v) for v in r.export_val.values())
            imports += sum(sum(v) for v in r.import_val.values())
            pop += r.total_population[-1] if r.total_population else 0
            food_prices.append(r.recipes[Goods.food]['price'])
            print(f"    {r.name}: pop={r.total_population[-1] if r.total_population else 0}, "
                  f"food=${r.recipes[Goods.food]['price']:.2f}")
        print(f"  GDP/turn: ${gdp:.0f}")
        print(f"  Exports: ${exports:.2f}, Imports: ${imports:.2f}, "
              f"Balance: {exports - imports:+.2f}")
        print(f"  Total Pop: {pop}, food prices: "
              + ", ".join(f"{p:.2f}" for p in food_prices))
        tr = n.treasury()
        print(f"  Treasury: ${tr['total']:.2f} ({tr['cash']:.2f} cash, "
              f"{tr['deposits']:.2f} deposits, {tr['food']} food)")
        init_w = sum(getattr(r, '_init_trader_wealth', 0.0) for r in n.tiles)
        fin_w = sum(trader_wealth(r) for r in n.tiles)
        roi = (fin_w - init_w) / init_w * 100 if init_w > 0 else 0.0
        print(f"  Trader wealth: ${fin_w:.2f} (start ${init_w:.2f}), "
              f"ROI: {roi:.1f}%")

    draw_map(tiles, nations, "tile_map.png")
    print("\nDone.")


def draw_map(tiles, nations, filename="tile_map.png"):
    """M0.6 tile-map sketch: nation tint + terrain glyphs + neighbor edges."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    # Place tiles on the 2x3 grid by name (A1 A2 / B1 B2 / G1 G2).
    coords = {}
    rows = {"A": 0, "B": 1, "G": 2}
    cols = {"1": 0, "2": 1}
    for r in tiles:
        row = rows[r.name[0]]
        col = cols[r.name[1]]
        coords[r.name] = (col, row)

    nation_colors = {}
    palette = ["#8dd3c7", "#ffffb3", "#bebada"]
    for i, n in enumerate(nations):
        nation_colors[n.name] = palette[i % len(palette)]

    fig, ax = plt.subplots(figsize=(7, 9))
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(-0.6, 2.6)
    ax.set_aspect('equal')
    ax.axis('off')

    # Neighbor edges from any tile's routes
    seen = set()
    for r in tiles:
        for name, other in r.neighbors.items():
            key = tuple(sorted((r.name, name)))
            if key in seen:
                continue
            seen.add(key)
            (x1, y1), (x2, y2) = coords[r.name], coords[name]
            ax.plot([x1, x2], [y1, y2], color='gray', lw=1.5, zorder=1)

    # Tiles
    for r in tiles:
        x, y = coords[r.name]
        owner = r.owner_nation.name if getattr(r, 'owner_nation', None) else '?'
        color = nation_colors.get(owner, "#cccccc")
        ax.add_patch(Rectangle((x - 0.4, y - 0.4), 0.8, 0.8,
                               facecolor=color, edgecolor='black', zorder=2))
        terrain_glyph = ""
        if r.terrain.get(Goods.food, 1.0) > 1.3:
            terrain_glyph = "\U0001F33E"  # wheat
        if r.terrain.get(Goods.wood, 1.0) > 1.3:
            terrain_glyph += "\U0001F333"  # tree
        if r.climate == "cold":
            terrain_glyph += "\u2744"  # snowflake
        ax.text(x, y + 0.24, f"{r.name} {terrain_glyph}".strip(),
                ha='center', va='center', fontsize=11, fontweight='bold',
                zorder=3)
        pop = r.total_population[-1] if r.total_population else 0
        food = r.recipes[Goods.food]['price']
        ax.text(x, y - 0.08, f"pop {pop}\nfood ${food:.2f}",
                ha='center', va='center', fontsize=8, zorder=3)

    # Legend
    handles = [Rectangle((0, 0), 1, 1, facecolor=nation_colors[n.name])
               for n in nations]
    names = [f"{n.name} ({n.currency})" for n in nations]
    ax.legend(handles, names, loc='upper center', bbox_to_anchor=(0.5, 1.06),
              ncol=3, frameon=False, fontsize=9)
    ax.set_title("REGNUM M0 tile map (nations / farm / forest / snow)",
                 fontsize=11)
    plt.tight_layout()
    plt.savefig(filename, dpi=110)
    plt.close(fig)
    print(f"Tile map saved to {filename}")


if __name__ == "__main__":
    main()