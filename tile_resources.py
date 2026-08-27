"""
tile_resources.py — Procedural Natural Resource Endowments for REGNUM.

Assigns natural resource deposits to tiles based on topography (elevation),
hydrology (rivers/coasts), and biomes:
- 🌾 Arable Silt: River floodplains & fertile lowlands (Food & crops).
- 🌲 Old-Growth Timber: Temperate foothills & mountain valleys (Lumber & charcoal).
- ⛏️ Iron Ore: High mountain ridges & sheer cliffs (Metallurgy & tools).
- 🪨 Coal Seams: Sub-alpine basins & highland valleys (Industrial smelting & steam).
- 🐑 Pasture & Flax: High steppes & savannah plains (Wool & fiber textiles).
- 🛢️ Crude Petroleum: Sedimentary lowlands & coastal basins (Hydrocarbons & plastics).
- ⚡ Rare Minerals & Silica: Deep granite summits & salt pans (Electricity & microchips).
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from random_cache import rand

if TYPE_CHECKING:
    from region import Region
    from nation import Nation


class TileResource(str, Enum):
    ARABLE_SILT = "arable_silt"
    TIMBER = "timber"
    IRON_ORE = "iron_ore"
    COAL_SEAM = "coal_seam"
    PASTURE_FLAX = "pasture_flax"
    CRUDE_PETROLEUM = "crude_petroleum"
    RARE_MINERALS = "rare_minerals"


@dataclass
class ResourceInfo:
    resource_id: TileResource
    name: str
    icon: str
    description: str
    color: tuple[int, int, int]


RESOURCE_META: dict[TileResource, ResourceInfo] = {
    TileResource.ARABLE_SILT: ResourceInfo(
        resource_id=TileResource.ARABLE_SILT,
        name="Arable Silt",
        icon="🌾",
        description="Fertile river alluvium; high grain productivity and farming surplus.",
        color=(120, 200, 100),
    ),
    TileResource.TIMBER: ResourceInfo(
        resource_id=TileResource.TIMBER,
        name="Old-Growth Timber",
        icon="🌲",
        description="Dense hardwood forests; lumber for construction, joinery, and charcoal.",
        color=(60, 150, 80),
    ),
    TileResource.IRON_ORE: ResourceInfo(
        resource_id=TileResource.IRON_ORE,
        name="Iron Ore Veins",
        icon="⛏️",
        description="Mountain hematite and magnetite veins; foundational for tools, armor, and steel.",
        color=(210, 120, 70),
    ),
    TileResource.COAL_SEAM: ResourceInfo(
        resource_id=TileResource.COAL_SEAM,
        name="Bituminous Coal",
        icon="🪨",
        description="Sub-surface fossil fuel seams; fuels blast furnaces, coking, and steam locomotion.",
        color=(100, 100, 115),
    ),
    TileResource.PASTURE_FLAX: ResourceInfo(
        resource_id=TileResource.PASTURE_FLAX,
        name="Pasture & Flax",
        icon="🐑",
        description="Grasslands and fiber crops; wool for spinning and linen sailcloth.",
        color=(230, 210, 110),
    ),
    TileResource.CRUDE_PETROLEUM: ResourceInfo(
        resource_id=TileResource.CRUDE_PETROLEUM,
        name="Crude Petroleum",
        icon="🛢️",
        description="Hydrocarbon reserves; refined into diesel, asphalt, petrochemicals, and fertilizer.",
        color=(60, 60, 70),
    ),
    TileResource.RARE_MINERALS: ResourceInfo(
        resource_id=TileResource.RARE_MINERALS,
        name="Rare Minerals & Quartz",
        icon="⚡",
        description="Highland quartz, copper, and silica; essential for electrification and microchips.",
        color=(80, 200, 255),
    ),
}


def assign_tile_resources(tiles: list[Region], heightmap_gen=None, seed: int = 42):
    """Procedurally assign realistic natural resources to each tile based on geography."""
    rng = random.Random(seed)

    for r in tiles:
        elev = getattr(r, 'elevation', 0.20)
        res_set: set[TileResource] = set()

        # 1. High Mountains (Elev >= 0.65)
        if elev >= 0.65:
            res_set.add(TileResource.IRON_ORE)
            if rng.random() < 0.45:
                res_set.add(TileResource.RARE_MINERALS)
            elif rng.random() < 0.35:
                res_set.add(TileResource.TIMBER)

        # 2. Highlands & Foothills (Elev in [0.35, 0.65))
        elif elev >= 0.35:
            res_set.add(TileResource.TIMBER)
            if rng.random() < 0.50:
                res_set.add(TileResource.COAL_SEAM)
            elif rng.random() < 0.40:
                res_set.add(TileResource.IRON_ORE)

        # 3. Lowlands & River Valleys (Elev in [0.05, 0.35))
        elif elev >= 0.05:
            # Check if near river corridor or normal plain
            is_river = getattr(r, 'is_river_corridor', False) or (rng.random() < 0.45)
            if is_river:
                res_set.add(TileResource.ARABLE_SILT)
            else:
                res_set.add(TileResource.PASTURE_FLAX)

            if rng.random() < 0.30:
                res_set.add(TileResource.CRUDE_PETROLEUM)
            elif rng.random() < 0.25:
                res_set.add(TileResource.COAL_SEAM)

        # 4. Coastal / Deltas (Elev < 0.05)
        else:
            res_set.add(TileResource.ARABLE_SILT)
            if rng.random() < 0.40:
                res_set.add(TileResource.CRUDE_PETROLEUM)
            else:
                res_set.add(TileResource.PASTURE_FLAX)

        # Fallback guarantee: every tile has at least 1 resource
        if not res_set:
            res_set.add(TileResource.ARABLE_SILT if elev < 0.4 else TileResource.TIMBER)

        r.natural_resources = res_set


def get_nation_resources(nation: Nation, tiles: list[Region] | None = None, world: dict | None = None) -> set[TileResource]:
    """Return all resources accessible to a nation via domestic ownership or trade imports."""
    accessible: set[TileResource] = set()

    # 1. Domestic ownership
    for r in nation.tiles:
        res = getattr(r, 'natural_resources', None)
        if res:
            accessible.update(res)

    # 2. Trade route imports & bilateral trade pacts
    if world:
        from diplomacy import get_diplomacy, TreatyType
        dip = get_diplomacy()
        for other_n in world.get('nations', []):
            if other_n.name == nation.name:
                continue
            # If active trade pact exists, nation has access to foreign export resources
            if dip.has_treaty(nation.name, other_n.name, TreatyType.TRADE_PACT.value):
                for r in other_n.tiles:
                    foreign_res = getattr(r, 'natural_resources', None)
                    if foreign_res:
                        accessible.update(foreign_res)

    return accessible
