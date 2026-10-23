import unittest
from trace_audit import audit
from trace_coverage import coverage
from treasury_trace import begin_public_change,finish_public_change


class DesktopTraceSessionTests(unittest.TestCase):
    def test_native_world_and_between_turn_action_have_closed_evidence(self):
        from client.desktop.engine import build_world_view,step_world
        world=build_world_view(seed=4242,terrain_seed=4242,nation_seed=4242)
        step_world(world)
        trace=world['run_trace']
        nation=world['nations'][0]
        before=nation.treasury()['total']
        context=begin_public_change(nation,nation.government.agent)
        nation.government.agent.cash-=10
        finish_public_change(context,'native_test_spending')
        step_world(world)
        rows=trace.query(kind='treasury_account_closure',subject={'id':nation.name},limit=1000)['events']
        command=next(row for row in rows if row['turn']==1 and row['epoch']>0)
        self.assertEqual(before-10,command['value_after'])
        self.assertTrue(command['formula_replay']['matches'])
        self.assertTrue(audit(trace.path)['structural_and_supported_formula_checks_pass'])
        self.assertEqual(0,coverage(trace.path)['_treasury_account_closure']['gaps'])


if __name__=='__main__':unittest.main()
