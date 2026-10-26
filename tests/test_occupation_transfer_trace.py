import unittest
from types import SimpleNamespace

from scenario_occupation import _settle_occupation_payment, intercept_revenue


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(with_trace=True):
    egypt_government = SimpleNamespace(
        name='Egypt Treasury', agent=SimpleNamespace(cash=100.0))
    britain_government = SimpleNamespace(
        name='Britain Treasury', agent=SimpleNamespace(cash=25.0))
    egypt = SimpleNamespace(name='Egypt', currency='EGP',
                            government=egypt_government, tiles=[])
    britain = SimpleNamespace(name='Britain', currency='GBP',
                              government=britain_government, tiles=[])
    tile = SimpleNamespace(name='Alexandria', home_currency='EGP',
                           owner_nation=egypt, gov=egypt_government)
    egypt.tiles.append(tile)
    britain.tiles.append(SimpleNamespace(name='London'))
    trace = MemoryTrace()
    tile._run_trace = trace
    tile._collective_trace_clock = {
        'turn': 4, 'phase': 'scenario_occupation', 'next': 1}
    if not with_trace:
        del tile._run_trace
        del tile._collective_trace_clock
    world = {
        'turn': 4, 'nations': [egypt, britain], 'tiles': [tile],
        'scenario_state': {
            'occupation': {
                'institutional_control': {'customs': 'Egypt', 'cabinet': 'Egypt'},
                'resistance': 0.2, 'boycott_until': 0, 'strike_until': 0,
                'collection_turn': 0, 'collected_this_turn': 0.0,
                'revenue_ledger': [],
            },
            'campaign': {'infrastructure_damage': {'Alexandria': 0.1}},
        },
    }
    return world, egypt, britain, trace


class OccupationTransferTraceTests(unittest.TestCase):
    def test_occupation_receipt_traces_paired_treasury_legs_and_formula(self):
        world, egypt, britain, trace = _fixture()
        egypt_gov = egypt.government
        britain_gov = britain.government

        self.assertEqual(intercept_revenue(world, egypt_gov, 'tariff', 40.0, 4), 0)
        assessment = next(row for row in trace.rows
                          if row.get('kind') == 'occupation_revenue_assessment')
        self.assertEqual(assessment['inputs']['reason'], 'institution_not_occupied')

        world['scenario_state']['occupation']['institutional_control']['customs'] = 'Britain'
        egypt_before = egypt_gov.agent.cash
        britain_before = britain_gov.agent.cash
        collected = intercept_revenue(world, egypt_gov, 'tariff', 40.0, 4)
        expected = round(40.0 * .35 * (1 - .6 * .2) * .9, 6)
        self.assertAlmostEqual(collected, expected)
        self.assertAlmostEqual(egypt_gov.agent.cash, egypt_before - collected)
        self.assertAlmostEqual(britain_gov.agent.cash, britain_before + collected)
        self.assertAlmostEqual(egypt_gov.agent.cash + britain_gov.agent.cash,
                               egypt_before + britain_before)

        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual(len(flows), 2)
        payer = next(row for row in flows if row['after'] < 0)
        payee = next(row for row in flows if row['after'] > 0)
        self.assertAlmostEqual(payer['after'], -collected)
        self.assertAlmostEqual(payee['after'], collected)
        payer_contract = payer['inputs']['transfer_contract']
        payee_contract = payee['inputs']['transfer_contract']
        self.assertEqual(payer_contract['contract_version'], 'treasury_transfer.v1')
        self.assertEqual(payer_contract['side'], 'payer')
        self.assertEqual(payee_contract['side'], 'payee')
        self.assertEqual(payer_contract['operation_id'], payee_contract['operation_id'])
        self.assertAlmostEqual(
            payer_contract['payer_account']['balance_before']
            - payer_contract['payer_account']['balance_after'], collected)
        self.assertAlmostEqual(
            payee_contract['payee_account']['balance_after']
            - payee_contract['payee_account']['balance_before'], collected)
        self.assertTrue(payer_contract['counterparty_currency_mismatch'])
        outcome = next(row for row in trace.rows
                       if row.get('kind') == 'occupation_revenue_assessment'
                       and row.get('after') == collected)
        self.assertEqual(set(outcome['cause_event_ids']),
                         {payer['event_id'], payee['event_id']})
        self.assertEqual(outcome['inputs']['resistance_factor'], .88)
        self.assertEqual(outcome['inputs']['port_factor'], .9)
        self.assertEqual(world['scenario_state']['occupation']['revenue_ledger'][-1]
                         ['operation_id'], payer_contract['operation_id'])

        plain_world, plain_egypt, plain_britain, _ = _fixture(False)
        plain_world['scenario_state']['occupation']['institutional_control']['customs'] = 'Britain'
        plain_amount = intercept_revenue(
            plain_world, plain_egypt.government, 'tariff', 40.0, 4)
        self.assertAlmostEqual(plain_amount, collected)
        self.assertEqual(
            plain_world['scenario_state']['occupation']['revenue_ledger'][-1]
            ['operation_id'], payer_contract['operation_id'])
        self.assertEqual((plain_egypt.government.agent.cash,
                          plain_britain.government.agent.cash),
                         (egypt_gov.agent.cash, britain_gov.agent.cash))

    def test_negotiated_withdrawal_payment_is_a_paired_treasury_transfer(self):
        world, egypt, britain, trace = _fixture()
        egypt_before = egypt.government.agent.cash
        britain_before = britain.government.agent.cash

        operation_id = _settle_occupation_payment(
            world, source='withdrawal_settlement', amount=30.0, turn=7)

        self.assertEqual(egypt.government.agent.cash, egypt_before - 30.0)
        self.assertEqual(britain.government.agent.cash, britain_before + 30.0)
        self.assertEqual(world['scenario_state']['occupation']['revenue_ledger'][0]
                         ['operation_id'], operation_id)
        flows = [row for row in trace.rows
                 if row.get('metric_id') == 'finance.treasury_flow']
        self.assertEqual([row['after'] for row in flows], [-30.0, 30.0])
        self.assertEqual({row['inputs']['transfer_contract']['operation_id']
                          for row in flows}, {operation_id})
        self.assertEqual(
            flows[0]['inputs']['transfer_contract']['payer_account']['balance_before'],
            egypt_before)
        self.assertEqual(
            flows[1]['inputs']['transfer_contract']['payee_account']['balance_after'],
            britain_before + 30.0)


if __name__ == '__main__':
    unittest.main()
