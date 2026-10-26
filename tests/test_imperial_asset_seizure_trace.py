import unittest
from types import SimpleNamespace

from government import Government
from macro.imperialism.manager import ImperialismManager
from macro.imperialism.models import CustomsReceivership


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, debtor_cash=100.0, granary=0.0, toll_route=True,
             with_trace=True, remaining=100.0):
    debtor_government = Government('Debtor Treasury', 1, initial_cash=debtor_cash)
    creditor_government = Government('Creditor Treasury', 2, initial_cash=50.0)
    debtor_government.currency = 'EGP'
    creditor_government.currency = 'GBP'
    trace = MemoryTrace()
    route = SimpleNamespace(has_turnpike=toll_route, has_canal=False)
    tile = SimpleNamespace(
        name='Delta', routes={'trade': route}, is_coast=False,
        granary_stock=float(granary), export_val={},
        _collective_trace_clock={'turn': 4, 'phase': 'imperialism', 'next': 1})
    if with_trace:
        tile._run_trace = trace
    debtor = SimpleNamespace(
        name='Egypt', currency='EGP', government=debtor_government,
        tiles=[tile], military_units=[], legitimacy=0.8,
        treasury=lambda: {'total': 1000.0})
    tile.owner_nation = debtor
    creditor = SimpleNamespace(
        name='Britain', currency='GBP', government=creditor_government,
        tiles=[], military_units=[SimpleNamespace(soldiers=1)], legitimacy=0.8,
        treasury=lambda: {'total': 1000.0})
    receiver = CustomsReceivership(
        receivership_id='caisse_test', creditor_nation='Britain',
        debtor_nation='Egypt', intercept_share=0.65,
        remaining_debt=float(remaining), total_collected=0.0,
        status='active', level='caisse_de_la_dette',
        enforcement_mode='military', creditor_obj=creditor)
    manager = ImperialismManager()
    manager.receiverships.append(receiver)
    world = {'turn': 4, 'nations': [debtor, creditor], 'tiles': [tile]}
    return world, debtor, creditor, tile, receiver, manager, trace


class ImperialAssetSeizureTraceTests(unittest.TestCase):
    def test_caisse_toll_seizure_pairs_available_cash_and_debt_change(self):
        world, debtor, creditor, tile, receiver, manager, trace = _fixture()
        debtor_before = debtor.government.agent.cash
        creditor_before = creditor.government.agent.cash

        manager.step_imperialism(world, 4)

        self.assertEqual(debtor.government.agent.cash, debtor_before - 10.0)
        self.assertEqual(creditor.government.agent.cash, creditor_before + 10.0)
        self.assertEqual(receiver.remaining_debt, 90.0)
        self.assertEqual(receiver.seized_tolls, 10.0)
        payer = next(row for row in trace.rows
                     if row.get('kind') == 'caisse_transit_toll_seizure_debtor_payment')
        payee = next(row for row in trace.rows
                     if row.get('kind') == 'caisse_transit_toll_seizure_creditor_receipt')
        self.assertEqual(payer['inputs']['transfer_contract']['operation_id'],
                         payee['inputs']['transfer_contract']['operation_id'])
        self.assertEqual(
            payer['inputs']['transfer_contract']['payer_account']['balance_before'],
            debtor_before)
        self.assertEqual(
            payer['inputs']['transfer_contract']['payer_account']['balance_after'],
            debtor_before - 10.0)
        self.assertTrue(payee['inputs']['transfer_contract']['counterparty_currency_mismatch'])
        debt = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.receivership_balance')
        self.assertEqual((debt['before'], debt['after']), (100.0, 90.0))
        self.assertEqual(set(debt['cause_event_ids']),
                         {payer['event_id'], payee['event_id']})

    def test_toll_fallback_exposes_receipt_without_source_cash_debit(self):
        world, debtor, creditor, tile, receiver, manager, trace = _fixture(debtor_cash=2.0)

        manager.step_imperialism(world, 4)

        self.assertEqual(debtor.government.agent.cash, 2.0)
        self.assertEqual(creditor.government.agent.cash, 55.0)
        self.assertEqual(receiver.remaining_debt, 95.0)
        self.assertFalse(any(row.get('kind') ==
                             'caisse_transit_toll_seizure_debtor_payment'
                             for row in trace.rows))
        payee = next(row for row in trace.rows
                     if row.get('kind') == 'caisse_transit_toll_seizure_creditor_receipt')
        source = payee['inputs']['transfer_contract']['payer_account']
        self.assertEqual(source['balance_status'],
                         'fallback_rule_created_receipt_without_debtor_debit')
        debt = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.receivership_balance')
        self.assertFalse(debt['inputs']['debtor_cash_debited'])
        self.assertTrue(debt['inputs']['creditor_cash_credited'])

    def test_granary_seizure_links_exact_stock_valuation_and_creditor_cash(self):
        world, debtor, creditor, tile, receiver, manager, trace = _fixture(
            debtor_cash=0.0, granary=8.0, toll_route=False, remaining=20.0)
        creditor_before = creditor.government.agent.cash

        manager.step_imperialism(world, 4)

        self.assertEqual(tile.granary_stock, 4.0)
        self.assertEqual(creditor.government.agent.cash, creditor_before + 8.0)
        self.assertEqual(receiver.remaining_debt, 12.0)
        self.assertEqual(receiver.seized_granary_grain, 4.0)
        grain = next(row for row in trace.rows
                     if row.get('kind') == 'caisse_granary_asset_seizure')
        self.assertEqual(grain['after'], 4.0)
        self.assertEqual(grain['inputs']['granary_stock_before'], 8.0)
        self.assertEqual(grain['inputs']['granary_stock_after'], 4.0)
        self.assertEqual(grain['inputs']['cash_value'], 8.0)
        payee = next(row for row in trace.rows
                     if row.get('kind') == 'caisse_granary_seizure_valuation_creditor_receipt')
        self.assertEqual(payee['after'], 8.0)
        self.assertEqual(payee['cause_event_ids'], [grain['event_id']])
        debt = next(row for row in trace.rows
                    if row.get('metric_id') == 'finance.receivership_balance')
        self.assertEqual((debt['before'], debt['after']), (20.0, 12.0))
        self.assertIn(grain['event_id'], debt['cause_event_ids'])
        self.assertIn(payee['event_id'], debt['cause_event_ids'])

    def test_toll_and_granary_state_is_unchanged_when_tracing_is_disabled(self):
        traced = _fixture(debtor_cash=2.0, granary=8.0, with_trace=True)
        untraced = _fixture(debtor_cash=2.0, granary=8.0, with_trace=False)
        for fixture in (traced, untraced):
            world, _, _, _, _, manager, _ = fixture
            manager.step_imperialism(world, 4)

        def state(fixture):
            _, debtor, creditor, tile, receiver, _, _ = fixture
            return (debtor.government.agent.cash, creditor.government.agent.cash,
                    tile.granary_stock, receiver.remaining_debt,
                    receiver.total_collected, receiver.seized_tolls,
                    receiver.seized_granary_grain)

        self.assertEqual(state(traced), state(untraced))


if __name__ == '__main__':
    unittest.main()
