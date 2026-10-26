"""
economy/transformation_graph.py — Generalized Transformation Graph and Operator Registry.

Theoretical Foundation (Sven Beckert / Political Economy):
Economic and institutional transitions (feudalism -> agrarian capitalism -> industrial capitalism)
are not hardcoded state machines. They emerge from agents discovering multi-step conversion
paths from their resource endowments (land, coercive authority, labor claims, capital) into
liquid money and prestige goods.

Zero-Hardcoding Principle:
Any new commodity, resource, technology, or institutional action can be registered at runtime
without altering the agent planning engine.
"""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from goods import Goods


@dataclass
class CommoditySpec:
    """Universal commodity and asset specification."""
    good: Any                      # Goods enum value or string identifier
    name: str
    category: str                  # 'subsistence', 'raw_material', 'intermediate', 'manufacture', 'luxury', 'currency'
    base_price: float = 1.0
    prestige_rating: float = 0.0   # Multiplier for status/luxury utility (0.0 for non-luxuries)
    subsistence_value: float = 0.0 # Caloric / survival utility
    durability: float = 1.0        # Preservation rate per turn
    tradeable: bool = True

    def marginal_utility(self, current_held: float) -> float:
        """Diminishing marginal utility of acquiring another unit."""
        if self.prestige_rating > 0:
            # Sombart/Veblen prestige curve: high initial spike, logarithmic diminishing return
            return self.prestige_rating / (1.0 + 0.15 * current_held)
        if self.subsistence_value > 0:
            # Subsistence: vital when starving, zero once satiated
            return self.subsistence_value if current_held < 4.0 else 0.05
        return 0.1 / (1.0 + 0.05 * current_held)


@dataclass
class TransformationOperator:
    """A generalized transformation process in the economy.
    
    Can represent physical production, institutional dispossession/enclosure,
    feudal corvée extraction, market exchange, or consumption.
    """
    id: str
    name: str
    category: str                  # 'feudal', 'enclosure', 'corvee', 'artisan', 'capitalist', 'market', 'consumption'
    input_goods: Dict[Any, float] = field(default_factory=dict)
    output_goods: Dict[Any, float] = field(default_factory=dict)
    required_tenure: Optional[str] = None # 'feudal', 'enclosed', etc.
    requires_lord: bool = False
    requires_capitalist: bool = False
    cash_cost: float = 0.0
    labor_slots_required: int = 1
    description: str = ""
    # Ecological, climate and geological gating
    allowed_climates: Optional[List[str]] = None
    disallowed_climates: Optional[List[str]] = None
    allowed_biomes: Optional[List[str]] = None
    disallowed_biomes: Optional[List[str]] = None
    required_terrain_tags: Optional[List[str]] = None
    # Optional dynamic feasibility, effect, and return estimation hooks
    check_prerequisites: Optional[Callable[[Any, Any], bool]] = None
    on_execute: Optional[Callable[[Any, Any, int], Dict[str, Any]]] = None
    estimate_return_hook: Optional[Callable[[Any, Any, float], float]] = None

    def can_agent_execute(self, agent: Any, region: Any) -> Tuple[bool, str]:
        """Check if *agent* in *region* can execute this operator."""
        if self.category == 'enclosure' and getattr(region, 'food_enclosure_moratorium', False):
            return False, "Food security policy suspends enclosure"
        if self.requires_lord and not getattr(agent, 'is_lord', False):
            return False, "Requires feudal lord status"
        if self.requires_capitalist and getattr(agent, 'cash', 0.0) < self.cash_cost:
            return False, f"Insufficient cash (requires ${self.cash_cost:.1f})"
        if getattr(agent, 'cash', 0.0) < self.cash_cost:
            return False, f"Cannot afford cash cost ${self.cash_cost:.1f}"

        # Check ecological & biome gating
        clim = getattr(region, 'climate', None)
        if clim:
            if self.allowed_climates and clim not in self.allowed_climates:
                return False, f"Requires climate in {self.allowed_climates}, but region is '{clim}'"
            if self.disallowed_climates and clim in self.disallowed_climates:
                return False, f"Disallowed in '{clim}' climate"

        bio = getattr(region, 'biome', None)
        if bio:
            if self.allowed_biomes and bio not in self.allowed_biomes:
                return False, f"Requires biome in {self.allowed_biomes}, but region is '{bio}'"
            if self.disallowed_biomes and bio in self.disallowed_biomes:
                return False, f"Disallowed in '{bio}' biome"

        if self.required_terrain_tags:
            terrain_dict = getattr(region, 'terrain', {}) or {}
            has_tag = any(
                (tag in terrain_dict) or
                bool(getattr(region, tag, False)) or
                bool(getattr(region, f"has_{tag}", False))
                for tag in self.required_terrain_tags
            )
            if not has_tag:
                return False, f"Requires terrain tags {self.required_terrain_tags}"

        # Check inventory requirements
        for good, required_qty in self.input_goods.items():
            held = 0
            if isinstance(good, Goods):
                held = agent.inv_get(good, 0)
            elif hasattr(agent, 'custom_inventory'):
                held = agent.custom_inventory.get(str(good), 0)
            if held < required_qty:
                return False, f"Missing input commodity: {good}"

        # Check institutional tenure prerequisites
        if self.required_tenure:
            tenure = getattr(region, 'tenure', None)
            if not tenure:
                return False, "Region has no land tenure system"
            matching_plots = [p for p in tenure.plots if getattr(p, 'lord_id', None) == agent.id
                              and p.tenure.value == self.required_tenure]
            if not matching_plots:
                return False, f"No plots with tenure '{self.required_tenure}'"

        # Check custom hook if provided
        if self.check_prerequisites:
            ok = self.check_prerequisites(agent, region)
            if not ok:
                return False, "Prerequisites hook failed"

        return True, "OK"

    def estimate_net_return(self, agent: Any, region: Any, shadow_price_cash: float) -> float:
        """Estimate the expected net economic/utility return of executing this operator."""
        if self.estimate_return_hook is not None:
            return self.estimate_return_hook(agent, region, shadow_price_cash)

        gross_value = 0.0
        # Value of outputs (using rational expected price E[P_{t+k}])
        for g, qty in self.output_goods.items():
            p = TransformationGraph.compute_expected_price(region, g)
            spec = TransformationGraph.get_commodity_spec(g)
            prestige = spec.prestige_rating if spec else 0.0
            if prestige > 0:
                gross_value += prestige * qty
            else:
                gross_value += p * qty * shadow_price_cash

        # Cost of inputs
        input_cost = self.cash_cost * shadow_price_cash
        for g, qty in self.input_goods.items():
            p = float(region.recipes.get(g, {}).get('price', 1.0)) if hasattr(region, 'recipes') else 1.0
            input_cost += p * qty * shadow_price_cash

        return gross_value - input_cost


