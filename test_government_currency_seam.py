"""A public actor's frontier payment must retain its actual denomination."""
import unittest
from agent import Agent
import forex
from goods import Goods
from nation import Nation
from region import Region
from trade_settle import settle_wilderness


class GovernmentCurrencySeamTests(unittest.TestCase):
    def test_claim_binds_seated_government_and_frontier_payment_conserves_currency(self):
        source = Region('local-name', 0, number_of_agents=0)
        nation = Nation('Country', 'CNY', register=False)
        nation.add_tile(source)
        trader = source.gov.agent
        self.assertEqual('CNY', trader.home_currency)
        self.assertEqual('CNY', source.gov.currency)
        self.assertEqual('CNY', nation.government.agent.home_currency)
        source.agents = [trader]
        trader.is_trader = True
        trader.cash = 100
        trader.inv_add(Goods.wood, 8)
        frontier = Region('Frontier', 0, number_of_agents=0, wilderness=True)
        settler = Agent(0)
        settler.is_homesteader = True
        frontier.agents = [settler]
        before = forex.audit_currency_total([source, frontier], 'CNY')
        result = settle_wilderness(trader, frontier, 30, source_region=source)
        self.assertGreater(result['sold_value'], 0)
        self.assertAlmostEqual(before, forex.audit_currency_total([source, frontier], 'CNY'))
        self.assertNotIn('local-name', settler.wallets)
        self.assertGreater(settler.wallets['CNY'], 0)


if __name__ == '__main__':
    unittest.main()
