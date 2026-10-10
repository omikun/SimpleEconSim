"""Small authored two-nation world using the normal regional economy tick."""

from __future__ import annotations

from pathlib import Path
import random

import forex as fx
import sim_engine
from agent import Agent, seed_traits
from goods import Goods
from hexmap import hex_bbox
from livelihood_access import seed_access_rights
from nation import Nation
from region import Region
from economy.map_generator import setup_capitalism_institutions
from scenarios.interpreter import ScenarioInterpreter


SCENARIO_ID = "labor_frontier_rivalry"
TEMPLATE_PATH = Path(__file__).parent / "scenarios" / "templates" / "labor_frontier_rivalry.scenario.json"
DISTRICTS = ("Meridian Works", "Meridian Fields", "Vesper Fields", "Vesper Works")


def get_interpreter() -> ScenarioInterpreter:
    return ScenarioInterpreter.from_file(TEMPLATE_PATH)


def _new_firm(region, owner, *, wage, capital):
    firm = Agent(0)
    seed_traits(firm)
    firm.is_corporation = True
    firm.company_name = f"{region.name} Textile Mill"
    firm.output = Goods.cloth
    firm.owner = owner
    firm.region = region.name
    firm.home_currency = region.home_currency
    firm._bank_ref = region.bank
    firm.cash = min(float(capital), max(0.0, owner.cash))
    owner.cash -= firm.cash
    owner.company_owned = firm
    firm.wage = float(wage)
    firm.max_employees = 8
    region.agents.append(firm)
    region.owner_nation.government._add_citizen(firm)
    return firm


def create_world(seed: int = 612) -> dict:
    """Build only four ticking districts; no sandbox world is built or discarded."""
    random.seed(seed)
    player = Nation("Meridian", currency="Frontier Crown", initial_cash=140.0)
    rival = Nation("Vesper", currency="Frontier Crown", initial_cash=155.0)
    nations = [player, rival]
    tiles = [Region(name, t=0, number_of_agents=20, number_of_traders=1)
             for name in DISTRICTS]
    for index, region in enumerate(tiles):
        (player if index < 2 else rival).add_tile(region)
        region.scenario_location = "capital" if index in (0, 3) else "borderland"
        region.elevation = 0.12
        region.biome = "plains"
        region.wilderness = False
        region.cash_tax_per_person = 0.15
        region.recipes[Goods.cotton]["price"] = 3.0
        region.recipes[Goods.cloth]["input"] = Goods.cotton
        region.recipes[Goods.cloth]["numInput"] = 2
        region.recipes[Goods.cloth]["production"] = 3
        region.recipes[Goods.cloth]["price"] = 13.0
        if index in (1, 2):
            setup_capitalism_institutions(region)
            seed_access_rights(region)
            for grower in region.agents[1:6]:
                grower.output = Goods.cotton
                grower.inv_add(Goods.cotton, 3)  # Starting physical crop stock.
        else:
            owner = next(a for a in region.agents if not a.is_trader and not a.is_government)
            firm = _new_firm(region, owner, wage=2.4 if index == 0 else 2.2,
                             capital=65.0 if index == 0 else 75.0)
            firm.inv_add(Goods.cotton, 12)  # Starting raw material reserve.
    player.government.food_inventory = 18
    rival.government.food_inventory = 18
    for left, right in zip(tiles, tiles[1:]):
        left.add_neighbor(right)
        right.add_neighbor(left)
    layout = {name: (index, 0) for index, name in enumerate(DISTRICTS)}
    pair_orders = [(r, o) for r in tiles for o in r.neighbors.values()]
    world = {
        "scenario_id": SCENARIO_ID,
        "player_nation_name": player.name,
        "tiles": tiles,
        "nations": nations,
        "grid": [tiles],
        "layout": layout,
        "bbox": hex_bbox(layout, 48),
        "by_name": {r.name: r for r in tiles},
        "pair_orders": pair_orders,
        "currencies": [player.currency],
        "turn": 0,
        "playing": False,
        "events": [],
        "scenario_state": {},
    }
    interpreter = get_interpreter()
    interpreter.initialize_scenario(world)
    world["currency_totals"] = {player.currency: fx.audit_currency_total(tiles, player.currency)}
    return world


def step_world(world: dict) -> list:
    """Advance the authoritative engine once, then read scenario outcomes."""
    turn = int(world["turn"]) + 1
    if world["scenario_state"].get("ending"):
        return []
    events = world["events"]
    violations, _ = sim_engine.step_turn(
        turn, world["tiles"], nations=world["nations"],
        pair_orders=world["pair_orders"], currencies=world["currencies"],
        on_event=lambda t, kind, message: events.append(
            {"turn": t, "kind": kind, "message": message}),
        ledger_exempt=True,
    )
    world["turn"] = turn
    world["violations"] = violations
    get_interpreter().advance_turn(world, turn)
    world["currency_totals"] = {
        currency: fx.audit_currency_total(world["tiles"], currency)
        for currency in world["currencies"]
    }
    return violations
