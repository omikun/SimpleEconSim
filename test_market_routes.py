"""Commodity shipments move through routes before entering destination auctions."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from goods import Goods
from region_logistics import post_exports_to_route, repoint_traders
from region_market import clear_discriminatory
from transporter import Route
from world_trade import pending_imports


class MarketRouteTests(unittest.TestCase):
    def _trader(self, source, destination, qty=3):
        trader = Agent(0)
        initialize_agent(trader, Goods.food, 0, 0, 50.0)
        trader.is_trader = True
        trader.home_region = source.name
        trader.home_currency = 'D'
        trader.destination_region = destination
        trader.inventory_export[Goods.cotton.value] = qty
        trader.cost_set(Goods.cotton, 5.0)
        source.trader_agents = [trader]
        return trader

    def _destination_market(self, destination, source, imports):
        return SimpleNamespace(
            name=destination.name, home_currency='D', recipes=destination.recipes,
            neighbors={source.name: source}, destination_region=source,
            forex_desks={}, forex=None, exchange_rate=1.0,
            _trade_fee_mult=1.0, gov=None,
            IMPORT_MARGIN_MIN=0.05, IMPORT_MARGIN_MAX=0.30,
            _auction_import_sales={}, pending_imports=imports,
        )

    def test_route_carries_cotton_from_export_stock_to_import_pool(self):
        source = SimpleNamespace(name='Upland', home_currency='D', routes={}, neighbors={},
                                 transport_delay=1,
                                 forex_desks={}, forex=None,
                                 recipes={Goods.cotton: {'price': 5.0}})
        destination = SimpleNamespace(name='Lowland')
        route = Route('Upland->Lowland', source, destination, base_delay=1)
        source.routes[destination.name] = route

        trader = Agent(0)
        initialize_agent(trader, Goods.food, 0, 0, 50.0)
        trader.is_trader = True
        trader.home_region = source.name
        trader.home_currency = 'D'
        trader.destination_region = destination
        trader.inventory_export[Goods.cotton.value] = 3
        trader.cost_set(Goods.cotton, 5.0)
        source.trader_agents = [trader]

        post_exports_to_route(source)
        self.assertEqual(trader.inventory_export[Goods.cotton.value], 0)
        self.assertEqual(route.pending[0][1:4], [Goods.cotton, 3, source.name])
        shipment_id = route.pending[0][4]
        self.assertEqual(route.pending[0][5], 5.0)

        route.deliver_pending()
        route.advance()
        destination.recipes = {
            Goods.cotton: {'price': 10.0},
            Goods.cloth: {'price': 20.0, 'input': Goods.cotton,
                          'numInput': 2, 'production': 4},
        }
        imports = pending_imports(destination, source)
        self.assertEqual(imports[Goods.cotton][0][:4], (trader, 3, False, shipment_id))
        self.assertEqual(trader.inventory_foreign[Goods.cotton.value], 3)

        destination_market = SimpleNamespace(
            name='Lowland', home_currency='D', recipes=destination.recipes,
            neighbors={source.name: source}, destination_region=source,
            forex_desks={}, forex=None, exchange_rate=1.0,
            _trade_fee_mult=1.0, gov=None,
            IMPORT_MARGIN_MIN=0.05, IMPORT_MARGIN_MAX=0.30,
            _auction_import_sales={}, pending_imports=imports,
        )
        buyer = Agent(0)
        initialize_agent(buyer, Goods.cloth, 2, 0, 100.0)
        buyer.is_corporation = True
        buyer.inv_set(Goods.cotton, 0)
        bought, paid, _ = clear_discriminatory(
            destination_market, Goods.cotton, 10.0, total_asks=3, total_bids=4,
            imp_pool=imports[Goods.cotton], agents=[buyer], t=1,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 4, 'limit_price': 10.0},
            ]})
        self.assertEqual(bought, 3)
        self.assertGreater(paid, 0)
        self.assertEqual(buyer.inv_get(Goods.cotton, 0), 3)
        self.assertEqual(trader.inventory_foreign[Goods.cotton.value], 0)
        self.assertEqual(trader.import_lots[0]['quantity'], 0)
        self.assertEqual(destination_market._auction_import_sales[Goods.cotton], (3, paid))
        imported_sale = next(e for e in destination_market.economic_events
                             if e['kind'] == 'spot_sale')
        self.assertEqual(imported_sale['detail']['shipment_id'], shipment_id)
        self.assertEqual(imported_sale['detail']['source_unit_cost'], 5.0)
        self.assertAlmostEqual(imported_sale['detail']['unit_price'], paid / 3)

    def test_parked_shipment_can_be_sold_with_its_original_provenance(self):
        source = SimpleNamespace(name='Upland', home_currency='D', routes={}, neighbors={},
                                 forex_desks={}, forex=None,
                                 recipes={Goods.cotton: {'price': 5.0}})
        parked_tile = SimpleNamespace(name='Lowland', recipes={Goods.cotton: {'price': 10.0}})
        new_destination = SimpleNamespace(name='Highland')
        route = Route('Upland->Lowland', source, parked_tile, base_delay=1)
        trader = self._trader(source, parked_tile)
        route.post(trader, Goods.cotton, 3, unit_cost=5.0, freight_per_unit=0.75)
        shipment_id = route.pending[0][4]
        route.deliver_pending()
        trader.destination_region = new_destination
        route.advance()

        imports = pending_imports(parked_tile, source)
        offered = imports[Goods.cotton][0]
        self.assertEqual(offered[:4], (trader, 3, True, shipment_id))
        self.assertEqual(offered[4:10], (5.0, 0.75, 'D', 'trader_cost_basis',
                                         shipment_id, 'Upland'))
        self.assertEqual(offered[10], ['Upland->Lowland'])

        market = self._destination_market(parked_tile, source, imports)
        buyer = Agent(0)
        initialize_agent(buyer, Goods.cloth, 2, 0, 100.0)
        buyer.is_corporation = True
        buyer.inv_set(Goods.cotton, 0)
        clear_discriminatory(
            market, Goods.cotton, 10.0, total_asks=3, total_bids=3,
            imp_pool=imports[Goods.cotton], agents=[buyer], t=1,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 3, 'limit_price': 10.0},
            ]})
        sale = next(e for e in market.economic_events if e['kind'] == 'spot_sale')
        detail = sale['detail']
        self.assertTrue(detail['parked'])
        self.assertEqual(detail['shipment_id'], shipment_id)
        self.assertEqual(detail['source_shipment_id'], shipment_id)
        self.assertEqual(detail['source_region'], 'Upland')
        self.assertEqual(detail['source_cost_status'], 'trader_cost_basis')
        self.assertEqual(detail['route_history'], ['Upland->Lowland'])
        self.assertEqual(trader.parked_get(parked_tile.name, Goods.cotton), 0)
        self.assertEqual(trader.import_lots[0]['quantity'], 0)

    def test_trader_market_purchase_links_seller_to_final_import_sale(self):
        source = SimpleNamespace(
            name='Upland', home_currency='D', neighbors={}, forex_desks={}, forex=None,
            recipes={Goods.cotton: {'price': 5.0}}, _trade_fee_mult=1.0,
            IMPORT_MARGIN_MIN=0.05, IMPORT_MARGIN_MAX=0.30,
            _auction_import_sales={}, gov=None)
        source_trace_rows = []
        source._collective_trace_clock = {'next': 1, 'turn': 1, 'phase': 'trade'}

        def collect_source_trace(clock, **row):
            clock['next'] += 1
            source_trace_rows.append(row)
            return f'test:{clock["next"]}'

        source._run_trace = SimpleNamespace(emit=collect_source_trace)
        destination = SimpleNamespace(name='Lowland', recipes={Goods.cotton: {'price': 12.0}})
        trader = self._trader(source, destination, qty=0)
        grower = Agent(2)
        initialize_agent(grower, Goods.cotton, 4, 0, 10.0)

        clear_discriminatory(
            source, Goods.cotton, 5.0, total_asks=4, total_bids=4,
            imp_pool=[], agents=[grower, trader], t=1,
            local_orders={
                'sellers': [{'agent': grower, 'quantity': 4, 'limit_price': 5.0}],
                'buyers': [{'agent': trader, 'quantity': 4, 'limit_price': 9.0}],
            })
        self.assertEqual(trader.inventory_export[Goods.cotton.value], 4)
        purchase = next(e for e in source.economic_events if e['kind'] == 'spot_sale')
        self.assertEqual(purchase['payer_id'], trader.id)
        self.assertEqual(purchase['recipient_id'], grower.id)
        acquisition = trader.trade_acquisition_lots[0]
        self.assertEqual(acquisition['acquisition_event'],
                         {'tile': source.name, 'id': purchase['id']})
        self.assertEqual(acquisition['purchase_trace_event_id'], purchase['source_id'])
        self.assertTrue(any(row.get('kind') == 'paid_market_sale'
                            for row in source_trace_rows))
        self.assertEqual(acquisition['source_seller_id'], grower.id)
        self.assertEqual(acquisition['unit_cost'], 7.0)

        route = Route('Upland->Lowland', source, destination, base_delay=1)
        self.assertEqual(route.post(trader, Goods.cotton, 4), 4)
        pending = route.pending[0]
        self.assertEqual(pending[5], 7.0)
        self.assertEqual(pending[10], 'market_purchase_linked')
        self.assertEqual(pending[12][0]['acquisition_event'], acquisition['acquisition_event'])
        route.deliver_pending()
        route.advance()
        imports = pending_imports(destination, source)
        self.assertEqual(imports[Goods.cotton][0][11][0]['source_seller_id'], grower.id)

        market = self._destination_market(destination, source, imports)
        buyer = Agent(3)
        initialize_agent(buyer, Goods.cloth, 2, 0, 100.0)
        buyer.is_corporation = True
        clear_discriminatory(
            market, Goods.cotton, 12.0, total_asks=4, total_bids=4,
            imp_pool=imports[Goods.cotton], agents=[buyer], t=2,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 4, 'limit_price': 12.0},
            ]})
        sale = next(e for e in market.economic_events if e['kind'] == 'spot_sale')
        link = sale['detail']['source_acquisitions'][0]
        self.assertEqual(link['acquisition_event'], acquisition['acquisition_event'])
        self.assertEqual(link['source_seller_id'], grower.id)
        self.assertEqual(link['source_region'], source.name)
        self.assertEqual(link['quantity'], 4)

    def test_mixed_tracked_and_legacy_stock_keeps_partial_cost_provenance(self):
        source = SimpleNamespace(name='Upland', home_currency='D')
        destination = SimpleNamespace(name='Lowland')
        trader = self._trader(source, destination, qty=4)
        trader.cost_set(Goods.cotton, 6.0)
        trader.trade_acquisition_lots = [{
            'good': Goods.cotton.name, 'quantity': 2, 'unit_cost': 4.0,
            'acquisition_event': {'tile': 'Upland', 'id': 11},
            'status': 'market_purchase_recorded'}]
        route = Route('Upland->Lowland', source, destination)
        route.post(trader, Goods.cotton, 4)
        pending = route.pending[0]
        self.assertEqual(pending[5], 6.0)
        self.assertEqual(pending[10], 'partially_linked_market_purchases')
        self.assertEqual([row['quantity'] for row in pending[12]], [2, 2])
        self.assertEqual(pending[12][1]['status'], 'unlinked_legacy_cargo')

    def test_rerouted_parked_shipment_retains_source_link_and_route_history(self):
        source = SimpleNamespace(name='Upland', home_currency='D', routes={}, neighbors={},
                                 forex_desks={}, forex=None,
                                 recipes={Goods.cotton: {'price': 5.0}})
        middle = SimpleNamespace(name='Lowland', home_currency='D', routes={},
                                 neighbors={'Highland': True})
        destination = SimpleNamespace(name='Highland', recipes={Goods.cotton: {'price': 15.0}})
        first_route = Route('Upland->Lowland', source, middle, base_delay=1)
        trader = self._trader(source, middle)
        first_route.post(trader, Goods.cotton, 3, unit_cost=5.0, freight_per_unit=0.75)
        source_shipment_id = first_route.pending[0][4]
        first_route.deliver_pending()
        trader.destination_region = destination
        first_route.advance()
        self.assertEqual(trader.parked_get(middle.name, Goods.cotton), 3)

        onward = Route('Lowland->Highland', middle, destination, base_delay=1)
        middle.routes = {destination.name: onward}
        trace_rows = []
        middle._collective_trace_clock = {'next': 1, 'turn': 2, 'phase': 'trade'}

        def collect_trace(clock, **row):
            clock['next'] += 1
            trace_rows.append(row)
            return f'test:{clock["next"]}'

        middle._run_trace = SimpleNamespace(emit=collect_trace)
        self.assertEqual(onward.post_parked(trader, Goods.cotton, 3), 3)
        pending = onward.pending[0]
        self.assertEqual(pending[4], 'Lowland->Highland:1')
        self.assertEqual(pending[5], 5.0)
        self.assertEqual(pending[6], 0.75)
        self.assertEqual(pending[8], source_shipment_id)
        self.assertEqual(pending[9], 'Upland')
        self.assertEqual(pending[10], 'trader_cost_basis')
        self.assertEqual(pending[11], ['Upland->Lowland', 'Lowland->Highland'])

        onward.deliver_pending()
        onward.advance()
        imports = pending_imports(destination, source)
        offered = imports[Goods.cotton][0]
        self.assertEqual(offered[3], pending[4])
        self.assertEqual(offered[4], 5.0)
        self.assertEqual(offered[5], 0.75)
        self.assertEqual(offered[8], source_shipment_id)
        self.assertEqual(offered[9], 'Upland')
        self.assertEqual(offered[10], ['Upland->Lowland', 'Lowland->Highland'])

        market = self._destination_market(destination, source, imports)
        buyer = Agent(1)
        initialize_agent(buyer, Goods.cloth, 2, 0, 100.0)
        buyer.is_corporation = True
        buyer.inv_set(Goods.cotton, 0)
        clear_discriminatory(
            market, Goods.cotton, 15.0, total_asks=3, total_bids=3,
            imp_pool=imports[Goods.cotton], agents=[buyer], t=2,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 3, 'limit_price': 15.0},
            ]})
        sale = next(e for e in market.economic_events if e['kind'] == 'spot_sale')
        self.assertEqual(sale['detail']['shipment_id'], pending[4])
        self.assertEqual(sale['detail']['source_shipment_id'], source_shipment_id)
        self.assertEqual(sale['detail']['source_region'], 'Upland')
        self.assertEqual(sale['detail']['route_history'],
                         ['Upland->Lowland', 'Lowland->Highland'])
        arrival_rows = [row for row in trace_rows
                        if row['kind'] == 'route_shipment_arrival']
        departure_rows = [row for row in trace_rows
                          if row['kind'] == 'route_shipment_departure']
        self.assertEqual(len(arrival_rows), 1)
        self.assertEqual(len(departure_rows), 1)
        self.assertEqual(arrival_rows[0]['inputs']['source_shipment_id'], source_shipment_id)
        self.assertEqual(arrival_rows[0]['inputs']['route_history'],
                         ['Upland->Lowland', 'Lowland->Highland'])

    def test_unlinked_parked_cargo_is_tagged_when_rerouted(self):
        source = SimpleNamespace(name='Lowland', home_currency='D')
        destination = SimpleNamespace(name='Highland')
        trader = self._trader(source, destination, qty=0)
        trader.parked_add(source.name, Goods.cotton, 4)
        route = Route('Lowland->Highland', source, destination)
        self.assertEqual(route.post_parked(trader, Goods.cotton, 4), 4)
        self.assertEqual(route.pending[0][5], None)
        self.assertEqual(route.pending[0][8], None)
        self.assertEqual(route.pending[0][10], 'unlinked_legacy_cargo')

    def test_reclaim_returns_not_yet_loaded_pending_cargo(self):
        source = SimpleNamespace(name='Upland', home_currency='D')
        destination = SimpleNamespace(name='Lowland')
        route = Route('Upland->Lowland', source, destination)
        trader = self._trader(source, destination, qty=7)
        trader.trade_acquisition_lots = [{
            'good': Goods.cotton.name, 'quantity': 5, 'unit_cost': 4.0,
            'acquisition_event': {'tile': 'Upland', 'id': 8},
            'status': 'market_purchase_recorded'}]
        self.assertEqual(route.post(trader, Goods.cotton, 5, unit_cost=5.0), 5)
        self.assertEqual(trader.inventory_export[Goods.cotton.value], 2)
        self.assertEqual(route.pending[0][5], 4.0)
        route.reclaim(trader)
        self.assertEqual(trader.inventory_export[Goods.cotton.value], 7)
        self.assertEqual(route.pending, [])
        self.assertEqual(trader.trade_acquisition_lots[0]['quantity'], 5)
        self.assertEqual(trader.trade_acquisition_lots[0]['acquisition_event']['id'], 8)

    def test_reclaim_restores_acquisition_links_from_in_transit_cargo(self):
        source = SimpleNamespace(name='Upland', home_currency='D')
        destination = SimpleNamespace(name='Lowland')
        route = Route('Upland->Lowland', source, destination)
        trader = self._trader(source, destination, qty=4)
        trader.trade_acquisition_lots = [{
            'good': Goods.cotton.name, 'quantity': 4, 'unit_cost': 6.0,
            'acquisition_event': {'tile': 'Upland', 'id': 9},
            'status': 'market_purchase_recorded'}]
        route.post(trader, Goods.cotton, 4)
        route.deliver_pending()
        route.reclaim(trader)
        self.assertEqual(trader.inventory_export[Goods.cotton.value], 4)
        self.assertEqual(trader.trade_acquisition_lots[0]['quantity'], 4)
        self.assertEqual(trader.trade_acquisition_lots[0]['acquisition_event']['id'], 9)

    def test_trader_repoints_toward_profitable_requested_input(self):
        source = SimpleNamespace(
            name='Upland', neighbors={}, routes={}, trader_agents=[],
            recipes={
                Goods.wood: {'price': 5.0},
                Goods.furniture: {'price': 7.0},
                Goods.transport: {'price': 1.0, 'capacity': 10},
            },
            forex_desks={}, forex=None, IMPORT_MARGIN_MIN=0.05,
        )
        destination = SimpleNamespace(
            name='Lowland', recipes={
                Goods.wood: {'price': 10.0},
                Goods.furniture: {'price': 7.0},
                Goods.transport: {'price': 1.0, 'capacity': 10},
                Goods.food: {'price': 2.0},
            },
            agents=[], gov=None,
        )
        source.neighbors[destination.name] = destination
        source.routes[destination.name] = Route('Upland->Lowland', source, destination)
        firm = Agent(0)
        initialize_agent(firm, Goods.furniture, 2, 0, 100.0)
        firm.is_corporation = True
        firm.inv_set(Goods.wood, 0)
        destination.agents.append(firm)
        trader = Agent(0)
        initialize_agent(trader, Goods.food, 0, 0, 100.0)
        trader.is_trader = True
        trader.trade_good = Goods.furniture
        trader.destination_region = destination
        source.trader_agents.append(trader)

        with patch('terrain_edges.get_edge_manager', return_value=None):
            repoint_traders(source)

        self.assertIs(trader.destination_region, destination)
        self.assertEqual(trader.trade_good, Goods.wood)


if __name__ == '__main__':
    unittest.main()
