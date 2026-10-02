"""Focused checks for Egypt's legacy bond and assigned revenue accounting."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from government import Government
from sovereign_bonds import SovereignBondMarket
from scenario_debt import initialize, bonds, outstanding, pay, revise, set_collection_assignment


class FakeGovernment:
    def __init__(self, cash):
        self.agent = SimpleNamespace(cash=float(cash))
        self._income_pending = {}


class FakeNation:
    def __init__(self, name, cash):
        self.name = name
        self.government = FakeGovernment(cash)
        self.tiles = []
        self.provinces = []


class ScenarioDebtTests(unittest.TestCase):
    def setUp(self):
        self.market = SovereignBondMarket()
        self.market_patch = patch('scenario_debt.get_bond_market', return_value=self.market)
        self.market_patch.start()
        self.addCleanup(self.market_patch.stop)
        self.egypt = FakeNation('Egypt', 500)
        self.britain = FakeNation('Britain', 400)
        self.france = FakeNation('France', 400)
        household = SimpleNamespace(alive=True, cash=0.0, is_government=False,
                                    is_corporation=False)
        tile = SimpleNamespace(gov=self.egypt.government, agents=[household])
        self.egypt.tiles = [tile]
        self.world = {'turn': 1, 'nations': [self.egypt, self.britain, self.france],
                      'scenario_state': {'scheduled_remittance': 200.0,
                                         'payment_window_turn': 6,
                                         'creditor_levy_per_turn': 0.0}}
        initialize(self.world)

    def test_legacy_bonds_and_revised_due_date(self):
        self.assertEqual([bond.principal for bond in bonds(self.world)], [100.0, 100.0])
        revise(self.world, 220, due_turn=9)
        self.assertEqual(outstanding(self.world), 220.0)
        self.assertEqual([bond.maturity_turn for bond in bonds(self.world)], [9, 9])

    def test_receipts_are_capped_and_final_payment_settles_bonds(self):
        state = self.world['scenario_state']
        state['creditor_levy_per_turn'] = 5.0
        state['creditor_levy_remaining'] = 200.0
        state['payment_status'] = 'defaulted'
        self.world['turn'] = 2
        total_before = sum(n.government.agent.cash for n in self.world['nations'])
        self.egypt.government.agent.cash += 20.0
        Government.record_income(self.egypt.government, 2, 'tax', 20.0)
        self.assertEqual(state['debt_collected_this_turn'], 5.0)
        self.assertEqual(self.egypt.government._income_pending['tax'], 15.0)
        self.assertEqual(outstanding(self.world), 195.0)
        self.assertEqual(self.britain.government.agent.cash, 402.5)
        self.assertEqual(self.france.government.agent.cash, 402.5)
        self.egypt.government.agent.cash += 20.0
        Government.record_income(self.egypt.government, 2, 'tax', 20.0)
        self.assertEqual(state['debt_collected_this_turn'], 5.0)
        self.assertEqual(self.egypt.government._income_pending['tax'], 35.0)
        self.assertEqual(sum(n.government.agent.cash for n in self.world['nations']), total_before + 40)
        ok, _ = pay(self.world, 195)
        self.assertTrue(ok)
        self.assertEqual(outstanding(self.world), 0.0)
        self.assertTrue(all(bond.status == 'redeemed' for bond in bonds(self.world)))
        self.assertEqual(sum(n.government.agent.cash for n in self.world['nations']), total_before + 40)

    def test_collection_assignment_records_terms_and_discharge(self):
        state = self.world['scenario_state']
        set_collection_assignment(self.world, 5, origin='caisse_consent')
        agreement = state['collection_assignment']
        self.assertEqual(agreement['origin'], 'caisse_consent')
        self.assertEqual(agreement['creditors'], {'Britain': 100.0, 'France': 100.0})
        self.assertEqual(agreement['sources']['tax'], .25)
        ok, reason = pay(self.world, 200)
        self.assertTrue(ok, reason)
        self.assertEqual(agreement['status'], 'discharged')
        self.assertEqual(state['creditor_levy_per_turn'], 0)

    def test_revoking_inspection_restores_conditional_bonds_without_cash_creation(self):
        from scenario_oversight import action, sign
        self.world['scenario'] = {'horizon_turns': 20}
        self.world['turn'] = 6
        state = self.world['scenario_state']
        state['creditor_confidence'] = .75
        state['fiscal_autonomy'] = .75
        ok, reason = pay(self.world, 100, kind='concession_payment', forgive_remainder=True)
        self.assertTrue(ok, reason)
        sign(self.world, written_down=100)
        cash_before = sum(n.government.agent.cash for n in self.world['nations'])
        ok, reason = action(self.world, 'revoke_oversight')
        self.assertTrue(ok, reason)
        self.assertEqual(outstanding(self.world), 100)
        self.assertEqual(state['payment_window_turn'], 8)
        self.assertEqual(state['payment_status'], 'deferred')
        self.assertEqual(sum(n.government.agent.cash for n in self.world['nations']), cash_before)


if __name__ == '__main__':
    unittest.main()