class TransformationGraph:
    """The central registry and graph search solver for economic operators."""

    _commodities: Dict[Any, CommoditySpec] = {}
    _operators: Dict[str, TransformationOperator] = {}

    @classmethod
    def register_commodity(cls, spec: CommoditySpec) -> None:
        """Register or update a commodity specification."""
        cls._commodities[spec.good] = spec
        if isinstance(spec.good, Goods):
            cls._commodities[spec.good.name] = spec

    @classmethod
    def get_commodity_spec(cls, good: Any) -> Optional[CommoditySpec]:
        """Look up commodity specification by enum or string."""
        if good in cls._commodities:
            return cls._commodities[good]
        if isinstance(good, Goods) and good.name in cls._commodities:
            return cls._commodities[good.name]
        return None

    @classmethod
    def register_operator(cls, op: TransformationOperator) -> None:
        """Register a transformation operator."""
        cls._operators[op.id] = op

    @classmethod
    def get_operator(cls, op_id: str) -> Optional[TransformationOperator]:
        return cls._operators.get(op_id)

    @classmethod
    def all_operators(cls) -> List[TransformationOperator]:
        return list(cls._operators.values())

    @classmethod
    def compute_expected_price(cls, region: Any, good: Any, horizon: int = 5) -> float:
        """Compute rational expected price E[P_{t+k}(g)] using EMA trend and pending capacity damping."""
        p_trend = 1.0
        if hasattr(region, 'price_log') and good in region.price_log and region.price_log[good]:
            prices = region.price_log[good]
            ema = float(prices[0])
            for p in prices[-10:]:
                ema = 0.25 * float(p) + 0.75 * ema
            p_trend = ema
        elif hasattr(region, 'recipes') and good in region.recipes:
            p_trend = float(region.recipes[good].get('price', 1.0))

        # Check pending unharvested or newly committed capacity
        pending = 0.0
        if hasattr(region, 'pending_capacity') and isinstance(region.pending_capacity, dict):
            pending = float(region.pending_capacity.get(good, 0.0))

        # Volume / sales baseline
        recent_sales = 1.0
        if hasattr(region, 'sold_log') and good in region.sold_log and region.sold_log[good]:
            sales = region.sold_log[good][-5:]
            if sales:
                recent_sales = max(1.0, float(sum(sales) / len(sales)))
        else:
            recent_sales = max(2.0, float(len(getattr(region, 'agents', []))) * 0.5)

        # Cobweb damping elasticity formula:
        # When supply commitments flood the market, expected price drops steeply (Ezekiel 1938)
        damping = (1.0 + (pending / recent_sales)) ** (-1.10)
        expected_p = max(0.1, p_trend * damping)
        return expected_p

    @classmethod
    def register_pending_capacity(cls, region: Any, good: Any, qty: float) -> None:
        """Register newly committed production capacity (e.g. newly enclosed pasture, plantation)."""
        if not hasattr(region, 'pending_capacity') or not isinstance(region.pending_capacity, dict):
            region.pending_capacity = {}
        region.pending_capacity[good] = region.pending_capacity.get(good, 0.0) + float(qty)

    @classmethod
    def step_pending_capacity_decay(cls, region: Any, t: int = 0) -> None:
        """Gradually decays pending capacity as crops are harvested or capacity is absorbed into market."""
        if getattr(region, '_last_capacity_decay_turn', None) == t:
            return
        region._last_capacity_decay_turn = t
        if hasattr(region, 'pending_capacity') and isinstance(region.pending_capacity, dict):
            for g in list(region.pending_capacity.keys()):
                region.pending_capacity[g] *= 0.85
                if region.pending_capacity[g] < 0.1:
                    del region.pending_capacity[g]

    @classmethod
    def find_conversion_paths(cls, agent: Any, region: Any, target_good: Any,
                              max_depth: int = 4) -> List[List[TransformationOperator]]:
        """Find candidate multi-step sequences from agent endowments to target_good."""
        valid_paths = []

        def search(current_held: set, path: List[TransformationOperator], depth: int):
            if depth > max_depth:
                return
            if target_good in current_held or target_good == 'cash':
                if path:
                    valid_paths.append(list(path))
                if target_good != 'cash':
                    return

            for op in cls._operators.values():
                if op in path:
                    continue
                # Check if inputs are reachable
                can_run, _ = op.can_agent_execute(agent, region)
                inputs_satisfied = all(inp in current_held for inp in op.input_goods.keys()) or not op.input_goods
                if can_run and inputs_satisfied:
                    new_held = set(current_held)
                    new_held.update(op.output_goods.keys())
                    path.append(op)
                    search(new_held, path, depth + 1)
                    path.pop()

        # Initial endowment set
        initial_held = set()
        for g in Goods:
            if agent.inv_get(g, 0) > 0:
                initial_held.add(g)
        if getattr(agent, 'is_lord', False):
            initial_held.add('feudal_land')
            initial_held.add('bound_serfs')
        if getattr(agent, 'cash', 0.0) > 0:
            initial_held.add('cash')

        search(initial_held, [], 0)
        return valid_paths


# =============================================================================
# Standard Ontology Initializer (Sven Beckert Sectors & Operators)
# =============================================================================

