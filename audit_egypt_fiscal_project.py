"""Compare the first two Egyptian debt windows with and without a revenue office."""

import json
import sys

from scenario_debt import outstanding
from test_scenario_playthroughs import play_campaign


def run(mode):
    checkpoints = {}

    def observe(world, _warnings):
        turn = int(world['turn'])
        if turn not in (1, 4, 5, 6, 11):
            return
        state = world['scenario_state']
        egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
        checkpoints[turn] = {
            'turn': turn,
            'treasury': round(float(egypt.government.agent.cash), 2),
            'claim': outstanding(world),
            'payment_status': state['payment_status'],
            'office_status': next((project['status'] for project in
                                   state['strategic_projects']['projects']
                                   if project['kind'] == 'revenue_office'), None),
            'caisse_collected': round(sum(row['amount'] for row in state['debt_ledger']
                                          if row['turn'] == turn and
                                          row['kind'] == 'assigned_revenue'), 2),
        }

    world, warnings = play_campaign(mode, observer=observe)
    state = world['scenario_state']
    return {
        'mode': mode, 'checkpoints': list(checkpoints.values()), 'warnings': warnings,
        'actions': [(row['turn'], row['action']) for row in state['actions_taken']],
        'revenue_reports': state['strategic_projects']['revenue_reports'],
        'creditor_news': [row for row in state['creditor_news']
                          if row['headline'] == 'Caisse reviews Alexandria office'],
        'ending': state['ending'],
    }


def main():
    results = [run('payment_first'), run('fiscal_project')]
    for result in results:
        print(result['mode'], result['ending'])
        for row in result['checkpoints']:
            print('  turn {turn}: treasury {treasury:.0f}, claim {claim:.0f}, '
                  'office {office_status}, payment {payment_status}'.format(**row))
        print('  Cairo transfers', round(sum(row['central_transfer']
                                               for row in result['revenue_reports']), 2))
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as handle:
            json.dump(results, handle, indent=2)


if __name__ == '__main__':
    main()
