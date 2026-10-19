"""Causal tracing for private warehouse releases to Egyptian households."""

import json
import tempfile
import unittest
from pathlib import Path

from goods import Goods
from run_trace import RunTrace, verify
from scenario_political_economy import (_households, _sell_to_households,
                                        _set_reserved, apply_action)
from worldview_engine import build_world_view


class MemoryTrace:
    def __init__(self):
        self.rows = []

    def emit(self, clock, **row):
        event_id = f'grain-release-test:{clock["next"]}'
        clock['next'] += 1
        json.dumps(row, allow_nan=False)
        self.rows.append({'event_id': event_id, **row})
        return event_id


def _fixture(*, traced=True, recorder=None):
    world = build_world_view(scenario_id='egypt_1877')
    world['turn'] = 1
    trace = recorder or MemoryTrace()
    clock = {'turn': 1, 'phase': 'scenario_economy', 'next': 1}
    if traced:
        for tile in world['tiles']:
            tile._run_trace = trace
            tile._collective_trace_clock = clock
    return world, trace, clock


def _prepare_release(world, tile):
    economy = world['scenario_state']['political_economy']
    owner_id = economy['warehouse_by_tile'][tile.name]
    owner = next(agent for agent in tile.agents if agent.id == owner_id)
    price = max(.25, float(tile.recipes[Goods.food]['price']))
    households = _households(tile)
    for person in households:
        person.cash = 0.0
        person.inv_set(Goods.food, 0)
    buyer = households[0]
    buyer.cash = price * 4 + .1
    owner.cash = 1000.0
    owner.inv_set(Goods.food, 20)
    egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
    for region in egypt.tiles:
        economy['private_reserve_by_tile'][region.name] = 0
        region.scenario_grain_reserved_units = 0
    _set_reserved(world, tile, 10)
    return owner, buyer, price


class PrivateGrainReleaseTraceTests(unittest.TestCase):
    @staticmethod
    def _row(trace, metric_id, *, kind=None, reason=None):
        return next(row for row in trace.rows
                    if row.get('metric_id') == metric_id
                    and (kind is None or row.get('kind') == kind)
                    and (reason is None or row.get('inputs', {}).get('reason') == reason))

    def test_release_records_need_affordability_and_exact_transfer_causes(self):
        world, trace, _ = _fixture()
        tile = next(tile for tile in world['tiles']
                    if getattr(tile, 'scenario_location', None) == 'Nile Delta')
        owner, buyer, price = _prepare_release(world, tile)
        event_ids = []

        sold = _sell_to_households(
            world, tile, owner, limit=10, trigger='test_release',
            trace_operation_id='test:nile-release', trace_event_ids=event_ids)

        self.assertEqual(sold, 4)
        release = self._row(
            trace, 'scenario.private_grain_release',
            kind='private_grain_release_resolved', reason='household_sales_completed')
        self.assertEqual(release['inputs']['operation_id'], 'test:nile-release')
        self.assertEqual(release['before'], 10)
        self.assertEqual(release['after'], 6)
        decisions = {row['buyer_id']: row
                     for row in release['inputs']['buyer_decisions']}
        self.assertEqual(decisions[buyer.id]['units_purchased'], 4)
        self.assertEqual(decisions[buyer.id]['decision_reason'], 'purchased')
        self.assertEqual(decisions[buyer.id]['cash_affordable_units'], 4)
        self.assertTrue(any(row['decision_reason'] == 'unaffordable_at_posted_price'
                            for row in decisions.values()
                            if row['food_need_units'] > 0 and row['buyer_id'] != buyer.id))
        self.assertGreaterEqual(decisions[buyer.id]['cash_before'], price * 4)
        self.assertEqual(owner.inv_get(Goods.food, 0), 16)
        self.assertEqual(buyer.inv_get(Goods.food, 0), 4)
        self.assertEqual(event_ids, [release['event_id']])

        transfer_events = [row for row in trace.rows
                           if row.get('metric_id') in
                           ('finance.cash_transfer', 'goods.grain_transfer')]
        self.assertEqual(len(transfer_events), 2)
        self.assertEqual(set(release['cause_event_ids']),
                         {row['event_id'] for row in transfer_events})

    def test_open_market_policy_links_district_releases_and_is_trace_neutral(self):
        def apply(traced, recorder=None):
            world, trace, clock = _fixture(traced=traced, recorder=recorder)
            egypt = next(nation for nation in world['nations'] if nation.name == 'Egypt')
            tile = next(tile for tile in world['tiles']
                        if getattr(tile, 'scenario_location', None) == 'Nile Delta')
            owner, buyer, _ = _prepare_release(world, tile)
            success, message = apply_action(world, egypt, 'open_private_grain_market')
            return (world, trace, clock, egypt, tile, owner, buyer,
                    success, message)

        world_on, trace_on, _, egypt_on, tile_on, owner_on, buyer_on, success, message = apply(True)
        self.assertTrue(success, message)
        policy = self._row(trace_on, 'scenario.private_grain_policy',
                           kind='private_grain_policy_resolved',
                           reason='private_sales_opened')
        self.assertEqual(policy['before'], 'hold')
        self.assertEqual(policy['after'], 'open')
        self.assertGreater(policy['inputs']['sold_units'], 0)
        releases = [row for row in trace_on.rows
                    if row.get('metric_id') == 'scenario.private_grain_release']
        self.assertEqual(set(policy['inputs']['release_event_ids']),
                         {row['event_id'] for row in releases})
        self.assertTrue(set(policy['cause_event_ids']).issuperset(
            policy['inputs']['release_event_ids']))

        rejected, _ = apply_action(world_on, egypt_on, 'open_private_grain_market')
        self.assertFalse(rejected)
        self.assertTrue(any(row.get('metric_id') == 'scenario.private_grain_policy'
                            and row.get('inputs', {}).get('reason')
                            == 'grain_market_already_open'
                            for row in trace_on.rows))

        world_off, _, _, egypt_off, tile_off, owner_off, buyer_off, success_off, _ = apply(False)
        self.assertTrue(success_off)
        self.assertEqual(world_on['scenario_state']['political_economy']['grain_policy'],
                         world_off['scenario_state']['political_economy']['grain_policy'])
        self.assertEqual(owner_on.inv_get(Goods.food, 0),
                         owner_off.inv_get(Goods.food, 0))
        self.assertEqual(buyer_on.inv_get(Goods.food, 0),
                         buyer_off.inv_get(Goods.food, 0))
        self.assertEqual(tile_on.scenario_grain_reserved_units,
                         tile_off.scenario_grain_reserved_units)
        self.assertEqual(egypt_on.government.agent.cash,
                         egypt_off.government.agent.cash)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'private-grain-release.ctr'
            recorder = RunTrace(path, 'private-grain-release-test')
            compact_world, compact_trace, _, _, _, _, _, _, _ = apply(
                True, recorder=recorder)
            self.assertEqual(
                recorder.query(metric_id='scenario.private_grain_policy')['total'], 1)
            self.assertGreater(
                recorder.query(metric_id='scenario.private_grain_release')['total'], 0)
            self.assertGreater(verify(path)['rows'], 1)


if __name__ == '__main__':
    unittest.main()
