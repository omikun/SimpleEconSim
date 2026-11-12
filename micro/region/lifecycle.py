"""Population lifecycle and trader transitions for one region turn."""

from econsim_states import (
    probability_birth, birth_gap, max_career_switches, starvation_limit,
)
from goods import Goods, profession
from logger import loginfo
from random_cache import rand

import region_logistics as _logistics


def step(region, turn, gameplay_flags=None):
    """Run demographic changes, trader exits, and trader conversions."""
    import econsim_live as live_module
    from econsim_live import LiveContext

    context = LiveContext(
        recipes=region.recipes,
        goods=region.goods,
        governments=[region.gov],
        default_gov=region.gov,
        hungry_log=region.hungry_log,
        dead_pop=region.dead_pop,
        deadstarve_pop=region.dead_starved_population,
        production_log=region.production_log,
        starve_limit=starvation_limit,
        profession=profession,
        max_career_switches=max_career_switches,
        p_birth=probability_birth,
        birth_gap=birth_gap,
        bank=region.bank,
        most_demand=getattr(region, 'most_demand', None),
        charity=region.charity,
        max_agents=region.max_agents,
        carrying_capacity=region.max_agents,
        cost_of_living=region.cost_of_living,
        food_price=region.food_price,
        source_region=region,
        gameplay_flags=gameplay_flags,
    )
    result = live_module.Live(turn, region.agents, context=context)
    _logistics.process_trader_exits(region, turn, result)
    _convert_traders(region, turn, result)
    return result


def _convert_traders(region, turn, agents):
    if not (region.neighbors or region.destination_region is not None) or turn <= 0:
        return
    has_arbitrage = any(
        region.recipes[good]['price'] < other.recipes[good]['price'] * 0.95
        for good in (Goods.wood, Goods.furniture)
        for other in (list(region.neighbors.values()) or [region.destination_region])
    )
    trader_count = sum(1 for agent in agents if agent.is_trader)
    max_traders = int(len(agents) * 0.2)
    for agent in agents:
        if agent.is_corporation:
            continue
        parent = agent.parent
        child = getattr(agent, 'is_native_child', False) and agent.age(turn) < 14
        if (parent is not None and parent.is_trader and not agent.is_trader
                and not child and trader_count < max_traders and rand.random() < 0.5):
            if _logistics.make_trader_internal(region, agent):
                trader_count += 1
                loginfo(turn, f"{agent.name()} inherited trader from parent {parent.name()}")
        elif (not agent.is_trader and not child and has_arbitrage
              and (agent.cash < 20 or agent.hungry_steps > 0)
              and trader_count < max_traders and rand.random() < 0.003):
            if _logistics.make_trader_internal(region, agent):
                trader_count += 1
                loginfo(turn, f"{agent.name()} switched to trader (cash=${agent.cash:.0f})")
