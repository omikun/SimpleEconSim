"""Compare Egypt strategies before the strategic-project implementation.

Run: venv/bin/python audit_egypt_strategy_baseline.py [output.json]
"""

from __future__ import annotations

import json
import sys

from scenario_status import snapshot
from test_scenario_playthroughs import play_campaign


PATHS = ('relief_payment', 'peace', 'historical', 'resistance')


def run_path(mode):
    turns = {}

    def observe(world, warnings):
        current = snapshot(world) or {}
        state = world['scenario_state']
        turn = int(world['turn'])
        turns[turn] = {
            'turn': turn,
            'horizon': int(world['scenario']['horizon_turns']),
            'treasury': round(float(current.get('cash', 0)), 2),
            'tax': round(float(current.get('tax', 0)), 2),
            'claim': round(float(current.get('debt', 0)), 2),
            'underfed': int(current.get('hungry_count', 0)),
            'households': int(current.get('household_count', 0)),
            'maize': int(current.get('maize', 0)),
            'private_food': int(current.get('private_food', 0)),
            'legitimacy': round(float(current.get('legitimacy', 0)), 3),
            'territory': dict(state.get('campaign', {}).get('territorial_control', {})),
            'warnings': [kind for warning_turn, kind in warnings if warning_turn == turn],
        }

    world, warnings = play_campaign(mode, observer=observe)
    actions = world['scenario_state']['actions_taken']
    by_turn = {}
    for action in actions:
        by_turn.setdefault(int(action['turn']), []).append(action['action'])
    for turn, row in turns.items():
        row['actions'] = by_turn.get(turn, [])
    return {
        'path': mode,
        'ending': world['scenario_state']['ending'],
        'turns': list(turns.values()),
        'action_turns': sorted(by_turn),
        'unused_major_decision_turns': [turn for turn in turns
                                        if turn < world['scenario']['horizon_turns']
                                        and turn not in by_turn],
        'warnings': warnings,
    }


def main():
    runs = [run_path(mode) for mode in PATHS]
    for run in runs:
        final = run['turns'][-1]
        print(f"{run['path']}: {run['ending']}; last action "
              f"{max(run['action_turns'], default='none')}; "
              f"unused major decisions {len(run['unused_major_decision_turns'])}; "
              f"underfed {final['underfed']}/{final['households']}; "
              f"treasury {final['treasury']:.0f}; claim {final['claim']:.0f}")
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as handle:
            json.dump(runs, handle, indent=2)


if __name__ == '__main__':
    main()
