"""Render the frozen 2026-10-31 review; new runs use food_growth.analyze_growth."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.food_growth import analyze_growth


def render(inputs, output):
    cases = []
    for path in inputs:
        data = json.loads(path.read_text())
        analysis = analyze_growth(data['observations'])
        cases.append({'seed': data['seed'], 'input': str(path.resolve()),
                      'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'simulation_source_signature': data['source_signature'], **analysis})
    if ({c['seed'] for c in cases} != {4243, 4242, 4244} or len(cases) != 3
            or any(c['simulation_source_signature'] !=
                   '0c16a014de22e1d033aaefb05c5a5cc124d9bca12c145233d53d352f5b7f8bae'
                   or len(c['blocks']) != 10 for c in cases)):
        raise ValueError('This narrative reviews the three frozen 2026-10-31 cases; '
                         'use food_growth.analyze_growth for other simulations')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'growth_trends.json').write_text(json.dumps(cases, indent=2) + '\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False})
    main = next((d for d in cases if d['seed'] == 4243), cases[0])
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9), constrained_layout=True)
    fig.suptitle('Does food supply keep up with population?', fontsize=19, fontweight='bold')
    blocks = main['blocks']
    x = [sum(b['turns']) / 2 for b in blocks]
    for metric, name, color in (
            ('population_mean', 'Population', '#2563eb'),
            ('farm_food_per_turn', 'Farm grain', '#d97706'),
            ('gross_new_food_per_turn', 'Grain + foraging', '#059669')):
        axes[0, 0].plot(x, [b[metric + '_index'] for b in blocks], color=color, label=name)
    for metric, name, color in (
            ('population_growth', 'Population', '#2563eb'),
            ('farm_food_growth', 'Farm grain', '#d97706'),
            ('gross_new_food_growth', 'Grain + foraging', '#059669')):
        axes[0, 1].plot(x[1:], [100 * b[metric] for b in blocks[1:]], color=color, label=name)
    axes[0, 0].legend(frameon=False)
    axes[0, 1].axhline(0, color='#6b7280', linewidth=.8)
    for case, color in zip(cases, ('#2563eb', '#d97706', '#059669', '#9333ea')):
        points = case['blocks']
        t = [sum(b['turns']) / 2 for b in points]
        axes[1, 0].plot(t, [b['food_per_resident_turn'] for b in points], color=color, label=str(case['seed']))
        axes[1, 1].plot(t, [100 * b['gross_ordinary_need_coverage'] for b in points], color=color)
    axes[1, 0].legend(title='Seed', frameon=False)
    axes[1, 1].axhline(100, color='#374151', linestyle='--', linewidth=1, label='Ordinary need')
    axes[1, 1].legend(frameon=False)
    headings = (
        (f"Population outgrows supply overall · seed {main['seed']}", 'Index · first 20-turn block = 100'),
        (f"Growth rates converge only temporarily · seed {main['seed']}", 'Change from previous 20-turn block (%)'),
        ('Food per person falls, then partly recovers', 'New grain + foraging per resident-turn'),
        ('Coverage nears 100% while hunger still occurs', 'Gross new food / ordinary nutritional need (%)'))
    for ax, (title, label) in zip(axes.flat, headings):
        ax.set_title(title, loc='left', fontsize=11, fontweight='bold', pad=10)
        ax.set_ylabel(label)
        ax.set_xlabel('Turn · complete 20-turn blocks')
        ax.grid(axis='y', alpha=.18)
        ax.set_xlim(1, 200)
    fig.savefig(output / 'growth_trends.png', dpi=150)
    plt.close(fig)

    lines = ['# Population and food growth review', '', 'Date: 2026-11-01.', '',
        'Equal growth is a useful long-run condition for stable food per person. Reaching abundance first requires food to outgrow nutritional demand, creating a dependable surplus and accessible reserves. Later, population, diet, processing and exports can absorb part of that surplus. Exact equality every turn is neither required nor a target to hard-code.', '',
        'This report reanalyzes the frozen 2026-10-31 campaigns. It does not represent a fresh run of the newer seasonal-farm implementation now in the workspace. The archived simulation source fingerprint and each input file hash are preserved in `growth_trends.json`.', '',
        '## Measurement', '',
        '- Compare nonoverlapping twenty-turn averages, each spanning two complete seasonal cycles. Never compare a harvest turn directly with a sowing turn.',
        '- Track population, farm grain, total new food (grain plus actual foraging), and ordinary nutritional demand separately. Prepared-food output converts existing grain; it adds no new calories.',
        '- Growth rates are percentage changes between adjacent block means. Population and food indices share their first complete block as 100.',
        '- Food per resident-turn is total new food divided by the sum of residents over the block. Ordinary-demand coverage allows for changing age composition.',
        '- Seeds and storage losses are deducted when recorded. They are unknown in the archived fixture, so the coverage below is explicitly gross. Imports, exports and drawdown of existing stocks are additional flows, not new local production.',
        '- Near alignment means food per person changes by at most 2% between blocks. The descriptive sustained test requires three consecutive comparisons with nonnegative population and food growth. This is a reporting convention, not a demographic constraint, and it is not evidence of household access.', '',
        '## First versus last twenty-turn blocks', '',
        '| Seed | Population growth | Farm grain growth | Grain + foraging growth | Food per resident-turn | Ordinary-demand coverage | Longest near-aligned growing streak |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in cases:
        a, b = case['blocks'][0], case['blocks'][-1]
        rates = [100 * (b[k] / a[k] - 1) for k in ('population_mean', 'farm_food_per_turn', 'gross_new_food_per_turn')]
        lines.append(f"| {case['seed']} | +{rates[0]:.0f}% | +{rates[1]:.0f}% | +{rates[2]:.0f}% | {a['food_per_resident_turn']:.2f} → {b['food_per_resident_turn']:.2f} | {a['gross_ordinary_need_coverage']:.0%} → {b['gross_ordinary_need_coverage']:.0%} | {case['longest_aligned_growth_streak']} comparisons |")
    lines += ['', 'Food per person finishes below its opening level in all three seeds. None meets the three-comparison sustained growing-alignment criterion. Their late recovery is useful evidence, but it does not establish a stable productive surplus.', '',
        f"## Seed {main['seed']} timeline", '',
        '| Turns | Population growth | Farm grain growth | Grain + foraging growth | Food/person | Ordinary need covered | Underfed share |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    pct = lambda value: '—' if value is None else f'{value:+.1%}'
    for b in blocks:
        lines.append(f"| {b['turns'][0]}–{b['turns'][1]} | {pct(b['population_growth'])} | {pct(b['farm_food_growth'])} | {pct(b['gross_new_food_growth'])} | {b['food_per_resident_turn']:.2f} | {b['gross_ordinary_need_coverage']:.1%} | {b['underfed_share']:.1%} |")
    lines += ['', 'In turns 81–100, population grows 25.9% and grain-plus-foraging grows 24.9%, but farm grain falls 39.4%. Underfeeding is 10.8% and gross production covers about 99% of ordinary need. Apparent alignment is driven by subsistence gathering, not agricultural productivity. The old foraging rule supplies eligible adults with up to four food units each turn, making supply rise mechanically with eligible adults.', '',
        'In the last comparison, population grows 10.2% while total food grows 17.3% and farm grain grows 83.8%. Food is catching up again. More than one recovering block is needed to establish stability, especially after the preceding contraction and interrupted farm work.', '',
        '![Population, production, per-capita supply and nutritional-demand coverage](growth_trends.png)', '',
        '## Review of the mechanisms', '',
        'The archived production replay found pollution-related revolt excluding about 91% of independent farm-worker snapshots at its worst twenty-turn block, while those adults could still forage. That path explains much of the middle-run collapse in cultivation and the dominance of foraging. It does not justify simply making all illness harmless.', '',
        'The newer implementation changes this interaction: `micro/work_allocation.py:begin` gives pollution-revolt participants zero available work, and both cultivation and gathering now use that same budget. `micro/foraging.py:capacity` also bounds supply by regional commons capacity instead of issuing a separate allowance to every adult. The earlier farming/foraging inconsistency should not be reported as an unchanged current-code defect; verify the replacement through new acceptance runs.', '',
        'The adoption gap remains visible in current code: `economy/technology_adoption.py:step_private_adoption` accepts corporations only. Independent peasants and estate owners still lack an equivalent automatic route. Providing crop rotation as a practice requires a different cost and adoption process from constructing a steam installation.', '',
        'A further integration gap is visible in the new crop path. `micro/agriculture.py:yield_factor` combines terrain, soil, water, installed technology, scenario/climate factors and pollution. `micro/agriculture.py:produce` records engineering operation but does not call the abundance proficiency/learning functions. Therefore the earlier +60% farmer-practice curve cannot be assumed to operate on these new crop harvests. A replacement should account for delivered sowing, tending and harvesting work, including hired workers, without awarding practice twice.', '',
        'Population responds to food indirectly. The current reproduction rule scales fertility with personal calorie deficits and body reserves, and requires two stored food units at the birth decision. It does not calculate births from regional production growth or the next harvest forecast. A lag, overshoot and later correction are therefore plausible. Review household provisioning and the ordinary-needs forecast before increasing birth rates or imposing a regional population/production equality.', '',
        'A current-model smoke run also stops in ordinary public food aid: `macro/government.py:provide_food_aid` checks only whether local stock is positive before debiting one whole unit for a child. The replacement fixed-point stores can hold a positive fraction below one; `core/food_store.py:add_food` correctly rejects that overdraw. This is a separate integration error in the live run, not a failure of the growth calculations. It must be addressed before accepting a fresh 200-turn campaign. No reserve floor or accounting guard was bypassed to make the smoke run pass.', '',
        '## Tracking added', '',
        '`scripts/food_growth.py` is a pure observation analyzer. `scripts/audit_natural_abundance.py` now includes `growth_trends` automatically in future run outputs, and records seed use and storage losses when available from the new food-history journal. It also records the actual food model/opening mode and the newer model’s storage-loss behavior rather than retaining the old unconditional “spoilage off” label. This reporting change does not enable or disable storage losses.', '',
        'The saved runs and their source archive are unchanged. This review changes reporting only; no reproduction, pollution, crop yield or adoption rule has been adjusted.', '',
        '## Next acceptance criteria', '',
        'After integration, rerun the same three seeds for 200 turns and compare complete crop cycles. Require ordinary demand and seed needs to be covered, food per person and accessible reserves to remain adequate, underfeeding to decline, actual agricultural output per delivered work to rise, and new processing demand to persist. Confirm that any alignment comes from viable production rather than unlimited gathering, shrinking population or depletion of stocks. Do not force the curves to match.', '',
        'Regenerate this report with `venv/bin/python scripts/review_food_growth.py <seed_4243.json> <seed_4242.json> <seed_4244.json> --output <directory>`. Run the calculation checks with `venv/bin/python -m unittest tests.test_food_growth`.', '']
    (output / 'review.md').write_text('\n'.join(lines))
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = render(args.inputs, args.output)
    print(json.dumps([{'seed': c['seed'], 'longest_aligned_growth_streak': c['longest_aligned_growth_streak'],
                       'sustained_alignment_while_both_growing': c['sustained_alignment_while_both_growing']}
                      for c in cases], indent=2))
