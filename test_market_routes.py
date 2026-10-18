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
        self.assertEqual(route.pending[0][1:], [Goods.cotton, 3, source.name])

        route.deliver_pending()
        route.advance()
        destination.recipes = {
            Goods.cotton: {'price': 10.0},
            Goods.cloth: {'price': 20.0, 'input': Goods.cotton,
                          'numInput': 2, 'production': 4},
        }
        imports = pending_imports(destination, source)
        self.assertEqual(imports[Goods.cotton], [(trader, 3, False)])
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
        self.assertEqual(destination_market._auction_import_sales[Goods.cotton], (3, paid))

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
