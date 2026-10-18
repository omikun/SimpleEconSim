"""Named actors and route in a normal seasonal engine step."""
import unittest
import pickle
from types import SimpleNamespace

from economy.actor_accounts import begin_turn, record, seal_turn
from goods import Goods
from scenario_labor_frontier_rivalry import create_world, step_world
from test_supply_rights import Person, Region
from supply_proposals import decide, propose
from economy.capitalist_planner import EliteCapitalistPlanner


class SupplyControlActorFixtureTests(unittest.TestCase):
    def test_two_growers_two_mills_and_route_survive_normal_tick(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        works = world['by_name']['Meridian Works']
        rival_works = world['by_name']['Vesper Works']
        growers = [a for a in fields.agents if a.output == Goods.cotton
                   and not a.is_corporation and getattr(a, 'alive', True)]
        mills = [a for r in (works, rival_works) for a in r.agents
                 if a.is_corporation and a.output == Goods.cloth]
        self.assertGreaterEqual(len(growers), 2)
        self.assertEqual(len(mills), 2)
        self.assertIn('Meridian Works', fields.routes)
        self.assertIn('Vesper Fields', fields.routes)
        named = [growers[0], growers[1], mills[0], mills[1]]
        before = {a.id: (a.cash, a.inv_get(a.output, 0)) for a in named}
        violations = step_world(world)
        self.assertFalse(violations)
        self.assertEqual(world['turn'], 1)
        for a in named:
            self.assertIn(a.id, before)
            self.assertTrue(any(person.id == a.id for person in
                                (fields if a in growers else works if a is mills[0]
                                 else rival_works).agents))
            home = fields if a in growers else works if a is mills[0] else rival_works
            self.assertTrue(any(row['actor_id'] == a.id for row in home.actor_turn_accounts))

    def test_poor_water_year_reduces_named_plot_allocation(self):
        world = create_world(seed=612)
        fields = world['by_name']['Meridian Fields']
        from supply_rights import allocate_seasonal_water
        normal = sum(allocate_seasonal_water(fields, 1).values())
        fields.seasonal_rainfall = 0.4
        drought = sum(allocate_seasonal_water(fields, 2).values())
        self.assertLess(drought, normal)


class ActorAccountTests(unittest.TestCase):
    def test_strike_support_cash_is_posted(self):
        from agent import Agent
        from collective_action import (CollectiveOrganization, CollectiveStrike,
                                       transfer_support)
        region = Region()
        donor, worker, firm = Agent(1), Agent(1), Agent(1)
        donor.cash, worker.cash = 12.0, 0.0
        donor.inv_add(Goods.food, 2)
        firm.is_corporation = True
        firm.employees = [worker]
        worker.employer = firm
        strike = CollectiveStrike(
            id='test-strike', firm_id=firm.id, started_turn=1,
            eligible_ids=(worker.id,), participant_ids=(worker.id,),
            baseline_wage=1.0, target_wage=2.0,
            baseline_hours=8.0, target_hours=8.0,
            baseline_food_price=2.0)
        org = CollectiveOrganization(
            firm_id=firm.id, strikes=[strike], active_strike_id=strike.id)
        region.agents = [donor, worker, firm]
        region.collective_organizations = {firm.id: org}
        begin_turn(region, 1)

        self.assertTrue(transfer_support(region, 1, donor.id, worker.id, cash=2.0))
        rows = {row['actor_id']: row for row in seal_turn(region, 1)}

        self.assertEqual(rows[donor.id]['posted_cash_change'], -2.0)
        self.assertEqual(rows[worker.id]['posted_cash_change'], 2.0)
        self.assertEqual(rows[worker.id]['unposted_cash_change'], 0.0)

    def test_charity_donations_are_posted_in_each_donors_tile_journal(self):
        from agent import Agent
        from charity import Charity
        from econsim_trade_money import Bank

        region = Region()
        region.home_currency = 'USD'
        region.cash_obligations = []
        bank = Bank()
        bank._attached_regions = [region]
        region.bank = bank
        charity = Charity(region.name, region.recipes)
        firm, wealthy = Agent(1), Agent(1)
        firm.is_corporation = True
        firm.cash = 20.0
        firm.retained_earnings = 100.0
        wealthy.cash = 1000.0
        residents = [Agent(1) for _ in range(5)]
        for person in residents:
            person.hungry_steps = 1
        region.agents = [firm, wealthy, *residents]
        begin_turn(region, 1)

        charity.collect_donations(1, region.agents, bank, regions=(region,))
        rows = {row['actor_id']: row for row in seal_turn(region, 1)}
        donations = [event for event in region.economic_events
                     if event['kind'] == 'charity_donation']

        self.assertEqual(sum(event['amount'] for event in donations), 46.0)
        self.assertEqual(rows[firm.id]['cash_change'], -10.0)
        self.assertEqual(rows[firm.id]['posted_cash_change'], -10.0)
        self.assertEqual(rows[firm.id]['unposted_cash_change'], 0.0)
        self.assertEqual(rows[wealthy.id]['cash_change'], -36.0)
        self.assertEqual(rows[wealthy.id]['posted_cash_change'], -36.0)
        self.assertEqual(rows[wealthy.id]['unposted_cash_change'], 0.0)

    def test_shared_province_actor_cash_uses_member_tile_postings(self):
        from agent import Agent

        treasury_region = Region()
        treasury_region.name = 'Treasury District'
        probate_region = Region()
        probate_region.name = 'Probate District'
        treasury = Agent(1)
        treasury.is_government = True
        decedent = Agent(1)
        treasury_region.agents = [treasury]
        probate_region.agents = [decedent]
        begin_turn(treasury_region, 9)

        treasury.cash += 42.5
        record(probate_region, 'inheritance', turn=9, payer_id=decedent.id,
               recipient_id=treasury.id, amount=42.5,
               detail={'destination': 'shared_province_treasury'})
        rows = {row['actor_id']: row for row in
                seal_turn(treasury_region, 9,
                          event_regions=(treasury_region, probate_region))}

        self.assertEqual(rows[treasury.id]['cash_change'], 42.5)
        self.assertEqual(rows[treasury.id]['posted_cash_change'], 42.5)
        self.assertEqual(rows[treasury.id]['unposted_cash_change'], 0.0)
        self.assertTrue(any(ref['tile'] == 'Probate District'
                            for ref in rows[treasury.id]['cash_event_refs']))

    def test_alienation_spending_and_entertainment_fees_reconcile(self):
        from test_supply_rights import Person
        from alienation import (apply_mass_entertainment_pacifier,
                                process_despair_spending)

        region = Region()
        worker = Person(101, 20)
        worker.alienation = 1.0
        worker.hungry_steps = 0
        worker.employer = None
        worker.is_trader = False
        merchant = Person(102, 20, Goods.furniture)
        merchant.employer = None
        merchant.is_trader = False
        treasury = Person(103, 100, Goods.gov)
        treasury.is_government = True
        region.gov = SimpleNamespace(agent=treasury)
        region.agents = [worker, merchant, treasury]
        region.entertainment_level = 1.0
        begin_turn(region, 10)

        process_despair_spending(worker, region, 10)
        apply_mass_entertainment_pacifier(region, 10)
        rows = {row['actor_id']: row for row in seal_turn(region, 10)}
        events = [event for event in region.economic_events if event['turn'] == 10]

        self.assertEqual({event['kind'] for event in events},
                         {'despair_spending', 'entertainment_fee'})
        self.assertEqual(rows[worker.id]['cash_change'], -2.0)
        self.assertEqual(rows[worker.id]['posted_cash_change'], -2.0)
        self.assertEqual(rows[merchant.id]['cash_change'], 1.0)
        self.assertEqual(rows[merchant.id]['posted_cash_change'], 1.0)
        self.assertEqual(rows[treasury.id]['cash_change'], 1.0)
        self.assertEqual(rows[treasury.id]['posted_cash_change'], 1.0)
        self.assertTrue(all(row['unposted_cash_change'] == 0.0
                            for row in rows.values()))

    def test_actor_statement_keeps_cash_changes_by_simulation_phase(self):
        from micro.region.stepper import audit_cash

        region = Region()
        actor = Person(31, 10)
        region.agents = [actor]
        region.bank = SimpleNamespace(deposits={}, loans=[], total_deposits=0,
                                      total_liabilities=0, equity=100)
        region.charity = SimpleNamespace(agent=SimpleNamespace(cash=0))
        region.cash_obligations = []
        begin_turn(region, 2)
        audit_cash(region, 2, 'step_start')
        actor.cash += 7
        audit_cash(region, 2, 'welfare_done')
        account = next(row for row in seal_turn(region, 2)
                       if row['actor_id'] == actor.id)

        self.assertEqual(account['cash_phase_changes'], [
            {'phase': 'welfare_done', 'cash_change': 7.0}])

    def test_elite_action_cash_delta_is_journaled_with_its_decision(self):
        from agent import Agent

        region = Region()
        region.goods = list(Goods)
        region.cash_obligations = []
        buyer, seller = Agent(1), Agent(1)
        buyer.cash, seller.cash = 50.0, 10.0
        region.agents = [buyer, seller]
        begin_turn(region, 3)
        planner = EliteCapitalistPlanner()
        planner._elite_candidate_snapshot = lambda *_args: []

        def buy_luxury(agent, _region, _turn):
            agent.cash -= 12.0
            seller.cash += 12.0
            return {'action_taken': 'PURCHASE_LUXURY',
                    'details': {'good': 'furniture', 'seller_id': seller.id}}

        planner._plan_and_execute_elite = buy_luxury
        planner.plan_and_execute_elite(buyer, region, 3)
        rows = {row['actor_id']: row for row in seal_turn(region, 3)}
        event = next(event for event in region.economic_events
                     if event['kind'] == 'capitalist_action_cash')

        self.assertEqual(event['payer_id'], buyer.id)
        self.assertEqual(event['recipient_id'], seller.id)
        self.assertEqual(event['detail']['action'], 'PURCHASE_LUXURY')
        self.assertEqual(rows[buyer.id]['unposted_cash_change'], 0.0)
        self.assertEqual(rows[seller.id]['unposted_cash_change'], 0.0)

    def test_turn_account_includes_a_company_founded_after_opening_snapshot(self):
        region = Region()
        region.cash_obligations = []
        founder, company = Person(8, 100), Person(9, 0, Goods.cloth)
        company.is_corporation = True
        region.agents = [founder]
        begin_turn(region, 4)
        founder.cash -= 30
        company.cash = 30
        region.agents.append(company)
        record(region, 'startup_equity', turn=4, payer_id=founder.id,
               recipient_id=company.id, amount=30)

        rows = {row['actor_id']: row for row in seal_turn(region, 4)}

        self.assertEqual(rows[company.id]['opening_cash'], 0.0)
        self.assertEqual(rows[company.id]['cash_change'], 30.0)
        self.assertEqual(rows[company.id]['unposted_cash_change'], 0.0)

    def test_government_welfare_and_ubi_transfers_reconcile_both_accounts(self):
        from agent import Agent
        from government import Government

        for transfer_kind in ('ubi_payment', 'welfare_payment'):
            with self.subTest(transfer_kind=transfer_kind):
                region = Region()
                region.home_currency = 'USD'
                region.cash_obligations = []
                region.bank = SimpleNamespace(deposits={}, loans=[])
                government = Government('Test Government', 0, initial_cash=100.0)
                recipient = Agent(1)
                recipient.hungry_steps = 1
                if transfer_kind == 'ubi_payment':
                    government.ubi_enabled = True
                    government.ubi_amount_per_turn = 7.0
                    government._add_citizen(recipient)
                region.agents = [government.agent, recipient]
                begin_turn(region, 1)

                if transfer_kind == 'ubi_payment':
                    government.distribute_ubi(1, region.agents, region=region)
                else:
                    government.distribute_welfare(1, region.agents, region=region)

                rows = {row['actor_id']: row for row in seal_turn(region, 1)}
                event = next(event for event in region.economic_events
                             if event['kind'] == transfer_kind)
                amount = event['amount']
                self.assertEqual(rows[recipient.id]['posted_cash_change'], amount)
                self.assertEqual(rows[recipient.id]['unposted_cash_change'], 0.0)
                self.assertEqual(rows[government.agent.id]['posted_cash_change'], -amount)
                self.assertEqual(rows[government.agent.id]['unposted_cash_change'], 0.0)

    def test_inherited_cash_is_posted_between_decedent_and_heir(self):
        from demographics_estate import handle_wealth_inheritance
        from types import SimpleNamespace
        region = Region()
        region.home_currency = 'USD'
        bank = SimpleNamespace(deposits={}, loans=[])
        region.bank = bank
        from agent import Agent
        decedent, heir = Agent(7), Agent(7)
        decedent.cash = 40
        decedent.descendants = [heir]
        heir._bank_ref = bank
        region.agents = [decedent, heir]
        begin_turn(region, 7)

        context = SimpleNamespace(bank=bank, default_gov=None,
                                  charity=None, source_region=region)
        handle_wealth_inheritance(context, 7, decedent, [heir])
        decedent.cash = 0
        rows = {a['actor_id']: a for a in seal_turn(region, 7)}

        self.assertEqual(heir.cash, 40)
        self.assertEqual(rows[decedent.id]['posted_cash_change'], -40)
        self.assertEqual(rows[heir.id]['posted_cash_change'], 40)
        self.assertEqual(rows[heir.id]['unposted_cash_change'], 0)

    def test_cash_rent_transfer_is_in_actor_cash_bridge(self):
        from land_rent import collect_rents
        from land_tenure import LandPlot, TenureStatus, TileTenure
        region = Region()
        lord, tenant = Person(8, 20), Person(3, 10)
        lord.is_trader = tenant.is_trader = False
        lord.is_lord = True
        plot = LandPlot(plot_id='rent-plot', tile_name='test', lord_id=lord.id,
                        fraction=1.0, tenure=TenureStatus.ENCLOSED,
                        rent_rate=4.0, tenant_ids=[tenant.id])
        region.agents = [lord, tenant]
        region.tenure = TileTenure(plots=[plot])
        region.protest_energy_log = [0.0]
        begin_turn(region, 1)

        collect_rents(region, 1)
        rows = {a['actor_id']: a for a in seal_turn(region, 1)}

        self.assertEqual(rows[tenant.id]['cash_change'], -0.5)
        self.assertEqual(rows[tenant.id]['posted_cash_change'], -0.5)
        self.assertEqual(rows[lord.id]['cash_change'], 0.5)
        self.assertEqual(rows[lord.id]['posted_cash_change'], 0.5)

    def test_contract_cash_and_debt_credit_are_separate(self):
        from crop_credit import settle_offtake_contracts
        region = Region()
        grower, mill = Person(3), Person(8, 20)
        region.agents = [grower, mill]
        grower.inventory[Goods.food] = 7
        region.production_receipts = [{'turn': 2, 'person_id': 3,
                                       'good': Goods.food, 'quantity': 5}]
        region.cash_obligations = [SimpleNamespace(id=7, balance=4.0,
                                                   status='active', debtor_id=3,
                                                   creditor_id=8)]
        region.offtake_contracts = [{'id': 1, 'lender_id': 8, 'grower_id': 3,
                                     'good': 'food', 'quantity': 3, 'remaining': 3,
                                     'unit_price': 2.0, 'due_turn': 2, 'claim_id': 7,
                                     'status': 'active'}]
        begin_turn(region, 2)
        settle_offtake_contracts(region, 2)
        accounts = {a['actor_id']: a for a in seal_turn(region, 2)}
        self.assertEqual(accounts[3]['sales_cash'], 2)
        self.assertEqual(accounts[3]['crop_value'], 6)
        self.assertEqual(accounts[3]['opening_debt'], 4)
        self.assertEqual(accounts[3]['closing_debt'], 0)
        self.assertEqual(accounts[8]['purchases_cash'], 2)
        self.assertEqual((grower.cash, mill.cash), (2, 18))
        self.assertEqual((grower.inv_get(Goods.food), mill.inv_get(Goods.food)), (4, 3))

    def test_owner_financing_changes_cash_without_recorded_profit(self):
        region = Region()
        owner, firm = Person(1, 100), Person(8, 10, Goods.cloth)
        firm.is_corporation = True
        region.agents = [owner, firm]
        begin_turn(region, 4)
        owner.cash -= 15
        firm.cash += 15
        record(region, 'owner_financing', turn=4, payer_id=1, recipient_id=8,
               amount=15)
        account = next(a for a in seal_turn(region, 4) if a['actor_id'] == 8)
        self.assertEqual(account['cash_change'], 15)
        self.assertEqual(account['owner_financing_received'], 15)
        self.assertEqual(account['operating_result_recorded'], 0)

    def test_company_scrip_is_recorded_without_faking_cash_wages(self):
        region = Region()
        worker, firm = Person(3, 0), Person(8, 20, Goods.cloth)
        firm.is_corporation = True
        worker.company_debt = 0.0
        region.agents = [worker, firm]
        begin_turn(region, 5)
        worker.scrip_wallet = 6.0
        record(region, 'scrip_wage', turn=5, payer_id=firm.id,
               recipient_id=worker.id, amount=6,
               detail={'tender': 'company_scrip'})
        worker.company_debt = 4.5
        record(region, 'scrip_food_credit', turn=5, payer_id=firm.id,
               recipient_id=worker.id, amount=4.5, debt_credit=4.5,
               detail={'tender': 'company_store_credit'})
        rows = {a['actor_id']: a for a in seal_turn(region, 5)}
        self.assertEqual(rows[firm.id]['wages_cash'], 0)
        self.assertEqual(rows[worker.id]['cash_change'], 0)
        self.assertEqual(rows[worker.id]['scrip_change'], 6)
        self.assertEqual(rows[worker.id]['closing_company_debt'], 4.5)
        self.assertEqual(rows[firm.id]['unposted_cash_change'], 0)

    def test_foreign_exchange_conversion_is_in_cash_bridge(self):
        import forex
        region = Region()
        region.home_currency = 'USD'
        region._last_turn = 6
        trader = Person(3, 10)
        trader.wallets = {'EUR': 4.0}
        region.agents = [trader]
        bank = SimpleNamespace(fx_pool=100.0, foreign_reserves={'EUR': 0.0})
        begin_turn(region, 6)
        paid = forex.sell_fx_to_bank(bank, trader, 'EUR', 4, 2,
                                     trace_region=region)
        account = next(a for a in seal_turn(region, 6) if a['actor_id'] == trader.id)
        self.assertEqual(paid, 8)
        self.assertEqual(account['fx_converted_in'], 8)
        self.assertEqual(account['cash_change'], account['posted_cash_change'])

    def test_imported_input_reports_actual_destination_fill_price(self):
        region = Region()
        firm = Person(8, 50, Goods.cloth)
        firm.is_corporation = True
        region.agents = [firm]
        region.recipes[Goods.cloth] = {'input': Goods.cotton}
        begin_turn(region, 7)
        firm.cash -= 12
        record(region, 'spot_sale', turn=7, payer_id=firm.id, recipient_id=3,
               good=Goods.cotton, quantity=3, amount=12,
               detail={'unit_price': 4, 'imported': True,
                       'source_cost_status': 'trader_cost_basis',
                       'source_shipment_id': 'Upland->Port:1',
                       'source_region': 'Upland',
                       'route_history': ['Upland->Port']})
        account = next(a for a in seal_turn(region, 7) if a['actor_id'] == firm.id)
        self.assertEqual(account['delivered_input_purchase_units'], 3)
        self.assertEqual(account['delivered_input_purchase_cash'], 12)
        self.assertEqual(account['delivered_input_unit_price'], 4)
        delivered = account['delivered_input_lots'][0]
        self.assertEqual(delivered['source_cost_status'], 'trader_cost_basis')
        self.assertEqual(delivered['source_shipment_id'], 'Upland->Port:1')
        self.assertEqual(delivered['source_region'], 'Upland')
        self.assertEqual(delivered['route_history'], ['Upland->Port'])

    def test_bank_deposit_and_withdrawal_reconcile_cash_and_savings(self):
        from econsim_trade_money import Bank
        region = Region()
        actor = Person(3, 20)
        actor.loans = []
        region.agents = [actor]
        bank = Bank()
        bank._attached_regions = [region]
        region.bank = bank
        begin_turn(region, 8)
        bank.Deposit(actor, 10)
        bank.Withdraw(actor, 4)
        bank.Borrow(8, actor, 100)
        from econsim_trade_money import PayLoans
        PayLoans(actor, bank=bank)
        bank.apply_bail_in_haircut(haircut_pct=.25, exemption_floor=1)
        account = next(a for a in seal_turn(region, 8) if a['actor_id'] == actor.id)
        self.assertAlmostEqual(actor.cash, 112.9)
        self.assertEqual(bank.deposits[actor], 4.75)
        self.assertAlmostEqual(account['cash_change'], 92.9)
        self.assertAlmostEqual(account['posted_cash_change'], 92.9)
        self.assertEqual(account['closing_bank_deposit'], 4.75)
        self.assertEqual(account['bank_deposit_loss'], 1.25)
        self.assertEqual(account['closing_bank_debt'], 99)
        self.assertAlmostEqual(account['bank_loan_repayment_cash'], 1.1)

    def test_estate_debt_settlement_records_foreign_payment_and_inherited_principal(self):
        from agent import Agent
        from demographics_estate import handle_debt_inheritance
        from econsim_trade_money import Bank, Loan

        region = Region()
        region.name = 'Estate District'
        region.home_currency = 'USD'
        domestic_treasury, foreign_treasury = Agent(1), Agent(1)
        domestic_treasury.home_currency = 'USD'
        foreign_treasury.home_currency = 'EUR'
        domestic_bank = Bank(gov=SimpleNamespace(agent=domestic_treasury))
        foreign_bank = Bank(gov=SimpleNamespace(agent=foreign_treasury))
        domestic_bank._attached_regions = [region]
        decedent, heir = Agent(1), Agent(1)
        decedent.cash = 10.0
        decedent.wallets = {'EUR': 10.0}
        decedent.loans = [Loan(domestic_bank, decedent, 40.0, 0.01),
                          Loan(foreign_bank, decedent, 50.0, 0.10)]
        heir.loans = []
        heir.wallets = {}
        heir._bank_ref = domestic_bank
        domestic_bank.loans = [decedent.loans[0]]
        domestic_bank.total_liabilities = 40.0
        domestic_bank.deposits[decedent] = 10.0
        domestic_bank.total_deposits = 10.0
        foreign_bank.loans = [decedent.loans[1]]
        foreign_bank.total_liabilities = 50.0
        region.bank = domestic_bank
        region.agents = [decedent, heir, domestic_treasury]
        begin_turn(region, 11)

        handle_debt_inheritance(
            SimpleNamespace(bank=domestic_bank, source_region=region),
            11, decedent, [heir])
        rows = {row['actor_id']: row for row in seal_turn(region, 11)}
        events = [event for event in region.economic_events if event['turn'] == 11]

        self.assertAlmostEqual(rows[decedent.id]['cash_change'], -10.0)
        self.assertAlmostEqual(rows[decedent.id]['posted_cash_change'], -10.0)
        self.assertEqual(rows[decedent.id]['foreign_wallet_debt_paid'], {'EUR': 10.0})
        self.assertEqual(rows[heir.id]['bank_debt_inherited'],
                         {'EUR': 45.0, 'USD': 20.4})
        self.assertAlmostEqual(rows[heir.id]['closing_bank_debt'], 20.4)
        self.assertEqual(rows[heir.id]['cash_change'], 0.0)
        self.assertEqual(rows[heir.id]['unposted_cash_change'], 0.0)
        self.assertTrue(any(event['kind'] == 'foreign_wallet_debt_payment'
                            and event['currency'] == 'EUR' for event in events))
        self.assertTrue(any(event['kind'] == 'bank_debt_inheritance'
                            and event['recipient_id'] == heir.id for event in events))

    def test_heirless_default_records_loss_waterfall_and_treasury_funding(self):
        from agent import Agent
        from demographics_estate import handle_debt_inheritance
        from econsim_trade_money import Bank, Loan

        region = Region()
        region.name = 'Default District'
        region.home_currency = 'USD'
        treasury, depositor, decedent = Agent(1), Agent(1), Agent(1)
        treasury.cash = 3.0
        treasury.home_currency = 'USD'
        depositor.cash = 20.0
        decedent.cash = 0.0
        bank = Bank(gov=SimpleNamespace(agent=treasury))
        bank._attached_regions = [region]
        bank.capital = 4.0
        loan = Loan(bank, decedent, 25.0, 0.0)
        decedent.loans = [loan]
        bank.loans = [loan]
        bank.total_liabilities = 25.0
        bank.deposits[depositor] = 10.0
        bank.total_deposits = 10.0
        region.bank = bank
        region.agents = [treasury, depositor, decedent]
        begin_turn(region, 12)

        handle_debt_inheritance(
            SimpleNamespace(bank=bank, source_region=region),
            12, decedent, [])
        rows = {row['actor_id']: row for row in seal_turn(region, 12)}
        events = [event for event in region.economic_events if event['turn'] == 12]
        writeoff = next(event for event in events
                        if event['kind'] == 'bank_debt_writeoff')

        self.assertEqual(writeoff['amount'], 25.0)
        self.assertEqual(writeoff['detail']['shareholder_capital_absorbed'], 4.0)
        self.assertEqual(writeoff['detail']['depositor_bail_in'], 10.0)
        self.assertEqual(writeoff['detail']['treasury_recapitalization'], 3.0)
        self.assertEqual(writeoff['detail']['unabsorbed_bank_loss'], 8.0)
        self.assertEqual(rows[decedent.id]['bank_debt_written_off'], {'USD': 25.0})
        self.assertEqual(rows[depositor.id]['bank_deposit_loss'], 10.0)
        self.assertEqual(rows[treasury.id]['cash_change'], -3.0)
        self.assertEqual(rows[treasury.id]['posted_cash_change'], -3.0)
        self.assertEqual(rows[treasury.id]['unposted_cash_change'], 0.0)


class PoliticalCampaignCurrencyTests(unittest.TestCase):
    def test_campaign_finance_keeps_nation_currency_in_candidate_wallet(self):
        from election import campaign_finance
        treasury = Person(1, 50)
        treasury.home_currency = 'USD'
        candidate_actor = Person(2, 10)
        candidate_actor.home_currency = 'JPY'
        candidate_actor.wallets = {}
        tile = SimpleNamespace(gov=SimpleNamespace(agent=treasury))
        nation = SimpleNamespace(tiles=[tile], currency='USD')
        candidate = SimpleNamespace(agent=candidate_actor, popularity=0)
        before_usd = treasury.cash + candidate_actor.wallets.get('USD', 0)
        before_jpy = candidate_actor.cash
        spent, _ = campaign_finance(nation, candidate, 20, 4)
        self.assertEqual(spent, 20)
        self.assertEqual(treasury.cash + candidate_actor.wallets['USD'], before_usd)
        self.assertEqual(candidate_actor.cash, before_jpy)

    def test_backlash_moves_either_cash_or_wallet_once(self):
        from labor_politics import capitalist_electoral_backlash
        tile = SimpleNamespace(agents=[])
        donor = Person(1, 100)
        donor.social_class = 'capitalist'
        donor.home_currency = 'USD'
        donor.wallets = {'USD': 80}
        candidate_actor = Person(2, 10)
        candidate_actor.home_currency = 'USD'
        candidate_actor.wallets = {'USD': 5}
        tile.agents = [donor, candidate_actor]
        candidate = SimpleNamespace(agent=candidate_actor,
                                    backing_faction='Proletariat', popularity=0)
        nation = SimpleNamespace(ten_hour_act=True, currency='USD', tiles=[tile],
                                 _incumbent_faction='Proletariat', regime_log=[])
        before = donor.cash + donor.wallets['USD'] + candidate_actor.cash + candidate_actor.wallets['USD']
        amount = capitalist_electoral_backlash(nation, [candidate], 4)
        after = donor.cash + donor.wallets['USD'] + candidate_actor.cash + candidate_actor.wallets['USD']
        self.assertAlmostEqual(amount, 12)
        self.assertAlmostEqual(after, before)
        self.assertAlmostEqual(donor.cash, 88)
        self.assertAlmostEqual(donor.wallets['USD'], 80)
        self.assertAlmostEqual(candidate_actor.cash, 22)
        self.assertAlmostEqual(candidate_actor.wallets['USD'], 5)

    def test_cross_currency_backlash_uses_existing_nation_currency_wallet(self):
        from labor_politics import capitalist_electoral_backlash
        tile = SimpleNamespace(agents=[])
        donor = Person(1, 100)
        donor.social_class = 'capitalist'
        donor.home_currency = 'JPY'
        donor.wallets = {'USD': 80}
        candidate_actor = Person(2, 10)
        candidate_actor.home_currency = 'JPY'
        candidate_actor.wallets = {}
        tile.agents = [donor, candidate_actor]
        candidate = SimpleNamespace(agent=candidate_actor,
                                    backing_faction='Proletariat', popularity=0)
        nation = SimpleNamespace(ten_hour_act=True, currency='USD', tiles=[tile],
                                 _incumbent_faction='Proletariat', regime_log=[])
        before_usd = donor.wallets['USD']
        before_jpy = donor.cash + candidate_actor.cash
        amount = capitalist_electoral_backlash(nation, [candidate], 4)
        self.assertAlmostEqual(amount, 9)
        self.assertAlmostEqual(donor.wallets['USD'] + candidate_actor.wallets['USD'], before_usd)
        self.assertAlmostEqual(donor.cash + candidate_actor.cash, before_jpy)


class SupplyProposalTests(unittest.TestCase):
    def test_direct_settlement_without_acceptance_is_rejected(self):
        from crop_credit import offer_advance
        from supply_rights import acquire_water_right, transfer_plot_title
        region = Region()
        seller, buyer, grower = Person(1), Person(8, 100), Person(3, 0, Goods.food)
        grower.assigned_plot_id = 'p1'
        region.agents = [seller, buyer, grower]
        self.assertIsNone(transfer_plot_title(region, seller, buyer, 'p1', 30, turn=2))
        self.assertIsNone(acquire_water_right(region, seller, buyer, 'p1', 'p2', .25, 5, 2))
        self.assertIsNone(offer_advance(buyer, grower, region, 8, 3, 'p1'))
        self.assertEqual((seller.cash, buyer.cash, grower.cash), (0, 100, 0))

    def test_secure_grower_refuses_low_offtake_without_transfer(self):
        region = Region()
        region.recipes[Goods.cotton] = {'price': 5.0, 'production': 5}
        grower, mill = Person(3, 20, Goods.cotton), Person(8, 100, Goods.cloth)
        grower.assigned_plot_id = 'p1'
        region.agents = [grower, mill]
        proposal = propose(region, 'advance_offtake', mill, grower, turn=2,
                           price=10, plot_id='p1', good='cotton', quantity=2,
                           unit_price=2, due_turn=4)
        self.assertEqual((grower.cash, mill.cash), (20, 100))
        decide(region, 3)
        self.assertEqual(proposal['status'], 'rejected')
        self.assertEqual((grower.cash, mill.cash), (20, 100))
        self.assertFalse(region.cash_obligations)

    def test_cash_poor_grower_accepts_useful_advance(self):
        region = Region()
        region.recipes[Goods.cotton] = {'price': 5.0, 'production': 5}
        grower, mill = Person(3, 0, Goods.cotton), Person(8, 100, Goods.cloth)
        grower.assigned_plot_id = 'p1'
        region.agents = [grower, mill]
        proposal = propose(region, 'advance_offtake', mill, grower, turn=2,
                           price=10, plot_id='p1', good='cotton', quantity=2,
                           unit_price=3, due_turn=4)
        decide(region, 3)
        self.assertEqual(proposal['status'], 'settled')
        self.assertEqual((grower.cash, mill.cash), (10, 90))
        self.assertEqual(region.offtake_contracts[0]['remaining'], 2)

    def test_title_holder_counters_and_can_refuse(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 100)
        region.agents = [seller, buyer]
        low = propose(region, 'land_sale', buyer, seller, turn=2,
                      price=8, plot_id='p1')
        decide(region, 3)
        self.assertEqual(low['status'], 'rejected')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 1)
        offer = propose(region, 'land_sale', buyer, seller, turn=3,
                        price=18, plot_id='p1', max_price=25)
        decide(region, 4)
        self.assertEqual(offer['status'], 'countered')
        decide(region, 5)
        self.assertEqual(offer['status'], 'settled')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 8)
        self.assertEqual((seller.cash, buyer.cash), (20, 80))

    def test_water_holder_can_refuse_diversion(self):
        region = Region()
        seller, buyer = Person(1), Person(8, 100)
        region.agents = [seller, buyer]
        proposal = propose(region, 'water_right', buyer, seller, turn=2,
                           price=0, units=.5, from_plot_id='p1',
                           to_plot_id='p2')
        decide(region, 3)
        self.assertEqual(proposal['status'], 'rejected')
        self.assertEqual(next(r.units for r in region.water_rights
                              if r.plot_id == 'p1' and r.holder_id == 1), 1.0)

    def test_pending_offer_survives_save_load_without_prepaid_transfer(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 100)
        region.agents = [seller, buyer]
        proposal = propose(region, 'land_sale', buyer, seller, turn=2,
                           price=30, plot_id='p1')
        loaded = pickle.loads(pickle.dumps(region))
        self.assertEqual(loaded.supply_proposals[0]['id'], proposal['id'])
        self.assertEqual((loaded.agents[0].cash, loaded.agents[1].cash), (0, 100))
        decide(loaded, 3)
        self.assertEqual(loaded.tenure.find_plot('p1').lord_id, 8)
        self.assertEqual((loaded.agents[0].cash, loaded.agents[1].cash), (30, 70))

    def test_duplicate_offer_and_lost_buyer_funds_cannot_settle(self):
        region = Region()
        seller, buyer = Person(1, 0), Person(8, 30)
        region.agents = [seller, buyer]
        first = propose(region, 'land_sale', buyer, seller, turn=2,
                        price=30, plot_id='p1')
        self.assertIsNone(propose(region, 'land_sale', buyer, seller, turn=2,
                                  price=30, plot_id='p1'))
        buyer.cash = 5
        decide(region, 3)
        self.assertEqual(first['status'], 'rejected')
        self.assertEqual(region.tenure.find_plot('p1').lord_id, 1)
        self.assertEqual(seller.cash, 0)

    def test_food_plot_keeps_minimum_water_and_contract_food_reserve(self):
        region = Region()
        farmer, buyer = Person(3, 0, Goods.food), Person(8, 100)
        farmer.assigned_plot_id = 'p1'
        region.agents = [farmer, buyer]
        from supply_rights import _seed_water_rights
        _seed_water_rights(region)
        owner = Person(1, 0, Goods.food)
        owner.assigned_plot_id = 'p1'
        region.agents.append(owner)
        self.assertIsNone(propose(region, 'water_right', buyer, owner, turn=2,
                                  price=20, units=.75, from_plot_id='p1',
                                  to_plot_id='p2'))
        region.recipes[Goods.food]['production'] = 8
        self.assertIsNone(propose(region, 'advance_offtake', buyer, farmer, turn=2,
                                  price=10, plot_id='p1', good='food', quantity=5,
                                  unit_price=2, due_turn=4))