def initialize_default_transformation_ontology():
    """Seed the default commodity specifications and operators for all sectors."""

    # 1. Register Commodities
    specs = [
        CommoditySpec(Goods.food, "Food / Grain", 'subsistence', base_price=1.0, subsistence_value=1.0),
        CommoditySpec(Goods.wood, "Timber / Wood", 'raw_material', base_price=1.0),
        CommoditySpec(Goods.furniture, "Furniture", 'manufacture', base_price=25.0),
        CommoditySpec(Goods.transport, "Transport Haulage", 'intermediate', base_price=1.0),
        CommoditySpec(Goods.wool, "Raw Fleece / Wool", 'raw_material', base_price=3.5),
        CommoditySpec(Goods.cloth, "Spun Cloth / Fabric", 'manufacture', base_price=18.0),
        CommoditySpec(Goods.nitrates, "Nitrate Minerals", 'raw_material', base_price=6.0),
        CommoditySpec(Goods.cotton, "Raw Cotton", 'raw_material', base_price=3.0),
        CommoditySpec(Goods.iron_ore, "Iron Ore", 'raw_material', base_price=4.0),
        CommoditySpec(Goods.iron, "Smelted Iron / Tools", 'intermediate', base_price=16.0),
        CommoditySpec(Goods.coal, "Combustible Coal", 'raw_material', base_price=3.5),
        CommoditySpec(Goods.tobacco, "Virginia Tobacco", 'raw_material', base_price=5.0),
        CommoditySpec(Goods.sugar, "Cane Sugar", 'raw_material', base_price=4.5),
        CommoditySpec(Goods.tea, "Fine Tea", 'raw_material', base_price=6.0),
        # Luxuries with prestige ratings
        CommoditySpec(Goods.fine_textiles, "Silk Damask & Fine Textiles", 'luxury', base_price=50.0, prestige_rating=10.0),
        CommoditySpec(Goods.porcelain, "Fine Porcelain & Ceramics", 'luxury', base_price=55.0, prestige_rating=12.0),
        CommoditySpec(Goods.rum, "Distilled Rum & Fine Spirits", 'luxury', base_price=30.0, prestige_rating=6.0),
        CommoditySpec(Goods.foreign_luxuries, "Foreign Prestige Imports", 'luxury', base_price=100.0, prestige_rating=25.0),
    ]
    for s in specs:
        TransformationGraph.register_commodity(s)

    # 2. Register Transformation Operators

    # A. Feudal Grain Cultivation (Status Quo)
    TransformationGraph.register_operator(TransformationOperator(
        id='feudal_grain_cultivation',
        name='Feudal Customary Grain Farming',
        category='feudal',
        input_goods={},
        output_goods={Goods.food: 3.0},
        requires_lord=False,
        description='Customary serf farming on feudal commons: provides food tribute to lord and keeps serfs fed.',
    ))

    # B. Feudal Enclosure to Pasture / Cash Crop (Beckert Enclosure Dynamic)
    def _execute_enclosure_op(agent, region, t):
        from enclosure import execute_enclosure
        tenure = getattr(region, 'tenure', None)
        if not tenure:
            return {'success': False, 'message': 'No tenure'}
        for plot in tenure.plots:
            if plot.lord_id == agent.id and plot.tenure.value == 'feudal':
                ok, msg, evs = execute_enclosure(region, plot.plot_id, t)
                if ok:
                    plot.production_type = 'pasture'
                    TransformationGraph.register_pending_capacity(region, Goods.wool, 12.0)
                    return {'success': True, 'plot_id': plot.plot_id, 'events': evs}
        return {'success': False, 'message': 'No eligible feudal plot found'}

    TransformationGraph.register_operator(TransformationOperator(
        id='enclose_plot_for_pasture',
        name='Enclose Commons for Sheep Grazing',
        category='enclosure',
        input_goods={},
        output_goods={Goods.wool: 12.0},
        required_tenure='feudal',
        requires_lord=True,
        cash_cost=15.0, # Surveying and bailiff fee
        description='Dispossesses customary serfs and fences fields for lucrative wool production.',
        on_execute=_execute_enclosure_op,
    ))

    # C. Corvée Labor Mandate for Cash Crops (Cotton, Tobacco, Sugar)
    def _execute_corvee_cotton(agent, region, t):
        # Direct serfs to cultivate cotton cash crop
        serfs = [a for a in region.agents if not getattr(a, 'is_lord', False)
                 and not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False) and a.alive]
        yield_amount = min(15, len(serfs))
        agent.inv_add(Goods.cotton, yield_amount)
        TransformationGraph.register_pending_capacity(region, Goods.cotton, float(yield_amount))
        return {'success': True, 'yield': yield_amount}

    TransformationGraph.register_operator(TransformationOperator(
        id='corvee_cotton_plantation',
        name='Mandate Corvée Cotton Cultivation',
        category='corvee',
        input_goods={},
        output_goods={Goods.cotton: 10.0},
        requires_lord=True,
        cash_cost=2.0, # Coercion enforcement cost
        allowed_climates=['temperate', 'subtropical', 'tropical', 'mediterranean'],
        disallowed_climates=['cold', 'arctic'],
        description='Forces customary peasant labor into high-value cotton cash-crop cultivation in suitable climates.',
        on_execute=_execute_corvee_cotton,
    ))

    # D. Corvée Sugar Plantation
    def _execute_corvee_sugar(agent, region, t):
        serfs = [a for a in region.agents if not getattr(a, 'is_lord', False)
                 and not getattr(a, 'is_trader', False) and not getattr(a, 'is_government', False) and a.alive]
        yield_amount = min(12, len(serfs))
        agent.inv_add(Goods.sugar, yield_amount)
        TransformationGraph.register_pending_capacity(region, Goods.sugar, float(yield_amount))
        return {'success': True, 'yield': yield_amount}

    TransformationGraph.register_operator(TransformationOperator(
        id='corvee_sugar_plantation',
        name='Mandate Corvée Sugar Cultivation',
        category='corvee',
        input_goods={},
        output_goods={Goods.sugar: 8.0},
        requires_lord=True,
        cash_cost=2.0,
        allowed_climates=['tropical', 'subtropical', 'temperate'],
        disallowed_climates=['cold', 'arctic'],
        description='Employs corvée labor to cultivate sugar cane for distilling and export in warm climates.',
        on_execute=_execute_corvee_sugar,
    ))

    # E. Industrial Weaving (Wool or Cotton -> Cloth)
    TransformationGraph.register_operator(TransformationOperator(
        id='weave_cloth',
        name='Spinning & Weaving Mill',
        category='artisan',
        input_goods={Goods.wool: 2.0},
        output_goods={Goods.cloth: 1.0},
        requires_lord=False,
        description='Processes raw fiber into market-ready woven cloth.',
    ))

    # F. Luxury Fine Textiles (Cloth -> Fine Textiles)
    TransformationGraph.register_operator(TransformationOperator(
        id='craft_fine_textiles',
        name='Luxury Silk & Fine Damask Tailoring',
        category='artisan',
        input_goods={Goods.cloth: 2.0},
        output_goods={Goods.fine_textiles: 1.0},
        requires_lord=False,
        cash_cost=5.0,
        description='Refines cloth into ultra-high-prestige fine textiles and silks.',
    ))

    # G. Mining & Metallurgy (Iron Ore & Coal -> Smelted Iron)
    TransformationGraph.register_operator(TransformationOperator(
        id='mine_iron_ore',
        name='Iron Ore Mining',
        category='artisan',
        input_goods={},
        output_goods={Goods.iron_ore: 3.0},
        allowed_biomes=['hills', 'mountains', 'snow_peaks', 'forest', 'plains'],
        disallowed_biomes=['ocean', 'deep_ocean', 'shallow_ocean'],
        required_terrain_tags=['iron_deposit', 'has_iron_deposit'],
        description='Extracts iron ore from verified geological iron deposits.',
    ))

    TransformationGraph.register_operator(TransformationOperator(
        id='mine_coal',
        name='Colliery Coal Mining',
        category='artisan',
        input_goods={},
        output_goods={Goods.coal: 4.0},
        allowed_biomes=['hills', 'forest', 'plains', 'mountains'],
        disallowed_biomes=['ocean', 'deep_ocean', 'shallow_ocean'],
        required_terrain_tags=['coal_vein', 'has_coal_vein'],
        description='Extracts coal from verified sedimentary coal seams for industrial blast furnaces.',
    ))

    TransformationGraph.register_operator(TransformationOperator(
        id='smelt_iron',
        name='Blast Furnace Iron Smelting',
        category='artisan',
        input_goods={Goods.iron_ore: 2.0, Goods.coal: 1.0},
        output_goods={Goods.iron: 1.0},
        description='Smelts raw iron ore with coal fuel into industrial bar iron.',
    ))

    # H. Luxury Porcelain Crafting
    TransformationGraph.register_operator(TransformationOperator(
        id='craft_porcelain',
        name='Fine Porcelain Kiln',
        category='artisan',
        input_goods={Goods.iron_ore: 1.0, Goods.wood: 2.0},
        output_goods={Goods.porcelain: 1.0},
        cash_cost=4.0,
        description='Fires fine ceramics and chinaware for high-status households.',
    ))

    # I. Luxury Rum Distilling
    TransformationGraph.register_operator(TransformationOperator(
        id='distill_rum',
        name='Rum & Spirits Distillery',
        category='artisan',
        input_goods={Goods.sugar: 2.0},
        output_goods={Goods.rum: 1.0},
        cash_cost=2.0,
        description='Distills fermented sugar into high-margin rum and liquor.',
    ))

    # J. Class Legislation & State Economic Warfare (Statute of Laborers & Vagrancy Enforcement)
    def _check_statute_prereqs(agent, region):
        is_already_active = (getattr(region, 'statute_of_laborers', False)
                             or getattr(region, 'labor_laws', {}).get('wage_cap') == 'enacted')
        if is_already_active:
            return False
        is_elite = (getattr(agent, 'is_lord', False)
                    or getattr(agent, 'is_corporation', False)
                    or (getattr(agent, 'company_owned', None) is not None)
                    or getattr(agent, 'cash', 0.0) >= 150.0)
        if not is_elite:
            return False
        has_severe_wage_squeeze = any(getattr(a, 'wage', 0.0) >= 2.40 for a in getattr(region, 'agents', ())
                                      if getattr(a, 'is_corporation', False))
        if has_severe_wage_squeeze:
            return True
        from region_labor import calculate_labor_market_tightness
        ltr = calculate_labor_market_tightness(region)
        return ltr >= 1.5

    def _execute_statute_of_laborers(agent, region, t):
        from labor_laws import submit_law_petition
        fee = 20.0
        petition = submit_law_petition(agent, region, 'wage_cap', fee, t)
        return {'success': petition is not None,
                'message': 'Labor-law petition filed for government review.' if petition else 'Petition could not be filed.',
                'petition_id': petition['id'] if petition else None,
                'fee_paid': fee if petition else 0.0}

    TransformationGraph.register_operator(TransformationOperator(
        id='petition_statute_of_laborers',
        name='Petition Crown for Statute of Laborers (Wage Cap)',
        category='political',
        input_goods={},
        output_goods={},
        cash_cost=20.0,
        description='Cartelizes employers and legally caps firm wages at $1.50 to suppress worker bargaining power and protect employer profit margins.',
        check_prerequisites=_check_statute_prereqs,
        on_execute=_execute_statute_of_laborers,
    ))

    def _check_vagrancy_prereqs(agent, region):
        from workhouse import has_workhouse
        is_elite = getattr(agent, 'is_lord', False) or getattr(agent, 'cash', 0.0) >= 100.0
        return (is_elite and has_workhouse(region)
                and not getattr(region, 'vagrancy_law_active', False)
                and not any(p.get('law') == 'vagrancy' and p.get('status') == 'proposed'
                            for p in getattr(region, 'labor_law_petitions', []))
                and getattr(agent, 'cash', 0.0) >= 10.0
                and getattr(getattr(region, 'gov', None), 'agent', None) is not None)

    def _execute_vagrancy_decree(agent, region, t):
        from labor_laws import submit_law_petition
        fee = 10.0
        petition = submit_law_petition(agent, region, 'vagrancy', fee, t)
        return {'success': petition is not None, 'events': [],
                'petition_id': petition['id'] if petition else None,
                'fee_paid': fee if petition else 0.0,
                'message': 'Vagrancy petition filed; government decision is pending.' if petition else 'Petition could not be filed.'}

    TransformationGraph.register_operator(TransformationOperator(
        id='enforce_vagrancy_decree',
        name='Enforce Vagrancy Arrests & Parish Workhouse Confinement',
        category='political',
        input_goods={},
        output_goods={},
        cash_cost=10.0,
        description='Arrests dispossessed and mobile commoners into the Parish Workhouse, forcing compulsory labor and dampening wage resistance.',
        check_prerequisites=_check_vagrancy_prereqs,
        on_execute=_execute_vagrancy_decree,
    ))

    # L. Capital Goods Sector: Machinery Construction & Maintenance (Issue-06)
    def _check_construct_machinery_prereqs(agent, region):
        is_corp = getattr(agent, 'is_corporation', False)
        company = getattr(agent, 'company_owned', None)
        target = agent if is_corp else company
        if target is None:
            firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
            if firms and getattr(agent, 'cash', 0.0) >= 60.0:
                target = firms[0]
        if target is None:
            return False
        tot_cash = getattr(agent, 'cash', 0.0) + (getattr(target, 'cash', 0.0) if target != agent else 0.0)
        iron_price = region.recipes.get(Goods.iron, {}).get('price', 5.0) if hasattr(region, 'recipes') else 5.0
        coal_price = region.recipes.get(Goods.coal, {}).get('price', 3.0) if hasattr(region, 'recipes') else 3.0
        needed_cost = 25.0 + (2.0 * iron_price) + (1.0 * coal_price)
        return tot_cash >= needed_cost

    def _execute_construct_machinery(agent, region, t):
        is_corp = getattr(agent, 'is_corporation', False)
        company = getattr(agent, 'company_owned', None)
        target = agent if is_corp else company
        if target is None:
            firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
            if firms:
                target = firms[0]
        if target is None:
            return {'success': False, 'message': 'No target firm'}

        iron_price = region.recipes.get(Goods.iron, {}).get('price', 5.0) if hasattr(region, 'recipes') else 5.0
        coal_price = region.recipes.get(Goods.coal, {}).get('price', 3.0) if hasattr(region, 'recipes') else 3.0

        iron_held = target.inv_get(Goods.iron, 0) + (agent.inv_get(Goods.iron, 0) if agent != target else 0)
        coal_held = target.inv_get(Goods.coal, 0) + (agent.inv_get(Goods.coal, 0) if agent != target else 0)

        cash_needed = 25.0
        if iron_held < 2:
            cash_needed += (2 - iron_held) * iron_price
        if coal_held < 1:
            cash_needed += (1 - coal_held) * coal_price

        if target.cash >= cash_needed:
            _trace_cash_write = _trace_public_begin(None, target)
            target.cash -= cash_needed
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:feec452fe80bfcc5:1'})
        elif (target.cash + agent.cash) >= cash_needed:
            rem = cash_needed - target.cash
            _trace_cash_write = _trace_public_begin(None, target)
            target.cash = 0.0
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:995753c55e94594f:1'})
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash -= rem
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:202a861a3a43a50c:1'})
        else:
            return {'success': False, 'message': 'Insufficient cash for machinery construction'}

        # Pay cash fee of 25.0 conserved to artisans/smelters or gov
        artisans = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                    and not getattr(a, 'is_corporation', False) and getattr(a, 'output', None) in (Goods.iron, Goods.coal, Goods.wood)]
        if artisans:
            split = 25.0 / len(artisans)
            for art in artisans:
                _trace_cash_write = _trace_public_begin(None, art)
                art.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:ce8ce99a0208fd87:1'})
        elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
            _trace_cash_write = _trace_public_begin(None, region.gov.agent)
            region.gov.agent.cash += 25.0
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:8fbba1a28d9cea0d:1'})
        else:
            if agent != target:
                _trace_cash_write = _trace_public_begin(None, agent)
                agent.cash += 25.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:608f2df2b0c7ac53:1'})
            else:
                _trace_cash_write = _trace_public_begin(None, target)
                target.cash += 25.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:169bf6283107c41d:1'})

        # Pay remaining market materials purchases to sellers
        materials_cost = cash_needed - 25.0
        if materials_cost > 0:
            sellers = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                       and (a.inv_get(Goods.iron, 0) > 0 or a.inv_get(Goods.coal, 0) > 0)]
            if sellers:
                m_split = materials_cost / len(sellers)
                for s in sellers:
                    _trace_cash_write = _trace_public_begin(None, s)
                    s.cash += m_split
                    _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                         inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:6f79f8dbb4f23bad:1'})
            elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                _trace_cash_write = _trace_public_begin(None, region.gov.agent)
                region.gov.agent.cash += materials_cost
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:5e0b094167969c0d:1'})
            else:
                if agent != target:
                    _trace_cash_write = _trace_public_begin(None, agent)
                    agent.cash += materials_cost
                    _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                         inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:883ef19c079a47c3:1'})
                else:
                    _trace_cash_write = _trace_public_begin(None, target)
                    target.cash += materials_cost
                    _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_construct_machinery',
                                         inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_construct_machinery:e14ca5c5bfc4118d:1'})

        # Deduct physical held goods
        if iron_held > 0:
            deduct_iron = min(iron_held, 2)
            if target.inv_get(Goods.iron, 0) >= deduct_iron:
                target.inv_add(Goods.iron, -deduct_iron)
            else:
                rem_iron = deduct_iron - target.inv_get(Goods.iron, 0)
                target.inv_add(Goods.iron, -target.inv_get(Goods.iron, 0))
                agent.inv_add(Goods.iron, -rem_iron)

        if coal_held > 0:
            deduct_coal = min(coal_held, 1)
            if target.inv_get(Goods.coal, 0) >= deduct_coal:
                target.inv_add(Goods.coal, -deduct_coal)
            else:
                agent.inv_add(Goods.coal, -deduct_coal)

        target.machinery_level = getattr(target, 'machinery_level', 1) + 1
        target.max_employees = min(100, getattr(target, 'max_employees', 10) + 5)
        return {
            'success': True,
            'target_firm_id': target.id,
            'new_machinery_level': target.machinery_level,
            'max_employees': target.max_employees
        }

    def _estimate_construct_machinery_return(agent, region, shadow_cash):
        return 35.0 * shadow_cash

    TransformationGraph.register_operator(TransformationOperator(
        id='construct_machinery',
        name='Construct Industrial Machinery (Dept I)',
        category='capital_goods',
        input_goods={Goods.iron: 2.0, Goods.coal: 1.0},
        output_goods={},
        cash_cost=25.0,
        description='Constructs mechanical machinery using bar iron and coal fuel, expanding factory capacity and workforce.',
        check_prerequisites=_check_construct_machinery_prereqs,
        on_execute=_execute_construct_machinery,
        estimate_return_hook=_estimate_construct_machinery_return,
    ))

    def _check_maintain_repair_prereqs(agent, region):
        is_corp = getattr(agent, 'is_corporation', False)
        company = getattr(agent, 'company_owned', None)
        target = agent if is_corp else company
        if target is None:
            firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False) and getattr(a, 'broken_machinery', 0) > 0]
            if firms and getattr(agent, 'cash', 0.0) >= 20.0:
                target = firms[0]
        if target is None:
            return False
        return getattr(target, 'broken_machinery', 0) > 0

    def _execute_maintain_repair_machinery(agent, region, t):
        is_corp = getattr(agent, 'is_corporation', False)
        company = getattr(agent, 'company_owned', None)
        target = agent if is_corp else company
        if target is None:
            firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False) and getattr(a, 'broken_machinery', 0) > 0]
            if firms:
                target = firms[0]
        if target is None or getattr(target, 'broken_machinery', 0) <= 0:
            return {'success': False, 'message': 'No broken machinery to repair'}

        iron_price = region.recipes.get(Goods.iron, {}).get('price', 5.0) if hasattr(region, 'recipes') else 5.0
        iron_held = target.inv_get(Goods.iron, 0) + (agent.inv_get(Goods.iron, 0) if agent != target else 0)
        cash_needed = 10.0
        if iron_held < 1:
            cash_needed += iron_price

        if target.cash >= cash_needed:
            _trace_cash_write = _trace_public_begin(None, target)
            target.cash -= cash_needed
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:feec452fe80bfcc5:1'})
        elif (target.cash + agent.cash) >= cash_needed:
            rem = cash_needed - target.cash
            _trace_cash_write = _trace_public_begin(None, target)
            target.cash = 0.0
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:995753c55e94594f:1'})
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash -= rem
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:202a861a3a43a50c:1'})
        else:
            return {'success': False, 'message': 'Insufficient funds to repair machinery'}

        blacksmiths = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                       and not getattr(a, 'is_corporation', False) and getattr(a, 'output', None) == Goods.iron]
        if blacksmiths:
            split = 10.0 / len(blacksmiths)
            for b in blacksmiths:
                _trace_cash_write = _trace_public_begin(None, b)
                b.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:34f52c260835fe73:1'})
        elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
            _trace_cash_write = _trace_public_begin(None, region.gov.agent)
            region.gov.agent.cash += 10.0
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:5e20c95dd86c504c:1'})
        else:
            if agent != target:
                _trace_cash_write = _trace_public_begin(None, agent)
                agent.cash += 10.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:b034cbabe92a07d2:1'})
            else:
                _trace_cash_write = _trace_public_begin(None, target)
                target.cash += 10.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_maintain_repair_machinery',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_maintain_repair_machinery:4051ab2fb8c668f3:1'})

        if iron_held >= 1:
            if target.inv_get(Goods.iron, 0) >= 1:
                target.inv_add(Goods.iron, -1)
            else:
                agent.inv_add(Goods.iron, -1)

        target.broken_machinery = max(0, getattr(target, 'broken_machinery', 0) - 1)
        if target.broken_machinery == 0:
            target.machinery_broken = False
            target.machinery_wear = 0
        target.machinery_level = getattr(target, 'machinery_level', 0) + 1
        return {
            'success': True,
            'target_firm_id': target.id,
            'broken_machinery': target.broken_machinery,
            'machinery_level': target.machinery_level
        }

    def _estimate_maintain_repair_return(agent, region, shadow_cash):
        return 40.0 * shadow_cash

    TransformationGraph.register_operator(TransformationOperator(
        id='maintain_repair_machinery',
        name='Overhaul & Repair Damaged Machinery',
        category='capital_goods',
        input_goods={Goods.iron: 1.0},
        output_goods={},
        cash_cost=10.0,
        description='Consumes iron replacement parts and artisan labor to restore broken machinery to active service.',
        check_prerequisites=_check_maintain_repair_prereqs,
        on_execute=_execute_maintain_repair_machinery,
        estimate_return_hook=_estimate_maintain_repair_return,
    ))

    # M. War Capitalism: Chartered Frontier Conquest & Dispossession (Issue-07)
    def _check_frontier_conquest_prereqs(agent, region):
        is_elite = getattr(agent, 'is_lord', False) or getattr(agent, 'cash', 0.0) >= 80.0 or getattr(agent, 'is_trader', False)
        if not is_elite or getattr(agent, 'cash', 0.0) < 50.0:
            return False
        neighbors = getattr(region, 'neighbors', {})
        has_frontier_neighbor = any(getattr(n, 'wilderness', False) or getattr(n, 'wilderness_pop', 0) > 0 for n in neighbors.values())
        has_internal_frontier = getattr(region, 'wilderness', False) or (getattr(region, 'wilderness_pop', 0) > 0)
        has_uncolonized_plots = hasattr(region, 'tenure') and len(getattr(region.tenure, 'plots', [])) < 8
        return has_frontier_neighbor or has_internal_frontier or has_uncolonized_plots

    def _execute_frontier_conquest(agent, region, t):
        expedition_cost = 50.0
        if agent.cash < expedition_cost:
            return {'success': False, 'message': 'Insufficient funds for expedition'}
        _trace_cash_write = _trace_public_begin(None, agent)
        agent.cash -= expedition_cost
        _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_frontier_conquest',
                             inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_frontier_conquest:351e618bf7c04071:1'})

        commoners = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                     and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)
                     and not getattr(a, 'is_government', False) and not getattr(a, 'is_trader', False)]
        soldier_wages = 35.0
        charter_fee = 15.0
        if commoners:
            split = soldier_wages / len(commoners)
            for c in commoners:
                _trace_cash_write = _trace_public_begin(None, c)
                c.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_frontier_conquest',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_frontier_conquest:8c727869bf20e137:1'})
        else:
            charter_fee += soldier_wages

        gov = getattr(region, 'gov', None)
        if gov and gov.agent:
            _trace_cash_write = _trace_public_begin(None, gov.agent)
            gov.agent.cash += charter_fee
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_frontier_conquest',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_frontier_conquest:d0ea08b2b95c65c9:1'})
        else:
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash += charter_fee
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_frontier_conquest',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_frontier_conquest:fc0e0f3153c18ef0:1'})

        neighbors = getattr(region, 'neighbors', {})
        target_region = None
        for n in neighbors.values():
            if getattr(n, 'wilderness', False) or getattr(n, 'wilderness_pop', 0) > 0:
                target_region = n
                break
        if target_region is None:
            target_region = region

        old_wild_pop = getattr(target_region, 'wilderness_pop', 0)
        displaced = min(old_wild_pop, 15)
        target_region.wilderness_pop = max(0, old_wild_pop - displaced)

        clim = getattr(target_region, 'climate', 'temperate')
        if clim in ('tropical', 'subtropical', 'mediterranean'):
            primary_commodity = Goods.cotton
        elif getattr(target_region, 'biome', 'plains') in ('mountains', 'hills'):
            primary_commodity = Goods.iron_ore
        else:
            primary_commodity = Goods.tobacco if Goods.tobacco in Goods else Goods.cotton

        yield_qty = 10
        agent.inv_add(primary_commodity, yield_qty)
        TransformationGraph.register_pending_capacity(region, primary_commodity, float(yield_qty))

        if not hasattr(agent, 'frontier_estates'):
            agent.frontier_estates = []
        estate_info = {
            'target_region': target_region.name,
            'primary_commodity': primary_commodity.name,
            'turn_acquired': t,
            'displaced_population': displaced,
            'captive_labor': 0,
        }
        agent.frontier_estates.append(estate_info)

        return {
            'success': True,
            'target_region': target_region.name,
            'commodity': primary_commodity.name,
            'yield_received': yield_qty,
            'displaced_pop': displaced,
            'mercenary_pay_distributed': soldier_wages,
            'charter_fee_paid': charter_fee,
        }

    def _estimate_frontier_conquest_return(agent, region, shadow_cash):
        p = TransformationGraph.compute_expected_price(region, Goods.cotton)
        return (p * 10.0 * shadow_cash) - (50.0 * shadow_cash) + 20.0

    TransformationGraph.register_operator(TransformationOperator(
        id='chartered_frontier_conquest',
        name='Chartered Frontier Conquest & Armed Expropriation (War Capitalism)',
        category='war_capitalism',
        input_goods={},
        output_goods={},
        cash_cost=50.0,
        description='Dispatches armed mercenaries backed by Crown charter to expropriate frontier land and establish primary commodity enclaves.',
        check_prerequisites=_check_frontier_conquest_prereqs,
        on_execute=_execute_frontier_conquest,
        estimate_return_hook=_estimate_frontier_conquest_return,
    ))

    # N. War Capitalism: Procure Captive Labor (Issue-08)
    def _check_procure_captive_labor_prereqs(agent, region):
        is_elite = getattr(agent, 'is_lord', False) or getattr(agent, 'cash', 0.0) >= 25.0 or getattr(agent, 'is_trader', False)
        if not is_elite:
            return False
        estates = getattr(agent, 'frontier_estates', [])
        if not estates:
            return False
        has_rum = agent.inv_get(Goods.rum, 0) >= 1
        has_cloth = agent.inv_get(Goods.cloth, 0) >= 2
        has_cash = agent.cash >= 25.0
        return has_rum or has_cloth or has_cash

    def _execute_procure_captive_labor(agent, region, t):
        estates = getattr(agent, 'frontier_estates', [])
        if not estates:
            return {'success': False, 'message': 'No frontier estates owned'}

        target_estate = min(estates, key=lambda e: e.get('captive_labor', 0))

        cost_type = 'cash'
        if agent.inv_get(Goods.rum, 0) >= 1:
            agent.inv_add(Goods.rum, -1)
            cost_type = 'rum'
        elif agent.inv_get(Goods.cloth, 0) >= 2:
            agent.inv_add(Goods.cloth, -2)
            cost_type = 'cloth'
        elif agent.cash >= 25.0:
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash -= 25.0
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_procure_captive_labor',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_procure_captive_labor:5106d4c8e23190a8:1'})
            commoners = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                         and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)
                         and not getattr(a, 'is_government', False) and not getattr(a, 'is_trader', False)]
            if commoners:
                split = 25.0 / len(commoners)
                for c in commoners:
                    _trace_cash_write = _trace_public_begin(None, c)
                    c.cash += split
                    _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_procure_captive_labor',
                                         inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_procure_captive_labor:f6f33edd3b564762:1'})
            elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                _trace_cash_write = _trace_public_begin(None, region.gov.agent)
                region.gov.agent.cash += 25.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_procure_captive_labor',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_procure_captive_labor:b21e4e05678a18a2:1'})
            else:
                _trace_cash_write = _trace_public_begin(None, agent)
                agent.cash += 25.0
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_procure_captive_labor',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_procure_captive_labor:81ca6b20397c8b75:1'})
            cost_type = 'cash'
        else:
            return {'success': False, 'message': 'Insufficient goods or cash to procure captive labor'}

        labor_increment = 5
        target_estate['captive_labor'] = target_estate.get('captive_labor', 0) + labor_increment

        return {
            'success': True,
            'target_region': target_estate.get('target_region'),
            'commodity': target_estate.get('primary_commodity'),
            'captive_labor_added': labor_increment,
            'captive_labor_total': target_estate['captive_labor'],
            'cost_type': cost_type,
        }

    def _estimate_procure_captive_labor_return(agent, region, shadow_cash):
        estates = getattr(agent, 'frontier_estates', [])
        if not estates:
            return 0.0
        target_estate = min(estates, key=lambda e: e.get('captive_labor', 0))
        comm_name = target_estate.get('primary_commodity', 'cotton')
        comm_good = getattr(Goods, comm_name, Goods.cotton)
        p = TransformationGraph.compute_expected_price(region, comm_good)
        return (p * 15.0 * 2.0 * shadow_cash) - (25.0 * shadow_cash)

    TransformationGraph.register_operator(TransformationOperator(
        id='procure_captive_labor',
        name='Procure Captive Plantation Labor (War Capitalism / Human Commodification)',
        category='war_capitalism',
        input_goods={},
        output_goods={},
        cash_cost=25.0,
        description='Acquires unfree captive laborers for frontier plantations via transatlantic trade in rum, textiles, or merchant coin.',
        check_prerequisites=_check_procure_captive_labor_prereqs,
        on_execute=_execute_procure_captive_labor,
        estimate_return_hook=_estimate_procure_captive_labor_return,
    ))

    # O. War Capitalism: Mandate Plantation Labor Gang (Issue-08)
    def _check_plantation_labor_gang_prereqs(agent, region):
        estates = getattr(agent, 'frontier_estates', [])
        if not estates:
            return False
        has_viable_gang = any(e.get('captive_labor', 0) >= 3 for e in estates)
        return has_viable_gang and getattr(agent, 'cash', 0.0) >= 10.0

    def _execute_plantation_labor_gang(agent, region, t):
        estates = getattr(agent, 'frontier_estates', [])
        viable_estates = [e for e in estates if e.get('captive_labor', 0) >= 3]
        if not viable_estates:
            return {'success': False, 'message': 'No frontier estate with sufficient captive labor (min 3)'}
        if agent.cash < 10.0:
            return {'success': False, 'message': 'Insufficient cash to pay armed overseers'}

        target_estate = viable_estates[0]

        overseer_cost = 10.0
        _trace_cash_write = _trace_public_begin(None, agent)
        agent.cash -= overseer_cost
        _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_plantation_labor_gang',
                             inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_plantation_labor_gang:662ed76fa419fa2a:1'})
        commoners = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True)
                     and not getattr(a, 'is_lord', False) and not getattr(a, 'is_corporation', False)
                     and not getattr(a, 'is_government', False) and not getattr(a, 'is_trader', False)]
        if commoners:
            split = overseer_cost / len(commoners)
            for c in commoners:
                _trace_cash_write = _trace_public_begin(None, c)
                c.cash += split
                _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_plantation_labor_gang',
                                     inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_plantation_labor_gang:8c727869bf20e137:1'})
        elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
            _trace_cash_write = _trace_public_begin(None, region.gov.agent)
            region.gov.agent.cash += overseer_cost
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_plantation_labor_gang',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_plantation_labor_gang:30f6cedbe6ea56c5:1'})
        else:
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash += overseer_cost
            _trace_public_finish(_trace_cash_write, 'economy/transformation_graph:initialize_default_transformation_ontology._execute_plantation_labor_gang',
                                 inputs={"source_writer": 'economy/transformation_graph.py:initialize_default_transformation_ontology._execute_plantation_labor_gang:4c69c6cb6d6cc5d7:1'})

        comm_name = target_estate.get('primary_commodity', 'cotton')
        comm_good = getattr(Goods, comm_name, Goods.cotton)
        yield_qty = 15

        agent.inv_add(comm_good, yield_qty)
        TransformationGraph.register_pending_capacity(region, comm_good, float(yield_qty))

        target_estate['captive_labor'] = max(0, target_estate.get('captive_labor', 0) - 1)

        return {
            'success': True,
            'target_region': target_estate.get('target_region'),
            'commodity': comm_good.name,
            'yield_received': yield_qty,
            'captive_labor_remaining': target_estate['captive_labor'],
            'overseer_wages_paid': overseer_cost,
            'wage_cost_to_laborers': 0.0,
            'attrition_loss': 1,
        }

    def _estimate_plantation_gang_return(agent, region, shadow_cash):
        estates = getattr(agent, 'frontier_estates', [])
        viable_estates = [e for e in estates if e.get('captive_labor', 0) >= 3]
        if not viable_estates:
            return 0.0
        target_estate = viable_estates[0]
        comm_name = target_estate.get('primary_commodity', 'cotton')
        comm_good = getattr(Goods, comm_name, Goods.cotton)
        base_p = float(region.recipes.get(comm_good, {}).get('price', 4.0)) if hasattr(region, 'recipes') else 4.0
        p = max(TransformationGraph.compute_expected_price(region, comm_good), base_p * 0.5)
        return (p * 15.0 * shadow_cash) - (10.0 * shadow_cash)

    TransformationGraph.register_operator(TransformationOperator(
        id='mandate_plantation_labor_gang',
        name='Mandate Coerced Plantation Gang Labor (Zero-Wage Primary Extraction)',
        category='war_capitalism',
        input_goods={},
        output_goods={},
        cash_cost=10.0,
        description='Forces unfree captive gangs into intensive primary commodity extraction with zero wages, armed overseer supervision, and mortal attrition.',
        check_prerequisites=_check_plantation_labor_gang_prereqs,
        on_execute=_execute_plantation_labor_gang,
        estimate_return_hook=_estimate_plantation_gang_return,
    ))

    # K. Market Sale Operator (Universal Asset-to-Money Liquidation)
    for g in Goods:
        if g not in (Goods.none, Goods.gov):
            TransformationGraph.register_operator(TransformationOperator(
                id=f'market_sell_{g.name}',
                name=f'Sell {g.name.capitalize()} on Market',
                category='market',
                input_goods={g: 1.0},
                output_goods={}, # Produces cash
                description=f'Liquidates {g.name} into universal monetary currency on the open market.',
            ))


# Auto-seed ontology on module import
initialize_default_transformation_ontology()


def apply_machinery_depreciation(region: Any, t: int) -> int:
    """Applies operational wear-and-tear depreciation to active machinery.
    
    When operational machinery breaks down, firm productivity drops until
    repaired using industrial iron via maintain_repair_machinery.
    """
    broken_count = 0
    firms = [a for a in getattr(region, 'agents', []) if getattr(a, 'is_corporation', False)]
    for firm in firms:
        curr_mach = getattr(firm, 'machinery_level', 1)
        if curr_mach > 0:
            shift = getattr(firm, 'shift_hours', 8.0)
            depreciation_interval = 8 if shift >= 12.0 else 12
            if t > 0 and t % depreciation_interval == 0:
                firm.machinery_level = max(0, curr_mach - 1)
                firm.broken_machinery = getattr(firm, 'broken_machinery', 0) + 1
                broken_count += 1
    return broken_count
