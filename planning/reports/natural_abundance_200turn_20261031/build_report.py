"""Validate saved observations and render the shareable acceptance report."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
SEEDS = (4243, 4242, 4244)
data = [json.loads((HERE / 'frozen' / f'seed_{seed}.json').read_text()) for seed in SEEDS]
manifest = json.loads((HERE / 'snapshot_manifest.json').read_text())
diagnostic = json.loads((HERE / 'frozen' / 'seed_4243_constraints.json').read_text())
assert diagnostic['observer_matches_unobserved_run']
assert diagnostic['source_signature'] == manifest['source_signature']
facts = []
for d in data:
    assert d['source_unchanged'] and d['source_signature'] == manifest['source_signature']
    assert not d['currency_audit_violations'] and d['negative_inventory_checks_passed']
    rows = d['observations']
    assert [r['turn'] for r in rows] == list(range(1, 201))
    assert all(r['population'] >= r['underfed'] >= 0 for r in rows)
    assert all(.1 <= r['food_quote'] <= 50 for r in rows)
    first, last, end = d['periods'][0], d['periods'][-1], rows[-1]
    facts.append({'seed': d['seed'], 'population_end': end['population'],
        'crop_rotation_discovered_turn': next(e['t'] for e in d['innovation_log'] if e.get('tech_id') == 'crop_rotation' and e['event'] == 'DISCOVERY'),
        'food_technology_installations_ever': max(sum(b['food_multiplier'] > 1 for b in r['installations']) for r in rows),
        'known_technologies_end': len(end['known_technologies']),
        'farm_food_mean_first_20': first['farm_food_per_turn'],
        'farm_food_mean_last_20': last['farm_food_per_turn'],
        'forage_share_last_20': 1 - last['farm_share_of_new_food'],
        'food_quote_mean_first_20': first['food_quote_mean'],
        'food_quote_mean_last_20': last['food_quote_mean'],
        'paid_food_vwap_first_20': first['food_paid_vwap'],
        'paid_food_vwap_last_20': last['food_paid_vwap'],
        'underfed_share_last_20': last['underfed_share'],
        'starvation_deaths': sum(r['deaths_by_cause'].get('starvation', 0) for r in rows),
        'prepared_food_output_first_20': first['prepared_food_output'],
        'prepared_food_output_last_20': last['prepared_food_output'],
        'farm_practice_gain_end': end['farm_practice_multiplier_mean'] - 1,
        'farm_adult_share_end': end['farm_adults'] / max(1, sum(end['adult_professions'].values())),
        'same_outcomes_as_initial_live_run': rows == json.loads((HERE / f"seed_{d['seed']}.json").read_text())['observations']})

constraint_periods = []
for start in range(1, 201, 20):
    rows = [r for r in diagnostic['rows'] if start <= r['turn'] < start + 20]
    n = sum(r['independent_farmers'] for r in rows)
    constraint_periods.append({'turns': [start, start + 19],
        **{key + '_share': sum(r[key] for r in rows) / max(1, n)
           for key in ('withheld_farmers', 'inventory_full_farmers', 'eligible_farmers',
                       'pollution_revolt_farmers')},
        'successful_operations_per_farm_worker_snapshot': sum(r['successful_independent_operations'] for r in rows) / max(1, n),
        'earned_practice_per_farm_worker_snapshot': sum(r['earned_farm_practice'] for r in rows) / max(1, n)})
assert all(f['same_outcomes_as_initial_live_run'] for f in facts)
assert len(diagnostic['rows']) == 200 and diagnostic['adoption_decisions']
summary = {'source_signature': manifest['source_signature'], 'seeds': facts,
           'seed_4243_constraint_periods': constraint_periods,
           'seed_4243_adoption_decision_counts': diagnostic['decision_counts'],
           'accepted_as_abundance': False,
           'checks': {'all_600_turns_complete': True, 'currency_audit_violations': 0,
                      'negative_inventory_failures': 0, 'observer_replay_exact': True}}
(HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')

colors = ('#2563eb', '#d97706', '#059669')
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.titleweight': 'bold'})
fig, axes = plt.subplots(3, 2, figsize=(12.5, 11), constrained_layout=True)
fig.suptitle('200 turns: growth without technological abundance', fontsize=19, fontweight='bold')
for d, color in zip(data, colors):
    rows, periods = d['observations'], d['periods']
    t = [r['turn'] for r in rows]
    mid = [sum(p['turns']) / 2 for p in periods]
    label = str(d['seed'])
    axes[0, 0].plot(t, [r['population'] for r in rows], color=color, label=label)
    axes[1, 0].plot(mid, [p['food_quote_mean'] for p in periods], color=color, label=label)
    axes[1, 0].plot(mid, [p['food_paid_vwap'] for p in periods], color=color, linestyle=':', alpha=.75)
    axes[1, 1].plot(mid, [100 * p['underfed_share'] for p in periods], color=color)
    axes[2, 0].plot(t, [100 * (r['farm_practice_multiplier_mean'] - 1) for r in rows], color=color)
    axes[2, 1].step(t, [len(r['known_technologies']) for r in rows], color=color, label=label)
p = data[0]['periods']
mid = [sum(r['turns']) / 2 for r in p]
axes[0, 1].stackplot(mid, [r['farm_food_per_turn'] for r in p], [r['forage_per_turn'] for r in p],
                     colors=('#2563eb', '#bbd7a7'), labels=('Farm grain', 'Foraging'))
axes[0, 1].legend(loc='upper left', frameon=False)
axes[0, 0].legend(title='Seed', frameon=False)
axes[2, 1].plot([1, 200], [0, 0], color='#111827', linewidth=2, linestyle='--', label='Food installations (all seeds)')
axes[2, 1].legend(loc='upper left', frameon=False, fontsize=9)
panels = [
    ('Residents', 'Living resident entities'),
    ('New food remains dominated by foraging · seed 4243', 'Units per turn · 20-turn means'),
    ('Grain gets dearer, then retreats', 'Price · solid: quote, dotted: paid VWAP'),
    ('Underfeeding persists', 'Underfed resident-turns (%) · 20-turn periods'),
    ('Practice gains remain modest among current farmers', 'Mean output bonus (%)'),
    ('Discoveries fail to become food installations', 'Technologies / installations')]
for ax, (title, ylabel) in zip(axes.flat, panels):
    ax.set_title(title, loc='left', fontsize=11, pad=10)
    ax.set_ylabel(ylabel)
    ax.set_xlabel('Turn')
    ax.set_xlim(1, 200)
    ax.grid(axis='y', alpha=.16)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
fig.savefig(HERE / 'overview.png', dpi=150)
plt.close(fig)

lines = ['# Natural abundance: 200-turn acceptance test', '',
    'Date: 2026-10-31. Status: simulations passed accounting checks; the intended abundance progression is **not yet demonstrated**.', '',
    'Three seeds ran 200 canonical turns each, with national innovation and the normal national AI enabled. The economy grew, but technology discovery never became an operating food installation. Prices ended above their opening level, and foraging still supplied roughly three quarters of new food in the last twenty turns.', '',
    '## Setup and reproducibility', '',
    '- Same 70-person feudal parish as the earlier local abundance fixture: 75% food, 15% wood, 10% furniture profession distribution; normal starting inventories and cash.',
    '- No artificial yield boost, granted technologies, preinstalled equipment, extra food, recurring cash, or harness-issued construction orders. Seasonal tribute and finite estate feeding remain enabled. Spoilage remains off.',
    '- A nation and its ordinary AI now participate in every turn. Authored local deposits are arable silt, timber, iron ore and coal: these provide research access, not extracted materials.',
    '- One isolated region, no outside trading partners. Exports, imports and technology diffusion cannot be assessed here.',
    '- Each seed uses a fresh process and `PYTHONHASHSEED=0`.',
    f"- Accepted frozen-source fingerprint: `{manifest['source_signature']}`. The exact copied source is archived in `source_snapshot.tar.gz`; its runtime path was `{manifest['snapshot_root']}`.",
    '- The original three live-workspace runs each reported unchanged source. New files appeared during a later diagnostic replay, so the accepted matrix was repeated from the frozen copy. All 600 daily observations match the original runs exactly.', '',
    '## Results', '',
    'Block averages use turns 1–20 and 181–200, covering complete ten-turn seasonal cycles. Underfeeding is underfed resident-turns divided by total resident-turns. Paid prices are quantity-weighted actual transactions; quotes are posted reference prices.', '',
    '| Seed | Residents at 200 | Farm grain/turn, opening → ending block | Grain quote, opening → ending block | Ending underfed share | Recorded starvation deaths |',
    '| --- | ---: | ---: | ---: | ---: | ---: |']
for f in facts:
    lines.append(f"| {f['seed']} | {f['population_end']} | {f['farm_food_mean_first_20']:.0f} → {f['farm_food_mean_last_20']:.0f} | {f['food_quote_mean_first_20']:.2f} → {f['food_quote_mean_last_20']:.2f} | {f['underfed_share_last_20']:.1%} | {f['starvation_deaths']} |")
lines += ['', '| Seed | Crop rotation discovered | Known technologies at 200 | Food installations ever | Ending forage share | Paid grain price, opening → ending block |',
          '| --- | ---: | ---: | ---: | ---: | ---: |']
for f in facts:
    lines.append(f"| {f['seed']} | {f['crop_rotation_discovered_turn']} | {f['known_technologies_end']} | {f['food_technology_installations_ever']} | {f['forage_share_last_20']:.1%} | {f['paid_food_vwap_first_20']:.2f} → {f['paid_food_vwap_last_20']:.2f} |")
lines += ['', '![Six panels showing population, food sources, grain prices, underfeeding, practice and discoveries](overview.png)', '',
    '## What stopped the progression', '',
    'Discovery is running. Crop rotation arrives at turns 46, 53 and 61, followed by other agronomy discoveries. Every discovered design remains at tier one; no productive machine work is attributed to installed technologies, and no food production installation is built during any of the three campaigns. Public AI builds roads, a canal, filtration and sewers, which do not directly multiply grain output in these runs.', '',
    'Deployment has a structural gap for this economy. `economy/technology_adoption.py:step_private_adoption` considers living corporations only. Independent peasants and estate owners have no equivalent automatic adoption path. Its final recorded decisions all report `no_operating_workforce`; these are the latest per-firm/design decisions, not a full history. The observed complete seed-4243 decision history is retained separately.', '',
    'More farmers do not produce proportionately more market grain. In seed 4243, the ending block has 244 farming adults on average, versus 39 initially, but grain output rises from 108 to 342 units per turn. Its headcount-normalized output falls from 2.79 to 1.40. This is output divided by worker snapshots, not a measurement of output per actual shift. The boundary replay below identifies the immediate production constraints.', '',
    '| Seed 4243 turns | Farm worker snapshots withheld | Inventory already full | Eligible for production | Successful independent operations / farmer snapshot |',
    '| --- | ---: | ---: | ---: | ---: |']
for p in constraint_periods:
    lines.append(f"| {p['turns'][0]}–{p['turns'][1]} | {p['withheld_farmers_share']:.1%} | {p['inventory_full_farmers_share']:.1%} | {p['eligible_farmers_share']:.1%} | {p['successful_operations_per_farm_worker_snapshot']:.2f} |")
lines += ['',
    'The dominant measured mid-campaign work blockage is pollution-related illness revolt, rather than ordinary wage strikes or full inventories. In turns 121–140, about 90.6% of independent farm-worker snapshots are on the pollution-revolt exclusion list; ordinary strikes account for about 0.02%, with possible overlap. Their farm production is skipped, while the separate commons-foraging eligibility rule remains open. Grain production in this block averages just 61 units per turn despite nearly 294 counted farming adults. This is an immediate code-path explanation of withheld output, not proof that any single pollution parameter caused the entire long-run result. The normal AI eventually builds filtration and sewer works, but the interruption is already substantial.', '',
    'Current farmers end with only about a 7% average practice bonus. The potential +60% cap is not an automatic gain over elapsed time: only successful productive work earns practice, reduced by work allocated elsewhere. Population turnover also matters: the model ages residents by one year each turn, so a 200-turn campaign spans many generations. This test does not isolate their separate causal effects.', '',
    'The economy has not diversified into sustained surplus processing. Prepared-food output in the opening versus ending twenty-turn blocks is 322 → 0 for seed 4243, 313 → 48 for 4242, and 251 → 9 for 4244. Prepared meals reuse grain calories and are not added to new grain and forage supply. Roughly 94–97% of the counted civilian production workforce is farming at turn 200. Neither more corporation entities nor more discovered designs is evidence of an operating industrial economy.', '',
    '## Verification and limits', '',
    '- All three frozen cases completed 200 turns at one unchanged source fingerprint, with zero reported currency-accounting violations and zero negative inventory failures.',
    '- A separate, read-only seed-4243 replay observes production and adoption boundaries. Its full daily economic observations, events, discoveries, latest adoption reasons and opening state match the unobserved run exactly.',
    '- This is an observational acceptance test, not a matched innovation-on/off experiment. Changes in population, soil, weather, policy, food access and workforce composition prevent attributing output changes to any one mechanism.',
    '- Counts exclude government and corporation entities, but existing person-to-company conversions can affect resident counts and death counters. Reported starvation deaths are engine counters, not an independently reconstructed mortality cohort.',
    '- A low quoted price or an ending stockpile alone cannot establish affordable meals, broad prosperity or successful technology deployment.', '',
    '## Next implementation target', '',
    'Two mechanisms need attention before claiming the abundance progression. First, review whether pollution-illness revolt should prevent subsistence farming this broadly, and whether sanitation and recovery act soon enough. Second, provide an adoption path for actual agricultural producers: independent farmers, estate owners and operating farm businesses. Cheap agronomic practices need suitable costs and local learning; machinery needs financed equipment, materials and labor. Keep discovery, adoption, actual use and refinement separately observable. Repeat this matrix after those changes, before adding spoilage or claiming successful surplus-driven diversification.', '',
    '## Files and rerun', '',
    '- `frozen/seed_4243.json`, `seed_4242.json`, `seed_4244.json`: daily observations and twenty-turn summaries.',
    '- `frozen/seed_4243_constraints.json`: production-boundary observations and complete adoption decision history.',
    '- `summary.json`: validated cross-seed results.',
    '- `snapshot_manifest.json` and `source_snapshot.tar.gz`: fixed source provenance.',
    '- `scripts/audit_natural_abundance.py`: reusable harness in the workspace and frozen archive.',
    '- `inspect_constraints.py` and `build_report.py`: diagnostic replay and report rendering.', '',
    'Extract the source archive into an empty directory and run its harness in a fresh process per seed with the project virtual environment. Set `PYTHONPATH` to that extracted directory, `PYTHONHASHSEED=0`, and `MPLCONFIGDIR` to a writable cache. Use `--turns 200 --seed 4243 --output <result.json>`. Repeat for seeds 4242 and 4244. The diagnostic script accepts `ABUNDANCE_SOURCE_ROOT` and `ABUNDANCE_REPORT_ROOT` to locate the extracted source and accepted results.', '']
(HERE / 'acceptance.md').write_text('\n'.join(lines))
print(json.dumps(summary, indent=2))
