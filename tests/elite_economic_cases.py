"""Twenty declared economic conditions, independent of the planner's implementation."""
from dataclasses import dataclass
import math
import random
import numpy as np
from goods import Goods
from world_config import GameplayFlags, GAMEPLAY_FLAG_NAMES
from tests.elite_plan_fixture import firm_fixture, set_fixture_price
from tests.test_elite_cash_accounting import person


@dataclass(frozen=True)
class EconomicCase:
    name: str
    family: str
    seed: int
    cash: float = 14
    workers: int = 1
    wage: float = 3
    input_price: float = 2
    output_price: float = 18
    initial_inputs: int = 0
    demand: int = 1
    buyer_cash: float = 500
    supply: int = 40
    turns: int = 2
    obligation: float = 0


def economic_cases():
    small = [EconomicCase(f'affordable_batch_{i+1}', 'one_batch', 101+i,
                         cash=2*(2+i*.1)+(3+i%2)+.5+(1 if i==4 else 0),
                         wage=3+i%2, input_price=2+i*.1, output_price=18+i,
                         obligation=1 if i == 4 else 0) for i in range(5)]
    large = []
    for i in range(5):
        workers = 2 + i % 3
        synergy = 1 + (.15 if workers < 4 else .20) * workers
        large.append(EconomicCase(f'capacity_batch_{workers}_workers_{i+1}', 'larger_batch', 106+i,
                                  cash=(6 if i < 3 else 10)*workers+1, workers=workers, wage=2,
                                  output_price=20+i, demand=math.floor(workers*synergy)))
    waiting = [EconomicCase(f'existing_inputs_{i+1}', 'wait', 111+i, cash=12+i,
                            workers=1+i%2, initial_inputs=2*(1+i%2)*(2+i%2),
                            demand=2*(1+i%2), turns=2+i%2) for i in range(5)]
    declined = [
        EconomicCase('no_observed_demand', 'decline', 116, demand=0, buyer_cash=0),
        EconomicCase('buyer_unfunded', 'decline', 117, buyer_cash=0),
        EconomicCase('negative_material_contribution', 'decline', 118, cash=30, input_price=3, output_price=2),
        EconomicCase('payroll_leaves_no_input_budget', 'decline', 119, cash=5, input_price=2),
        EconomicCase('incomplete_input_batch', 'decline', 120, supply=1),
    ]
    return small + large + waiting + declined


def build_case(case):
    random.seed(case.seed)
    np.random.seed(case.seed)
    from random_cache import rand
    rand.reset(force=True)
    region, firm, worker, supplier, buyer = firm_fixture()
    stepped = {'elite_planning', 'local_market', 'production', 'wages'}
    region._gameplay_flags = GameplayFlags(**{name:name in stepped for name in GAMEPLAY_FLAG_NAMES})
    firm.cash, firm.wage = case.cash, case.wage
    workers = [worker] + [person(Goods.iron, 0) for _ in range(case.workers - 1)]
    for employee in workers:
        employee.employer, employee.founding_age_offset = firm, 30
    firm.employees = workers
    region.agents = [firm, *workers, supplier, buyer, region.gov.agent]
    supplier.inv_set(Goods.wood, case.supply)
    firm.inv_set(Goods.wood, case.initial_inputs)
    firm.cost_set(Goods.wood, case.input_price)
    # Two buyers keep funded demand compatible with the real per-household caps.
    second_buyer = person(Goods.iron, case.buyer_cash / 2)
    buyer.cash = case.buyer_cash / 2
    for consumer in (buyer, second_buyer):
        consumer.consumption_multiplier = max(2, case.demand)
    region.agents.append(second_buyer)
    set_fixture_price(region, Goods.wood, case.input_price)
    set_fixture_price(region, Goods.furniture, case.output_price)
    region.economic_events[0]['quantity'] = case.demand / 2
    region.economic_events.append({**region.economic_events[0], 'id': 2,
                                   'payer_id': second_buyer.id, 'quantity': case.demand / 2})
    region._next_economic_event_id = 3
    if case.obligation:
        from livelihood_access import assess_obligation
        assess_obligation(region, firm.id, supplier.id, 'service', case.obligation, 2)
    return region, firm
