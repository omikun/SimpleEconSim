"""
buildings.py — Modular Buildings and Construction Projects for REGNUM.

Implements the physical construction and operational loop:
1. Sovereign / AI funds a project by hiring an emergent contractor corporation.
2. Construction project requires physical materials (Goods.wood, Goods.transport, etc.)
   and live navvy labor. Progress rate is dynamically calculated each turn based on
   resource availability and worker headcount. Missing resources stall the project!
3. Option for emergency overrun subsidies to keep contractors solvent and prevent layoffs.
4. Upon completion, installs the Building into the target Region.
5. Completed buildings require ongoing operational staffing of specific professions
   (e.g., Weavers for mills, Lock-keepers for canals) to maintain full efficiency.
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
    """Blueprint for a constructible building across Municipal, Provincial, and National tiers."""

    def __init__(self, name: str, display_name: str, cost: float,
                 base_turns: int, tier: str = 'tile', required_goods: dict = None,
                 production_bonuses: dict = None, description: str = "",
                 construction_workers: int = 2, staff_required: dict = None):
        self.name = name
        self.display_name = display_name
        self.cost = float(cost)
        self.base_turns = int(base_turns)
        self.tier = tier  # 'tile' | 'province' | 'nation'
        self.required_goods = required_goods if required_goods is not None else {}
        self.production_bonuses = production_bonuses if production_bonuses is not None else {}
        self.description = description
        self.construction_workers = int(construction_workers)
        self.staff_required = staff_required if staff_required is not None else {}

    def __repr__(self):
        return f"BuildingRecipe({self.name}, tier={self.tier}, cost={self.cost}, turns={self.base_turns})"


BUILDING_RECIPES: dict[str, BuildingRecipe] = {
    # ── MUNICIPAL / TILE LEVEL INFRASTRUCTURE ───────────────────────
    'farm': BuildingRecipe(
        name='farm',
        display_name='Irrigation Farm Estate',
        cost=250.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 3},
        construction_workers=2,
        staff_required={Goods.food: 2},
        production_bonuses={Goods.food: 1.20},
        description='Local irrigation and farming estate (+20% Food yield).'
    ),
    'granary': BuildingRecipe(
        name='granary',
        display_name='State Granary',
        cost=250.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 4},
        construction_workers=2,
        staff_required={Goods.food: 2},
        production_bonuses={Goods.food: 1.25},
        description='Improves grain storage and municipal food security (+25% Food output).'
    ),
    'sawmill': BuildingRecipe(
        name='sawmill',
        display_name='Mechanized Sawmill',
        cost=300.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 6},
        construction_workers=2,
        staff_required={Goods.wood: 2},
        production_bonuses={Goods.wood: 1.30},
        description='Water/wind-powered timber mill (+30% Wood output).'
    ),
    'workshop': BuildingRecipe(
        name='workshop',
        display_name='Artisan Guildhall & Workshop',
        cost=400.0,
        base_turns=3,
        tier='tile',
        required_goods={Goods.wood: 8},
        construction_workers=3,
        staff_required={Goods.furniture: 2},
        production_bonuses={Goods.furniture: 1.30},
        description='Centralized manufacturing facility (+30% Furniture output).'
    ),
    'textile_mill': BuildingRecipe(
        name='textile_mill',
        display_name='Mechanized Textile Mill',
        cost=320.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 4, Goods.furniture: 2},
        construction_workers=3,
        staff_required={Goods.cloth: 3},
        production_bonuses={Goods.cloth: 1.35},
        description='Centralized water-powered textile manufactory producing high-value woven cloth from raw fleece.'
    ),
    'trunk_sewer': BuildingRecipe(
        name='trunk_sewer',
        display_name='Bazalgette Intercepting Sewer Network',
        cost=1000.0,
        base_turns=4,
        tier='tile',
        required_goods={Goods.wood: 6, Goods.transport: 4},
        construction_workers=6,
        staff_required={Goods.gov: 2},
        production_bonuses={},
        description='Massive civil engineering megaproject channeling urban wastewater away from rivers; eradicates cholera and restores infant survival.'
    ),
    'smoke_scrubber': BuildingRecipe(
        name='smoke_scrubber',
        display_name='Smokestack Wet Scrubber',
        cost=300.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 3, Goods.furniture: 2},
        construction_workers=2,
        staff_required={Goods.gov: 1},
        production_bonuses={},
        description='Water-spray condensation tower filtering 70% of atmospheric smokestack soot into chemical sludge.'
    ),
    'soil_conservation_reserve': BuildingRecipe(
        name='soil_conservation_reserve',
        display_name='Agroecological Conservation Reserve',
        cost=200.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 2},
        construction_workers=2,
        staff_required={Goods.food: 1},
        production_bonuses={},
        description='Protected agroecological reserve boosting local soil fertility regeneration by +25%.'
    ),
    'municipal_clinic': BuildingRecipe(
        name='municipal_clinic',
        display_name='Municipal Apothecary & Clinic',
        cost=250.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 3, Goods.furniture: 1},
        construction_workers=2,
        staff_required={Goods.gov: 1},
        production_bonuses={},
        description='Municipal apothecary and medical clinic providing subsidized diagnoses, increasing cure rates to 95%.'
    ),
    'workhouse': BuildingRecipe(
        name='workhouse',
        display_name='Parish Workhouse',
        cost=200.0,
        base_turns=2,
        tier='tile',
        required_goods={Goods.wood: 4},
        construction_workers=2,
        staff_required={Goods.gov: 1},
        production_bonuses={},
        description='Confines dispossessed vagrants to compulsory labor for municipal revenue in exchange for bare-subsistence gruel.'
    ),

    # ── PROVINCIAL LEVEL PUBLIC WORKS ───────────────────────────────
    'paved_road': BuildingRecipe(
        name='paved_road',
        display_name='Paved Highway Network',
        cost=350.0,
        base_turns=2,
        tier='province',
        required_goods={Goods.wood: 3},
        construction_workers=3,
        staff_required={Goods.transport: 2},
        production_bonuses={},
        description='Reduces regional transport friction and inter-tile trade delays by 40%.'
    ),
    'turnpike_road': BuildingRecipe(
        name='turnpike_road',
        display_name='Turnpike Trust Road',
        cost=300.0,
        base_turns=2,
        tier='province',
        required_goods={Goods.wood: 3, Goods.transport: 2},
        construction_workers=3,
        staff_required={Goods.transport: 2},
        production_bonuses={},
        description='Macadamized crushed stone toll road cutting overland freight friction by 50% and boosting farm rents by +30%.'
    ),
    'barge_canal': BuildingRecipe(
        name='barge_canal',
        display_name='Contour Barge Canal & Locks',
        cost=380.0,
        base_turns=3,
        tier='province',
        required_goods={Goods.wood: 5, Goods.transport: 3},
        construction_workers=4,
        staff_required={Goods.transport: 3},
        production_bonuses={},
        description='Inland waterway cutting bulk waterborne freight friction by 75% for grain and wool.'
    ),
    'river_bridge': BuildingRecipe(
        name='river_bridge',
        display_name='Fluvial River Bridge & Port',
        cost=300.0,
        base_turns=2,
        tier='province',
        required_goods={Goods.wood: 5},
        construction_workers=3,
        staff_required={Goods.transport: 2},
        production_bonuses={},
        description='Constructs permanent river crossing to maximize fluvial trade capacity and speed.'
    ),
    'sanatorium': BuildingRecipe(
        name='sanatorium',
        display_name='Provincial Sanatorium / Hospital',
        cost=500.0,
        base_turns=3,
        tier='province',
        required_goods={Goods.wood: 5, Goods.furniture: 2},
        construction_workers=3,
        staff_required={Goods.gov: 2},
        production_bonuses={},
        description='Public healthcare institution that reduces citizen mortality across the province.'
    ),
    'water_filtration_plant': BuildingRecipe(
        name='water_filtration_plant',
        display_name='Provincial Water Filtration Plant',
        cost=450.0,
        base_turns=3,
        tier='province',
        required_goods={Goods.wood: 5, Goods.furniture: 3},
        construction_workers=3,
        staff_required={Goods.gov: 2},
        production_bonuses={},
        description='Slow sand-bed water purification facility eliminating chemical and bacterial toxins.'
    ),

    # ── NATIONAL / SOVEREIGN STRATEGIC PROJECTS ─────────────────────
    'mountain_pass': BuildingRecipe(
        name='mountain_pass',
        display_name='Alpine Mountain Pass Road',
        cost=380.0,
        base_turns=2,
        tier='nation',
        required_goods={Goods.wood: 6},
        construction_workers=4,
        staff_required={Goods.transport: 3},
        production_bonuses={},
        description='Engineers an alpine mountain pass road to unblock overland trade across high peaks.'
    ),
    'central_mint': BuildingRecipe(
        name='central_mint',
        display_name='Central Mint & Treasury Exchange',
        cost=600.0,
        base_turns=3,
        tier='nation',
        required_goods={Goods.wood: 6, Goods.furniture: 4},
        construction_workers=4,
        staff_required={Goods.gov: 3},
        production_bonuses={},
        description='National monetary headquarters: stabilizes currency inflation and boosts tax efficiency (+15%).'
    ),
    'military_citadel': BuildingRecipe(
        name='military_citadel',
        display_name='Grand Military Citadel & Barracks',
        cost=550.0,
        base_turns=3,
        tier='nation',
        required_goods={Goods.wood: 8, Goods.furniture: 3},
        construction_workers=4,
        staff_required={Goods.gov: 3},
        production_bonuses={},
        description='National fortress: expands garrison defense and speeds up state military training by 50%.'
    ),
}


class Building:
    """An active, installed building on a tile."""

    def __init__(self, name: str, recipe: BuildingRecipe, built_turn: int, region_name: str):
        self.name = name
        self.recipe = recipe
        self.built_turn = built_turn
        self.region_name = region_name
        self.staff_ids: list[int] = []
        self.operational_efficiency: float = 1.0

    @property
    def display_name(self) -> str:
        return self.recipe.display_name

    @property
    def production_bonuses(self) -> dict:
        eff = self.operational_efficiency
        if eff >= 1.0:
            return self.recipe.production_bonuses
        # Scale bonuses by operational efficiency
        return {g: 1.0 + (mult - 1.0) * eff for g, mult in self.recipe.production_bonuses.items()}

    def step_operational_staffing(self, region: Region, t: int):
        """Hires and retains living workers to operate the facility at full efficiency."""
        req = getattr(self.recipe, 'staff_required', {}) or {}
        if not req:
            self.operational_efficiency = 1.0
            return

        total_req = sum(req.values())
        agents_by_id = {a.id: a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)}
        self.staff_ids = [aid for aid in self.staff_ids if aid in agents_by_id]

        current_by_good = {}
        for aid in self.staff_ids:
            a = agents_by_id[aid]
            current_by_good[a.output] = current_by_good.get(a.output, 0) + 1

        for good, needed in req.items():
            have = current_by_good.get(good, 0)
            if have < needed:
                candidates = [
                    a for a in region.agents
                    if getattr(a, 'alive', True)
                    and not getattr(a, 'is_corporation', False)
                    and not getattr(a, 'is_government', False)
                    and a.employer is None
                    and a.id not in self.staff_ids
                    and (a.output == good or a.output == Goods.none or a.output == Goods.food)
                ]
                for c in candidates[:(needed - have)]:
                    c.output = good
                    self.staff_ids.append(c.id)
                    current_by_good[good] = current_by_good.get(good, 0) + 1

        self.operational_efficiency = max(0.2, min(1.0, len(self.staff_ids) / max(1, total_req)))

    def __repr__(self):
        return f"Building({self.name} in {self.region_name}, built t={self.built_turn}, eff={self.operational_efficiency:.2f})"


class ConstructionProject:
    """Active construction project on a Region funded by a Nation.
    
    Hires a contractor company. Physical materials and live navvy labor are required.
    Build speed is dynamic based on material availability and labor headcount.
    """

    def __init__(self, project_id: str, nation_name: str, region, recipe: BuildingRecipe,
                 contractor: Agent = None, overrun_turns: int = None, started_turn: int = 0):
        self.project_id = project_id
        self.nation_name = nation_name
        self.region = region
        self.recipe = recipe
        self.contractor = contractor
        self.started_turn = started_turn
        self.base_turns = max(1, recipe.base_turns)
        self.overrun_turns = (rand.randint(1, 2) if overrun_turns is None
                              else int(overrun_turns))
        self.total_turns = self.base_turns + self.overrun_turns
        self.turns_elapsed = 0
        self.progress_pct = 0.0
        self.status = 'in_progress'  # 'in_progress' | 'stalled' | 'completed' | 'cancelled'
        self.stall_reason = ""
        self.materials_delivered: dict[Goods, int] = {}
        self.navvy_ids: list[int] = []
        self.events: list[dict] = []
        self.emergency_subsidies_received = 0.0

    @property
    def turns_remaining(self) -> int:
        rem_pct = max(0.0, 100.0 - self.progress_pct)
        return max(0, int(round(self.total_turns * (rem_pct / 100.0))))

    def step(self, t: int, world: dict = None) -> Building | None:
        """Advance construction by 1 turn using real-time resources and navvy labor."""
        if self.status in ('completed', 'cancelled'):
            return None

        self.turns_elapsed += 1

        # 1. Physical Material Procurement Loop
        req_goods = getattr(self.recipe, 'required_goods', {}) or {}
        missing_materials = False
        if self.contractor is not None:
            for g, needed in req_goods.items():
                cur_deliv = self.materials_delivered.get(g, 0)
                if cur_deliv < needed:
                    to_buy = needed - cur_deliv
                    # Check regional market price and attempt purchase
                    g_recipe = self.region.recipes.get(g, {})
                    p = g_recipe.get('price', 4.0)
                    can_afford = int(self.contractor.cash // max(0.5, p))
                    buy_qty = min(to_buy, can_afford)
                    if buy_qty > 0:
                        total_cost = buy_qty * p
                        self.contractor.cash -= total_cost
                        self.materials_delivered[g] = cur_deliv + buy_qty
                    else:
                        missing_materials = True

        # 2. Navvy Recruitment & Wage Payroll Loop
        req_workers = max(1, getattr(self.recipe, 'construction_workers', 2))
        living_navvies = []
        agents_by_id = {a.id: a for a in getattr(self.region, 'agents', []) if getattr(a, 'alive', True)}
        for nid in self.navvy_ids:
            if nid in agents_by_id:
                living_navvies.append(agents_by_id[nid])
        self.navvy_ids = [a.id for a in living_navvies]

        if self.contractor is not None:
            # Recruit missing navvies
            if len(self.navvy_ids) < req_workers:
                needed_w = req_workers - len(self.navvy_ids)
                candidates = [
                    a for a in getattr(self.region, 'agents', [])
                    if getattr(a, 'alive', True)
                    and not getattr(a, 'is_corporation', False)
                    and not getattr(a, 'is_government', False)
                    and a.employer is None
                    and a.id not in self.navvy_ids
                ]
                for c in candidates[:needed_w]:
                    c.employer = self.contractor
                    c.social_class = 'proletarian'
                    self.navvy_ids.append(c.id)
                    living_navvies.append(c)
                    if not hasattr(self.contractor, 'employees'):
                        self.contractor.employees = []
                    if c not in self.contractor.employees:
                        self.contractor.employees.append(c)

            # Pay navvy retaining wages ($1.50/turn)
            navvy_wage = 1.50
            for w in living_navvies:
                if self.contractor.cash >= navvy_wage:
                    self.contractor.cash -= navvy_wage
                    w.cash += navvy_wage
                else:
                    # Contractor broke: unable to pay full wages
                    w.mem_push('mem_unemployment', 1.0)

        # 3. Dynamic Progress Multipliers
        total_req_mat = sum(req_goods.values()) if req_goods else 0
        total_deliv_mat = sum(self.materials_delivered.get(g, 0) for g in req_goods) if total_req_mat > 0 else 0
        m_resource = (total_deliv_mat / total_req_mat) if total_req_mat > 0 else 1.0
        m_labor = min(1.5, len(self.navvy_ids) / req_workers)

        # Check for Stalling
        if total_req_mat > 0 and total_deliv_mat == 0:
            self.status = 'stalled'
            self.stall_reason = "missing_materials"
            msg = (f"[STALLED] Construction of {self.recipe.display_name} in {self.region.name} "
                   f"halted: missing physical construction materials on local market.")
            self.events.append({'t': t, 'event': 'STALLED', 'message': msg})
            if world is not None:
                try:
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'CONSTRUCT', msg, (245, 140, 50))
                except Exception:
                    pass
            return None

        if len(self.navvy_ids) == 0:
            self.status = 'stalled'
            self.stall_reason = "missing_labor"
            msg = (f"[STALLED] Construction of {self.recipe.display_name} in {self.region.name} "
                   f"halted: zero active navvies employed.")
            self.events.append({'t': t, 'event': 'STALLED', 'message': msg})
            return None

        # Active construction progress
        self.status = 'in_progress'
        self.stall_reason = ""
        base_progress_per_turn = 100.0 / max(1, self.total_turns)
        progress_delta = base_progress_per_turn * max(0.2, m_resource) * m_labor
        self.progress_pct = min(100.0, self.progress_pct + progress_delta)

        # 4. Completion Check
        if self.progress_pct >= 100.0:
            self.status = 'completed'
            building = Building(
                name=self.recipe.name,
                recipe=self.recipe,
                built_turn=t,
                region_name=self.region.name
            )
            if hasattr(self.region, 'buildings'):
                self.region.buildings.append(building)

            if self.contractor is not None:
                self.contractor.projects_completed = getattr(self.contractor, 'projects_completed', 0) + 1

            # Apply dynamic geographic unblocking
            try:
                from terrain_edges import get_edge_manager
                em = get_edge_manager()
                if em is not None:
                    if self.recipe.name == 'mountain_pass':
                        for other_name in list(em.tiles_by_name.keys()):
                            edge = em.get_edge(self.region.name, other_name)
                            if edge and (not edge.passable or edge.edge_type.value in ('alpine_blocked', 'cliff_blocked')):
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
            except Exception:
                pass

            msg = (f"Completed construction of {self.recipe.display_name} in {self.region.name} "
                   f"after {self.turns_elapsed} turns.")
            self.events.append({'t': t, 'event': 'COMPLETED', 'message': msg})
            if world is not None:
                try:
                    from worldview_engine import ticker_push
                    ticker_push(world, t, 'CONSTRUCT', msg, (100, 230, 140))
                except Exception:
                    pass
            return building

        return None

    def __repr__(self):
        return (f"ConstructionProject({self.recipe.name} in {self.region.name}, "
                f"{self.progress_pct:.1f}%, status={self.status})")
