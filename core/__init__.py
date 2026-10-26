"""
core package — Simulation world generation, game loop engine, state mutation handler,
topology indices, and central configuration.
"""

from __future__ import annotations

from game_time import GameClock
from goods import Goods
from ledger import Ledger
from random_cache import rand
from sim_engine import SimEngine
from sim_world import SimWorld
from sim_world_voronoi import build_world_voronoi
from state_handler import StateMutationHandler, StateViolationError, state_handler
from world_config import WorldConfig
from world_topology import (
    build_nation_tile_index,
    build_neighbor_index,
    clear_topology_caches,
    get_nation_tile_index,
    get_neighbor_index,
    get_province_tile_index,
)

__all__ = [
    "GameClock",
    "Goods",
    "Ledger",
    "rand",
    "SimEngine",
    "SimWorld",
    "build_world_voronoi",
    "StateMutationHandler",
    "StateViolationError",
    "state_handler",
    "WorldConfig",
    "build_neighbor_index",
    "build_nation_tile_index",
    "get_neighbor_index",
    "get_nation_tile_index",
    "get_province_tile_index",
    "clear_topology_caches",
]
