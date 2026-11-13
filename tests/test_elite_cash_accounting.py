"""Source-owned elite payments reconcile every real payer and recipient."""
import unittest
from types import SimpleNamespace

from agent import Agent, initialize_agent
from goods import Goods
from region import Region
from economy.actor_accounts import begin_turn, seal_turn
from economy.transformation_graph import TransformationGraph
from tests.test_medical_care_trace import MemoryTrace


def person(good, cash, *, company=False):
    actor = Agent(0)
    initialize_agent(actor, good, 0, 0, cash)
    actor.is_corporation = company
    return actor


class EliteCashAccountingTests(unittest.TestCase):
    def machinery(self, *, construct, traced, refund=False):
        region = Region('Machinery books', 0, number_of_agents=0)
        owner = person(Goods.food, 100.0)
        company = person(Goods.furniture, 10.0, company=True)
        company.broken_machinery = 1
        owner.company_owned = company
        artisan = person(Goods.wood if construct else Goods.iron, 0.0)
        region.agents = [owner, company]
        if refund:
            region.gov = None
        else:
            region.agents.extend((artisan, region.gov.agent))
        region.recipes[Goods.iron]['price'] = 5.0
        region.recipes[Goods.coal]['price'] = 3.0
        for actor in region.agents:
            actor.inv_set(Goods.iron, 0)
            actor.inv_set(Goods.coal, 0)
        if traced:
            region._run_trace = MemoryTrace()
            region._collective_trace_clock = {'turn': 1, 'phase': 'local', 'next': 1}
        before = sum(a.cash for a in region.agents)
        begin_turn(region, 1)
        operation = 'construct_machinery' if construct else 'maintain_repair_machinery'
        result = TransformationGraph.get_operator(operation).on_execute(owner, region, 1)
        self.assertTrue(result['success'])
        self.assertAlmostEqual(before, sum(a.cash for a in region.agents))
        rows = {row['actor_id']: row for row in seal_turn(region, 1)}
        for row in rows.values():
            self.assertAlmostEqual(row['unposted_cash_change'], 0.0, msg=str(row['actor_id']))
        self.assertTrue(region.economic_events)
        self.assertTrue(all(e['payer_id'] is not None and e['recipient_id'] is not None
                            for e in region.economic_events))
        self.assertFalse(any(e['kind'] == 'capitalist_action_cash' for e in region.economic_events))
        return region, owner, company, rows

    def test_split_company_owner_funding_and_material_surcharge_are_journaled(self):
        for construct in (True, False):
            for traced in (True, False):
                with self.subTest(construct=construct, traced=traced):
                    region, owner, company, rows = self.machinery(construct=construct, traced=traced)
                    self.assertEqual(rows[company.id]['cash_change'], -10.0)
                    self.assertEqual(rows[owner.id]['cash_change'], -28.0 if construct else -5.0)
                    self.assertEqual({e['payer_id'] for e in region.economic_events},
                                     {owner.id, company.id})

    def test_missing_recipients_refund_the_named_funding_accounts(self):
        for construct in (True, False):
            with self.subTest(construct=construct):
                _, owner, company, rows = self.machinery(construct=construct, traced=False, refund=True)
                # Original service fallback credits the sponsoring owner.
                self.assertEqual(rows[company.id]['cash_change'], -10.0)
                self.assertEqual(rows[owner.id]['cash_change'], 10.0)

    def test_frontier_cash_payments_reconcile_all_commoners(self):
        for op_id in ('chartered_frontier_conquest', 'procure_captive_labor',
                      'mandate_plantation_labor_gang'):
            with self.subTest(operator=op_id):
                region = Region('Frontier books', 0, number_of_agents=0)
                owner = person(Goods.food, 100.0)
                owner.is_lord = True
                owner.frontier_estates = [{'primary_commodity': 'cotton', 'captive_labor': 5}]
                region.agents = [owner, person(Goods.wood, 0), person(Goods.wood, 0), region.gov.agent]
                region.neighbors = {'Frontier': SimpleNamespace(name='Frontier', wilderness=True,
                                                               wilderness_pop=15, climate='tropical')}
                before = sum(a.cash for a in region.agents)
                begin_turn(region, 1)
                result = TransformationGraph.get_operator(op_id).on_execute(owner, region, 1)
                self.assertTrue(result['success'])
                self.assertAlmostEqual(sum(a.cash for a in region.agents), before)
                for row in seal_turn(region, 1):
                    self.assertAlmostEqual(row['unposted_cash_change'], 0.0)

    def test_capital_expansion_and_new_company_equity_are_posted_at_source(self):
        from dataclasses import replace
        from world_config import FULL_GAMEPLAY_FLAGS
        from economy.elite_decision import EliteDecision
        from economy.elite_investment import invest_capital
        for existing_company in (True, False):
            with self.subTest(existing_company=existing_company):
                region = Region('Equity books', 0, number_of_agents=0)
                region._gameplay_flags = replace(FULL_GAMEPLAY_FLAGS, abundance=False)
                owner = person(Goods.wood, 400.0)
                region.agents = [owner, region.gov.agent]
                if existing_company:
                    company = person(Goods.furniture, 50.0, company=True)
                    company.home_currency = region.home_currency
                    company.wage, company.max_employees = 2.0, 10
                    owner.company_owned = company
                    region.agents.append(company)
                before = sum(a.cash for a in region.agents)
                begin_turn(region, 1)
                decision = EliteDecision(owner, region, 1, 1.0, [])
                result = invest_capital(decision)
                self.assertIsNotNone(result)
                self.assertAlmostEqual(sum(a.cash for a in region.agents), before)
                for row in seal_turn(region, 1):
                    self.assertAlmostEqual(row['unposted_cash_change'], 0.0)
                events = [e for e in region.economic_events if e['kind'] == 'owner_financing']
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['recipient_id'], owner.company_owned.id)

    def test_law_petition_fee_is_journaled_without_the_planner_wrapper(self):
        from labor_laws import submit_law_petition
        region = Region('Law books', 0, number_of_agents=0)
        owner = person(Goods.wood, 100.0)
        region.agents = [owner, region.gov.agent]
        begin_turn(region, 1)
        self.assertIsNotNone(submit_law_petition(owner, region, 'wage_cap', 20.0, 1))
        for row in seal_turn(region, 1):
            self.assertEqual(row['unposted_cash_change'], 0.0)

    def voyage(self):
        from economy.trade_circuit_discovery import TradeCircuitSpec
        from economy.triangular_trade import TradeTriangleManager
        circuit = TradeCircuitSpec('books', 'Books voyage', 'cloth', None, 'foreign_luxuries',
                                   base_voyage_turns=2)
        region = Region('Voyage books', 0, number_of_agents=0)
        owner = person(Goods.food, 100.0)
        owner.inv_add(Goods.cloth, 5)
        region.agents = [owner, person(Goods.wood, 0), region.gov.agent]
        return TradeTriangleManager([circuit]), region, owner

    def test_voyage_freight_and_arrival_tariff_are_paired(self):
        manager, region, owner = self.voyage()
        region._last_turn = 1
        begin_turn(region, 1)
        self.assertTrue(manager.charter_voyage(owner, region, 'books')['success'])
        for row in seal_turn(region, 1):
            self.assertAlmostEqual(row['unposted_cash_change'], 0.0)
        begin_turn(region, 2)
        manager.step_all_voyages({'regions': [region]}, 2)
        manager.step_all_voyages({'regions': [region]}, 2)
        for row in seal_turn(region, 2):
            self.assertAlmostEqual(row['unposted_cash_change'], 0.0)
        self.assertTrue(any(e['kind'] == 'voyage_tariff' for e in region.economic_events))

    def test_voyage_missing_cargo_producer_cannot_charge_or_create_cargo(self):
        manager, region, owner = self.voyage()
        owner.inv_set(Goods.cloth, 0)
        before = [a.cash for a in region.agents]
        result = manager.charter_voyage(owner, region, 'books')
        self.assertFalse(result['success'])
        self.assertEqual(before, [a.cash for a in region.agents])
        self.assertEqual(manager.active_voyages, [])

    def test_missing_tariff_payer_or_recipient_cannot_mint_or_destroy_cash(self):
        for missing in ('investor', 'government'):
            with self.subTest(missing=missing):
                manager, region, owner = self.voyage()
                self.assertTrue(manager.charter_voyage(owner, region, 'books')['success'])
                if missing == 'investor':
                    owner.alive = False
                else:
                    region.gov = None
                before = sum(a.cash for a in region.agents)
                manager.step_all_voyages({'regions': [region]}, 2)
                manager.step_all_voyages({'regions': [region]}, 2)
                self.assertAlmostEqual(before, sum(a.cash for a in region.agents))
                self.assertEqual(manager.total_tariffs_collected, 0.0)

    def test_unjournaled_custom_callback_is_not_disguised_as_a_transfer(self):
        from economy.capitalist_planner import EliteCapitalistPlanner
        region = Region('Unrecorded callback', 0, number_of_agents=0)
        owner, recipient = person(Goods.wood, 50.0), person(Goods.food, 0.0)
        region.agents = [owner, recipient]
        begin_turn(region, 1)

        def unrecorded_callback(actor, region, turn):
            actor.cash -= 12.0
            recipient.cash += 12.0
            return {'action_taken': 'CUSTOM', 'details': {'recipient_id': recipient.id}}

        planner = EliteCapitalistPlanner()
        planner._plan_and_execute_elite = unrecorded_callback
        planner.plan_and_execute_elite(owner, region, 1)
        self.assertFalse(getattr(region, 'economic_events', []))
        rows = {row['actor_id']: row for row in seal_turn(region, 1)}
        self.assertEqual(rows[owner.id]['unposted_cash_change'], -12.0)
        self.assertEqual(rows[recipient.id]['unposted_cash_change'], 12.0)

    def test_full_self_refund_does_not_report_a_fictitious_cash_transaction(self):
        region = Region('Self refund', 0, number_of_agents=0)
        company = person(Goods.furniture, 100.0, company=True)
        region.agents, region.gov = [company], None
        for good in (Goods.iron, Goods.coal):
            company.inv_set(good, 0)
        begin_turn(region, 1)
        result = TransformationGraph.get_operator('construct_machinery').on_execute(company, region, 1)
        self.assertTrue(result['success'])
        self.assertEqual(company.cash, 100.0)
        self.assertFalse(getattr(region, 'economic_events', []))
        self.assertEqual(seal_turn(region, 1)[0]['unposted_cash_change'], 0.0)
