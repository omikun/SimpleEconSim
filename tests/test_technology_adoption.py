"""Commercial decisions, private ownership and conserved physical deployment."""
import pickle
from unittest import TestCase
from unittest.mock import patch

from agent import Agent, seed_traits
from buildings import BUILDING_RECIPES, Building
from economy.actor_accounts import record
from engineering import quote_recipe, record_operation
from innovation import InnovationSystem
from nation import Nation
from region import Region
from goods import Goods
from technology_adoption import (investment_economics, observe_firm_market,
    adoption_candidates, commission_private_adoption, step_private_adoption)
from tests.test_engineering import grant


class CommercialAdoptionTests(TestCase):
    def setUp(self):
        self.nation = Nation('Adoption', initial_cash=5000)
        self.region = Region('Factory', 0, 12, number_of_traders=0)
        self.nation.add_tile(self.region)
        self.system = InnovationSystem()
        grant(self.system, self.nation)
        self.firm = Agent(0)
        seed_traits(self.firm)
        self.firm.is_corporation = True
        self.firm.region = self.region.name
        self.firm.home_currency = self.region.home_currency
        self.firm._bank_ref = self.region.bank
        self.firm.output = Goods.furniture
        self.firm.wage = 2
        self.firm.cash = 5000
        self.firm.risk_tolerance = 0.5
        self.region.agents.append(self.firm)
        people = [a for a in self.region.agents if not a.is_government and not a.is_lord
                  and not a.is_corporation and not a.is_trader]
        self.firm.employees = people[:2]
        for worker in self.firm.employees:
            worker.employer = self.firm
        for good in Goods:
            people[-1].inv_add(good, 100)
        for turn in range(1, 9):
            record(self.region, 'production', turn=turn, recipient_id=self.firm.id,
                   good=Goods.furniture, quantity=40)
            record(self.region, 'spot_sale', turn=turn, recipient_id=self.firm.id,
                   payer_id=people[-1].id, good=Goods.furniture, quantity=40, amount=2000)
            record(self.region, 'wage', turn=turn, payer_id=self.firm.id,
                   recipient_id=people[0].id, amount=4)
            observe_firm_market(self.region, self.firm, turn)

    def candidate(self, action='install'):
        return next(c for c in adoption_candidates(self.system, self.nation, self.region, self.firm, 9)
                    if c['tech_id'] == 'steam_engines' and c['action'] == action)

    def economics(self, **overrides):
        inputs = dict(revenue=300, produced=10, sold=10, operating_cost=80,
            gain_fraction=0.5, lost_fraction=0.2, capital_cost=400, downtime=0,
            cash=1000, reserve=100, credit_capacity=1800, interest_rate=0.001,
            risk_tolerance=0.5)
        return investment_economics(**{**inputs, **overrides})

    def complete(self, candidate):
        project = commission_private_adoption(self.system, self.nation, self.region,
                                              self.firm, candidate, 9)
        self.assertIsNotNone(project)
        for turn in range(9, 30):
            if project.step(turn) is not None:
                break
        self.assertEqual(project.status, 'completed')
        return project

    def test_actual_sales_not_cash_or_unsold_production_drive_adoption(self):
        self.assertTrue(self.economics()['feasible'])
        self.assertEqual(self.economics(revenue=0, sold=0, cash=100000)['reason'], 'no_realized_demand')
        self.assertLess(self.economics(sold=1)['net_gain_per_turn'], self.economics()['net_gain_per_turn'])
        self.assertGreater(self.economics(downtime=8)['payback_turns'], self.economics()['payback_turns'])
        self.assertLess(self.economics(risk_tolerance=0)['horizon'], self.economics(risk_tolerance=1)['horizon'])
        self.assertFalse(self.economics(operating_cost=1000)['feasible'])

    def test_credit_and_debt_service_constrain_illiquid_firms(self):
        self.assertTrue(self.economics(cash=100)['feasible'])
        self.assertEqual(self.economics(cash=100, credit_capacity=0)['reason'], 'credit_unavailable')
        self.assertFalse(self.economics(cash=100, interest_rate=0.3)['feasible'])

    def test_saved_cash_is_withdrawn_before_new_debt(self):
        self.region.bank.Deposit(self.firm, 4950, trace_region=self.region, t=8)
        candidate = self.candidate()
        self.assertEqual(candidate['economics']['borrowing'], 0)
        project = commission_private_adoption(self.system, self.nation, self.region, self.firm, candidate, 9)
        self.assertIsNotNone(project)
        self.assertEqual(self.firm.technology_adoption_borrowed, 0)
        self.assertGreater(self.firm.last_technology_investment['savings_withdrawn'], 0)

    def test_a_full_sales_window_is_required_and_zero_turn_is_not_an_observation(self):
        history = list(self.firm.technology_market_history)
        self.firm.technology_market_history = history[:3]
        self.assertEqual(adoption_candidates(self.system, self.nation, self.region, self.firm, 9), [])
        self.firm.technology_market_history = []
        self.assertEqual(observe_firm_market(self.region, self.firm, 0), [])

    def test_settled_sales_exclude_foreign_seller_accounts_and_use_cash_receipts(self):
        record(self.region, 'spot_sale', turn=9, recipient_id=self.firm.id,
               good=Goods.furniture, quantity=10, amount=100,
               detail={'seller_account_tile': 'Other'})
        record(self.region, 'spot_sale', turn=9, recipient_id=self.firm.id,
               good=Goods.furniture, quantity=3, amount=90, detail={'cash_receipt': 75})
        sample = observe_firm_market(self.region, self.firm, 9)[-1]
        self.assertEqual(sample['revenue'], 75)
        self.assertEqual(sample['sold'], 3)

    def test_decisions_link_sales_evidence_and_replay_the_recorded_estimate(self):
        from tests.test_build_intent_trace import MemoryTrace
        trace = MemoryTrace()
        self.region._run_trace = trace
        self.region._collective_trace_clock = {'turn': 9, 'phase': 'projects', 'next': 1}
        self.firm.technology_market_history = []
        for turn in range(1, 9):
            observe_firm_market(self.region, self.firm, turn)
        turn = 9
        with patch('technology_adoption.DECISION_INTERVAL', 1):
            step_private_adoption([self.region], [self.nation], turn, self.system)
        decisions = [r for r in trace.rows if r['kind'] == 'commercial_technology_adoption_decision']
        self.assertTrue(decisions)
        for row in decisions:
            self.assertTrue(row['cause_event_ids'])
            self.assertEqual(investment_economics(**row['inputs']['estimate_inputs']), row['inputs']['economics'])
        spending = next(r for r in trace.rows if r['kind'] == 'commercial_technology_commissioned')
        self.assertEqual(spending['after'], self.firm.technology_adoption_spent)
        self.assertTrue(spending['cause_event_ids'])

    def test_observations_are_idempotent_and_ignore_credit_and_unsold_stock(self):
        record(self.region, 'bank_loan', turn=8, recipient_id=self.firm.id, amount=10000)
        self.firm.inv_add(Goods.furniture, 1000)
        observe_firm_market(self.region, self.firm, 8)
        self.assertEqual(len(self.firm.technology_market_history), 8)
        self.assertEqual(self.firm.technology_market_history[-1]['revenue'], 2000)
        self.assertEqual(self.firm.technology_market_history[-1]['produced'], 40)

    def test_install_uses_firm_money_real_materials_and_private_benefits(self):
        candidate = self.candidate()
        self.assertTrue(candidate['economics']['feasible'])
        treasury = self.nation.government.agent.cash
        cash = sum(a.cash for a in self.region.agents)
        stocks = {g: sum(a.inv_get(g, 0) for a in self.region.agents) for g in candidate['recipe'].required_goods}
        project = self.complete(candidate)
        self.assertAlmostEqual(cash, sum(a.cash for a in self.region.agents))
        self.assertEqual(self.nation.government.agent.cash, treasury)
        for good, quantity in project.recipe.required_goods.items():
            self.assertEqual(stocks[good] - sum(a.inv_get(good, 0) for a in self.region.agents), quantity)
        asset = self.region.buildings[-1]
        self.assertEqual(asset.private_owner_id, self.firm.id)
        from region_production import terrain_bonus
        owner_bonus = terrain_bonus(self.region, Goods.furniture, 25, producer=self.firm)
        outsider = self.firm.employees[0]
        self.assertGreater(owner_bonus, terrain_bonus(self.region, Goods.furniture, 25, producer=outsider))
        record_operation(self.region, outsider, Goods.furniture, 2, 2, 25)
        self.assertEqual(self.region.technology_usage, {})
        record_operation(self.region, self.firm, Goods.furniture, 2, 2, 25)
        self.assertEqual(len(self.region.technology_usage), 1)
        self.assertFalse(any(c['tech_id'] == 'steam_engines' for c in
            adoption_candidates(self.system, self.nation, self.region, self.firm, 9)))

    def test_bank_financing_is_real_and_frozen_bank_does_not_convert_people(self):
        self.firm.cash = 150
        candidate = self.candidate()
        self.region.bank.is_frozen = True
        roles = [(a.id, a.is_corporation) for a in self.region.agents]
        self.assertIsNone(commission_private_adoption(self.system, self.nation, self.region, self.firm, candidate, 9))
        self.assertEqual(roles, [(a.id, a.is_corporation) for a in self.region.agents])
        self.region.bank.is_frozen = False
        liabilities = self.region.bank.total_liabilities
        project = commission_private_adoption(self.system, self.nation, self.region, self.firm, candidate, 9)
        self.assertIsNotNone(project)
        borrowed = self.firm.technology_adoption_borrowed
        self.assertGreater(borrowed, 0)
        self.assertAlmostEqual(self.region.bank.total_liabilities - liabilities, borrowed)
        self.assertAlmostEqual(self.firm.loans[-1].principle, borrowed)

    def test_missing_crew_does_not_spend_borrow_or_convert_a_founder(self):
        for a in self.region.agents:
            if a not in self.firm.employees and not a.is_corporation and not a.is_government:
                a.is_native_child = True
        before = [(a.id, a.cash, a.is_corporation) for a in self.region.agents]
        self.assertIsNone(commission_private_adoption(self.system, self.nation, self.region, self.firm, self.candidate(), 9))
        self.assertEqual(before, [(a.id, a.cash, a.is_corporation) for a in self.region.agents])

    def test_retrofit_and_replacement_update_owned_asset_without_stacking(self):
        for action in ('retrofit', 'replace'):
            with self.subTest(action=action):
                recipe = quote_recipe(self.nation, BUILDING_RECIPES['steam_engines_prototype'], self.system)
                old = Building(recipe.name, recipe, 0, self.region.name)
                old.technology_designs = {'steam_engines': 1}
                old.private_owner_id = self.firm.id
                self.region.buildings = [old]
                self.system.tech_refinement_xp[self.nation.name]['steam_engines'] = 60
                candidate = self.candidate(action)
                project = self.complete(candidate)
                self.assertEqual(len(self.region.buildings), 1)
                self.assertEqual(self.region.buildings[0].technology_designs['steam_engines'], 3)
                self.assertIsNone(old.retrofit_project_id)
                self.assertEqual(self.region.buildings[0].private_owner_id, self.firm.id)
                if action == 'retrofit':
                    self.assertIs(self.region.buildings[0], old)

    def test_cancelled_replacement_restores_existing_equipment(self):
        recipe = quote_recipe(self.nation, BUILDING_RECIPES['steam_engines_prototype'], self.system)
        old = Building(recipe.name, recipe, 0, self.region.name)
        old.private_owner_id = self.firm.id
        self.region.buildings = [old]
        self.system.tech_refinement_xp[self.nation.name]['steam_engines'] = 60
        project = commission_private_adoption(self.system, self.nation, self.region, self.firm, self.candidate('replace'), 9)
        self.assertFalse(old.production_bonuses)
        project.status = 'cancelled'
        project.step(10)
        self.assertTrue(old.production_bonuses)

    def test_duplicate_turns_and_saved_graph_preserve_single_investment(self):
        turn = 9
        with patch('technology_adoption.DECISION_INTERVAL', 1):
            step_private_adoption([self.region], [self.nation], turn, self.system)
            spent = self.firm.technology_adoption_spent
            step_private_adoption([self.region], [self.nation], turn, self.system)
        self.assertEqual(self.firm.technology_adoption_spent, spent)
        saved_nation, saved_firm = pickle.loads(pickle.dumps((self.nation, self.firm)))
        self.assertEqual(saved_firm.last_technology_investment, self.firm.last_technology_investment)
        self.assertIs(saved_nation.tiles[0].construction_projects[0].region, saved_nation.tiles[0])
        status = self.system.engineering_status(self.nation, 'steam_engines', turn)
        self.assertEqual(status['commercial_decisions'][0]['firm_id'], self.firm.id)
