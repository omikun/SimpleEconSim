"""Replay a funded Tel el Kebir line; run each funding condition separately."""

import json
import sys

from test_scenario_playthroughs import play_campaign


def run(extra_british_cash):
    funded = [False]

    def configure(world, _seen):
        if not funded[0]:
            britain = next(nation for nation in world['nations'] if nation.name == 'Britain')
            britain.government.agent.cash += extra_british_cash
            funded[0] = True

    world, warnings = play_campaign('sovereignty_project', observer=configure)
    state = world['scenario_state']
    project = next(project for project in state['strategic_projects']['projects']
                   if project['kind'] == 'canal_line')
    return {
        'extra_british_cash': extra_british_cash,
        'ending': state['ending'], 'warnings': warnings,
        'actions': [(row['turn'], row['action']) for row in state['actions_taken']],
        'project': project,
        'crew_food': sum(row['food_units'] for row in
                         state['strategic_projects']['payments'] if row['kind'] == 'crew_food'),
        'route': state['campaign']['expedition']['route'],
        'battles': state['campaign']['battles'],
        'civilian_casualties': state['campaign']['civilian_casualties'],
        'british_decisions': [entry for entry in state['diplomatic_crisis']['history']
                              if entry['actor'] == 'Britain'],
    }


def main():
    extra = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    row = run(extra)
    print(f"British funding +{extra}: {row['ending']}; "
          f"route {row['route']}; crew meals {row['crew_food']}; "
          f"battles {[(battle['location'], battle['defense_project_bonus'], battle['winner']) for battle in row['battles']]}")
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as handle:
            json.dump(row, handle, indent=2)


if __name__ == '__main__':
    main()
