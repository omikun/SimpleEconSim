"""Isolated campaign audit for the Egypt strategic loop.

Run a single path with ``--case MODE [--yield N] [--fiscal N]``. Run the
curated matrix with ``--suite``; each campaign gets a fresh Python process so
global bond, market, and imperialism registries cannot contaminate the next.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


PATHS = ('food_project', 'food_project_access', 'fiscal_project', 'sovereignty_project', 'peace',
         'historical', 'resistance', 'mediation')
ENDING_PATHS = ('relief_payment', 'settlement', 'extraction', 'imposed',
                'control', 'mediation', 'nationalist', 'stalled', 'breakdown',
                'disarm', 'joint', 'french_brokered', 'unresolved', 'hardship',
                'historical', 'canal')


def run_case(mode: str, nile_yield: float | None, fiscal_delta: float) -> dict:
    from test_scenario_playthroughs import play_campaign
    from scenario_debt import bonds, outstanding
    from scenario_status import snapshot

    adjusted = [False]
    opening = {}
    status_by_turn = {}

    def observer(world, _warnings):
        if not adjusted[0]:
            adjusted[0] = True
            egypt = next(n for n in world['nations'] if n.name == 'Egypt')
            treasury = egypt.government.agent
            private = [agent for tile in egypt.tiles for agent in tile.agents
                       if getattr(agent, 'alive', True)
                       and not getattr(agent, 'is_government', False)
                       and not getattr(agent, 'is_corporation', False)
                       and not getattr(agent, 'is_trader', False)]
            affluent = max(private, key=lambda agent: (float(agent.cash), agent.id))
            cash_before = treasury.cash + sum(agent.cash for agent in private)
            if fiscal_delta > 0:
                transfer = min(fiscal_delta, max(0.0, float(affluent.cash)))
                affluent.cash -= transfer
                treasury.cash += transfer
            elif fiscal_delta < 0:
                transfer = min(-fiscal_delta, max(0.0, float(treasury.cash)))
                treasury.cash -= transfer
                affluent.cash += transfer
            cash_after = treasury.cash + sum(agent.cash for agent in private)
            assert abs(cash_before - cash_after) < 1e-5
            if nile_yield is not None:
                for tile in egypt.tiles:
                    if getattr(tile, 'scenario_location', '') in ('Nile Delta', 'Upper Egypt'):
                        tile.scenario_food_yield_modifier = nile_yield
                        tile.scenario_food_yield_modifier_until = 12
            opening.update(treasury=round(float(treasury.cash), 2),
                           nile_yield=nile_yield, fiscal_delta=fiscal_delta)
        current = snapshot(world)
        if current:
            status_by_turn[int(world['turn'])] = current

    world, warnings = play_campaign(mode, observer=observer)
    state = world['scenario_state']
    projects = state['strategic_projects']
    reports = projects['grain_entitlement_reports']
    material_turns = {turn for turn, _kind in warnings}
    material_turns.update(int(row['turn']) for row in state['actions_taken'])
    for source in (projects['events'], projects['food_reports'],
                   projects['revenue_reports'], reports,
                   state.get('creditor_news', []), state.get('naval_news', []),
                   state.get('debt_ledger', [])):
        material_turns.update(int(row['turn']) for row in source if 'turn' in row)
    meaningful_status_change = []
    for turn in range(2, int(state.get('ending_turn') or world['turn']) + 1):
        before = status_by_turn.get(turn - 1)
        after = status_by_turn.get(turn)
        if not before or not after:
            continue
        limits = {'hungry_count': 12, 'cash': 30, 'tax': 10, 'debt': .1,
                  'legitimacy': .025, 'unrest': .04, 'creditors': .05,
                  'autonomy': .05}
        if any(abs(float(after.get(key, 0)) - float(before.get(key, 0))) >= limit
               for key, limit in limits.items()):
            material_turns.add(turn)
            meaningful_status_change.append(turn)
    passive = []
    longest = current = 0
    for turn in range(1, int(state.get('ending_turn') or world['turn']) + 1):
        current = 0 if turn in material_turns else current + 1
        if current:
            passive.append(turn)
        longest = max(longest, current)
    return {
        'mode': mode, 'opening': opening, 'ending': state['ending'],
        'ending_turn': state.get('ending_turn'), 'metrics': state.get('ending_metrics'),
        'claim': outstanding(world), 'payment_status': state['payment_status'],
        'bonds': [(bond.bond_id, bond.principal, bond.status, bond.bond_purpose)
                  for bond in bonds(world)],
        'debt_ledger_tail': state['debt_ledger'][-5:],
        'warnings': warnings,
        'actions': [(row['turn'], row['action']) for row in state['actions_taken']],
        'projects': [(p['id'], p['status'], p['progress']) for p in projects['projects']],
        'private_surplus_delivered': sum(row['units'] for row in reports),
        'carrier_wages': round(sum(row['transport_wages'] for row in reports), 2),
        'hunger_household_turns': world.get('scenario_status_history', {}).get(
            'social_costs', {}).get('household_hunger_turns', 0),
        'passive_turns': passive, 'longest_passive_streak': longest,
        'material_status_turns': meaningful_status_change,
    }


def run_suite(output: str | None) -> int:
    cases = [(mode, None, 0.0, 1) for mode in ENDING_PATHS]
    cases.append(('food_project_access', None, 0.0, 0))
    cases += [(mode, severity, fiscal, seed)
              for mode in PATHS
              for severity, fiscal, seed in ((0.25, -40.0, 0), (0.55, 40.0, 1))]
    cases += [('relief_payment', 0.55, 40.0, 0),
              ('settlement', 0.55, 40.0, 0)]
    results = []
    for mode, severity, fiscal, seed in cases:
        command = [sys.executable, __file__, '--case', mode,
                   '--fiscal', str(fiscal)]
        if severity is not None:
            command += ['--yield', str(severity)]
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        completed = subprocess.run(command, capture_output=True, text=True,
                                   env=env, timeout=180, check=False)
        lines = [line[12:] for line in completed.stdout.splitlines()
                 if line.startswith('RESULT_JSON=')]
        if completed.returncode == 0 and lines:
            row = json.loads(lines[-1])
        else:
            row = {'mode': mode, 'error': completed.stderr.strip()[-1000:]}
        row['hash_seed'] = seed
        results.append(row)
        print(f'{mode:22} yield={severity!s:4} fiscal={fiscal:+4.0f} '
              f'-> {row.get("ending", "ERROR"):26} '
              f'hunger={row.get("metrics", {}).get("hunger_rate", 0):.2f}', flush=True)
    if output:
        with open(output, 'w', encoding='utf-8') as handle:
            json.dump(results, handle, indent=2)
    from scenario_egypt_1877 import SCENARIO
    declared = {outcome['id'] for outcome in SCENARIO['outcomes']}
    reached = {row.get('ending') for row in results}
    missing = sorted(declared - reached)
    print(f'Outcome coverage: {len(declared) - len(missing)}/{len(declared)}; '
          f'missing: {missing}', flush=True)
    return int(any('error' in row for row in results) or bool(missing))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=sorted(set(ENDING_PATHS + PATHS)))
    parser.add_argument('--suite', action='store_true')
    parser.add_argument('--yield', dest='nile_yield', type=float)
    parser.add_argument('--fiscal', type=float, default=0.0)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.suite:
        return run_suite(args.output)
    if args.case:
        print('RESULT_JSON=' + json.dumps(run_case(args.case, args.nile_yield, args.fiscal)))
        return 0
    parser.error('select --case or --suite')


if __name__ == '__main__':
    raise SystemExit(main())
