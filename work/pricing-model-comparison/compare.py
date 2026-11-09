"""Illustrative controlled pricing comparison, not a full game simulation.

Run from the repository root: venv/bin/python work/pricing-model-comparison/compare.py
The game series calls the current update_price_ref implementation. Orders,
inventories and costs are synthetic; no auction settlement is simulated.
"""
from pathlib import Path
import csv
import json
import math
import os
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import sitecustomize  # noqa: E402,F401 -- repository's bare-module import paths

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/pricing-comparison-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from goods import Goods
from region_market import update_price_ref


def fixture():
    producer = SimpleNamespace(output=Goods.wood, is_trader=False,
                               inv_get=lambda good, default=0: 5)
    return SimpleNamespace(
        agents=[producer], _price_ref={Goods.wood: 10.0},
        recipes={Goods.wood: {'price': 10.0, 'maxinv': 10,
                             'numInput': 0, 'production': 1}},
        name='Synthetic', home_currency='TEST', abundance_enabled=True,
        wilderness=False, scenario_owner_policy=False, _last_turn=0,
    )


def demand(price):
    return 100 * (price / 10) ** -1


def supply(price, capacity):
    return min(capacity, 100 * (price / 10))


def main():
    feedback, quantity_only = fixture(), fixture()
    sticky_price = 10.0
    rows = []
    for turn in range(101):
        shock = 10 <= turn < 15
        capacity = 60 if shock else 120
        equilibrium = max(10.0, 10 * 100 / capacity)
        if turn:
            for region, responsive in ((feedback, True), (quantity_only, False)):
                price = region._price_ref[Goods.wood]
                bids = demand(price) if responsive else 100
                asks = supply(price, capacity) if responsive else min(100, capacity)
                region._last_turn = turn
                update_price_ref(region, Goods.wood, bids / asks,
                                 local_asks=asks, imported_asks=0, bids=bids)
            speed = .5 if equilibrium > sticky_price else .1
            sticky_price *= math.exp(speed * math.log(equilibrium / sticky_price))
        rows.append(dict(turn=turn, capacity=capacity, equilibrium=equilibrium,
                         game_elastic=feedback._price_ref[Goods.wood],
                         game_fixed_orders=quantity_only._price_ref[Goods.wood],
                         asymmetric_target=sticky_price))

    assert abs(rows[-1]['game_elastic'] - 10) < .001
    assert abs(rows[-1]['asymmetric_target'] - 10) < .001
    assert rows[-1]['game_fixed_orders'] > 11
    output = Path(__file__).resolve().parent
    with (output / 'comparison.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'scope': 'Synthetic reference-rule comparison; no full-game or auction run',
        'shock': 'Capacity 120 to 60 during turns 10-14, then fully restored',
        'controls': 'Constant costs, neutral producer stock, no paid-price samples',
        'checkpoints': [rows[i] for i in (0, 14, 15, 30, 60, 100)],
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    ax.axvspan(10, 15, color='#e7b27a', alpha=.3, label='Capacity crunch')
    for key, label, style in (
        ('equilibrium', 'Competitive equilibrium', '--'),
        ('game_elastic', 'Current game rule: elastic orders', '-'),
        ('asymmetric_target', 'Target model: slow downward adjustment', '-.'),
        ('game_fixed_orders', 'Current game rule: fixed order quantities', ':'),
    ):
        ax.plot([r['turn'] for r in rows], [r[key] for r in rows],
                style, linewidth=2, label=label)
    ax.set(xlabel='Turn', ylabel='Price (test currency per unit)', xlim=(0, 70),
           title='Same temporary crunch, different recovery mechanisms')
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=.15)
    fig.savefig(output / 'comparison.png', dpi=170)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
