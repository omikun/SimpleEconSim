"""Replay contrasting sovereignty and intervention paths in Egypt's second chapter.

Run: venv/bin/python audit_egypt_chapter_two.py [output.json]
"""

from __future__ import annotations

import json
import sys

from scenario_debt import outstanding
from test_scenario_playthroughs import play_campaign


def _snapshot(world, warnings):
    state = world['scenario_state']
    politics = state['politics']
    campaign = state['campaign']
    occupation = state['occupation']
    geography = state['geography']
    egypt = next(n for n in world['nations'] if n.name == 'Egypt')
    britain = next(n for n in world['nations'] if n.name == 'Britain')
    fleet = geography['fleets'].get('Britain') or {}
    return {
        'turn': int(world['turn']),
        'chapter': int(state['chapter']),
        'horizon': int(world['scenario']['horizon_turns']),
        'ruler': politics['ruler'],
        'coalition': politics['governing_coalition'],
        'army_loyalty': round(float(politics['army_loyalty']), 3),
        'nationalist_movement': round(float(politics['nationalist_movement']), 3),
        'egypt_treasury': round(float(egypt.government.agent.cash), 2),
        'britain_treasury': round(float(britain.government.agent.cash), 2),
        'caisse_claim': round(outstanding(world), 2),
        'naval_stage': state['naval_crisis'].get('stage', 'none'),
        'fleet_location': fleet.get('location'),
        'fleet_coal': fleet.get('coal'),
        'canal_open': bool(geography.get('canal_open', True)),
        'alexandria_fort': round(float(campaign['forts']['Alexandria']['integrity']), 2),
        'civilian_injuries': int(campaign['civilian_casualties']),
        'port_damage': round(float(campaign['infrastructure_damage'].get('Alexandria', 0)), 3),
        'territory': dict(campaign['territorial_control']),
        'resistance': round(float(occupation['resistance']), 3),
        'occupied_receipts': round(sum(float(row['amount']) for row in occupation['revenue_ledger']
                                       if row.get('source') in ('tax', 'tariff')), 2),
        'garrison_supply': round(float(occupation['garrison_supply_paid']), 2),
        'withdrawal_pending': bool(occupation.get('withdrawal_proposal')),
        'withdrawal_replies': list(occupation.get('withdrawal_replies', [])),
        'french_policy': state.get('diplomatic_crisis', {}).get('french_policy'),
        'warning': warnings[-1][1] if warnings and warnings[-1][0] == int(world['turn']) else None,
        'ending': state.get('ending'),
    }


def run_path(mode):
    rows = []
    world, warnings = play_campaign(mode, observer=lambda world, seen: rows.append(_snapshot(world, seen)))
    state = world['scenario_state']
    return {
        'path': mode,
        'ending': state['ending'],
        'chapter_two_start': state.get('chapter_two_start_turn'),
        'occupation_start': state.get('occupation_start_turn'),
        'warnings': warnings,
        'actions': state.get('actions_taken', []),
        'rows': rows,
        'debrief': state.get('debrief'),
    }


def main():
    runs = [run_path(mode) for mode in
            ('historical', 'resistance', 'premature_offer', 'canal', 'mediation',
             'disarm', 'imposed')]
    for run in runs:
        first = run['rows'][0]
        last = run['rows'][-1]
        print(f"{run['path']}: {run['ending']} | chapter II turn {run['chapter_two_start']} | "
              f"ends {last['turn']}/{last['horizon']} | debt {first['caisse_claim']:.0f}"
              f"→{last['caisse_claim']:.0f} | civilians {last['civilian_injuries']} | "
              f"occupation receipts {last['occupied_receipts']:.1f} | "
              f"territory {last['territory']}")
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as handle:
            json.dump(runs, handle, indent=2, default=str)
        print('saved', sys.argv[1])


if __name__ == '__main__':
    main()
