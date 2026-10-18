"""Matched-start supply rivalry audit. Run with the project venv Python."""
from __future__ import annotations

import json
import sys

from goods import Goods
from scenario_supply_rivalry import apply_action, create_world, step_world


def run(seed, policy, turns=20):
    from agent import _agentid_counter
    _agentid_counter[0] = 0
    world = create_world(seed=seed)
    fields, port = world['tiles']
    if policy != 'none':
        ok, message = apply_action(world, policy)
        if not ok:
            raise RuntimeError(message)
    violations = []
    for _ in range(turns):
        violations.extend(step_world(world))
    state = world['scenario_state']
    mills = []
    for region, ident in ((fields, state['domestic_mill_id']),
                          (port, state['rival_mill_id'])):
        mill = next((a for a in region.agents if a.id == ident), None)
        rows = [a for a in getattr(region, 'actor_account_history', [])
                if a['actor_id'] == ident]
        mills.append({'name': 'Meridian' if region is fields else 'Vesper',
                      'cash': round(mill.cash, 2) if mill else None,
                      'sales_cash': round(sum(a['sales_cash'] for a in rows), 2),
                      'input_consumed_cost': round(sum(a['input_consumed_cost'] for a in rows), 2),
                      'wages_cash': round(sum(a['wages_cash'] for a in rows), 2),
                      'cotton_stock': mill.inv_get(Goods.cotton, 0) if mill else None})
    growers = []
    for ident in state['grower_ids']:
        person = next((a for a in fields.agents if a.id == ident), None)
        rows = [a for a in getattr(fields, 'actor_account_history', [])
                if a['actor_id'] == ident]
        growers.append({'id': ident, 'cash': round(person.cash, 2) if person else None,
                        'food': person.inv_get(Goods.food, 0) if person else None,
                        'crop_cash': round(sum(a['sales_cash'] for a in rows), 2),
                        'crop_value': round(sum(a['crop_value'] for a in rows), 2),
                        'food_intake': round(sum(a['food_intake'] for a in rows), 2)})
    charters = [c for c in getattr(fields, 'market_charters', [])]
    fills = [e for r in world['tiles'] for e in getattr(r, 'market_trade_events', [])
             if e['good'] == Goods.cotton.name]
    return {'seed': seed, 'policy': policy, 'turns': world['turn'],
            'violations': len(violations), 'mills': mills, 'growers': growers,
            'cotton_fills': sum(e['quantity'] for e in fills),
            'imported_cotton_fills': sum(e['quantity'] for e in fills if e['imported']),
            'charters': [{'status': c['status'], 'opposition': round(c.get('opposition', 0), 2)}
                         for c in charters],
            'treasury': round(fields.gov.agent.cash, 2),
            'unrest': round(float(getattr(fields, 'unrest_level', 0)), 3),
            'canal_condition': round(float(fields.canal_condition), 3)}


if __name__ == '__main__':
    seeds = [int(x) for x in sys.argv[1:]] or [812, 813, 814]
    for seed in seeds:
        for policy in ('reject_charter', 'approve_charter',
                       'public_crop_purchase', 'fund_irrigation'):
            print(json.dumps(run(seed, policy), sort_keys=True))
