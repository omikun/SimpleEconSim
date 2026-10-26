"""Actual public balance chains for military and medical settlements."""
from pathlib import Path
import random
import tempfile
import unittest

from agent import Agent
from army import MilitaryUnit, step_armies
from disease import DIS_MALNUTRITION, step_medical_care
from goods import Goods
from nation import Nation
from region import Region
from run_trace import RunTrace, verify


class MilitaryMedicalAccountTraceTests(unittest.TestCase):
    def attach(self, nation, tile):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        trace = RunTrace(Path(directory.name) / 'accounts.ctr', 'accounts', recent_limit=10000)
        clock = {'turn': 0, 'phase': 'setup', 'next': 1}
        for source in (nation, tile):
            source._run_trace, source._collective_trace_clock = trace, clock
        trace.bank_book.register_tiles([tile], clock)
        trace.treasury_book.register_nations([nation], clock)
        before = {('finance.treasury', nation.name): (None, nation.currency, nation.treasury()['total'])}
        clock.update(turn=3, phase='military')
        return trace, clock, before

    def close(self, nation, tile, trace, clock, before):
        trace.bank_book.close([tile], clock, {})
        trace.treasury_book.close([nation], clock, before)
        row = next(row for row in reversed(trace.recent) if row['kind'] == 'treasury_account_closure')
        self.assertEqual('calculation', row['record_class'], row['inputs'])
        self.assertTrue(row['formula_replay']['matches'])
        flows = trace._treasury_flows.get(nation.name, ())
        self.assertAlmostEqual(nation.treasury()['total'] - before[('finance.treasury', nation.name)][2],
                               sum(flow['amount'] for flow in flows))
        trace.checkpoint(clock)
        self.assertEqual(1, verify(trace.path)['checkpoints'])

    def test_procurement_and_full_payroll_link_to_account_writes(self):
        from test_military_upkeep_trace import _scenario_personnel_fixture
        nation, tile, _sellers, _balances, soldiers, unit, _ = _scenario_personnel_fixture(traced=False)
        # Region's zero-agent constructor can populate default households.
        # Keep this fixture's explicit seller and two soldiers in both runs.
        tile.agents = tile.agents[-3:]
        trace, clock, before = self.attach(nation, tile)
        rng = random.getstate()
        step_armies([tile], [nation], t=3)
        self.assertEqual(rng, random.getstate())
        self.close(nation, tile, trace, clock, before)
        rows = list(trace.recent)
        writes = {row['event_id']: row for row in rows if row['kind'] == 'public_account_write'}
        for kind in ('army_payroll', 'army_ration_cash_payment'):
            payment = next(row for row in rows if row['kind'] == kind)
            sources = [writes[ident] for ident in payment['cause_event_ids'] if ident in writes]
            self.assertEqual(1, len(sources))
            self.assertEqual(payment['inputs']['operation_id'], sources[0]['inputs']['operation_id'])
        self.assertEqual(4, sum(person.cash for person in soldiers))
        plain = _scenario_personnel_fixture(traced=False)
        plain[1].agents = plain[1].agents[-3:]
        step_armies([plain[1]], [plain[0]], t=3)
        def state(nation, region, soldiers, unit):
            return (nation.government.agent.cash, nation.government.food_inventory,
                    region.bank.total_deposits, region.bank.total_liabilities,
                    unit.soldiers, unit.morale, [person.cash for person in soldiers],
                    sorted((person.output.name, person.cash, person.inv_get(Goods.food, 0))
                           for person in region.agents))
        self.assertEqual(state(nation, tile, soldiers, unit),
                         state(plain[0], plain[1], plain[4], plain[5]))

    def test_partial_payroll_frozen_withdrawal_opens_after_funding(self):
        from test_military_upkeep_trace import _scenario_personnel_fixture
        nation, tile, *_ = _scenario_personnel_fixture(traced=False)
        gov = nation.government.agent
        gov.cash = 0
        tile.bank.deposits[gov] = 10
        tile.bank.total_deposits = 10
        tile.bank.is_frozen = True
        tile.bank.subsistence_withdrawal_cap = 2
        trace, clock, before = self.attach(nation, tile)
        step_armies([tile], [nation], t=3)
        self.close(nation, tile, trace, clock, before)
        debit = next(row for row in trace.recent if row['kind'] == 'public_account_write'
                     and row['inputs']['operation_kind'] == 'military_payroll_debit')
        self.assertEqual((2, 0), (debit['value_before'], debit['value_after']))
        payroll = next(row for row in trace.recent if row['kind'] == 'army_payroll')
        self.assertEqual(-2, payroll['value_after'])
        self.assertEqual(8, tile.bank.deposits[gov])

    def test_unfunded_payroll_does_not_create_public_write(self):
        from test_military_upkeep_trace import _scenario_personnel_fixture
        nation, tile, *_ = _scenario_personnel_fixture(traced=False)
        nation.government.agent.cash = 0
        trace, clock, before = self.attach(nation, tile)
        step_armies([tile], [nation], t=3)
        self.close(nation, tile, trace, clock, before)
        self.assertFalse(any(row['kind'] == 'public_account_write' for row in trace.recent))
        self.assertTrue(any(row['kind'] == 'army_payroll_unpaid' for row in trace.recent))

    def medical(self, public, practitioner, *, patient_cash=60, public_cash=100, traced=True):
        nation = Nation('Medical', 'C', initial_cash=0, register=False)
        tile = Region('Ward', 0, 0)
        nation.add_tile(tile)
        tile.public_healthcare_decree = public
        tile.gov.agent.cash = public_cash
        patient = Agent(0)
        patient.output, patient.cash = Goods.food, patient_cash
        patient.diseases = [DIS_MALNUTRITION]
        tile.agents = [patient]
        doctor = None
        if practitioner:
            doctor = Agent(0)
            doctor.output, doctor.cash = Goods.furniture, 40
            tile.agents.append(doctor)
        if traced:
            trace, clock, before = self.attach(nation, tile)
            clock['phase'] = 'healthcare'
        else:
            trace = clock = before = None
        rng = random.Random(18)
        result = step_medical_care(tile, 3, rng)
        state = (patient.cash, list(patient.diseases), patient.medical_expenses_paid,
                 doctor.cash if doctor else None, tile.gov.agent.cash,
                 tile.medical_spending_public_log, tile.medical_spending_private_log, result, rng.getstate())
        return nation, tile, trace, clock, before, state

    def test_medical_public_private_and_self_refund_have_parity_and_closure(self):
        cases = [(True, True, 60, 100), (False, True, 60, 100),
                 (True, False, 60, 100), (False, False, 60, 100),
                 (True, True, 0, 0)]
        for public, doctor, cash, funds in cases:
            with self.subTest(public=public, doctor=doctor, cash=cash):
                args = dict(patient_cash=cash, public_cash=funds)
                plain = self.medical(public, doctor, traced=False, **args)
                world = self.medical(public, doctor, traced=True, **args)
                nation, tile, trace, clock, before, state = world
                self.assertEqual(plain[-1], state)
                self.close(nation, tile, trace, clock, before)
                rows = list(trace.recent)
                if public and not doctor:
                    writes = [row for row in rows if row['kind'] == 'public_account_write']
                    self.assertEqual([-20, 20], [row['delta'] for row in writes])
                    self.assertEqual(1, len({row['inputs']['operation_id'] for row in writes}))
                    treatment = next(row for row in rows if row['kind'] == 'medical_treatment')
                    self.assertEqual([row['event_id'] for row in writes], treatment['cause_event_ids'])
                    self.assertFalse(any(row.get('metric_id') == 'finance.cash_transfer' for row in rows))
                for payment in (row for row in rows if row['kind'] == 'medical_care_payment'):
                    public_writes = [row for row in rows if row['kind'] == 'public_account_write']
                    if public_writes:
                        self.assertTrue(payment['cause_event_ids'])
                        self.assertTrue(all(row['inputs']['operation_id'] == payment['inputs']['operation_id']
                                            for row in public_writes))

    def test_omitted_self_refund_probe_is_visible_despite_zero_net_spending(self):
        from unittest.mock import patch
        from treasury_trace import finish_public_change
        def omit_refund(context, kind, **kwargs):
            if kind == 'public_medical_self_refund':
                return []
            return finish_public_change(context, kind, **kwargs)
        with patch('disease.finish_public_change', side_effect=omit_refund):
            nation, tile, trace, clock, before, _ = self.medical(True, False)
        trace.treasury_book.close([nation], clock, before)
        closure = next(row for row in reversed(trace.recent) if row['kind'] == 'treasury_account_closure')
        self.assertEqual(before[('finance.treasury', nation.name)][2], nation.treasury()['total'])
        self.assertEqual('audit', closure['record_class'])
        self.assertFalse(closure['formula_replay']['matches'])


if __name__ == '__main__':
    unittest.main()
