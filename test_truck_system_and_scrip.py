"""
test_truck_system_and_scrip.py — Tests for Company Scrip, Tommy Shop, Debt Peonage, and Anti-Truck Act.
"""

import unittest
from agent import Agent
from nation import Nation
from goods import Goods
import region_finance as _fin
from labor_politics import enact_anti_truck_act


class MockTile:
    def __init__(self, name="TestCity"):
        self.name = name
        self.food_price = 2.0
        self.food = 50.0
        self.agents = []
        self.owner_nation = None


class TestTruckSystemAndScrip(unittest.TestCase):

    def test_scrip_wage_payment_and_conservation(self):
        tile = MockTile()
        corp = Agent(0)
        corp.is_corporation = True
        corp.cash = 5.0  # Cash poor
        corp.pay_mode = "scrip"
        corp.wage = 8.0
        corp.employees = []

        worker = Agent(1)
        worker.cash = 10.0
        worker.scrip_wallet = 0.0
        worker.employer = corp
        corp.employees.append(worker)

        tile.agents = [corp, worker]

        # Employer has $5 cash, owed $8. In scrip mode, employer issues 8 scrip.
        _fin.pay_wages(tile, 1)

        self.assertEqual(corp.cash, 5.0)  # Conserved, no cash paid
        self.assertEqual(worker.scrip_wallet, 8.0)
        self.assertEqual(corp.scrip_issued, 8.0)
        self.assertEqual(corp.scrip_redeemed, 0.0)

    def test_tommy_shop_redemption_markup(self):
        tile = MockTile()
        tile.food_price = 2.0
        tommy_price = 2.70

        corp = Agent(0)
        corp.is_corporation = True
        corp.inv_add(Goods.food, 20)
        corp.pay_mode = "scrip"

        worker = Agent(1)
        worker.scrip_wallet = 5.40  # Can buy 2 units at 2.70
        worker.employer = corp
        corp.employees = [worker]

        tile.agents = [corp, worker]

        # Worker needs food (food == 0 < 4)
        _fin.redeem_company_scrip(tile, 1)

        # Bought 2 units: 2 * 2.70 = 5.40 scrip
        self.assertEqual(worker.inv_get(Goods.food, 0), 2)
        self.assertEqual(corp.inv_get(Goods.food, 0), 18)  # 1-for-1 conserved
        self.assertAlmostEqual(worker.scrip_wallet, 0.0)
        self.assertAlmostEqual(corp.scrip_redeemed, 5.40)

    def test_debt_peonage_advances_the_slate(self):
        tile = MockTile()
        tile.food_price = 2.0
        tommy_price = 2.70

        corp = Agent(0)
        corp.is_corporation = True
        corp.inv_add(Goods.food, 10)
        corp.pay_mode = "scrip"

        worker = Agent(1)
        worker.cash = 0.50  # Broke
        worker.scrip_wallet = 0.0  # No scrip
        worker.company_debt = 0.0
        worker.despair = 0.10
        worker.alienation = 0.10
        worker.employer = corp
        corp.employees = [worker]

        tile.agents = [corp, worker]

        _fin.redeem_company_scrip(tile, 1)

        # Worker granted food on credit ("the slate")
        self.assertEqual(worker.inv_get(Goods.food, 0), 1)
        self.assertEqual(corp.inv_get(Goods.food, 0), 9)
        self.assertAlmostEqual(worker.company_debt, tommy_price)
        self.assertAlmostEqual(worker.despair, 0.25)
        self.assertAlmostEqual(worker.alienation, 0.20)

    def test_anti_truck_act_enactment(self):
        nat = Nation("Testland")
        tile = MockTile()
        tile.owner_nation = nat
        nat.tiles = [tile]

        corp = Agent(0)
        corp.is_corporation = True
        corp.pay_mode = "scrip"
        corp.wage = 2.0

        worker = Agent(1)
        worker.company_debt = 25.0
        worker.employer = corp
        corp.employees = [worker]

        tile.agents = [corp, worker]

        self.assertFalse(nat.truck_act_enacted)
        self.assertEqual(corp.pay_mode, "scrip")
        self.assertEqual(worker.company_debt, 25.0)

        ok, msg = enact_anti_truck_act(nat)
        self.assertTrue(ok)
        self.assertTrue(nat.truck_act_enacted)
        self.assertEqual(corp.pay_mode, "cash")
        self.assertEqual(worker.company_debt, 0.0)  # All peonage debt canceled!

        # Now verify pay_wages under enacted Truck Act:
        # Firm cannot pay in scrip even if low cash
        corp.cash = 2.0
        worker.scrip_wallet = 0.0
        worker.cash = 0.0
        _fin.pay_wages(tile, 2)
        self.assertEqual(worker.scrip_wallet, 0.0)  # No scrip paid
        self.assertEqual(corp.cash, 0.0)  # Cash was paid up to available
        self.assertEqual(worker.cash, 2.0)


if __name__ == '__main__':
    unittest.main()
