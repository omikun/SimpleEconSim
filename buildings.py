"""
buildings.py — Modular Buildings and Construction Projects for REGNUM.

Implements the physical construction loop:
1. Sovereign / AI funds a project by hiring a contractor corporation.
2. Construction project takes N turns (from recipe) + random overruns (1-2 turns)
   due to weather or accidents.
3. Upon completion, installs the Building into the target Region, providing
   permanent economic and regional modifiers.
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING
from goods import Goods
from random_cache import rand

if TYPE_CHECKING:
    from region import Region
    from nation import Nation
    from agent import Agent


class BuildingRecipe:
    """Blueprint for a constructible building."""

    def __init__(self, name: str, display_name: str, cost: float,
                 base_turns: int, required_goods: dict = None,
                 production_bonuses: dict = None, description: str = ""):
        self.name = name
        self.display_name = display_name
        self.cost = float(cost)
        self.base_turns = int(base_turns)
        self.required_goods = required_goods if required_goods is not None else {}
        self.production_bonuses = production_bonuses if production_bonuses is not None else {}
        self.description = description

    def __repr__(self):
        return f"BuildingRecipe({self.name}, cost={self.cost}, turns={self.base_turns})"


BUILDING_RECIPES: dict[str, BuildingRecipe] = {
    'granary': BuildingRecipe(
        name='granary',
        display_name='State Granary',
        cost=250.0,
        base_turns=2,
        required_goods={Goods.wood: 4},
        production_bonuses={Goods.food: 1.25},
        description='Improves grain storage and farming efficiency (+25% Food output).'
    ),
    'sawmill': BuildingRecipe(
        name='sawmill',
        display_name='Mechanized Sawmill',
        cost=300.0,
        base_turns=2,
        required_goods={Goods.wood: 6},
        production_bonuses={Goods.wood: 1.30},
        description='Water/wind-powered timber mill (+30% Wood output).'
    ),
    'workshop': BuildingRecipe(
        name='workshop',
        display_name='Artisan Guildhall & Workshop',
        cost=400.0,
        base_turns=3,
        required_goods={Goods.wood: 8},
        production_bonuses={Goods.furniture: 1.30},
        description='Centralized manufacturing facility (+30% Furniture output).'
    ),
    'paved_road': BuildingRecipe(
        name='paved_road',
        display_name='Paved Highway Network',
        cost=350.0,
        base_turns=2,
        required_goods={Goods.wood: 3},
        production_bonuses={},
        description='Reduces regional transport delays and trade friction.'
    ),
    'mountain_pass': BuildingRecipe(
        name='mountain_pass',
        display_name='Alpine Mountain Pass Road',
        cost=380.0,
        base_turns=2,
        required_goods={Goods.wood: 6},
        production_bonuses={},
        description='Engineers an alpine mountain pass road to unblock overland trade across high peaks.'
    ),
    'river_bridge': BuildingRecipe(
        name='river_bridge',
        display_name='Fluvial River Bridge & Port',
        cost=300.0,
        base_turns=2,
        required_goods={Goods.wood: 5},
        production_bonuses={},
        description='Constructs a permanent river crossing to maximize fluvial trade capacity and speed.'
    ),
    'sanatorium': BuildingRecipe(
        name='sanatorium',
        display_name='Public Sanatorium',
        cost=500.0,
        base_turns=3,
        required_goods={Goods.wood: 5, Goods.furniture: 2},
        production_bonuses={},
        description='Public healthcare institution that reduces citizen mortality.'
    ),
}


class Building:
    """An active, installed building on a tile."""

    def __init__(self, name: str, recipe: BuildingRecipe, built_turn: int, region_name: str):
        self.name = name
        self.recipe = recipe
        self.built_turn = built_turn
        self.region_name = region_name

    @property
    def display_name(self) -> str:
        return self.recipe.display_name

    @property
    def production_bonuses(self) -> dict:
        return self.recipe.production_bonuses

    def __repr__(self):
        return f"Building({self.name} in {self.region_name}, built t={self.built_turn})"


class ConstructionProject:
    """Active construction project on a Region funded by a Nation.
    
    Hires a corporation as the contractor. The project progresses turn by turn
    for (base_turns + random overrun).
    """

    def __init__(self, project_id: str, nation_name: str, region, recipe: BuildingRecipe,
                 contractor: Agent = None, overrun_turns: int = None, started_turn: int = 0):
        self.project_id = project_id
        self.nation_name = nation_name
        self.region = region
        self.recipe = recipe
        self.contractor = contractor
        self.started_turn = started_turn
        self.base_turns = recipe.base_turns
        # Overruns due to weather or accidents (random 1-2 turns)
        self.overrun_turns = (rand.randint(1, 2) if overrun_turns is None
                              else int(overrun_turns))
        self.total_turns = self.base_turns + self.overrun_turns
        self.turns_remaining = self.total_turns
        self.turns_elapsed = 0
        self.status = 'in_progress'  # 'in_progress' | 'completed' | 'cancelled'
        self.events: list[dict] = []

    def step(self, t: int) -> Building | None:
        """Advance construction by 1 turn.
        
        Returns the completed Building if finished this turn, otherwise None.
        """
        if self.status != 'in_progress':
            return None

        self.turns_elapsed += 1
        self.turns_remaining -= 1

        # Check if we just entered the overrun phase
        if self.turns_remaining == self.overrun_turns and self.overrun_turns > 0:
            msg = (f"Construction of {self.recipe.display_name} in {self.region.name} "
                   f"experienced unexpected delays (weather/accidents): +{self.overrun_turns} turns.")
            self.events.append({'t': t, 'event': 'OVERRUN', 'message': msg})

        # Check for completion
        if self.turns_remaining <= 0:
            self.status = 'completed'
            building = Building(
                name=self.recipe.name,
                recipe=self.recipe,
                built_turn=t,
                region_name=self.region.name
            )
            if hasattr(self.region, 'buildings'):
                self.region.buildings.append(building)
                
            # Apply dynamic geographic unblocking
            from terrain_edges import get_edge_manager
            em = get_edge_manager()
            if em is not None:
                if self.recipe.name == 'mountain_pass':
                    for other_name in list(em.tiles_by_name.keys()):
                        edge = em.get_edge(self.region.name, other_name)
                        if edge and (not edge.passable or edge.edge_type.value == 'alpine_blocked' or edge.edge_type.value == 'cliff_blocked'):
                            em.unblock_mountain_pass(self.region.name, other_name)
                            other_tile = em.tiles_by_name.get(other_name)
                            if other_tile and other_name not in self.region.neighbors:
                                self.region.add_neighbor(other_tile, t)
                                other_tile.add_neighbor(self.region, t)
                elif self.recipe.name == 'river_bridge':
                    for other_name in list(em.tiles_by_name.keys()):
                        edge = em.get_edge(self.region.name, other_name)
                        if edge and edge.is_river:
                            em.build_river_bridge(self.region.name, other_name)

            msg = (f"Completed construction of {self.recipe.display_name} in {self.region.name} "
                   f"after {self.turns_elapsed} turns.")
            self.events.append({'t': t, 'event': 'COMPLETED', 'message': msg})
            return building

        return None

    def __repr__(self):
        return (f"ConstructionProject({self.recipe.name} in {self.region.name}, "
                f"{self.turns_elapsed}/{self.total_turns} turns, status={self.status})")
