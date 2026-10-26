"""Replay the Nile repair and its fiscal/household consequences.

Run: venv/bin/python audit_egypt_food_project.py [output.json]
"""
import pathlib as _pathlib, sys as _sys
_ROOT = _pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / 'tests')):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import json
import sys

from scenario_status import snapshot
from test_scenario_playthroughs import play_campaign


def run_path(mode):
    world, warnings = play_campaign(mode)
    state = world['scenario_state']
    projects = state['strategic_projects']
    current = snapshot(world)
    result = {
        'path': mode,
        'ending': state['ending'],
        'warnings': warnings,
        'actions': [(row['turn'], row['action']) for row in state['actions_taken']],
        'project': projects['projects'][0],
        'food_reports': projects['food_reports'],
        'owner_responses': [event for event in projects['events']
                            if 'Warehouse owner' in event['message']],
        'final': {key: current[key] for key in
                  ('cash', 'debt', 'hungry_count', 'household_count', 'maize', 'private_food')},
    }
    return result


def main():
    results = [run_path(mode) for mode in ('food_project', 'food_project_access')]
    for result in results:
        print(f"{result['path']}: {result['ending']}; {result['final']['hungry_count']}/"
              f"{result['final']['household_count']} underfed; "
              f"treasury {result['final']['cash']:.0f}; claim {result['final']['debt']:.0f}")
        for row in result['food_reports'][:6]:
            print(f"turn {row['turn']}: harvest {row['food_produced']}, "
                  f"held {row['private_reserved']}, underfed {row['underfed']}/"
                  f"{row['households']}, repair yield factor {row['yield_factor']:.2f}")
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as handle:
            json.dump(results, handle, indent=2)


if __name__ == '__main__':
    main()
