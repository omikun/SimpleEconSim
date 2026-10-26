"""Journal and actor-statement coverage for in-kind crop claims."""
import unittest
from types import SimpleNamespace

from agent import Agent
from crop_credit import settle_crop_liens, settle_crop_shares
from economy.actor_accounts import begin_turn, seal_turn
from goods import Goods
from labor_institutions import CashObligation, TenancyAgreement


class Recorder:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        row['event_id'] = f"test:{clock['next']}"
        clock['next'] += 1
        self.rows.append(row)
        return self.rows[-1]['event_id']


def region_for(agents, *, turn=1):
    region = SimpleNamespace(
        name='CropTile', home_currency='USD', agents=agents,
        cash_obligations=[], recipes={Goods.food: {'price': 2.0}},
        production_receipts=[], economic_events=[], _last_turn=turn,
        province=None, tenure=None)
    recorder = Recorder()
    region._collective_trace_clock = {'turn': turn, 'phase': 'settlement', 'next': 1}
    region._run_trace = recorder
    return region, recorder


class CropCreditAccountingTests(unittest.TestCase):
    def test_crop_lien_records_harvest_credit_and_any_uncredited_value(self):
        tenant, lender = Agent(0), Agent(0)
        tenant.output = Goods.food
        tenant.home_currency = lender.home_currency = 'USD'
        tenant.inv_add(Goods.food, 8)
        claim = CashObligation(
            id=1, debtor_id=tenant.id, creditor_id=lender.id, origin='advance',
            original_principal=4.0, balance=4.0, due_turn=1,
            collateral_plot_id='plot-1')
        claim.lien_good = Goods.food
        claim.lien_share = 0.5
        claim.lien_settled_turn = -1
        region, recorder = region_for([tenant, lender])
        region.cash_obligations.append(claim)
        region.production_receipts = [
            {'person_id': tenant.id, 'good': Goods.food, 'quantity': 8}]
        begin_turn(region, 1)

        events = settle_crop_liens(region, 1)

        accounts = {row['actor_id']: row for row in seal_turn(region, 1)}
        tenant_account, lender_account = accounts[tenant.id], accounts[lender.id]
        journal = next(event for event in region.economic_events
                       if event['kind'] == 'crop_lien_settlement')
        trace = next(row for row in recorder.rows
                     if row['kind'] == 'crop_lien_settlement')
        self.assertEqual(events[0]['quantity'], 4)
        self.assertEqual(events[0]['reference_value'], 8.0)
        self.assertEqual(events[0]['debt_credit'], 4.0)
        self.assertEqual(events[0]['uncredited_value'], 4.0)
        self.assertEqual(claim.status, 'paid')
        self.assertEqual(tenant.inv_get(Goods.food), 4)
        self.assertEqual(lender.inv_get(Goods.food), 4)
        self.assertEqual(journal['asset_id'], claim.id)
        self.assertEqual(journal['amount'], 4.0)
        self.assertEqual(journal['quantity'], 4.0)
        self.assertAlmostEqual(tenant_account['crop_lien_debt_settled'], 4.0)
        self.assertAlmostEqual(lender_account['crop_lien_receivable_settled'], 4.0)
        self.assertAlmostEqual(tenant_account['crop_lien_goods_paid'], 4.0)
        self.assertAlmostEqual(lender_account['crop_lien_goods_received'], 4.0)
        self.assertAlmostEqual(tenant_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(lender_account['unposted_cash_change'], 0.0)
        self.assertEqual(trace['metric_id'], 'finance.crop_lien_settlement')
        self.assertEqual(trace['inputs']['economic_event_id'], journal['id'])

    def test_crop_share_rent_records_quantity_value_and_actor_sides(self):
        tenant, landlord = Agent(0), Agent(0)
        tenant.output = Goods.food
        tenant.home_currency = landlord.home_currency = 'USD'
        tenant.inv_add(Goods.food, 8)
        agreement = TenancyAgreement(
            tenant_id=tenant.id, landlord_id=landlord.id, plot_id='plot-2',
            type='crop_share', crop_share=0.25)
        region, recorder = region_for([tenant, landlord])
        region.tenancy_agreements = [agreement]
        region.production_receipts = [
            {'person_id': tenant.id, 'good': Goods.food, 'quantity': 8}]
        begin_turn(region, 1)

        events = settle_crop_shares(region, 1)

        accounts = {row['actor_id']: row for row in seal_turn(region, 1)}
        tenant_account, landlord_account = accounts[tenant.id], accounts[landlord.id]
        journal = next(event for event in region.economic_events
                       if event['kind'] == 'crop_share_rent')
        trace = next(row for row in recorder.rows
                     if row['kind'] == 'crop_share_rent_settlement')
        self.assertEqual(events[0]['quantity'], 2)
        self.assertEqual(events[0]['reference_value'], 4.0)
        self.assertEqual(journal['quantity'], 2.0)
        self.assertEqual(journal['amount'], 4.0)
        self.assertAlmostEqual(tenant_account['crop_share_rent_paid'], 4.0)
        self.assertAlmostEqual(landlord_account['crop_share_rent_received'], 4.0)
        self.assertAlmostEqual(tenant_account['crop_share_goods_paid'], 2.0)
        self.assertAlmostEqual(landlord_account['crop_share_goods_received'], 2.0)
        self.assertAlmostEqual(tenant_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(landlord_account['unposted_cash_change'], 0.0)
        self.assertEqual(trace['metric_id'], 'land.crop_share')
        self.assertEqual(trace['inputs']['economic_event_id'], journal['id'])


if __name__ == '__main__':
    unittest.main()