class SupplyStrategyTests(unittest.TestCase):
    def _world(self, grower_cash):
        region = Region()
        region.recipes = {Goods.food: {'price': 2.0},
                          Goods.cotton: {'price': 5.0, 'production': 5},
                          Goods.cloth: {'price': 40.0, 'production': 4,
                                        'numInput': 2, 'input': Goods.cotton}}
        grower = Person(3, grower_cash, Goods.cotton)
        grower.assigned_plot_id = 'p1'
        mill = Person(8, 100, Goods.cloth)
        mill.is_corporation = True
        title_holder = Person(1, 20, Goods.food)
        region.agents = [title_holder, grower, mill]
        return region, grower, mill

    def test_secure_grower_outside_option_makes_advance_unprofitable(self):
        region, grower, mill = self._world(20)
        options = EliteCapitalistPlanner()._input_control_options(mill, region)
        advance = next(o for o in options if o['candidate'] == 'advance_offtake')
        lease = next(o for o in options if o['candidate'] == 'lease_input_land')
        self.assertEqual(advance['acceptance_probability'], 0)
        self.assertEqual(advance['score'], 0)
        self.assertFalse(lease['feasible'])
        self.assertIsNone(EliteCapitalistPlanner()._execute_input_control(mill, region, 5))

    def test_cash_poor_grower_makes_advance_valuable(self):
        region, grower, mill = self._world(0)
        planner = EliteCapitalistPlanner()
        options = planner._input_control_options(mill, region)
        advance = next(o for o in options if o['candidate'] == 'advance_offtake')
        self.assertGreater(advance['score'], 0)
        action = planner._execute_input_control(mill, region, 5)
        self.assertEqual(action['action_taken'], 'ADVANCE_OFFTAKE')
        self.assertEqual(region.supply_proposals[0]['status'], 'proposed')
        self.assertEqual(mill.cash, 100)

    def test_negative_unit_margin_pauses_and_releases_workers(self):
        region, grower, mill = self._world(0)
        region.recipes[Goods.cloth]['price'] = 1.0
        region.recipes[Goods.cloth]['production'] = 1
        worker = Person(9, 0)
        worker.employer = mill
        mill.employees = [worker]
        mill.max_employees = 3
        mill.wage = 3.0
        action = EliteCapitalistPlanner()._execute_input_control(mill, region, 5)
        self.assertEqual(action['action_taken'], 'REDUCE_OR_PAUSE_OUTPUT')
        self.assertEqual(mill.max_employees, 0)
        self.assertIsNone(worker.employer)
        self.assertEqual(mill.supply_pause_until, 10)


