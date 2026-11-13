import unittest
from goods import Goods
from economy.capitalist_planner import EliteCapitalistPlanner
from tests.elite_plan_fixture import firm_fixture, set_fixture_price
from tests.elite_economic_accounts import FirmAccounts
from tests.elite_economic_turn import run_turn
from world_config import ElitePlanningConfig


class EconomicAccountingTests(unittest.TestCase):
    def test_manufacturing_cost_is_an_asset_until_sold_not_immediate_profit(self):
        r, firm, *_ = firm_fixture()
        accounts = FirmAccounts(firm)
        firm.cash = 13  # 20 minus 4 material and 3 direct wages.
        firm.inv_set(Goods.furniture, 1)
        accounts.observe_turn(firm, [
            dict(kind='input_consumed', payer_id=firm.id, recipient_id=None, amount=4),
            dict(kind='production', payer_id=None, recipient_id=firm.id, quantity=1),
            dict(kind='wage', payer_id=firm.id, recipient_id=None, amount=3)])
        sheet = accounts.balance_sheet(firm, r, {Goods.furniture:10})
        self.assertEqual(sheet['net_assets_at_manufacturing_cost'], 20)
        firm.cash += 10
        firm.inv_set(Goods.furniture, 0)
        accounts.observe_turn(firm, [dict(kind='spot_sale', payer_id=-1, recipient_id=firm.id,
                                        good='furniture', quantity=1, amount=10)])
        self.assertEqual(accounts.balance_sheet(firm, r, {})['net_assets_at_manufacturing_cost'], 23)

    def test_fixture_prices_and_anchors_agree(self):
        r, *_ = firm_fixture()
        for good in (Goods.wood, Goods.furniture):
            self.assertEqual(r._price_ref[good], r.recipes[good]['price'])
        set_fixture_price(r, Goods.furniture, 18)
        self.assertEqual(r._price_ref[Goods.furniture], 18)

    def test_complete_turn_keeps_payroll_and_inventory_debt_in_net_assets(self):
        r, firm, *_ = firm_fixture()
        r.elite_planner = EliteCapitalistPlanner()
        account = FirmAccounts(firm)
        observed = run_turn(r, firm, 1, account)
        self.assertTrue(any(e['kind'] == 'wage' and e['payer_id'] == firm.id for e in observed['events']))
        self.assertAlmostEqual(observed['statement']['unposted_cash_change'], 0)
        sheet = account.balance_sheet(firm, r, {Goods.wood:3, Goods.furniture:15})
        self.assertGreater(sheet['inventory']['furniture']['manufacturing_cost'], 0)
        replay = sheet['cash'] + sheet['deposits'] + sum(v['manufacturing_cost'] for v in sheet['inventory'].values()) - sheet['bank_principal'] - sheet['cash_obligations'] - sheet['wage_arrears']
        self.assertAlmostEqual(replay, sheet['net_assets_at_manufacturing_cost'])

    def test_wait_and_decline_replace_the_ordinary_input_bid(self):
        for action in ('wait', 'decline'):
            with self.subTest(action=action):
                r, firm, *_ = firm_fixture()
                r._elite_planning_config = ElitePlanningConfig(mode='active')
                r.elite_planner = EliteCapitalistPlanner()
                if action == 'wait':
                    firm.inv_set(Goods.wood, 2)
                    firm.cost_set(Goods.wood, 3)
                else:
                    r.economic_events = []
                observed = run_turn(r, firm, 1, FirmAccounts(firm))
                self.assertEqual(observed['decision']['action_taken'], 'WAIT_INPUT' if action == 'wait' else 'DECLINE_INPUT')
                buys = [e for e in observed['events'] if e['kind'] == 'spot_sale' and e['payer_id'] == firm.id and e['good'] == 'wood']
                self.assertFalse(buys)
                self.assertEqual(len(firm.loans), 0)
                self.assertEqual(firm.inv_get(Goods.furniture), 1 if action == 'wait' else 0)
                from economy.elite_plan_execution import maintain_plans
                maintain_plans(r.elite_planner, r, 2)
                self.assertTrue(r.elite_planner.should_run_planning(firm, r, 2, False))

    def test_hold_survives_checkpoint_serialization_and_mode_switch(self):
        import io, pickle
        from simulation_checkpoint import CheckpointPickler
        from economy.elite_plan_execution import review_plan, maintain_plans
        from economy.elite_plan_orders import input_bid
        r, firm, *_ = firm_fixture()
        r._elite_planning_config = ElitePlanningConfig(mode='active')
        r.elite_planner = EliteCapitalistPlanner()
        firm.inv_set(Goods.wood, 2)
        review_plan(r.elite_planner, firm, r, 1)
        payload = io.BytesIO()
        CheckpointPickler(payload).dump((r, firm.id))
        restored, firm_id = pickle.loads(payload.getvalue())
        actor = next(a for a in restored.agents if a.id == firm_id)
        self.assertEqual(input_bid(restored, actor, Goods.wood), 0)
        restored._elite_planning_config = ElitePlanningConfig(mode='off')
        maintain_plans(restored.elite_planner, restored, 1)
        self.assertIsNone(input_bid(restored, actor, Goods.wood))
