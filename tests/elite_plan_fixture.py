"""Real firm/market objects with explicitly scoped gameplay for planner acceptance."""
from dataclasses import replace
from goods import Goods
from region import Region
from world_config import FULL_GAMEPLAY_FLAGS
from tests.test_elite_cash_accounting import person


def set_fixture_price(region, good, price):
    """Initialize both quoted and internal prices; subsequent discovery is normal."""
    region.recipes[good]['price'] = price
    region._price_ref[good] = price


def firm_fixture():
    region = Region('Planning fixture', 0, number_of_agents=0)
    region._gameplay_flags = replace(FULL_GAMEPLAY_FLAGS, abundance=False)
    firm = person(Goods.furniture, 20, company=True)
    worker = person(Goods.iron, 0)
    worker.founding_age_offset = 30
    worker.employer = firm
    firm.employees, firm.wage = [worker], 4
    supplier = person(Goods.wood, 0)
    supplier.inv_set(Goods.wood, 40)
    buyer = person(Goods.iron, 100)
    region.agents = [firm, worker, supplier, buyer, region.gov.agent]
    region.recipes[Goods.furniture].update(input=Goods.wood, numInput=2, production=1, price=15, maxinv=100)
    region.recipes[Goods.wood].update(price=3, maxinv=100)
    set_fixture_price(region, Goods.furniture, 15)
    set_fixture_price(region, Goods.wood, 3)
    region.terrain[Goods.furniture] = 1
    region.economic_events = [{'id': 1, 'turn': 0, 'kind': 'spot_sale', 'good': 'furniture',
                               'payer_id': buyer.id, 'recipient_id': supplier.id, 'quantity': 1}]
    region._next_economic_event_id = 2
    region._last_turn = 1
    return region, firm, worker, supplier, buyer