class SupplyRivalryScenarioTests(unittest.TestCase):
    def test_public_buyer_moves_paid_cash_and_existing_crop(self):
        from scenario_supply_rivalry import create_world, apply_action, project, step_world
        import forex
        world = create_world(seed=812)
        fields = world['by_name']['Cotton Fields']
        self.assertEqual(len([a for a in fields.agents if a.output == Goods.cotton
                              and not a.is_corporation]), 2)
        self.assertEqual(len([a for r in world['tiles'] for a in r.agents
                              if a.is_corporation and a.output == Goods.cloth]), 2)
        self.assertTrue(project(world)['petition_deadline'])
        cash_before = forex.audit_currency_total(world['tiles'], world['currencies'][0])
        public_crop_before = fields.gov.agent.inv_get(Goods.cotton, 0)
        ok, _ = apply_action(world, 'public_crop_purchase')
        self.assertTrue(ok)
        self.assertEqual(fields.gov.agent.inv_get(Goods.cotton, 0), public_crop_before + 2)
        self.assertAlmostEqual(forex.audit_currency_total(world['tiles'], world['currencies'][0]),
                               cash_before, places=6)
        self.assertFalse(step_world(world))

    def test_web_server_exposes_and_executes_supply_decisions(self):
        from sim_server.sim_server import SimServer
        from sim_server.protocol import CommandMessage, CommandType
        server = SimServer(seed=812, scenario_id='supply_rivalry')
        snapshot = server.serialize_world()
        self.assertEqual(snapshot['scenario_info']['scenario_name'], 'Cotton Supply Rivalry')
        self.assertTrue(any(a['id'] == 'approve_charter'
                            for a in snapshot['scenario_info']['actions']))
        response = server.execute_command(CommandMessage(
            CommandType.SCENARIO_ACTION, {'action_id': 'reject_charter'}))
        self.assertTrue(response['success'])
        self.assertEqual(server.by_name['Cotton Fields'].concession_petitions[0]['status'],
                         'rejected')

    def test_desktop_guided_world_uses_same_supply_projection(self):
        from client.desktop.engine import build_world_view
        from client.desktop.panels.scenario_ui import scenario_pressures
        world = build_world_view(seed=812, scenario_id='supply_rivalry')
        self.assertEqual(world['selected_region'].name, 'Cotton Fields')
        self.assertEqual(world['ui_mode'], 'guided')
        self.assertEqual(scenario_pressures(world)[0]['title'], 'Cotton market')

    def test_player_can_repeal_control_after_a_response_turn(self):
        from scenario_supply_rivalry import create_world, apply_action, step_world
        world = create_world(seed=812)
        self.assertTrue(apply_action(world, 'approve_charter')[0])
        fields = world['by_name']['Cotton Fields']
        self.assertEqual(fields.market_charters[0]['status'], 'active')
        step_world(world)
        self.assertTrue(apply_action(world, 'repeal_charter')[0])
        self.assertEqual(fields.market_charters[0]['status'], 'repealed')


if __name__ == '__main__':
    unittest.main()
