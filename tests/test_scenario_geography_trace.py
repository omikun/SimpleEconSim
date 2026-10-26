import unittest
from types import SimpleNamespace

from scenario_geography import ROUTES, create_fleet, move_fleet


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'test:{clock["next"]}'
        clock['next'] += 1
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _government(name, cash):
    return SimpleNamespace(name=name, agent=SimpleNamespace(cash=float(cash)))


def _fixture(with_trace=True):
    egypt = SimpleNamespace(name='Egypt', currency='EGP',
                            government=_government('Egypt Treasury', 100.0), tiles=[])
    britain = SimpleNamespace(name='Britain', currency='GBP',
                              government=_government('Britain Treasury', 50.0), tiles=[])
    trace = MemoryTrace()
    tile = SimpleNamespace(name='Delta', owner_nation=egypt, home_currency='EGP')
    egypt.tiles.append(tile)
    if with_trace:
        tile._run_trace = trace
        tile._collective_trace_clock = {
            'turn': 4, 'phase': 'scenario_geography', 'next': 1}
    world = {
        'turn': 4, 'nations': [egypt, britain], 'tiles': [tile],
        'scenario_state': {'geography': {
            'routes': ROUTES, 'canal_open': True, 'transit_rights': ['Egypt', 'Britain'],
            'fleets': {}, 'canal_tolls_collected': 0.0,
        }},
    }
    fleet = create_fleet(world, 'Britain')
    fleet['location'] = 'Port Said'
    return world, egypt, britain, fleet, trace


class ScenarioGeographyTraceTests(unittest.TestCase):
    def test_canal_toll_records_paired_treasuries_currency_mismatch_and_movement(self):
        world, egypt, britain, fleet, trace = _fixture()
        egypt_before = egypt.government.agent.cash
        britain_before = britain.government.agent.cash
        trace_event_ids = []

        self.assertTrue(move_fleet(world, 'Britain', 'Ismailia',
                                   trace_event_ids=trace_event_ids))

        self.assertEqual(egypt.government.agent.cash, egypt_before + 2.0)
        self.assertEqual(britain.government.agent.cash, britain_before - 2.0)
        self.assertEqual(world['scenario_state']['geography']['canal_tolls_collected'], 2.0)
        self.assertEqual((fleet['location'], fleet['coal']), ('Ismailia', 4))
        payer = next(row for row in trace.rows
                     if row.get('kind') == 'canal_transit_toll_payment')
        payee = next(row for row in trace.rows
                     if row.get('kind') == 'canal_transit_toll_receipt')
        payer_contract = payer['inputs']['transfer_contract']
        payee_contract = payee['inputs']['transfer_contract']
        self.assertEqual(payer_contract['operation_id'], payee_contract['operation_id'])
        self.assertEqual(payer_contract['payer_account']['currency'], 'GBP')
        self.assertEqual(payee_contract['payee_account']['currency'], 'EGP')
        self.assertFalse(payee_contract['currency_conversion_applied'])
        self.assertTrue(payee_contract['counterparty_currency_mismatch'])
        self.assertTrue(payee_contract['unconverted_currency_mismatch'])
        assessment = next(row for row in trace.rows
                          if row.get('metric_id') == 'finance.canal_toll')
        self.assertEqual(set(assessment['cause_event_ids']),
                         {payer['event_id'], payee['event_id']})
        self.assertEqual((assessment['before'], assessment['after']), (0.0, 2.0))
        movement = next(row for row in trace.rows
                        if row.get('metric_id') == 'military.fleet_position')
        self.assertEqual((movement['before'], movement['after']),
                         ('Port Said', 'Ismailia'))
        self.assertEqual(movement['cause_event_ids'], [assessment['event_id']])
        self.assertEqual(set(trace_event_ids),
                         {payer['event_id'], payee['event_id'],
                          assessment['event_id'], movement['event_id']})

    def test_toll_movement_state_is_identical_with_trace_disabled(self):
        traced = _fixture(True)
        untraced = _fixture(False)
        for world, *_ in (traced, untraced):
            self.assertTrue(move_fleet(world, 'Britain', 'Ismailia'))

        def state(fixture):
            world, egypt, britain, fleet, _ = fixture
            geography = world['scenario_state']['geography']
            return (egypt.government.agent.cash, britain.government.agent.cash,
                    geography['canal_tolls_collected'], fleet['location'], fleet['coal'])

        self.assertEqual(state(traced), state(untraced))


if __name__ == '__main__':
    unittest.main()
