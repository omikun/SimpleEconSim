"""Record reproducible Egypt campaign paths for balance and presentation review.

Run: venv/bin/python audit_egypt_political_economy.py [output.json]
"""

from __future__ import annotations

import json
import random
import sys

from scenario_campaign import resolve_landing
from scenario_debt import outstanding
from scenario_egypt_1877 import apply_action, finish_due_campaign
from scenario_gunboat import resolve_naval_response
from scenario_occupation import resolve_capital
from scenario_politics import resolve as resolve_politics
from scenario_situation import creditor_response_options, resolve_creditor_response
from scenario_status import snapshot
from scenario_political_economy import stock as warehouse_stock
from worldview_engine import build_world_view, step_world


def _economy_metrics(world):
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    state = world['scenario_state']
    economy = state['political_economy']
    status = snapshot(world)
    return {
        'turn': int(world['turn']),
        'treasury': round(float(nation.government.agent.cash), 2),
        'debt': round(outstanding(world), 2),
        'instalment': round(float(state['scheduled_remittance']), 2),
        'due_turn': int(state['payment_window_turn']),
        'payment_status': state['payment_status'],
        'public_maize': int(nation.government.food_inventory),
        'private_warehouse': warehouse_stock(world, nation),
        'hungry': status['hungry_count'],
        'households': status['household_count'],
        'calorie_gap': round(status['calorie_gap'], 4),
        'arrears': round(sum(float(row['balance']) for row in economy['arrears'].values()), 2),
        'land_loss': len(economy['tenure_transfers']),
        'migrations': len(economy['migrations']),
        'petitioners': sum(int(row['petitioners']) for row in economy['collective_by_tile'].values()),
        'strikers': sum(int(row['strikers']) for row in economy['collective_by_tile'].values()),
        'legitimacy': round(float(nation.legitimacy), 4),
        'unrest': round(status['unrest'], 4),
        'assigned_to_creditors': round(sum(
            float(row.get('diverted', 0)) for row in economy['fiscal_reports']), 2),
        'ending': state.get('ending'),
        'factors': [
            {'source': item['source'],
             'legitimacy': round(item['changes'].get('legitimacy', 0.0), 4),
             'unrest': round(item['changes'].get('unrest', 0.0), 4)}
            for item in world.get('scenario_status_history', {}).get('factors', [])
            if abs(item['changes'].get('legitimacy', 0.0)) > .03
            or abs(item['changes'].get('unrest', 0.0)) > .03],
    }


def _try_action(world, choices, decisions):
    state = world['scenario_state']
    if state.get('last_action_turn') == int(world['turn']):
        return
    for action in choices:
        ok, message = apply_action(world, action)
        if ok:
            decisions.append({'turn': int(world['turn']), 'action': action, 'message': message})
            return


