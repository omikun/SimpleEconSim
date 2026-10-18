"""Commodity shipments move through routes before entering destination auctions."""

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from economy.actor_accounts import begin_turn, recorded_cash_delta, seal_turn
from forex import ForexDesk, fx_balance
from goods import Goods
from region_logistics import post_exports_to_route, repoint_traders
from region_market import clear_discriminatory, import_ask_price
from run_trace import RunTrace
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

    def test_trace_links_shipment_arrival_quote_and_paid_sale(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = RunTrace(Path(tmp) / 'imports.ctr', 'import-chain')
            clock = {'next': 1, 'turn': 2, 'phase': 'trade'}
            source = SimpleNamespace(
                name='Upland', home_currency='D', neighbors={}, forex_desks={},
                forex=None, recipes={Goods.cotton: {'price': 5.0}})
            destination = SimpleNamespace(
                name='Lowland', home_currency='D', recipes={Goods.cotton: {'price': 10.0}})
            trader = self._trader(source, destination, qty=0)
            shipment_id = 'Upland->Lowland:trace-test'
            source_sale_id = trace.emit(
                clock, kind='paid_market_sale', record_class='transfer',
                subject={'type': 'tile', 'id': source.name, 'good': 'cotton'},
                inputs={'buyer_id': trader.id, 'seller_id': 44,
                        'unit_price': 5.0, 'total_paid': 15.0})
            departure_id = trace.emit(
                clock, kind='route_shipment_departure',
                subject={'type': 'shipment', 'id': shipment_id},
                inputs={'trader_id': trader.id, 'good': 'cotton', 'quantity': 3,
                        'source_acquisitions': [{
                            'quantity': 3, 'purchase_trace_event_id': source_sale_id,
                        }]})
            departure_row = next(
                row for row in trace.query(turn=2)['events']
                if row['kind'] == 'route_shipment_departure')
            self.assertEqual(departure_row['cause_event_ids'], [source_sale_id])
            self.assertEqual(
                departure_row['inputs']['source_acquisition_event_ids'],
                [source_sale_id])
            arrival_id = trace.emit(
                clock, kind='route_shipment_arrival',
                subject={'type': 'shipment', 'id': shipment_id},
                inputs={'trader_id': trader.id, 'good': 'cotton', 'quantity': 3})
            arrival_row = next(
                row for row in trace.query(turn=2)['events']
                if row['kind'] == 'route_shipment_arrival')
            self.assertEqual(arrival_row['cause_event_ids'], [departure_id])

            trader.inventory_foreign[Goods.cotton.value] = 3
            trader.import_lots = [{
                'shipment_id': shipment_id, 'destination': destination.name,
                'good': Goods.cotton.name, 'quantity': 3,
                'unit_cost': 5.0, 'freight_per_unit': 0.0,
                'source_currency': 'D', 'source_cost_status': 'trader_cost_basis',
                'source_shipment_id': shipment_id, 'source_region': source.name,
                'route_history': ['Upland->Lowland'], 'source_acquisitions': [],
                'parked': False,
            }]
            market = self._destination_market(
                destination, source,
                {Goods.cotton: [(trader, 3, False, shipment_id, 5.0, 0.0,
                                  'D', 'trader_cost_basis', shipment_id,
                                  source.name, ['Upland->Lowland'], [], source)]})
            market._collective_trace_clock = clock
            market._run_trace = trace
            buyer = Agent(0)
            initialize_agent(buyer, Goods.cloth, 2, 0, 100.0)
            buyer.is_corporation = True
            buyer.inv_set(Goods.cotton, 0)
            clear_discriminatory(
                market, Goods.cotton, 10.0, total_asks=3, total_bids=3,
                imp_pool=market.pending_imports[Goods.cotton], agents=[buyer], t=2,
                local_orders={'sellers': [], 'buyers': [
                    {'agent': buyer, 'quantity': 3, 'limit_price': 10.0},
                ]})

            rows = trace.query(turn=2)['events']
            by_id = {row['event_id']: row for row in rows}
            arrival = by_id[arrival_id]
            quote = next(row for row in rows
                         if row['kind'] == 'import_delivered_quote')
            sale = next(row for row in rows
                        if row['kind'] == 'paid_market_sale'
                        and row.get('inputs', {}).get('imported'))
            self.assertEqual(arrival['cause_event_ids'], [departure_id])
            self.assertIn(arrival_id, quote['cause_event_ids'])
            self.assertEqual(quote['inputs']['arrival_event_id'], arrival_id)
            self.assertEqual(quote['inputs']['owner_trader_id'], trader.id)
            self.assertIn(quote['event_id'], sale['cause_event_ids'])
            self.assertEqual(sale['inputs']['shipment_id'], shipment_id)

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

    def test_foreign_import_sale_separates_cash_and_wallet_receipts(self):
        source = SimpleNamespace(
            name='Upland', home_currency='EUR', routes={}, neighbors={},
            transport_delay=1, forex_desks={}, forex=None,
            recipes={Goods.cotton: {'price': 5.0}}, trader_agents=[],
            agents=[], bank=None, province=None, tenure=None,
            cash_obligations=[], economic_events=[], _last_turn=1)
        destination = SimpleNamespace(
            name='Lowland', home_currency='USD',
            recipes={Goods.cotton: {'price': 10.0},
                     Goods.cloth: {'price': 20.0, 'input': Goods.cotton,
                                   'numInput': 2, 'production': 4}},
            neighbors={source.name: source}, destination_region=source,
            forex_desks={}, forex=None, exchange_rate=1.0,
            _trade_fee_mult=1.0, gov=None, IMPORT_MARGIN_MIN=0.05,
            IMPORT_MARGIN_MAX=0.30, _auction_import_sales={},
            pending_imports={}, economic_events=[], market_trade_events=[],
            agents=[], bank=None, province=None, tenure=None,
            cash_obligations=[], _next_economic_event_id=1)
        trader = self._trader(source, destination, qty=3)
        trader.home_currency = 'EUR'
        trader.inventory_export[Goods.cotton.value] = 0
        trader.inventory_foreign[Goods.cotton.value] = 3
        buyer = Agent(0)
        initialize_agent(buyer, Goods.cloth, 0, 0, 100.0)
        buyer.is_corporation = True
        buyer.inv_set(Goods.cotton, 0)
        source.agents = [trader]
        destination.agents = [buyer]
        imports = pending_imports(destination, source)
        begin_turn(source, 1)
        begin_turn(destination, 1)

        clear_discriminatory(
            destination, Goods.cotton, 10.0, total_asks=3, total_bids=3,
            imp_pool=imports[Goods.cotton], agents=[buyer], t=1,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 3, 'limit_price': 10.0},
            ]})

        sale = next(event for event in destination.economic_events
                    if event['kind'] == 'spot_sale')
        wallet_receipt = next(event for event in source.economic_events
                              if event['kind'] == 'wallet_transfer_in')
        source_accounts = {row['actor_id']: row for row in
                           seal_turn(source, 1, event_regions=[source])}
        accounts = {row['actor_id']: row for row in
                    seal_turn(destination, 1, event_regions=[destination])}
        trader_account = source_accounts[trader.id]
        buyer_account = accounts[buyer.id]

        self.assertGreater(sale['amount'], 0.0)
        self.assertEqual(sale['detail']['cash_receipt'], 0.0)
        self.assertAlmostEqual(sale['detail']['wallet_receipt'], sale['amount'])
        self.assertAlmostEqual(wallet_receipt['amount'], sale['amount'])
        self.assertEqual(wallet_receipt['source_id'], sale['id'])
        self.assertEqual(wallet_receipt['detail']['payment_kind'],
                         'imported_market_sale')
        self.assertAlmostEqual(recorded_cash_delta(source.economic_events,
                                                   trader.id), 0.0)
        self.assertAlmostEqual(trader_account['cash_change'], 0.0)
        self.assertAlmostEqual(trader_account['posted_cash_change'], 0.0)
        self.assertAlmostEqual(trader_account['unposted_cash_change'], 0.0)
        self.assertAlmostEqual(
            trader_account['wallet_change_by_currency']['USD'],
            round(sale['amount'], 2))
        self.assertAlmostEqual(
            trader_account['wallet_transfer_in_by_currency']['USD'],
            round(sale['amount'], 2))
        self.assertAlmostEqual(buyer_account['unposted_cash_change'], 0.0)
        self.assertEqual(wallet_receipt['tile'], 'Upland')
        self.assertEqual(wallet_receipt['detail']['settlement_region'], 'Lowland')

    def test_import_quote_and_paid_lot_trace_include_fx_freight_and_drawback(self):
        source = SimpleNamespace(name='Source', home_currency='USD', forex_desks={},
                                 forex=None, recipes={Goods.cotton: {'price': 8.0}})
        destination_fx = ForexDesk('USD', 'EUR', mid=2.0, spread=0.0,
                                   seed_reserves=False)
        source.forex_desks['Port'] = destination_fx
        destination = SimpleNamespace(name='Port')
        trader = self._trader(source, destination, qty=2)
        trader.home_currency = 'USD'
        trader.inventory_foreign[Goods.cotton.value] = 2

        class TariffGovernment:
            import_tariff_enabled = True
            import_tariff_rate = 0.10
            import_drawback_enabled = True
            import_drawback_rate = 0.20

            def __init__(self):
                self.agent = Agent(0)
                initialize_agent(self.agent, Goods.gov, 0, 0, 0.0)
                self.tariff_received = 0.0

            def receive_tariff(self, _turn, amount, region=None):
                self.agent.cash += amount
                self.tariff_received += amount

        government = TariffGovernment()
        market = SimpleNamespace(
            name='Port', home_currency='EUR', recipes={
                Goods.cotton: {'price': 20.0},
                Goods.cloth: {'price': 30.0, 'input': Goods.cotton,
                              'numInput': 1, 'production': 1},
            }, neighbors={source.name: source}, destination_region=source,
            forex_desks={}, forex=None, exchange_rate=1.0, _trade_fee_mult=1.0,
            gov=government, IMPORT_MARGIN_MIN=0.10, IMPORT_MARGIN_MAX=0.10,
            _auction_import_sales={}, agents=[],
        )
        shipment_id = 'shipment-landed-cost-test'
        lot = (trader, 2, False, shipment_id, 8.0, 2.0, 'USD',
               'trader_cost_basis', shipment_id, source.name, [], [])
        ask = import_ask_price(
            market, trader, Goods.cotton, shipment_id=shipment_id,
            source_unit_cost=8.0, freight_per_unit=2.0, source_currency='USD',
            source_region_name=source.name, source_cost_status='trader_cost_basis')
        expected_ask = 5.0 * 1.10 / 0.92
        self.assertAlmostEqual(ask, expected_ask)

        buyer = Agent(0)
        initialize_agent(buyer, Goods.cloth, 1, 0, 100.0)
        buyer.is_corporation = True
        buyer.inv_set(Goods.cotton, 0)
        market.agents = [buyer, trader]
        bought, paid, _ = clear_discriminatory(
            market, Goods.cotton, 20.0, total_asks=2, total_bids=2,
            imp_pool=[lot], agents=market.agents, t=1,
            local_orders={'sellers': [], 'buyers': [
                {'agent': buyer, 'quantity': 2, 'limit_price': ask},
            ]})
        self.assertEqual(bought, 2)
        self.assertAlmostEqual(paid, 2 * ask)
        self.assertAlmostEqual(fx_balance(trader, 'EUR'), paid * 0.92)
        self.assertAlmostEqual(government.tariff_received, paid * 0.08)

        sale = next(e for e in market.economic_events if e['kind'] == 'spot_sale')
        detail = sale['detail']
        self.assertEqual(detail['destination_currency'], 'EUR')
        self.assertEqual(detail['source_cost_currency'], 'USD')
        self.assertAlmostEqual(detail['fx_source_to_destination_rate'], 0.5)
        self.assertEqual(detail['fx_valuation_method'], 'source_home_buy_rate_inverse')
        self.assertAlmostEqual(detail['landed_cost_source_currency'], 10.0)
        self.assertAlmostEqual(detail['landed_cost_destination_currency'], 5.0)
        self.assertAlmostEqual(detail['import_tariff_assessed_per_unit'], ask * 0.10)
        self.assertAlmostEqual(detail['import_tariff_rebate_per_unit'], ask * 0.02)
        self.assertAlmostEqual(detail['import_tariff_paid_per_unit'], ask * 0.08)
        self.assertAlmostEqual(detail['seller_net_receipt_per_unit'], ask * 0.92)
        self.assertAlmostEqual(detail['trader_landed_margin_per_unit'], 0.5)

        accounts = seal_turn(market, 1, event_regions=[market])
        buyer_account = next(row for row in accounts if row['actor_id'] == buyer.id)
        delivered = buyer_account['delivered_input_lots'][0]
        self.assertEqual(buyer_account['delivered_input_currency'], 'EUR')
        self.assertAlmostEqual(delivered['landed_cost_destination_currency'], 5.0)
        self.assertAlmostEqual(delivered['import_tariff_paid_per_unit'], ask * 0.08)
        self.assertAlmostEqual(delivered['trader_landed_margin_per_unit'], 0.5)

    def test_import_reference_cap_never_quotes_below_landed_break_even(self):
        source = SimpleNamespace(name='Source', home_currency='D', forex_desks={},
                                 forex=None, recipes={Goods.cotton: {'price': 8.0}})
        destination = SimpleNamespace(name='Port',
                                      recipes={Goods.cotton: {'price': 2.0}})
        trader = self._trader(source, destination, qty=1)
        market = self._destination_market(destination, source, {})
        market.recipes[Goods.cotton]['price'] = 2.0
        market.IMPORT_MARGIN_MIN = 0.10
        market.IMPORT_MARGIN_MAX = 0.10
        ask = import_ask_price(
            market, trader, Goods.cotton, source_unit_cost=8.0,
            freight_per_unit=2.0, source_currency='D',
            source_region_name=source.name)
        self.assertGreaterEqual(ask, 10.0)

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
