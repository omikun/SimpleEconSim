"""Economic decisions at complete-turn boundaries, without requiring universal wins."""
from collections import Counter
import json
import os
from pathlib import Path
import unittest
from goods import Goods
from world_config import ElitePlanningConfig
from tests.elite_economic_cases import economic_cases, build_case
from tests.elite_economic_acceptance import compare_case, freeze_case, observe_case


def twenty_decisions():
    rows = [compare_case(case) for case in economic_cases()]
    assert len(rows) == len({row['case']['name'] for row in rows}) == 20
    # These are independently specified operational choices, not required profit wins.
    for row in rows:
        case, active = row['case'], row['active']
        action = active['first_decision']['action_taken']
        quantity = active['first_input_quantity']
        family = case['family']
        assert abs(active['wages_paid'] - case['workers'] * case['wage'] * case['turns']) < 1e-8, row
        assert abs(active['obligations_paid'] - case['obligation']) < 1e-8, row
        if family == 'one_batch':
            assert action == 'PRODUCTION_PLAN' and quantity == 2, row
        elif family == 'larger_batch':
            assert action == 'PRODUCTION_PLAN' and quantity >= 2 * case['workers'], row
        else:
            assert action == ('WAIT_INPUT' if family == 'wait' else 'DECLINE_INPUT') and quantity == 0, row
        if family in ('one_batch', 'larger_batch', 'wait'):
            assert active['output_produced'] > 0 and active['output_sold'] > 0, row
        for policy in ('active', 'baseline'):
            observed = row[policy]
            assert observed['measured_turns'] == case['turns'], row
            assert all(abs(v)<1e-8 for v in observed['unposted_cash_change']), row
            assert abs(observed['aggregate_cash_change'])<1e-7, row
            assert len(observed['turns']) == case['turns'], row
            assert observed['boundary'] == 'after_production_payroll_arrears_and_obligations', row
    return dict(scope='Twenty paired production/supply decisions over complete declared turns',
                schema_version=2, decisions_checked=len(rows),
                decision_families=dict(Counter(row['case']['family'] for row in rows)),
                outcomes_at_manufacturing_cost=dict(Counter(row['outcome'] for row in rows)),
                decisions=rows)


class PlannerAcceptanceTests(unittest.TestCase):
    def test_case_is_reproducible_after_other_cases_have_consumed_rng(self):
        case = economic_cases()[0]
        first = compare_case(case)
        compare_case(economic_cases()[7])
        repeated = compare_case(case)
        for policy in ('active', 'baseline'):
            self.assertEqual(first[policy]['closing'], repeated[policy]['closing'])
            self.assertEqual(first[policy]['first_input_quantity'], repeated[policy]['first_input_quantity'])

    def test_twenty_economic_decisions(self):
        report = twenty_decisions()
        self.assertEqual(report['decision_families'], dict(one_batch=5, larger_batch=5, wait=5, decline=5))
        self.assertTrue(any(row['active']['first_input_quantity'] == 12 for row in report['decisions']))
        output = os.environ.get('ELITE_PLANNER_ACCEPTANCE_REPORT')
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')

    def test_off_and_shadow_leave_identical_complete_turn_economy_and_rng(self):
        from simulation_semantics import canonical_state, graph_differences
        # Load all normal handlers before capturing module-global state.
        compare_case(economic_cases()[0])
        case = economic_cases()[1]
        region, firm = build_case(case)
        frozen = freeze_case(region, firm)
        off, _, _ = observe_case(case, frozen, 'off')
        expected = canonical_state([off], [])
        shadow, _, _ = observe_case(case, frozen, 'shadow')
        shadow._elite_planning_config = ElitePlanningConfig(horizon=case.turns)
        actual = canonical_state([shadow], [])
        self.assertFalse(graph_differences(expected['graph'], actual['graph']))