def _resolve_warning(world, path, decisions):
    warning = world.get('scenario_warning_modal')
    if not warning:
        return
    kind = warning['kind']
    state = world['scenario_state']
    if kind == 'debt_due':
        cash = float(next(n for n in world['nations'] if n.name == 'Egypt').government.agent.cash)
        amount = float(state['scheduled_remittance'])
        choices = (['pay_remittance', 'concede_revenue', 'defer_remittance', 'default_remittance']
                   if path == 'creditors' else
                   ['concede_revenue', 'defer_remittance', 'pay_remittance', 'default_remittance']
                   if path == 'protect' else
                   ['pay_remittance', 'default_remittance'])
        ok = False
        message = ''
        for answer in choices:
            if answer == 'pay_remittance' and cash < amount:
                continue
            if answer == 'concede_revenue' and cash < amount * .5:
                continue
            ok, message = apply_action(world, answer)
            if ok:
                break
    elif kind == 'creditor_reaction':
        branch = warning['action_id']
        options = creditor_response_options(world, branch)
        preferred = 'contest_customs_claim' if branch == 'default_remittance' else None
        answer = next((item['id'] for item in options if item['id'] == preferred and item['enabled']), None)
        answer = answer or next(item['id'] for item in options if item['enabled'])
        ok, message = resolve_creditor_response(world, answer)
    elif kind in ('naval_ultimatum', 'naval_blockade'):
        ok, message = resolve_naval_response(world, 'naval_defend' if kind == 'naval_ultimatum' else 'naval_hold')
    elif kind in ('french_terms', 'joint_guarantee_terms'):
        from scenario_diplomacy import resolve_terms
        ok, message = resolve_terms(world, 'accept')
    elif kind == 'landing_warning':
        ok, message = resolve_landing(world, 'defend_canal')
    elif kind == 'capital_warning':
        ok, message = resolve_capital(world, 'defend_cairo')
    elif kind in ('dynastic_crisis', 'officer_movement'):
        ok, message = resolve_politics(world, 'accept_tawfiq' if kind == 'dynastic_crisis' else 'support_urabi')
    elif kind == 'breakdown':
        import pygame
        from ui_targets import clear_targets
        from worldview_scenario_ui import draw_scenario_warning_modal, scenario_warning_modal_hit
        pygame.font.init()
        clear_targets(world)
        draw_scenario_warning_modal(pygame.Surface((1400, 900)), world)
        target = next(target for target in world['_ui_targets']
                      if target.action == ('scenario_warning', 'accept_breakdown'))
        ok = scenario_warning_modal_hit(target.rect.center, world)
        message = 'Accepted government breakdown.'
    else:
        raise RuntimeError(f'Unexpected warning {kind}')
    decisions.append({'turn': int(world['turn']), 'warning': kind, 'response': message})
    if not ok:
        raise RuntimeError(f'Could not resolve {kind}: {message}')
    world['scenario_warning_modal'] = None
    finish_due_campaign(world)


def run_path(path):
    random.seed(1877)
    from agent import _agentid_counter
    from random_cache import rand
    _agentid_counter[0] = 0
    rand._idx = rand._capacity
    world = build_world_view(scenario_id='egypt_1877')
    state = world['scenario_state']
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    rows = [_economy_metrics(world)]
    decisions = []
    for _ in range(25):
        if state.get('ending'):
            break
        turn = int(world['turn'])
        if path == 'protect':
            if turn == 1:
                choices = ['release_maize']
            elif turn == 2:
                choices = ['reduce_fellahin_tax']
            else:
                choices = ['release_maize', 'buy_private_grain', 'reduce_fellahin_tax']
        elif path == 'creditors':
            choices = ['raise_local_taxes'] if turn in (1, 7) else []
        else:
            choices = ['open_private_grain_market'] if turn == 1 else []
        if choices:
            _try_action(world, choices, decisions)
        if not world.get('scenario_warning_modal'):
            step_world(world)
        if world.get('scenario_warning_modal'):
            _resolve_warning(world, path, decisions)
        rows.append(_economy_metrics(world))
    return {'path': path, 'rows': rows, 'decisions': decisions,
            'ending': state.get('ending'), 'debrief': state.get('debrief')}


def main():
    runs = [run_path(path) for path in ('protect', 'creditors', 'market')]
    for run in runs:
        print('\n' + run['path'].upper() + ' → ' + str(run['ending']))
        print('turn cash debt public private hungry gap arrears loss petition strike legitimacy')
        for row in run['rows']:
            print(f"{row['turn']:>2} {row['treasury']:>6.0f} {row['debt']:>5.0f} "
                  f"{row['public_maize']:>5} {row['private_warehouse']:>6} "
                  f"{row['hungry']:>5} {row['calorie_gap']:>4.0%} {row['arrears']:>6.1f} "
                  f"{row['land_loss']:>4} {row['petitioners']:>5} {row['strikers']:>4} "
                  f"{row['legitimacy']:>4.0%}")
        print('choices:', ', '.join(f"t{d['turn']} {d.get('action', d.get('warning'))}"
                                  for d in run['decisions']))
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as out:
            json.dump(runs, out, indent=2, default=str)
        print('saved', sys.argv[1])


if __name__ == '__main__':
    main()
