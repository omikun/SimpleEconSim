"""
sim_server/sim_server.py — Authoritative Simulation Server implementation.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

import time
import math
from trace_clock import trace_command_boundary
import random
import threading
import uuid
from typing import Any, Dict, List, Optional

from sim_world import build_world, GRID_ROWS, GRID_COLS
from hexmap import rectangular_hex_layout, hex_bbox
from client.desktop.camera import HEX_SIZE
import forex as fx
from goods import Goods
from buildings import BUILDING_RECIPES
from diplomacy import get_diplomacy, TreatyType
from sovereign_bonds import get_bond_market
from innovation import get_innovation_system, TECH_CATALOG, COMPLEXITY_STEAL_CAPS
from client.desktop.map.map_renderer import NATION_COLORS, get_nation_color
from world_names import assign_world_identities
from sim_server.protocol import CommandType, CommandMessage, ServerEvent
from collective_action import organization_summary, recent_collective_events
from collective_politics import political_summary
from metric_catalog import grievance_breakdown, protest_band
from run_trace import RunTrace
from pathlib import Path
from world_config import (FULL_GAMEPLAY_FLAGS, GAMEPLAY_FLAGS_VERSION,
                          GameplayFlags, ElitePlanningConfig, resolve_gameplay_flags,
                          validate_gameplay_profile)


# Web chart keys fed by Nation trade, Citizen, and Labor reducers also written
# into the causal trace. Scales mirror the tile chart serialization.
_NATION_CHART_HISTORY_KEYS = {
    ('trade', 'net'): ('trade', 1.0),
    ('trade', 'exports'): ('trade_exports', 1.0),
    ('trade', 'imports'): ('trade_imports', 1.0),
    ('government', 'income'): ('government_income', 1.0),
    ('ecology', 'soil'): ('soil', 100.0),
    ('ecology', 'nutrition'): ('nutrition', 100.0),
    ('ecology', 'smog'): ('smog', 1.0),
    ('ecology', 'effluent'): ('effluent', 1.0),
    ('ecology', 'soil toxicity'): ('soil_pollution', 1.0),
    ('health', 'malnutrition cases'): ('malnutrition_cases', 1.0),
    ('health', 'waterborne cases'): ('waterborne_cases', 1.0),
    ('health', 'respiratory cases'): ('respiratory_cases', 1.0),
    ('health', 'chemical cases'): ('chemical_cases', 1.0),
    ('health', 'outlays'): ('health_outlays', 1.0),
    ('health', 'untreated'): ('untreated_cases', 1.0),
    ('health', 'fatalities'): ('illness_deaths', 1.0),
    ('citizen', 'serf'): ('class_serf', 1.0),
    ('citizen', 'tenant'): ('class_tenant', 1.0),
    ('citizen', 'worker'): ('class_worker', 1.0),
    ('citizen', 'disposs'): ('class_dispossessed', 1.0),
    ('citizen', 'gentry'): ('class_gentry', 1.0),
    ('citizen', 'artisan'): ('class_artisan', 1.0),
    ('citizen', 'foraged'): ('food_foraged', 1.0),
    ('citizen', 'market food'): ('food_purchased', 1.0),
    ('citizen', 'hungry'): ('hungry', 1.0),
    ('citizen', 'avg commons %'): ('commons_access', 100.0),
    ('citizen', 'rent ($)'): ('rent_collected', 1.0),
    ('citizen', 'arrears ($)'): ('rent_arrears', 1.0),
    ('citizen', 'avg gini (x100)'): ('gini', 100.0),
    ('labor', 'avg shift hrs'): ('shift_hours', 1.0),
    ('labor', 'avg effective cap'): ('workday_cap', 1.0),
    ('labor', 'avg s/v rate (%)'): ('exploitation', 100.0),
    ('labor', 'alienation (x100)'): ('alienation', 100.0),
    ('labor', 'bodily wear (x100)'): ('bodily_wear', 100.0),
    ('labor', 'accidents'): ('workplace_accidents', 1.0),
    ('labor', 'consciousness (x100)'): ('consciousness', 100.0),
    ('labor', 'entertainment (x100)'): ('entertainment', 100.0),
    ('labor', 'strikers'): ('strikes', 1.0),
    ('labor', 'broken stock'): ('broken_machinery', 1.0),
    ('labor', 'sabotaged this turn'): ('machinery_sabotaged', 1.0),
}


class SimServer:
    """Authoritative headless simulation server for Call of Capital."""

    def __init__(self, seed: Optional[int] = None, terrain_seed: Optional[int] = None,
                 nation_seed: Optional[int] = None,
                 topology: Optional[str] = None, scenario_id: Optional[str] = None,
                 autoplay_nations: bool = False, trace_enabled: bool = True,
                 gameplay_flags: GameplayFlags | None = None,
                 gameplay_profile: str | None = None,
                 elite_planning_config: ElitePlanningConfig | None = None):
        if gameplay_flags is None:
            self.gameplay_flags = resolve_gameplay_flags(
                profile='full', scenario_id=scenario_id)
        else:
            self.gameplay_flags = gameplay_flags
        if not isinstance(self.gameplay_flags, GameplayFlags):
            raise TypeError('gameplay_flags must be a GameplayFlags value')
        if gameplay_profile is None:
            self.gameplay_profile = 'full' if gameplay_flags is None else 'custom'
        else:
            self.gameplay_profile = validate_gameplay_profile(gameplay_profile)
        self.elite_planning_config = ElitePlanningConfig() if elite_planning_config is None else elite_planning_config
        if not isinstance(self.elite_planning_config, ElitePlanningConfig):
            raise TypeError('elite_planning_config must be an ElitePlanningConfig')
        self.trace_enabled = bool(trace_enabled)
        self.scenario_id = scenario_id
        self.autoplay_nations = bool(autoplay_nations)
        if scenario_id in ('labor_frontier_rivalry', 'supply_rivalry'):
            topology = 'hex'
        if topology in ('voronoi', 'hex'):
            from world_config import set_map_topology
            set_map_topology(topology)
        from world_config import is_voronoi_topology, load_mapgen_slot_one
        self.topology = "voronoi" if is_voronoi_topology() else "hex"
        slot_default = self.topology == "voronoi" and seed is None and terrain_seed is None
        slot_state = load_mapgen_slot_one() if slot_default else {}
        self.seed = int(slot_state.get('seed', 777)) if slot_default else seed
        self.terrain_seed = terrain_seed if terrain_seed is not None else (
            self.seed if self.seed is not None else 4242
        )
        self.nation_seed = nation_seed if nation_seed is not None else (
            int(slot_state.get('nation_seed', 777)) if slot_default else random.randint(1, 999999)
        )

        self.turn = 0
        self.playing = False
        self.turn_interval_sec = 0.150  # 150 ms per turn
        self.last_tick_time = time.time()

        self._lock = threading.RLock()
        self.instance_id = uuid.uuid4().hex
        self._ticker_events: List[Dict[str, Any]] = []
        self._subscribers = []
        self.player_nation_name = None
        self._nation_history = {}

        self.init_world()

    def __getstate__(self):
        state = dict(self.__dict__)
        state.pop('_lock', None)
        state.pop('_subscribers', None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if not hasattr(self, 'gameplay_profile'):
            self.gameplay_profile = ('full' if self.gameplay_flags == FULL_GAMEPLAY_FLAGS
                                     else 'custom')
        self.elite_planning_config = getattr(self, 'elite_planning_config', ElitePlanningConfig())
        for tile in self.tiles:
            tile._elite_planning_config = self.elite_planning_config
        self._lock = threading.RLock()
        self._subscribers = []
        self.playing = False
        self.last_tick_time = time.time()

    def save_checkpoint(self, directory):
        from simulation_checkpoint import save
        return save(self, directory)

    @classmethod
    def restore_checkpoint(cls, manifest_path, branch_directory):
        from simulation_checkpoint import restore
        return restore(manifest_path, branch_directory)

    def init_world(self):
        """Build and initialize authoritative world state."""
        with self._lock:
            from world_config import is_voronoi_topology, VORONOI_WIDTH, VORONOI_HEIGHT
            self.topology = "voronoi" if is_voronoi_topology() else "hex"
            scenario_world = None
            if self.scenario_id == 'labor_frontier_rivalry':
                from scenario_labor_frontier_rivalry import create_world
                scenario_world = create_world(seed=612 if self.seed is None else self.seed)
                tiles, nations, _grid = scenario_world['tiles'], scenario_world['nations'], None
                self.topology = 'hex'
            elif self.scenario_id == 'supply_rivalry':
                from scenario_supply_rivalry import create_world
                scenario_world = create_world(seed=812 if self.seed is None else self.seed)
                tiles, nations, _grid = scenario_world['tiles'], scenario_world['nations'], None
                self.topology = 'hex'
            else:
                tiles, nations, _grid = build_world(
                    seed=self.seed, terrain_seed=self.terrain_seed,
                    nation_seed=self.nation_seed)
                assign_world_identities(tiles, nations, seed=self.nation_seed)

            self.tiles = tiles
            self.nations = nations
            for participant in (*tiles, *nations):
                participant._gameplay_flags = self.gameplay_flags
                participant._elite_planning_config = self.elite_planning_config
            self.currencies = [n.currency for n in nations if getattr(n, 'currency', None)]
            self.hex_size = HEX_SIZE

            if scenario_world is not None:
                self.layout = scenario_world['layout']
                self.reverse_layout = {v: k for k, v in self.layout.items()}
                self.bbox = hex_bbox(self.layout, HEX_SIZE)
                self.gen = None
                self.scenario_state = scenario_world['scenario_state']
            elif self.topology == "voronoi":
                self.layout = {t.name: getattr(t, 'centroid', (0.0, 0.0)) for t in tiles}
                self.reverse_layout = {}
                self.bbox = (0.0, 0.0, VORONOI_WIDTH, VORONOI_HEIGHT)
                self.gen = _grid
            else:
                grid_layout = rectangular_hex_layout(GRID_ROWS, GRID_COLS)
                grid_positions = list(grid_layout.values())
                # Generated regions are named c0..cN; the layout helper uses rNcN keys.
                self.layout = {tile.name: grid_positions[i] for i, tile in enumerate(tiles)}
                self.reverse_layout = {v: k for k, v in self.layout.items()}
                self.bbox = hex_bbox(self.layout, HEX_SIZE)
                self.gen = None

            self.by_name = {r.name: r for r in tiles}
            self.pair_orders = [(r, o) for r in tiles for o in tiles if o is not r
                                and r.neighbors.get(o.name) is not None
                                and not getattr(o, 'wilderness', False)
                                and not getattr(r, 'wilderness', False)]

            self.currency_totals = {c: fx.audit_currency_total(tiles, c) for c in self.currencies}
            self.violations = []
            self.turn = 0
            self.world_generation = getattr(self, 'world_generation', 0) + 1
            self.state_revision = 0
            self.playing = False
            self._ticker_events.clear()
            self.player_nation_name = self.nations[0].name if self.nations else None
            self._configure_nation_ai()
            self._nation_history = {}
            for n in self.nations:
                self._nation_history[n.name] = {
                    'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
                }
            self._record_history(0)
            if not self.trace_enabled:
                self.run_trace = None
                return
            run_id = f'{self.instance_id}-{self.world_generation}'
            trace_path = Path(__file__).resolve().parents[1] / 'tmp' / 'traces' / f'{run_id}.ctr'
            self.run_trace = RunTrace(trace_path, run_id, seed=self.seed,
                                      scenario=self.scenario_id)
            setup_clock = {'turn': 0, 'phase': 'setup', 'next': 1}
            for tile in self.tiles:
                tile._run_trace = self.run_trace
                tile._collective_trace_clock = setup_clock
            for nation in self.nations:
                nation._run_trace = self.run_trace
                nation._collective_trace_clock = setup_clock
            self.run_trace.bank_book.register_tiles(self.tiles, setup_clock)
            self.run_trace.treasury_book.register_nations(self.nations, setup_clock)
            self.run_trace.wilderness.register(self.tiles,self.nations)
            for tile in self.tiles:
                fx.flush_pending_trader_float_traces(tile)
            self.run_trace.wilderness.record(self.tiles,setup_clock)
            from trace_snapshots import (entity_role_census, resident_census,
                                         sample)
            from labor_census_trace import capture_labor_censuses
            self._trace_previous_labor_censuses = capture_labor_censuses(self.tiles)
            self._trace_previous = sample(self.tiles, self.nations,
                                         labor_censuses=self._trace_previous_labor_censuses)
            self._trace_previous_people = resident_census(self.tiles)
            self._trace_previous_roles = entity_role_census(self.tiles)
            self._trace_previous_nation_membership = {
                nation.name: [tile.name for tile in nation.tiles]
                for nation in self.nations}
            self._trace_previous_tile_currencies = {
                tile.name: getattr(tile, 'home_currency', None) for tile in self.tiles}
            self._trace_previous_nation_currencies = {
                nation.name: getattr(nation, 'currency', None)
                for nation in self.nations}

    def _configure_nation_ai(self):
        """Run sovereign AI for rivals while leaving the selected nation to the player."""
        if self.scenario_id is not None:
            return
        from ai_nation import NationPolicyAI
        for nation in self.nations:
            should_control = (self.autoplay_nations
                              or nation.name != self.player_nation_name)
            if should_control and nation.ai is None:
                nation.ai = NationPolicyAI(nation)
            elif not should_control and isinstance(nation.ai, NationPolicyAI):
                nation.ai = None

    def step(self) -> int:
        """Advance the simulation by exactly one turn."""
        from sim_server.turn_pipeline import advance
        return advance(self)

    def _record_history(self, t: int):
        """Record macro time series for charting."""
        from trace_snapshots import nation_chart_aggregation_rows
        for n in self.nations:
            hist = self._nation_history.setdefault(n.name, {
                'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
            })
            tr = n.treasury()
            tiles = getattr(n, 'tiles', [])
            gdp = sum(r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0 for r in tiles)
            pop = sum(r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents) for r in tiles)
            avg_food = (sum(r.recipes[Goods.food]['price'] for r in tiles if Goods.food in getattr(r, 'recipes', {})) / max(1, len(tiles))) if tiles else 1.0
            unrest = (sum(r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0 for r in tiles) / max(1, len(tiles))) if tiles else 0.0

            hist['turns'].append(t)
            hist['treasury'].append(round(float(tr['total']), 1))
            hist['gdp'].append(round(float(gdp), 1))
            hist['pop'].append(int(pop))
            hist['food_price'].append(round(float(avg_food), 2))
            hist['unrest'].append(round(float(unrest), 2))

            aggregates = nation_chart_aggregation_rows(n, turn=t)
            market_history_values = {}
            environment_history_values = {}
            for aggregate in aggregates:
                family = aggregate['inputs']['chart_family']
                chart_series = aggregate['inputs']['chart_series']
                if family in ('market_production', 'market_inventory',
                              'market_demand_ratio'):
                    market_history_values[(family, chart_series)] = aggregate['after']
                if family in ('ecology', 'health', 'government'):
                    environment_history_values[(family, chart_series)] = aggregate['after']
                    continue
                key = _NATION_CHART_HISTORY_KEYS.get((
                    family, chart_series))
                if key is None:
                    continue
                history_key, display_scale = key
                series = hist.setdefault(history_key, [])
                series.append(round(float(aggregate['after']) * display_scale, 1))

            # Dynamic good histories are turn-aligned. Missing local readings
            # stay gaps instead of borrowing an older production or market value.
            market_families = (
                ('market_production', 1),
                ('market_inventory', 1),
                ('market_demand_ratio', 2),
            )
            for good in Goods:
                if good in (Goods.gov, Goods.none):
                    continue
                good_name = good.name.lower()
                for family, digits in market_families:
                    history_key = f'{family}_{good_name}'
                    series = hist.setdefault(history_key, [])
                    while len(series) < len(hist['turns']) - 1:
                        series.append(None)
                    value = market_history_values.get((family, good_name))
                    series.append(round(float(value), digits)
                                  if value is not None else None)

            # Ecology, health, and government income use one point per Nation
            # turn. Missing readings remain gaps at their original turns.
            for (family, chart_series), (history_key, display_scale) in (
                    _NATION_CHART_HISTORY_KEYS.items()):
                if family not in ('ecology', 'health', 'government'):
                    continue
                series = hist.setdefault(history_key, [])
                while len(series) < len(hist['turns']) - 1:
                    series.append(None)
                value = environment_history_values.get((family, chart_series))
                series.append(round(float(value) * display_scale, 1)
                              if value is not None else None)

            # Keep Nation-wide reference-price histories on the same covered-
            # member mean used by goods.national_reference_price trace rows.
            prices_by_good = {}
            for tile in tiles:
                for good, recipe in getattr(tile, 'recipes', {}).items():
                    if (isinstance(good, Goods) and recipe is not None
                            and 'price' in recipe):
                        prices_by_good.setdefault(good, []).append(
                            float(recipe['price']))
            for good in Goods:
                if good in (Goods.gov, Goods.none):
                    continue
                history_key = f"market_price_{good.name.lower()}"
                prices = prices_by_good.get(good, ())
                series = hist.setdefault(
                    history_key, [None] * (len(hist['turns']) - 1))
                series.append(round(sum(prices) / len(prices), 2)
                              if prices else None)

            if len(hist['turns']) > 50:
                for k in hist:
                    del hist[k][:len(hist[k]) - 50]

    def _calc_nation_macro(self, n) -> Dict[str, Any]:
        """Calculate complete macroeconomic indicators for a sovereign nation."""
        tiles = getattr(n, 'tiles', [])
        tr = n.treasury()
        tr_cur = tr['total']
        tr_food = tr['food']
        from food_security import diagnose_tile
        food_tiles = [diagnose_tile(tile) for tile in tiles]
        food_residents = sum(row['residents'] for row in food_tiles)
        food_underfed = sum(row['underfed_residents'] for row in food_tiles)
        food_emergency_tiles = sum(bool(getattr(tile.gov, 'emergency_food_policy', False))
                                   for tile in tiles)
        food_enclosure_moratoria = sum(bool(getattr(tile, 'food_enclosure_moratorium', False))
                                       for tile in tiles)
        food_governments = list({id(tile.gov): tile.gov for tile in tiles}.values())
        food_aid_units = sum(int(getattr(gov, 'food_aid_last_turn', 0))
                             for gov in food_governments)
        food_levy_units = sum(int(getattr(gov, 'food_levy_last_turn', 0))
                              for gov in food_governments)

        pop_cur = sum(r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents) for r in tiles)
        pop_prev = sum(r.total_population[-2] if getattr(r, 'total_population', None) and len(r.total_population) >= 2 else (r.total_population[-1] if getattr(r, 'total_population', None) else len(r.agents)) for r in tiles)
        d_pop = pop_cur - pop_prev

        gdp_cur = sum(r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0 for r in tiles)
        gdp_prev = sum(r.gdp_log[-2] if getattr(r, 'gdp_log', None) and len(r.gdp_log) >= 2 else (r.gdp_log[-1] if getattr(r, 'gdp_log', None) else 0.0) for r in tiles)
        d_gdp = gdp_cur - gdp_prev
        gdp_pc = gdp_cur / max(1, pop_cur)

        unrest_cur = (sum(r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0 for r in tiles) / max(1, len(tiles))) if tiles else 0.0
        unrest_prev = (sum(r.protest_energy_log[-2] if getattr(r, 'protest_energy_log', None) and len(r.protest_energy_log) >= 2 else (r.protest_energy_log[-1] if getattr(r, 'protest_energy_log', None) else 0.0) for r in tiles) / max(1, len(tiles))) if tiles else 0.0
        d_unrest = unrest_cur - unrest_prev

        stage = protest_band(unrest_cur)

        avg_gini = 0.0
        for r in tiles:
            for g in (Goods.food, Goods.wood, Goods.furniture):
                vals = sorted(a.cash for a in getattr(r, 'agents', []) if getattr(a, 'output', None) == g)
                if len(vals) > 5:
                    n_v = len(vals)
                    s_v = sum(vals)
                    if s_v > 0:
                        wsum = sum((i + 1) * v for i, v in enumerate(vals))
                        avg_gini = max(avg_gini, (2 * wsum) / (n_v * s_v) - (n_v + 1) / n_v)

        col_cur = (sum(r.cost_of_living for r in tiles) / max(1, len(tiles))) if tiles else 1.0

        exports_cur = sum(sum(v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_cur = sum(sum(v[-1] for v in r.import_val.values() if v) for r in tiles)
        trade_net = exports_cur - imports_cur
        exports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.export_val.values() if v) for r in tiles)
        imports_prev = sum(sum(v[-2] if len(v) >= 2 else v[-1] for v in r.import_val.values() if v) for r in tiles)
        trade_prev = exports_prev - imports_prev
        d_trade = trade_net - trade_prev

        # Treasury delta
        hist_tr = self._nation_history.get(n.name, {}).get('treasury', [])
        d_tr = (tr_cur - hist_tr[-1]) if hist_tr else 0.0

        tot_debt = sum(getattr(r.gov, 'debt', 0.0) for r in tiles)
        tot_garrison = sum(int(getattr(r, 'garrison', 0)) for r in tiles)
        standing_armies = len(getattr(n, 'armies', []))

        # Sovereign upkeep calculation (military soldier wages + debt coupons)
        units = getattr(n, 'military_units', getattr(n, 'units', []))
        mil_upkeep = sum(getattr(u, 'soldiers', 0) * getattr(u, 'wage_per_soldier', 1.0) for u in units)
        mil_food_upkeep = sum(int(getattr(u, 'soldiers', 0) * getattr(u, 'food_per_soldier', 0.1)) for u in units)

        credit_rating = "BBB"
        market_yield = 0.0018
        coupons_owed = 0.0
        try:
            from sovereign_bonds import get_bond_market
            market = get_bond_market()
            credit_rating, market_yield = market.isrb.get_market_yield(n, 20, self.get_world_dict())
            coupons_owed = sum(b.per_turn_coupon for b in market.get_bonds_owed_by(n.name))
        except Exception:
            pass
        tot_upkeep = mil_upkeep + coupons_owed

        rgb = NATION_COLORS.get(n.name, (80, 160, 240))
        flag_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        return {
            'name': n.name,
            'currency': getattr(n, 'currency', 'USD'),
            'regime_type': getattr(n, 'regime_type', 'Monarchy'),
            'flag_color': flag_hex,
            'treasury_cash': round(float(tr_cur), 1),
            'treasury_delta': round(float(d_tr), 1),
            'treasury_food': int(tr_food),
            'food_security': {
                'residents': food_residents,
                'underfed': food_underfed,
                'underfed_share': round(food_underfed / max(1, food_residents), 4),
                'emergency_tiles': food_emergency_tiles,
                'enclosure_moratoria': food_enclosure_moratoria,
                'aid_units_last_turn': food_aid_units,
                'levy_units_last_turn': food_levy_units,
                'production_units': sum(row['production_units_last_turn'] for row in food_tiles),
                'foraged_units': sum(row['foraged_units_last_turn'] for row in food_tiles),
                'meal_need_units': sum(row['minimum_meal_units'] for row in food_tiles),
                'offered_units': sum(row['food_available_for_sale'] for row in food_tiles),
                'company_units': sum(row['company_food_units'] for row in food_tiles),
                'household_units': sum(row['household_food_units'] for row in food_tiles),
                'public_units': sum(max(0, gov.food_inventory) for gov in food_governments),
                'charity_units': sum(max(0, charity.food_inventory) for charity in
                                     {id(tile.charity): tile.charity for tile in tiles}.values()),
                'in_transit_units': sum(row['food_in_transit'] for row in food_tiles),
                'meal_cost_min': min((row['meal_reference_cost'] for row in food_tiles), default=0),
                'meal_cost_max': max((row['meal_reference_cost'] for row in food_tiles), default=0),
                'mean_employee_wage': (sum(float(a.employer.wage) for tile in tiles for a in tile.agents
                                          if a.alive and a.employer is not None)
                    / max(1, sum(1 for tile in tiles for a in tile.agents if a.alive and a.employer is not None))),
                'granary_units': sum(row['granary_food_units'] for row in food_tiles),
                'unaffordable_residents': sum(row['unaffordable_residents'] for row in food_tiles),
                'unmet_calorie_units': sum(row['unmet_calorie_units_last_turn'] for row in food_tiles),
                'access_reasons': list(dict.fromkeys(reason for row in food_tiles
                                                   for reason in row['access_reasons'])),
                'tiles': food_tiles,
            },
            'treasury_upkeep': round(float(tot_upkeep), 1),
            'military_upkeep': round(float(mil_upkeep), 1),
            'debt_upkeep': round(float(coupons_owed), 1),
            'food_upkeep': int(mil_food_upkeep),
            'population': int(pop_cur),
            'population_delta': int(d_pop),
            'gdp': round(float(gdp_cur), 1),
            'gdp_delta': round(float(d_gdp), 1),
            'gdp_per_capita': round(float(gdp_pc), 1),
            'unrest_energy': round(float(unrest_cur), 2),
            'unrest_stage': stage,
            'unrest_delta': round(float(d_unrest), 2),
            'gini': round(float(avg_gini), 2),
            'gini_delta': None,
            'cost_of_living': round(float(col_cur), 2),
            'exports': round(float(exports_cur), 1),
            'imports': round(float(imports_cur), 1),
            'trade_balance': round(float(trade_net), 1),
            'trade_delta': round(float(d_trade), 1),
            'tax_rate': float(getattr(n, 'tax_rate', 0.15)),
            'tariff_rate': float(getattr(n, 'tariff_rate', 0.10)),
            'max_workday_hours': float(getattr(n, 'max_workday_hours', 12.0)),
            'ten_hour_act': bool(getattr(n, 'ten_hour_act', False)),
            'credit_rating': str(credit_rating),
            'bond_yield': round(float(market_yield * 100), 2),
            'public_debt': round(float(tot_debt), 1),
            'garrison': int(tot_garrison),
            'standing_armies': int(standing_armies),
            'tiles_count': len(tiles),
        }

    def play(self):
        with self._lock:
            self.playing = True

    def pause(self):
        with self._lock:
            self.playing = False

    def toggle_play(self) -> bool:
        with self._lock:
            self.playing = not self.playing
            return self.playing

    def set_speed(self, interval_sec: float):
        with self._lock:
            self.turn_interval_sec = max(0.02, float(interval_sec))

    def push_ticker(self, turn: int, kind: str, text: str, color=(240, 240, 240), limit: int = 140):
        with self._lock:
            self._ticker_events.append({
                't': turn, 'kind': kind, 'text': text, 'color': color
            })
            if len(self._ticker_events) > limit:
                del self._ticker_events[:len(self._ticker_events) - limit]
            self._broadcast(ServerEvent.TICKER_MESSAGE, {
                't': turn, 'kind': kind, 'text': text, 'color': color
            })

    @trace_command_boundary
    def execute_command(self, cmd: CommandMessage) -> Dict[str, Any]:
        """Dispatch and execute an authoritative player / AI command."""
        with self._lock:
            # Commands can change state without advancing the turn.
            self.state_revision += 1
            c_type = cmd.cmd_type
            p = cmd.payload

            if self.scenario_id == 'supply_rivalry' and c_type == CommandType.SCENARIO_ACTION:
                if not self.gameplay_flags.scenario_progression:
                    return {'success': False, 'error': 'Scenario progression is disabled.'}
                from scenario_supply_rivalry import apply_action
                ok, message = apply_action(self.get_world_dict(), p.get('action_id'))
                self.push_ticker(self.turn, 'SUPPLY', message,
                                 (120, 240, 150) if ok else (240, 90, 90))
                return {'success': ok, 'message': message, 'turn': self.turn}

            if self.scenario_id == 'labor_frontier_rivalry':
                if c_type == CommandType.SCENARIO_ACTION:
                    if not self.gameplay_flags.scenario_progression:
                        return {'success': False, 'error': 'Scenario progression is disabled.'}
                    from labor_frontier_labor import apply_action
                    ok, message = apply_action(self.get_world_dict(), p.get('action_id'))
                    self.push_ticker(self.turn, 'DECISION', message,
                                     (120, 240, 150) if ok else (240, 90, 90))
                    return {'success': ok, 'message': message, 'turn': self.turn}
                allowed = {CommandType.STEP, CommandType.PLAY, CommandType.PAUSE,
                           CommandType.SET_SPEED, CommandType.RELOAD_WORLD,
                           CommandType.SELECT_REGION, CommandType.GET_STATE}
                if c_type not in allowed:
                    return {'success': False, 'error':
                            'Use this scenario’s decisions; one major action is available per turn.'}

            if c_type == CommandType.STEP:
                new_turn = self.step()
                return {'success': True, 'turn': new_turn}

            elif c_type == CommandType.PLAY:
                self.play()
                return {'success': True, 'playing': True}

            elif c_type == CommandType.PAUSE:
                self.pause()
                return {'success': True, 'playing': False}

            elif c_type == CommandType.SET_SPEED:
                self.set_speed(p.get('interval', 0.150))
                return {'success': True, 'interval': self.turn_interval_sec}

            elif c_type == CommandType.RELOAD_WORLD:
                self.seed = p.get('seed', self.seed)
                self.terrain_seed = p.get('terrain_seed', self.terrain_seed)
                self.nation_seed = p.get('nation_seed', self.nation_seed)
                self.init_world()
                return {'success': True, 'turn': 0}

            elif c_type == CommandType.SELECT_NATION:
                target_nation = p.get('nation')
                if any(n.name == target_nation for n in self.nations):
                    self.player_nation_name = target_nation
                    self._configure_nation_ai()
                    self.push_ticker(self.turn, 'SOVEREIGN', f"Assumed sovereign control of {target_nation}.", (140, 210, 255))
                    return {'success': True, 'nation': target_nation}
                return {'success': False, 'error': f"Nation '{target_nation}' not found."}

            elif c_type == CommandType.BUILD_PROJECT:
                if not self.gameplay_flags.construction_projects:
                    return {'success': False, 'error': 'Construction projects are disabled for this run.'}
                tile_name = p.get('tile')
                b_type = p.get('building')
                nat_name = p.get('nation') or self.player_nation_name
                tile = self.by_name.get(tile_name)
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not tile and nation and nation.tiles:
                    tile = nation.tiles[0]

                if not tile or not nation:
                    return {'success': False, 'error': "Invalid target territory or nation."}
                if b_type not in BUILDING_RECIPES:
                    return {'success': False, 'error': f"Unknown building recipe '{b_type}'."}

                from intents import BuildIntent
                intent = BuildIntent(nat_name, tile.name, b_type, submitted_turn=self.turn)
                nation.submit_intent(intent, self.turn)
                ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                self.push_ticker(self.turn, 'BUILD', msg, (120, 240, 150) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SET_POLICY:
                target_nation = next((n for n in self.nations if n.name == (p.get('nation') or self.player_nation_name)), None)
                if not target_nation:
                    return {'success': False, 'error': "Target nation not found"}
                key = p.get('key')
                val = p.get('val')

                if key in ('tax_rate', 'income_tax'):
                    val_f = float(val)
                    setattr(target_nation, 'tax_rate', val_f)
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} adjusted income tax to {val_f:.1%}.", (245, 210, 90))
                    return {'success': True, 'key': 'tax_rate', 'val': val_f, 'message': f"Income tax rate set to {val_f:.1%}"}

                elif key in ('tariff_rate', 'import_tariff'):
                    val_f = float(val)
                    setattr(target_nation, 'tariff_rate', val_f)
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} adjusted import tariffs to {val_f:.1%}.", (245, 210, 90))
                    return {'success': True, 'key': 'tariff_rate', 'val': val_f, 'message': f"Import tariff rate set to {val_f:.1%}"}

                elif key in ('workday', 'max_workday_hours'):
                    val_f = float(val)
                    target_nation.max_workday_hours = val_f
                    target_nation.ten_hour_act = (val_f <= 10.0)
                    for t in target_nation.tiles:
                        t.max_workday_hours = val_f
                        t.ten_hour_act = target_nation.ten_hour_act
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} regulated workday to {val_f:.1f} hours.", (140, 220, 160))
                    return {'success': True, 'key': 'workday', 'val': val_f, 'message': f"Max workday set to {val_f:.1f}h"}

                elif key == 'ten_hour_act':
                    val_b = bool(val)
                    target_nation.ten_hour_act = val_b
                    if val_b:
                        target_nation.max_workday_hours = min(10.0, getattr(target_nation, 'max_workday_hours', 12.0))
                    for t in target_nation.tiles:
                        t.ten_hour_act = val_b
                    self.push_ticker(self.turn, 'POLICY', f"{target_nation.name} {'enacted' if val_b else 'repealed'} the Ten-Hour Act.", (140, 220, 160))
                    return {'success': True, 'key': 'ten_hour_act', 'val': val_b, 'message': f"Ten-Hour Act {'enacted' if val_b else 'repealed'}"}

                elif key == 'granary_relief':
                    tr = target_nation.treasury()
                    if tr['food'] >= 20:
                        disbursed = min(50, tr['food'])
                        target_nation.government.agent.food -= disbursed
                        hungry_agents = [a for t in target_nation.tiles for a in t.agents if getattr(a, 'hungry_steps', 0) > 0]
                        fed_count = 0
                        for a in hungry_agents[:disbursed]:
                            a.hungry_steps = 0
                            a.food += 1.0
                            fed_count += 1
                        self.push_ticker(self.turn, 'RELIEF', f"{target_nation.name} opened state granaries, feeding {fed_count} citizens.", (100, 240, 160))
                        return {'success': True, 'message': f"Disbursed {disbursed} food units to relief granaries (fed {fed_count} citizens)."}
                    return {'success': False, 'error': "Insufficient emergency food in state granary."}

                elif key == 'law_enforcement':
                    if target_nation.government.agent.cash >= 50.0:
                        _trace_cash_write = _trace_public_begin(None, target_nation.government.agent)
                        target_nation.government.agent.cash -= 50.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:fd4bf5244975630a:1'})
                        for t in target_nation.tiles:
                            if t.protest_energy_log:
                                t.protest_energy_log[-1] = max(0.0, t.protest_energy_log[-1] - 1.5)
                        self.push_ticker(self.turn, 'ORDER', f"{target_nation.name} deployed public order decree (-1.5 protest energy).", (240, 200, 100))
                        return {'success': True, 'message': "Public order decree enacted (-1.5 protest energy across nation)."}
                    return {'success': False, 'error': "Insufficient treasury funds ($50 required)."}

                else:
                    if hasattr(target_nation, 'policies') and isinstance(target_nation.policies, dict):
                        target_nation.policies[key] = val
                    else:
                        setattr(target_nation, key, val)
                    return {'success': True, 'nation': target_nation.name, 'key': key, 'val': val}

            elif c_type == CommandType.PRODUCTION_PROGRAM:
                target = next((n for n in self.nations if n.name == (p.get('nation') or self.player_nation_name)), None)
                tile = self.by_name.get(p.get('tile'))
                if target is None or tile is None or tile not in target.tiles:
                    return {'success': False, 'error': 'Target tile must belong to the selected nation.'}
                from production_policy import submit
                try:
                    program = submit(tile, p.get('kind'), p.get('good', 'food'),
                                     float(p.get('quantity', 0)), float(p.get('budget', 0)),
                                     float(p.get('duration', 2)), self.turn)
                except (ValueError, TypeError, KeyError) as error:
                    return {'success': False, 'error': str(error)}
                return {'success': True, 'tile': tile.name, 'program': program}

            elif c_type == CommandType.LABOR_LAW_ACTION:
                target_nation = next((n for n in self.nations
                                      if n.name == (p.get('nation') or self.player_nation_name)), None)
                tile = self.by_name.get(p.get('tile'))
                law, action = p.get('law'), p.get('action')
                if target_nation is None or tile is None or tile not in target_nation.tiles:
                    return {'success': False, 'error': 'Target tile must belong to the selected nation.'}
                if law not in ('vagrancy', 'gathering_restriction', 'quit_penalty', 'wage_cap'):
                    return {'success': False, 'error': 'Unknown labor law.'}
                if action not in ('enact', 'repeal'):
                    return {'success': False, 'error': 'Action must be enact or repeal.'}
                from labor_laws import set_labor_law
                status = 'enacted' if action == 'enact' else 'repealed'
                set_labor_law(tile, law, status)
                self.push_ticker(self.turn, 'LABOR_LAW',
                                 f"{target_nation.name} {action}ed {law.replace('_', ' ')} in {tile.name}.",
                                 (245, 210, 90))
                return {'success': True, 'tile': tile.name, 'law': law, 'status': status}

            elif c_type == CommandType.DIPLOMATIC_ACTION:
                if not self.gameplay_flags.diplomacy:
                    return {'success': False, 'error': 'Diplomacy is disabled for this run.'}
                action = p.get('action')
                target = p.get('target')
                source = p.get('nation') or self.player_nation_name
                dip = get_diplomacy()

                if action == 'propose_trade':
                    ok, msg = dip.propose_treaty(
                        source, target, TreatyType.TRADE_PACT, self.turn,
                        _trace_world={'nations': self.nations})
                elif action == 'propose_nap':
                    ok, msg = dip.propose_treaty(
                        source, target, TreatyType.NON_AGGRESSION, self.turn,
                        _trace_world={'nations': self.nations})
                elif action == 'propose_alliance':
                    ok, msg = dip.propose_treaty(
                        source, target, TreatyType.DEFENSIVE_ALLIANCE, self.turn,
                        _trace_world={'nations': self.nations})
                elif action == 'break_treaty':
                    t_type = p.get('treaty_type', TreatyType.TRADE_PACT)
                    res = dip.break_treaty(
                        source, target, t_type, self.turn,
                        _trace_world={'nations': self.nations})
                    ok, msg = res['success'], res['message']
                elif action == 'declare_war':
                    if not self.gameplay_flags.wars:
                        return {'success': False, 'error': 'Wars are disabled for this run.'}
                    events = dip.declare_war(source, target, self.turn,
                                             reason=p.get('reason', 'Geopolitical confrontation'),
                                             nations={n.name: n for n in self.nations})
                    ok, msg = True, f"War declared on {target} by {source}."
                else:
                    return {'success': False, 'error': f"Unknown diplomatic action '{action}'."}

                self.push_ticker(self.turn, 'DIPLO', msg, (100, 220, 255) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SOVEREIGN_BOND:
                if not self.gameplay_flags.sovereign_bonds:
                    return {'success': False, 'error': 'Sovereign bonds are disabled for this run.'}
                action = p.get('action')
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found"}
                market = get_bond_market()

                if action == 'issue_bond':
                    amount = float(p.get('amount', 500.0))
                    duration = int(p.get('duration', 20))
                    ok, msg, off = market.announce_bond_offering(nation, amount, duration, self.turn, world=self.get_world_dict())
                    if ok:
                        self.push_ticker(self.turn, 'BOND', f"{nation.name} announced ${amount:,.0f} sovereign bond tranche ({duration}t maturity).", (245, 210, 90))
                    return {'success': ok, 'message': msg}

                elif action == 'lobby_upgrade':
                    if nation.government.agent.cash >= 200.0:
                        ok, msg, scandal = market.isrb.lobby_upgrade(nation, self.turn)
                        self.push_ticker(self.turn, 'ISRB', msg, (120, 240, 160) if ok else (240, 90, 90))
                        return {'success': ok, 'message': msg, 'scandal': scandal}
                    return {'success': False, 'error': "Insufficient treasury funds ($200 required)."}

                return {'success': False, 'error': f"Unknown bond action '{action}'."}

            elif c_type == CommandType.RESEARCH_TECH:
                if not self.gameplay_flags.innovation:
                    return {'success': False, 'error': 'Innovation is disabled for this run.'}
                action = p.get('action', 'pledge_prize')
                tech_id = p.get('tech_id')
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found"}
                innov = get_innovation_system()

                if action == 'preview_engineering':
                    from engineering import OBJECTIVES
                    budget = float(p.get('budget', 0))
                    objective = str(p.get('objective', 'balanced'))
                    host = p.get('host')
                    if (tech_id not in TECH_CATALOG or not math.isfinite(budget) or budget < 0
                            or budget > 1_000_000 or objective not in OBJECTIVES
                            or not any(tile.name == host for tile in nation.tiles)):
                        return {'success': False, 'message': 'Invalid engineering preview.'}
                    return {'success': True, 'engineering': innov.engineering_status(
                        nation, tech_id, self.turn, {'budget': budget, 'objective': objective,
                                                   'host': host, 'status': 'active' if budget else 'inactive'})}

                elif action == 'set_engineering':
                    ok, msg = innov.set_engineering_program(
                        nation, tech_id, p.get('budget', 0), str(p.get('objective', 'balanced')),
                        host=p.get('host'), t=self.turn)
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (120, 200, 255))
                    return {'success': ok, 'message': msg,
                            'engineering': innov.engineering_status(nation, tech_id, self.turn) if ok else None}

                elif action == 'retrofit':
                    ok, msg = innov.commission_retrofit(nation, tech_id, p.get('tile'),
                                                       p.get('building_index'), t=self.turn)
                    return {'success': ok, 'message': msg}

                elif action == 'pledge_prize':
                    amount = float(p.get('amount', 300.0))
                    ok = innov.post_royal_bounty(nation, tech_id, amount, self.turn)
                    tech_meta = TECH_CATALOG.get(tech_id)
                    tech_title = tech_meta.name if tech_meta else tech_id
                    msg = f"Pledged ${amount:,.0f} Royal Science Prize for '{tech_title}'." if ok else "Failed to pledge prize (insufficient treasury or already discovered)."
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (180, 140, 255))
                    return {'success': ok, 'message': msg}

                elif action == 'set_subsidy':
                    mode = str(p.get('mode', 'commercial'))
                    ok, msg = innov.set_subsidy_mode(nation, tech_id, mode, t=self.turn)
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (120, 200, 255))
                    return {'success': ok, 'message': msg, 'subsidy_mode': innov.get_subsidy_mode(nation.name, tech_id)}

                elif action == 'steal_tech':
                    ok, msg = innov.attempt_tech_espionage(nation, tech_id, t=self.turn, nations=self.nations)
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (255, 190, 90))
                    return {'success': ok, 'message': msg, 'tier': innov.get_tech_tier(nation.name, tech_id), 'refinement_xp': innov.get_refinement_xp(nation.name, tech_id)}

                elif action == 'resolve_guild':
                    guild_action = str(p.get('guild_action', 'repeal'))
                    ok, msg = innov.resolve_guild_blockade(nation, tech_id, guild_action, t=self.turn)
                    if ok:
                        self.push_ticker(self.turn, 'SCIENCE', msg, (110, 230, 160))
                    return {'success': ok, 'message': msg, 'guild_blockade': innov.get_guild_blockade(nation, tech_id)}

                return {'success': False, 'error': f"Unknown science action '{action}'."}

            elif c_type == CommandType.RECRUIT_UNIT:
                if not self.gameplay_flags.military:
                    return {'success': False, 'error': 'Military recruitment is disabled for this run.'}
                tile_name = p.get('tile')
                soldiers = int(p.get('soldiers', 15))
                wage = float(p.get('wage', 1.0))
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                tile = self.by_name.get(tile_name)
                if not tile or tile not in getattr(nation, 'tiles', []):
                    tile = nation.tiles[0] if nation and nation.tiles else None

                if not tile or not nation:
                    return {'success': False, 'error': "Territory or nation not found."}

                from intents import RecruitArmyIntent
                intent = RecruitArmyIntent(nation.name, tile.name, soldiers, wage=wage, submitted_turn=self.turn)
                ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                if ok:
                    self.push_ticker(self.turn, 'MILITARY', msg, (240, 110, 110))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.ENCLOSE_PLOT:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile:
                    return {'success': False, 'error': f"Tile '{tile_name}' not found."}
                from enclosure import execute_enclosure
                ok, msg, _evs = execute_enclosure(tile, plot_id, self.turn)
                self.push_ticker(self.turn, 'ENCLOSURE', msg, (230, 140, 70) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.CADASTRE_TOGGLE_LAND_USE:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile or not hasattr(tile, 'tenure'):
                    return {'success': False, 'error': f"Tile '{tile_name}' has no cadastre tenure."}
                pl = tile.tenure.find_plot(plot_id)
                if not pl:
                    return {'success': False, 'error': f"Plot #{plot_id} not found."}
                new_t = p.get('production_type')
                if not new_t:
                    new_t = 'pasture' if getattr(pl, 'production_type', 'arable') != 'pasture' else 'arable'
                tile.tenure.convert_production_type(plot_id, new_t, self.turn)
                msg = f"Plot {pl.display_name} switched to {new_t.upper()} on {tile.name}."
                if new_t == 'pasture':
                    msg += " 75% tenants dispossessed."
                self.push_ticker(self.turn, 'LAND_USE', msg, (210, 180, 100))
                return {'success': True, 'message': msg, 'production_type': new_t}

            elif c_type == CommandType.RESTORE_COMMONS:
                tile_name = p.get('tile') or p.get('region')
                plot_id = str(p.get('plot_id', ''))
                tile = self.by_name.get(tile_name)
                if not tile or not hasattr(tile, 'tenure'):
                    return {'success': False, 'error': f"Tile '{tile_name}' has no cadastre tenure."}
                tile.tenure.revert_plot_to_commons(plot_id, self.turn)
                tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.25)
                msg = f"Plot #{plot_id} restored to Customary Commons on {tile.name}!"
                self.push_ticker(self.turn, 'COMMONS', msg, (120, 220, 140))
                return {'success': True, 'message': msg}

            elif c_type == CommandType.TRANSFER_LAND_TITLE:
                tile = self.by_name.get(p.get('tile') or p.get('region'))
                if not tile:
                    return {'success': False, 'error': 'Territory not found.'}
                if not getattr(tile, 'owner_nation', None) or tile.owner_nation.name != self.player_nation_name:
                    return {'success': False, 'error': 'This territory is outside player jurisdiction.'}
                actors = {a.id: a for a in tile.agents}
                seller, buyer = actors.get(int(p.get('seller_id', -1))), actors.get(int(p.get('buyer_id', -1)))
                from supply_proposals import propose
                lease_turns = int(p.get('lease_turns', 0))
                event = (propose(tile, 'land_lease' if lease_turns > 0 else 'land_sale',
                                 buyer, seller, turn=self.turn, price=p.get('price', 0),
                                 plot_id=str(p.get('plot_id', '')), lease_turns=lease_turns,
                                 max_price=p.get('max_price', p.get('price', 0)))
                         if seller and buyer else None)
                ok = event is not None
                msg = (f"Plot {event['plot_id']} offer #{event['id']} sent; owner decides next turn."
                       if ok else 'Land offer failed: check title, cash, and parties.')
                self.push_ticker(self.turn, 'LAND', msg, (210, 180, 100) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg, 'event': event}

            elif c_type == CommandType.ACQUIRE_WATER_RIGHT:
                tile = self.by_name.get(p.get('tile') or p.get('region'))
                if not tile:
                    return {'success': False, 'error': 'Territory not found.'}
                if not getattr(tile, 'owner_nation', None) or tile.owner_nation.name != self.player_nation_name:
                    return {'success': False, 'error': 'This territory is outside player jurisdiction.'}
                actors = {a.id: a for a in tile.agents}
                seller, buyer = actors.get(int(p.get('seller_id', -1))), actors.get(int(p.get('buyer_id', -1)))
                from supply_proposals import propose
                event = (propose(tile, 'water_right', buyer, seller, turn=self.turn,
                                 price=p.get('price', 0), units=p.get('units', .25),
                                 from_plot_id=str(p.get('from_plot_id', '')),
                                 to_plot_id=str(p.get('to_plot_id', '')),
                                 max_price=p.get('max_price', p.get('price', 0)))
                         if seller and buyer else None)
                ok = event is not None
                msg = (f"Water-right offer #{event['id']} sent; holder decides next turn."
                       if ok else 'Water-right transfer failed: check right, cash, and parties.')
                self.push_ticker(self.turn, 'WATER', msg, (90, 180, 230) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg, 'event': event}

            elif c_type == CommandType.PETITION_MARKET_CHARTER:
                tile = self.by_name.get(p.get('tile') or p.get('region'))
                if not tile:
                    return {'success': False, 'error': 'Territory not found.'}
                actors = {a.id: a for a in tile.agents}
                sponsor = actors.get(int(p.get('sponsor_id', -1)))
                good = next((g for g in tile.recipes
                             if getattr(g, 'name', str(g)) == str(p.get('good', ''))), None)
                from market_concessions import submit_concession_petition
                petition = (submit_concession_petition(sponsor, tile, good,
                            str(p.get('charter_type', '')), p.get('fee', 10),
                            p.get('term_turns', 10), self.turn)
                            if sponsor and good is not None else None)
                ok = petition is not None
                if petition is not None:
                    owner = getattr(tile, 'owner_nation', None)
                    petition['player_review'] = bool(owner and owner.name == self.player_nation_name)
                    if petition['player_review']:
                        petition['decision_turn'] = self.turn + 2
                msg = (f"Charter petition #{petition['id']} submitted; the council will decide next turn."
                       if ok else 'Charter petition failed: check sponsor, commodity, fee, and charter type.')
                self.push_ticker(self.turn, 'CHARTER', msg, (180, 140, 230) if ok else (240, 90, 90))
                return {'success': ok, 'message': msg, 'petition': petition}

            elif c_type == CommandType.RESOLVE_MARKET_CHARTER:
                tile = self.by_name.get(p.get('tile') or p.get('region'))
                petition_id = int(p.get('petition_id', -1))
                decision = str(p.get('decision', ''))
                petition = next((item for item in getattr(tile, 'concession_petitions', [])
                                 if item['id'] == petition_id and item['status'] == 'proposed'), None) if tile else None
                owner = getattr(tile, 'owner_nation', None) if tile else None
                if (petition is None or decision not in ('approve', 'reject')
                        or not petition.get('player_review')
                        or not owner or owner.name != self.player_nation_name):
                    return {'success': False, 'error': 'Petition is not awaiting this government\'s decision.'}
                petition['player_decision'] = decision
                petition['decision_turn'] = self.turn
                from market_concessions import decide_concession_petitions
                events = decide_concession_petitions(tile, self.turn)
                event = next((item for item in events if item.get('petition_id') == petition_id), None)
                msg = f"The government {decision}d charter petition #{petition_id}."
                self.push_ticker(self.turn, 'CHARTER', msg, (120, 210, 140) if decision == 'approve' else (230, 140, 100))
                return {'success': event is not None, 'message': msg, 'event': event}

            elif c_type == CommandType.PROVINCE_DECREE:
                prov_name = p.get('province')
                decree = p.get('decree')
                province = next((pr for n in self.nations for pr in getattr(n, 'provinces', []) if pr.name == prov_name), None)
                if not province:
                    return {'success': False, 'error': f"Province '{prov_name}' not found."}
                pgov = getattr(province, 'gov', None)
                pcash = pgov.agent.cash if pgov and hasattr(pgov, 'agent') else 0.0

                if decree == 'pave_highway':
                    if pcash >= 120.0:
                        _trace_cash_write = _trace_public_begin(None, pgov.agent)
                        pgov.agent.cash -= 120.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:78dd88bba15f9a7e:1'})
                        for t in province.tiles:
                            t.road_quality = min(1.0, getattr(t, 'road_quality', 0.5) + 0.25)
                        msg = f"Paved regional highway across {province.name} (trade speed +25%)."
                        self.push_ticker(self.turn, 'PROVINCE', msg, (120, 220, 150))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($120 required)."}

                elif decree == 'healthcare':
                    if pcash >= 150.0:
                        _trace_cash_write = _trace_public_begin(None, pgov.agent)
                        pgov.agent.cash -= 150.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:7048a6c8bc81afe0:1'})
                        for t in province.tiles:
                            setattr(t, 'medical_spending_public', getattr(t, 'medical_spending_public', 0.0) + 25.0)
                        msg = f"Regional Healthcare Initiative launched across {province.name}."
                        self.push_ticker(self.turn, 'HEALTH', msg, (100, 240, 180))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($150 required)."}

                elif decree == 'equalization':
                    if pcash >= 200.0:
                        _trace_cash_write = _trace_public_begin(None, pgov.agent)
                        pgov.agent.cash -= 200.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:f7629de2a2432c46:1'})
                        share = 200.0 / max(1, len(province.tiles))
                        for t in province.tiles:
                            if hasattr(t, 'gov') and hasattr(t.gov, 'agent'):
                                _trace_cash_write = _trace_public_begin(None, t.gov.agent)
                                t.gov.agent.cash += share
                                _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                                     inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:606929e243442718:1'})
                        msg = f"Provincial equalization transfer (${share:,.0f} per city) disbursed in {province.name}."
                        self.push_ticker(self.turn, 'FISCAL', msg, (245, 210, 100))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($200 required)."}

                elif decree == 'standardize_routes':
                    for t in province.tiles:
                        t.trade_efficiency = min(1.0, getattr(t, 'trade_efficiency', 0.7) + 0.15)
                    msg = f"Trade routes standardized across {province.name}."
                    self.push_ticker(self.turn, 'PROVINCE', msg, (200, 230, 150))
                    return {'success': True, 'message': msg}

                elif decree == 'harmonize_taxes':
                    avg_tax = sum(t.gov.tax_rate for t in province.tiles if hasattr(t, 'gov')) / max(1, len(province.tiles))
                    for t in province.tiles:
                        if hasattr(t, 'gov'):
                            t.gov.tax_rate = avg_tax
                    msg = f"Tax rates harmonized to {avg_tax*100:.1f}% across {province.name}."
                    self.push_ticker(self.turn, 'PROVINCE', msg, (240, 200, 120))
                    return {'success': True, 'message': msg}

                elif decree == 'soil_conservation':
                    if pcash >= 150.0:
                        _trace_cash_write = _trace_public_begin(None, pgov.agent)
                        pgov.agent.cash -= 150.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:1da86897d01d9a3a:1'})
                        for t in province.tiles:
                            t.soil_fertility = min(1.0, getattr(t, 'soil_fertility', 0.8) + 0.10)
                        msg = f"Provincial soil conservation campaign funded in {province.name}."
                        self.push_ticker(self.turn, 'ECOLOGY', msg, (130, 240, 160))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient provincial treasury ($150 required)."}

                return {'success': False, 'error': f"Unknown provincial decree '{decree}'."}

            elif c_type == CommandType.FRONTIER_EXPEDITION:
                if not self.gameplay_flags.frontier_claims:
                    return {'success': False, 'error': 'Frontier claims are disabled for this run.'}
                tile_name = p.get('tile') or p.get('region')
                action = p.get('action', 'sponsor_settlers')
                tile = self.by_name.get(tile_name)
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), self.nations[0] if self.nations else None)
                if not tile:
                    return {'success': False, 'error': f"Tile '{tile_name}' not found."}

                if action == 'sponsor_settlers':
                    if nation and nation.government.agent.cash >= 100.0:
                        _trace_cash_write = _trace_public_begin(None, nation.government.agent)
                        nation.government.agent.cash -= 100.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:65ded6c263c10afa:1'})
                        from agent import Agent
                        for _ in range(3):
                            a = Agent(tile, is_homesteader=True, cash=25.0)
                            tile.agents.append(a)
                        msg = f"Sponsored 3 homesteading pioneer families to {tile.name} ($100)."
                        self.push_ticker(self.turn, 'FRONTIER', msg, (100, 240, 160))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient national treasury ($100 required)."}

                elif action == 'pioneer_aid':
                    if nation and nation.government.agent.cash >= 40.0:
                        _trace_cash_write = _trace_public_begin(None, nation.government.agent)
                        nation.government.agent.cash -= 40.0
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:f0798bfe57980a87:1'})
                        for a in tile.agents:
                            if getattr(a, 'is_homesteader', False):
                                a.food += 2.0
                                a.hungry_steps = 0
                        msg = f"Pioneer food aid delivered to settlers on {tile.name} ($40)."
                        self.push_ticker(self.turn, 'FRONTIER', msg, (160, 220, 150))
                        return {'success': True, 'message': msg}
                    return {'success': False, 'error': "Insufficient national treasury ($40 required)."}

                return {'success': False, 'error': f"Unknown frontier action '{action}'."}

            elif c_type == CommandType.PURCHASE_FOREIGN_BOND:
                if not self.gameplay_flags.sovereign_bonds:
                    return {'success': False, 'error': 'Sovereign bonds are disabled for this run.'}
                seller_name = p.get('seller_nation')
                buyer_name = p.get('buyer_nation') or self.player_nation_name
                amount = float(p.get('amount', 500.0))
                term = int(p.get('term', 20))
                market = get_bond_market()
                buyer = next((n for n in self.nations if n.name == buyer_name), None)
                seller = next((n for n in self.nations if n.name == seller_name), None)
                if not buyer or not seller:
                    return {'success': False, 'error': "Buyer or seller nation not found."}
                ok, msg = market.buy_foreign_bond(buyer, seller, amount, term, self.turn)
                if ok:
                    self.push_ticker(self.turn, 'BOND', f"{buyer.name} purchased ${amount:,.0f} of {seller.name} bonds.", (120, 240, 180))
                return {'success': ok, 'message': msg}

            elif c_type == CommandType.SET_BORDER_POLICY:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                open_b = bool(p.get('open_borders', True))
                setattr(nation, 'open_borders', open_b)
                msg = f"Border immigration {'OPENED' if open_b else 'CLOSED'} for {nation.name}."
                self.push_ticker(self.turn, 'BORDER', msg, (120, 200, 255))
                return {'success': True, 'message': msg, 'open_borders': open_b}

            elif c_type == CommandType.SET_FACTORY_SAFETY:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                val = bool(p.get('enabled', True))
                setattr(nation, 'factory_safety_act', val)
                msg = f"Factory Safety Act {'ENACTED' if val else 'REPEALED'} in {nation.name}."
                self.push_ticker(self.turn, 'LABOR', msg, (130, 220, 140))
                return {'success': True, 'message': msg, 'factory_safety_act': val}

            elif c_type == CommandType.SET_TRUCK_ACT:
                nat_name = p.get('nation') or self.player_nation_name
                nation = next((n for n in self.nations if n.name == nat_name), None)
                if not nation:
                    return {'success': False, 'error': "Nation not found."}
                val = bool(p.get('enabled', True))
                setattr(nation, 'truck_act_enacted', val)
                msg = f"Truck Act (Scrip Wage Ban) {'ENACTED' if val else 'REPEALED'} in {nation.name}."
                self.push_ticker(self.turn, 'LABOR', msg, (240, 190, 80))
                return {'success': True, 'message': msg, 'truck_act_enacted': val}

            elif c_type == CommandType.FISCAL_TRANSFER_RESOLVE:
                funding_source = p.get('funding_source')
                tile_name = p.get('tile')
                tile = self.by_name.get(tile_name)
                recipe_name = p.get('recipe_name')
                cost = float(p.get('cost', 250.0))
                nation = getattr(tile, 'owner_nation', None)
                province = getattr(tile, 'province', None)
                if not tile:
                    return {'success': False, 'error': "Tile not found."}

                on_hand = tile.gov.agent.cash if hasattr(tile, 'gov') and hasattr(tile.gov, 'agent') else 0.0
                shortfall = max(0.0, cost - on_hand)

                if funding_source == 'province_grant':
                    pgov = getattr(province, 'gov', None)
                    if pgov and pgov.agent.cash >= shortfall:
                        _trace_cash_write = _trace_public_begin(None, pgov.agent)
                        pgov.agent.cash -= shortfall
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:9c3af421074576d2:1'})
                        _trace_cash_write = _trace_public_begin(None, tile.gov.agent)
                        tile.gov.agent.cash += shortfall
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:4fea59098d6f2cb4:1'})
                    else:
                        return {'success': False, 'error': "Provincial treasury has insufficient funds."}
                elif funding_source == 'national_bailout':
                    if nation and nation.government.agent.cash >= shortfall:
                        _trace_cash_write = _trace_public_begin(None, nation.government.agent)
                        nation.government.agent.cash -= shortfall
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:af50ce90caf71d8c:1'})
                        _trace_cash_write = _trace_public_begin(None, tile.gov.agent)
                        tile.gov.agent.cash += shortfall
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:50ecbee8239267e0:1'})
                    else:
                        return {'success': False, 'error': "National sovereign treasury has insufficient funds."}
                elif funding_source == 'bank_loan':
                    if hasattr(tile, 'gov') and hasattr(tile.gov, 'agent'):
                        _trace_cash_write = _trace_public_begin(None, tile.gov.agent)
                        tile.gov.agent.cash += shortfall
                        _trace_public_finish(_trace_cash_write, 'sim_server/sim_server:SimServer.execute_command',
                                             inputs={"source_writer": 'sim_server/sim_server.py:SimServer.execute_command:b4591666fc9dc861:1'})

                recipe = BUILDING_RECIPES.get(recipe_name)
                if recipe:
                    from intents import BuildIntent
                    intent = BuildIntent(tile.name, recipe.name, submitted_turn=self.turn)
                    ok, msg = intent.execute(self.by_name, {n.name: n for n in self.nations}, self.turn)
                    return {'success': ok, 'message': f"Shortfall resolved via {funding_source}: {msg}"}
            elif c_type == CommandType.EMERGENCY_OVERRUN_SUBSIDY:
                proj_id = p.get('project_id')
                amount = float(p.get('amount', 100.0))
                player_nation = next((n for n in self.nations if n.name == self.player_nation_name), self.nations[0] if self.nations else None)
                target_proj = None
                for t in self.tiles:
                    for proj in getattr(t, 'construction_projects', []):
                        if getattr(proj, 'project_id', None) == proj_id:
                            target_proj = proj
                            break
                    if target_proj:
                        break
                if not target_proj and player_nation:
                    for proj in getattr(player_nation, 'construction_projects', []):
                        if getattr(proj, 'project_id', None) == proj_id:
                            target_proj = proj
                            break
                if not target_proj:
                    return {'success': False, 'error': f"Project '{proj_id}' not found."}

                from construction_politics import subsidize_contractor
                ok, msg = subsidize_contractor(target_proj, amount, player_nation, world=self.get_world_dict())
                if ok:
                    self.push_ticker(self.turn, 'SUBSIDY', f"Dispatched ${amount:.0f} overrun grant to {target_proj.recipe.display_name}.", (120, 240, 150))
                    return {'success': True, 'message': msg}
                return {'success': False, 'error': msg}

            elif c_type == CommandType.GET_STATE:
                target_tile = p.get('tile')
                if target_tile:
                    tile_obj = self.by_name.get(target_tile)
                    if tile_obj:
                        return {'success': True, 'tile': self.serialize_tile(tile_obj, layout=self.layout, turn=self.turn)}
                    return {'success': False, 'error': f"Tile '{target_tile}' not found"}
                return {'success': True, 'world': self.serialize_world()}

            return {'success': False, 'error': f"Unknown command {c_type}"}

    def subscribe(self, callback):
        """Register a callback for server broadcast events."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback):
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _broadcast(self, event_type: ServerEvent, data: Dict[str, Any]):
        for cb in list(self._subscribers):
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"[SimServer] Broadcast error: {e}")

    def get_world_dict(self) -> Dict[str, Any]:
        """Produce a world representation compatible with legacy worldview panels."""
        with self._lock:
            return {
                'tiles': self.tiles,
                'nations': self.nations,
                'currencies': self.currencies,
                'pair_orders': self.pair_orders,
                'by_name': self.by_name,
                'layout': self.layout,
                'reverse': self.reverse_layout,
                'bbox': self.bbox,
                'turn': self.turn,
                'playing': self.playing,
                'ticker_events': self._ticker_events,
                'currency_totals': self.currency_totals,
                'violations': self.violations,
                'seed': self.seed,
                'terrain_seed': self.terrain_seed,
                'nation_seed': self.nation_seed,
                'player_nation_name': self.player_nation_name,
                'scenario_id': self.scenario_id,
                'scenario_state': getattr(self, 'scenario_state', {}),
                'gameplay_profile': self.gameplay_profile,
                'gameplay_flags': self.gameplay_flags.as_dict(),
                'gameplay_flags_version': GAMEPLAY_FLAGS_VERSION,
                'elite_planning': self.elite_planning_config.as_dict(),
            }

    def _collect_progress_suite(self) -> Dict[str, Any]:
        """Collect active construction, research, and legislation items for progress drawer."""
        try:
            from worldview_progress_panel import _collect_items_for_nation
            w_dict = self.get_world_dict()
            player_nat = next((n for n in self.nations if n.name == self.player_nation_name), self.nations[0] if self.nations else None)

            def _clean_item(it):
                clean = dict(it)
                proj = clean.pop('project', None)
                if proj is not None and 'project_id' not in clean:
                    clean['project_id'] = getattr(proj, 'project_id', None)
                if 'bar_color' in clean and isinstance(clean['bar_color'], (tuple, list)):
                    c = clean['bar_color']
                    clean['bar_color'] = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
                return clean

            active_items = [_clean_item(it) for it in _collect_items_for_nation(player_nat, w_dict)] if player_nat else []
            all_items = []
            for n in self.nations:
                for it in _collect_items_for_nation(n, w_dict):
                    all_items.append(_clean_item(it))

            stalled_count = sum(1 for it in active_items if it.get('is_stalled'))
            return {
                'active_nation': active_items,
                'all_nations': all_items,
                'stalled_count': stalled_count,
            }
        except Exception as e:
            return {'active_nation': [], 'all_nations': [], 'stalled_count': 0, 'error': str(e)}

    def _calc_seasonal_info(self) -> Dict[str, Any]:
        """Calculate live seasonal timeline, biological crop multiplier, and buffer stats."""
        import math
        from game_time import seasonal_cycle_phase, seasonal_cycle_year
        t_mod = seasonal_cycle_phase(self.turn)
        mult = 1.0 + 0.45 * math.sin(2.0 * math.pi * (t_mod - 2) / 10.0)
        pct_delta = int(round((mult - 1.0) * 100))

        seasonal_meta = [
            (0, "Early Spring", "spring", "#78e18c", "Thaw & Sowing"),
            (1, "Mid Spring", "spring", "#8ceb96", "Germination"),
            (2, "Late Spring", "spring", "#a0f0a0", "Baseline Growth"),
            (3, "Early Summer", "summer", "#ffe65a", "Crop Maturation"),
            (4, "Mid Summer", "summer", "#ffd73c", "Pre-Harvest Ripening"),
            (5, "Harvest Peak", "autumn", "#ffaf2d", "Harvest Festival (+45%)"),
            (6, "Autumn Harvest", "autumn", "#f58c28", "Granary Inflow (+15%)"),
            (7, "Frost Fallow", "autumn", "#d27832", "Post-Harvest Tillage"),
            (8, "Early Winter", "winter", "#a0d2f5", "Dormancy & Chill"),
            (9, "Deep Winter", "winter", "#78dcff", "The Lean Season (-45%)"),
        ]
        meta = seasonal_meta[t_mod]

        player_nat = next((n for n in self.nations if n.name == self.player_nation_name), self.nations[0] if self.nations else None)
        granary_food = player_nat.treasury().get('food', 0) if player_nat else 0
        pop = sum(len(r.agents) for r in getattr(player_nat, 'tiles', [])) if player_nat else 1
        burn_rate = max(1, int(pop * 0.1))
        buffer_turns = round(granary_food / burn_rate, 1)

        return {
            'turn': self.turn,
            'year': seasonal_cycle_year(self.turn),
            'turn_in_year': t_mod,
            'name': meta[1],
            'icon': meta[2],
            'color': meta[3],
            'phase_desc': meta[4],
            'mult': round(mult, 3),
            'pct_delta': pct_delta,
            'is_winter': (t_mod == 9),
            'is_storing': (4 <= t_mod <= 7),
            'is_buffering': (t_mod in (9, 0, 1)),
            'granary_food': int(granary_food),
            'burn_rate': burn_rate,
            'buffer_turns': buffer_turns,
        }

    def _collect_trade_network(self) -> Dict[str, Any]:
        """Collect overland trading network edges and active bilateral flow vectors."""
        edges = []
        seen = set()
        for r, o in self.pair_orders:
            k = tuple(sorted((r.name, o.name)))
            if k not in seen:
                seen.add(k)
                edges.append({'from': r.name, 'to': o.name})

        flows = []
        for r, o in self.pair_orders:
            flow = r.trade_flow_log[-1] if getattr(r, 'trade_flow_log', None) else 0.0
            if abs(flow) >= 0.5:
                flows.append({
                    'from': r.name,
                    'to': o.name,
                    'volume': round(abs(flow), 1),
                    'forward': flow > 0
                })

        return {'edges': edges, 'flows': flows}

    def _collect_scenario_info(self) -> Dict[str, Any]:
        """Collect scenario pressures and guided objectives."""
        try:
            if self.scenario_id == 'labor_frontier_rivalry':
                from labor_frontier_projection import project
                return project(self.get_world_dict())
            if self.scenario_id == 'supply_rivalry':
                from scenario_supply_rivalry import project
                return project(self.get_world_dict())
            from worldview_scenario_ui import scenario_pressures
            w_dict = self.get_world_dict()
            pressures = scenario_pressures(w_dict)
            return {'pressures': pressures, 'active': bool(getattr(self, 'scenario_id', None))}
        except Exception:
            return {'pressures': [], 'active': False}

    @staticmethod
    def serialize_plot(plot) -> Dict[str, Any]:
        from sim_server.serialization import serialize_plot
        return serialize_plot(plot)

    @classmethod
    def serialize_tile(cls, tile, layout: Optional[Dict[str, Any]] = None, turn: int = 0,
                       summary: bool = False) -> Dict[str, Any]:
        from sim_server.serialization import serialize_tile
        return serialize_tile(tile, layout=layout, turn=turn, summary=summary)

    def serialize_world(self, compact: bool = False) -> Dict[str, Any]:
        """Produce a complete JSON-serializable snapshot of the simulation world."""
        with self._lock:
            tiles_data = [self.serialize_tile(t, layout=self.layout, turn=self.turn, summary=compact) for t in self.tiles]
            player_nation = next((n for n in self.nations if n.name == self.player_nation_name), self.nations[0] if self.nations else None)
            player_nat_name = player_nation.name if player_nation else None

            # All nations macro stats for comparison modal & dropdown
            nations_summary = [self._calc_nation_macro(n) for n in self.nations]
            active_macro = next((m for m in nations_summary if m['name'] == player_nat_name), (nations_summary[0] if nations_summary else {}))

            # History series for charting
            history_data = self._nation_history.get(player_nat_name, {
                'turns': [], 'treasury': [], 'gdp': [], 'pop': [], 'food_price': [], 'unrest': []
            })

            # Build Recipes (Categorized)
            build_recipes = {}
            for k, r in BUILDING_RECIPES.items():
                if player_nation:
                    from engineering import quote_recipe
                    try:
                        r = quote_recipe(player_nation, r, get_innovation_system())
                    except ValueError:
                        continue
                req_g = {}
                if getattr(r, 'required_goods', None):
                    for g, cnt in r.required_goods.items():
                        req_g[g.name if hasattr(g, 'name') else str(g)] = cnt
                cat = 'industry'
                if k in ('night_soil_depot', 'sewer_system', 'infirmary', 'water_filtration', 'sanitarium', 'waste_incinerator'):
                    cat = 'ecology'
                elif k in ('fortress', 'naval_dockyard'):
                    cat = 'defense'
                elif k in ('paved_road', 'canal', 'railroad', 'telegraph'):
                    cat = 'roads'
                build_recipes[k] = {
                    'name': r.name,
                    'display_name': r.display_name,
                    'cost': float(r.cost),
                    'base_turns': int(r.base_turns),
                    'tier': r.tier,
                    'category': cat,
                    'description': r.description,
                    'required_goods': req_g
                }

            # Diplomacy state
            diplo_list = []
            try:
                dip = get_diplomacy()
                for other_n in self.nations:
                    if other_n.name == player_nat_name:
                        continue
                    rel = dip.get_relation(player_nat_name, other_n.name)
                    treaties = dip.get_active_treaties(player_nat_name, other_n.name)
                    status_str = "Neutral"
                    if rel >= 0.6: status_str = "Allied"
                    elif rel >= 0.2: status_str = "Cordial"
                    elif rel <= -0.6: status_str = "Hostile / War"
                    elif rel <= -0.2: status_str = "Strained"

                    diplo_list.append({
                        'nation': other_n.name,
                        'relation': round(float(rel), 2),
                        'status': status_str,
                        'treaties': [t.treaty_type for t in treaties if getattr(t, 'status', 'active') == 'active'],
                        'flag_color': next((m['flag_color'] for m in nations_summary if m['name'] == other_n.name), '#38bdf8'),
                        'gdp': next((m['gdp'] for m in nations_summary if m['name'] == other_n.name), 0.0),
                        'pop': next((m['population'] for m in nations_summary if m['name'] == other_n.name), 0)
                    })
            except Exception as e:
                print(f"[SimServer] Diplo serialize note: {e}")

            # Science Tech Tree & National Resources
            science_tree = []
            resources_list = []
            try:
                innov = get_innovation_system()
                bounties = {b.tech_id: b.bounty_amount for b in innov.active_bounties if b.nation_name == player_nat_name}
                for tid, tech in TECH_CATALOG.items():
                    is_mastered = innov.has_tech(player_nat_name, tid)
                    has_bounty = tid in bounties
                    prereqs = getattr(tech, 'required_techs', [])
                    can_research = all(innov.has_tech(player_nat_name, req) for req in prereqs)

                    st = "locked"
                    if is_mastered: st = "mastered"
                    elif has_bounty: st = "bounty_active"
                    elif can_research: st = "unlocked"

                    c_class = getattr(tech, 'complexity_class', getattr(tech, 'era', 1))
                    max_s_tier, max_s_xp = COMPLEXITY_STEAL_CAPS.get(c_class, (3, 65.0))
                    g_block = innov.get_guild_blockade(player_nat_name, tid)
                    avenues_list = [
                        {
                            'id': av.avenue_id,
                            'name': av.name,
                            'crisis': av.crisis_label,
                            'prototype': av.prototype_building,
                        }
                        for av in getattr(tech, 'discovery_avenues', [])
                    ]

                    science_tree.append({
                        'id': tech.tech_id,
                        'name': tech.name,
                        'domain': tech.domain.value if hasattr(tech.domain, 'value') else str(tech.domain),
                        'era': getattr(tech, 'era', 1),
                        'complexity_class': int(c_class),
                        'max_steal_tier': int(max_s_tier),
                        'max_steal_xp': float(max_s_xp),
                        'tier': innov.get_tech_tier(player_nat_name, tid),
                        'refinement_xp': round(innov.get_refinement_xp(player_nat_name, tid), 1),
                        'subsidy_mode': innov.get_subsidy_mode(player_nat_name, tid),
                        'engineering': innov.engineering_status(player_nation, tid, self.turn) if player_nation else None,
                        'adoption_options': innov.adoption_options(player_nation, tid) if player_nation else [],
                        'prototype_recipe': f'{tid}_prototype',
                        'guild_blockade': g_block,
                        'incumbent_guild': getattr(tech, 'incumbent_guild', ''),
                        'protectionist_law': getattr(tech, 'protectionist_law', ''),
                        'avenues': avenues_list,
                        'description': tech.description,
                        'productivity_effects': [{'good': Goods(good).name,
                            'frontier_multiplier': value} for good, value in tech.production_modifiers.items()],
                        'source_urls': list(getattr(tech, 'source_urls', ())),
                        'base_xp': float(tech.base_xp_required),
                        'status': st,
                        'prerequisites': list(prereqs),
                        'unlocked_buildings': list(getattr(tech, 'unlocked_buildings', [])),
                        'bounty_amount': bounties.get(tid, 300.0)
                    })

                # Extract regional resources for nation
                if player_nation:
                    res_set = set()
                    for t in player_nation.tiles:
                        for res in getattr(t, 'natural_resources', []):
                            res_set.add(res if isinstance(res, str) else getattr(res, 'name', str(res)))
                    resources_list = sorted(list(res_set))
            except Exception as e:
                print(f"[SimServer] Science serialize note: {e}")

            # Sovereign Debt State (Domestic + Foreign Portfolio)
            sovereign_debt_data = {
                'rating': active_macro.get('credit_rating', 'BBB'),
                'yield_rate': active_macro.get('bond_yield', 0.18),
                'public_debt': active_macro.get('public_debt', 0.0),
                'offerings': [],
                'foreign_portfolio': [],
                'available_foreign_bonds': []
            }
            try:
                market = get_bond_market()
                for off in getattr(market, 'offerings', []):
                    if off.issuer_nation == player_nat_name and off.status in ('announced', 'live'):
                        sovereign_debt_data['offerings'].append({
                            'id': off.offering_id,
                            'principal': float(off.principal),
                            'duration': int(off.duration_turns),
                            'coupon_rate': round(float(off.coupon_rate)*100, 2),
                            'status': off.status
                        })
                    elif off.issuer_nation != player_nat_name and off.status in ('announced', 'live'):
                        sovereign_debt_data['available_foreign_bonds'].append({
                            'id': off.offering_id,
                            'issuer': off.issuer_nation,
                            'principal': float(off.principal),
                            'duration': int(off.duration_turns),
                            'coupon_rate': round(float(off.coupon_rate)*100, 2)
                        })
                for b in getattr(market, 'active_bonds', []):
                    if getattr(b, 'holder_nation', None) == player_nat_name and b.issuer_nation != player_nat_name:
                        sovereign_debt_data['foreign_portfolio'].append({
                            'id': b.bond_id,
                            'issuer': b.issuer_nation,
                            'principal': float(b.principal),
                            'duration': int(b.duration),
                            'coupon_rate': round(float(b.coupon_rate)*100, 2),
                            'turns_remaining': max(0, int(b.maturity_turn - self.turn))
                        })
            except Exception:
                pass

            # Military Suite
            armies_data = []
            if player_nation:
                for a in getattr(player_nation, 'armies', []):
                    armies_data.append({
                        'id': getattr(a, 'unit_id', 'Army'),
                        'soldiers': int(getattr(a, 'soldiers', 0)),
                        'strength': round(float(getattr(a, 'strength', 1.0)), 1),
                        'morale': round(float(getattr(a, 'morale', 1.0)), 2),
                        'xp': round(float(getattr(a, 'veteran_xp', 0.0)), 1)
                    })

            # 6-Tab Comparison Accounts Suite
            # 6-Tab Comparison Accounts Suite
            comparison_suite = {
                'tab1_macro': {'by_country': nations_summary, 'by_province': [], 'by_tile': []},
                'tab2_goods': {'by_country': [], 'by_province': [], 'by_tile': []},
                'tab3_forex': {'banking': [], 'fx_matrix': {}},
                'tab4_extraction': {'by_country': [], 'by_province': [], 'by_tile': []},
                'tab5_protest': {'by_country': [], 'by_province': [], 'by_tile': []},
                'tab6_ecology': {'by_country': [], 'by_province': [], 'by_tile': []}
            }
            try:
                def _safe_l(lst, d=0.0):
                    return lst[-1] if (lst is not None and len(lst) > 0) else d

                def _protest_row(name, regions):
                    energy = (sum(_safe_l(getattr(tile, 'protest_energy_log', None), 0.0)
                                  for tile in regions) / max(1, len(regions)))
                    return {'name': name, 'unrest': round(energy, 2),
                            'metric_id': 'politics.protest_energy',
                            **grievance_breakdown(regions)}

                for n in self.nations:
                    m = next((nm for nm in nations_summary if nm['name'] == n.name), {})
                    c_tiles = getattr(n, 'tiles', [])

                    # Country Goods
                    c_food_q = round(sum(_safe_l(t.production_log.get(Goods.food), 0.0) for t in c_tiles), 1)
                    c_wood_q = round(sum(_safe_l(t.production_log.get(Goods.wood), 0.0) for t in c_tiles), 1)
                    c_furn_q = round(sum(_safe_l(t.production_log.get(Goods.furniture), 0.0) for t in c_tiles), 1)
                    c_food_p = round(sum(_safe_l(t.price_log.get(Goods.food), 1.0) for t in c_tiles) / max(1, len(c_tiles)), 2)
                    c_inv = round(sum(sum(_safe_l(t.inventory_log.get(g), 0.0) for g in (Goods.food, Goods.wood, Goods.furniture)) for t in c_tiles), 1)
                    comparison_suite['tab2_goods']['by_country'].append({
                        'province': n.name, 'nation': n.name,
                        'food_output': c_food_q, 'wood_output': c_wood_q, 'furniture_output': c_furn_q,
                        'food_price': c_food_p, 'stockpiles': c_inv
                    })

                    # Country Forex
                    bank_dep = sum(sum(b.deposits.values()) for t in c_tiles if hasattr(t, 'bank') for b in [t.bank])
                    comparison_suite['tab3_forex']['banking'].append({
                        'name': n.name, 'province': n.name, 'nation': n.name,
                        'currency': getattr(n, 'currency', 'USD'),
                        'neer': None,
                        'reserves': None,
                        'deposits': round(float(bank_dep), 0),
                        'liquidity': None
                    })

                    # Country Extraction
                    c_trib = sum(_safe_l(getattr(t, 'tribute_collected_log', None), 0.0) for t in c_tiles)
                    c_rent = sum(_safe_l(getattr(t, 'rent_collected_log', None), 0.0) for t in c_tiles)
                    c_sv = sum(_safe_l(getattr(t, 'surplus_value_log', None), 0.0) for t in c_tiles)
                    c_sv_rate = (sum(_safe_l(getattr(t, 'rate_of_exploitation_log', None), 0.0) for t in c_tiles) / max(1, len(c_tiles))) * 100.0
                    c_tax = sum(sum(t.gov.tax_collected_history[-1:]) if hasattr(t, 'gov') and hasattr(t.gov, 'tax_collected_history') and t.gov.tax_collected_history else 0.0 for t in c_tiles)
                    c_health = (sum(_safe_l(getattr(t, 'health_attrition_log', None), 0.0) for t in c_tiles) / max(1, len(c_tiles))) * 1000.0
                    comparison_suite['tab4_extraction']['by_country'].append({
                        'name': n.name, 'tribute': round(c_trib, 1), 'rent': round(c_rent, 1), 'surplus_value': round(c_sv, 1),
                        'sv_rate': round(c_sv_rate, 1), 'tax': round(c_tax, 1), 'attrition': round(c_health, 1)
                    })

                    # Country Protest
                    comparison_suite['tab5_protest']['by_country'].append(
                        _protest_row(n.name, c_tiles))

                    # Country Ecology
                    avg_f = sum(getattr(t, 'soil_fertility', 1.0) for t in c_tiles) / max(1, len(c_tiles)) * 100.0
                    avg_nu = sum(getattr(t, 'nutrition_density', 1.0) for t in c_tiles) / max(1, len(c_tiles)) * 100.0
                    avg_sm = sum(getattr(t, 'pollution_air', 0.0) for t in c_tiles) / max(1, len(c_tiles))
                    tot_inf = sum(sum(c.get('malnutrition', 0) + c.get('waterborne', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in c_tiles)
                    comparison_suite['tab6_ecology']['by_country'].append({
                        'name': n.name, 'soil_fertility': round(avg_f, 1), 'nutrition': round(avg_nu, 1),
                        'smog': round(avg_sm, 1), 'infections': tot_inf
                    })

                    # Provinces & Tiles Drilldowns
                    for prov in getattr(n, 'provinces', []):
                        p_tiles = getattr(prov, 'tiles', [])
                        if not p_tiles: continue

                        pop_prov = sum(t.total_population[-1] if getattr(t, 'total_population', None)
                                       else len(getattr(t, 'agents', [])) for t in p_tiles)
                        gdp_prov = round(sum(_safe_l(getattr(t, 'real_gdp_output_log', None), 0.0) for t in p_tiles), 1)
                        cash_prov = round(prov.gov.agent.cash if hasattr(prov, 'gov') and hasattr(prov.gov, 'agent') else 0.0, 1)

                        comparison_suite['tab1_macro']['by_province'].append({
                            'name': prov.name, 'nation': n.name, 'regime_type': getattr(n, 'regime_type', 'Monarchy'),
                            'treasury_cash': cash_prov, 'population': pop_prov, 'gdp': gdp_prov,
                            'unrest_stage': protest_band(sum(_safe_l(getattr(t, 'protest_energy_log', None), 0.0)
                                                               for t in p_tiles) / max(1, len(p_tiles))),
                            'credit_rating': m.get('credit_rating', 'BBB'),
                            'treasury_delta': None
                        })

                        p_food_p = round(sum(_safe_l(t.price_log.get(Goods.food), 1.0) for t in p_tiles) / max(1, len(p_tiles)), 2)
                        p_food_q = round(sum(_safe_l(t.production_log.get(Goods.food), 0.0) for t in p_tiles), 1)
                        p_wood_q = round(sum(_safe_l(t.production_log.get(Goods.wood), 0.0) for t in p_tiles), 1)
                        p_furn_q = round(sum(_safe_l(t.production_log.get(Goods.furniture), 0.0) for t in p_tiles), 1)
                        p_inv = round(sum(sum(_safe_l(t.inventory_log.get(g), 0.0) for g in (Goods.food, Goods.wood, Goods.furniture)) for t in p_tiles), 1)
                        comparison_suite['tab2_goods']['by_province'].append({
                            'province': prov.name, 'nation': n.name,
                            'food_output': p_food_q, 'wood_output': p_wood_q, 'furniture_output': p_furn_q,
                            'food_price': p_food_p, 'stockpiles': p_inv
                        })

                        comparison_suite['tab4_extraction']['by_province'].append({
                            'name': prov.name,
                            'tribute': round(sum(_safe_l(getattr(t, 'tribute_collected_log', None), 0.0) for t in p_tiles), 1),
                            'rent': round(sum(_safe_l(getattr(t, 'rent_collected_log', None), 0.0) for t in p_tiles), 1),
                            'surplus_value': round(sum(_safe_l(getattr(t, 'surplus_value_log', None), 0.0) for t in p_tiles), 1),
                            'sv_rate': round(sum(_safe_l(getattr(t, 'rate_of_exploitation_log', None), 0.0) for t in p_tiles) / max(1, len(p_tiles)) * 100.0, 1),
                            'tax': round(sum(sum(t.gov.tax_collected_history[-1:]) if hasattr(t, 'gov') and hasattr(t.gov, 'tax_collected_history') and t.gov.tax_collected_history else 0.0 for t in p_tiles), 1),
                            'attrition': round(sum(_safe_l(getattr(t, 'health_attrition_log', None), 0.0) for t in p_tiles) / max(1, len(p_tiles)) * 1000.0, 1)
                        })

                        comparison_suite['tab5_protest']['by_province'].append(
                            _protest_row(prov.name, p_tiles))

                        comparison_suite['tab6_ecology']['by_province'].append({
                            'name': prov.name,
                            'soil_fertility': round(sum(getattr(t, 'soil_fertility', 1.0) for t in p_tiles) / max(1, len(p_tiles)) * 100.0, 1),
                            'nutrition': round(sum(getattr(t, 'nutrition_density', 1.0) for t in p_tiles) / max(1, len(p_tiles)) * 100.0, 1),
                            'smog': round(sum(getattr(t, 'pollution_air', 0.0) for t in p_tiles) / max(1, len(p_tiles)), 1),
                            'infections': sum(sum(c.get('malnutrition', 0) + c.get('waterborne', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:]) for t in p_tiles)
                        })

                        # City / Tile Level
                        for t in p_tiles:
                            t_pop = t.total_population[-1] if getattr(t, 'total_population', None) else len(getattr(t, 'agents', []))
                            t_gdp = round(_safe_l(getattr(t, 'real_gdp_output_log', None), 0.0), 1)
                            t_cash = round(t.gov.agent.cash if hasattr(t, 'gov') and hasattr(t.gov, 'agent') else 0.0, 1)

                            comparison_suite['tab1_macro']['by_tile'].append({
                                'name': t.display_name or t.name, 'nation': n.name, 'province': prov.name,
                                'regime_type': getattr(n, 'regime_type', 'Monarchy'),
                                'treasury_cash': t_cash, 'population': t_pop, 'gdp': t_gdp,
                                'unrest_stage': protest_band(_safe_l(getattr(t, 'protest_energy_log', None), 0.0)),
                                'credit_rating': m.get('credit_rating', 'BBB'),
                                'treasury_delta': None
                            })

                            comparison_suite['tab2_goods']['by_tile'].append({
                                'province': f"{t.display_name or t.name} ({prov.name})", 'nation': n.name,
                                'tile_id': t.name,
                                'food_output': round(_safe_l(t.production_log.get(Goods.food), 0.0), 1),
                                'wood_output': round(_safe_l(t.production_log.get(Goods.wood), 0.0), 1),
                                'furniture_output': round(_safe_l(t.production_log.get(Goods.furniture), 0.0), 1),
                                'food_price': round(_safe_l(t.price_log.get(Goods.food), 1.0), 2),
                                'stockpiles': round(sum(_safe_l(t.inventory_log.get(g), 0.0) for g in (Goods.food, Goods.wood, Goods.furniture)), 1)
                            })

                            comparison_suite['tab4_extraction']['by_tile'].append({
                                'name': t.display_name or t.name,
                                'tribute': round(_safe_l(getattr(t, 'tribute_collected_log', None), 0.0), 1),
                                'rent': round(_safe_l(getattr(t, 'rent_collected_log', None), 0.0), 1),
                                'surplus_value': round(_safe_l(getattr(t, 'surplus_value_log', None), 0.0), 1),
                                'sv_rate': round(_safe_l(getattr(t, 'rate_of_exploitation_log', None), 0.0) * 100.0, 1),
                                'tax': round(sum(t.gov.tax_collected_history[-1:]) if hasattr(t, 'gov') and hasattr(t.gov, 'tax_collected_history') and t.gov.tax_collected_history else 0.0, 1),
                                'attrition': round(_safe_l(getattr(t, 'health_attrition_log', None), 0.0) * 1000.0, 1)
                            })

                            comparison_suite['tab5_protest']['by_tile'].append(
                                _protest_row(t.display_name or t.name, [t]))

                            comparison_suite['tab6_ecology']['by_tile'].append({
                                'name': t.display_name or t.name,
                                'soil_fertility': round(getattr(t, 'soil_fertility', 1.0) * 100.0, 1),
                                'nutrition': round(getattr(t, 'nutrition_density', 1.0) * 100.0, 1),
                                'smog': round(getattr(t, 'pollution_air', 0.0), 1),
                                'infections': sum(c.get('malnutrition', 0) + c.get('waterborne', 0) for c in getattr(t, 'disease_cases_log', [{}])[-1:])
                            })

                # FX bilateral matrix
                fx_m = {}
                for n1 in self.nations:
                    c1 = getattr(n1, 'currency', n1.name[:3].upper())
                    fx_m[c1] = {}
                    for n2 in self.nations:
                        c2 = getattr(n2, 'currency', n2.name[:3].upper())
                        if c1 == c2:
                            fx_m[c1][c2] = 1.0
                            continue
                        desks = [desk for tile in n1.tiles
                                 for desk in getattr(tile, 'forex_desks', {}).values()
                                 if getattr(desk, 'home', None) == c1
                                 and getattr(desk, 'other', None) == c2]
                        fx_m[c1][c2] = (sum(desk.mid for desk in desks) / len(desks)) if desks else None
                comparison_suite['tab3_forex']['fx_matrix'] = fx_m

            except Exception as e:
                print(f"[SimServer] Comparison suite serialize note: {e}")

            x0, y0, x1, y1 = self.bbox
            from world_config import is_voronoi_topology
            is_voronoi = getattr(self, 'topology', None) == 'voronoi' or is_voronoi_topology()
            from render_engine.camera import MAP_PAD_RATIO
            pad_ratio = 0.0 if is_voronoi else MAP_PAD_RATIO
            pad_x = (x1 - x0) * pad_ratio
            pad_y = (y1 - y0) * pad_ratio
            terrain_bounds = {
                'min_x': float(x0 - pad_x),
                'min_y': float(y0 - pad_y),
                'max_x': float(x1 + pad_x),
                'max_y': float(y1 + pad_y),
                'width': float((x1 - x0) + 2.0 * pad_x),
                'height': float((y1 - y0) + 2.0 * pad_y),
                'hex_size': float(getattr(self, 'hex_size', 50.0)),
                'pad_ratio': float(pad_ratio),
            }

            return {
                'topology': 'voronoi' if is_voronoi else 'hex',
                'turn': self.turn,
                'playing': self.playing,
                'is_playing': self.playing,
                'seed': self.seed,
                'terrain_seed': self.terrain_seed,
                'nation_seed': self.nation_seed,
                'gameplay_profile': self.gameplay_profile,
                'gameplay_flags': self.gameplay_flags.as_dict(),
                'gameplay_flags_version': GAMEPLAY_FLAGS_VERSION,
                'elite_planning': self.elite_planning_config.as_dict(),
                'hex_size': float(getattr(self, 'hex_size', 50.0)),
                'bbox': [float(v) for v in self.bbox],
                'terrain_bounds': terrain_bounds,
                'player_nation': player_nat_name,
                'production_programs_allowed': self.scenario_id != 'labor_frontier_rivalry',
                'macro': active_macro,
                'history': history_data,
                'nations': nations_summary,
                'tiles': tiles_data,
                'build_recipes': build_recipes,
                'diplomacy': diplo_list,
                'science_tree': science_tree,
                'resources': resources_list,
                'sovereign_debt': sovereign_debt_data,
                'armies': armies_data,
                'comparison_suite': comparison_suite,
                'progress_suite': self._collect_progress_suite(),
                'seasonal_info': self._calc_seasonal_info(),
                'trade_network': self._collect_trade_network(),
                'scenario_info': self._collect_scenario_info(),
                'ticker_events': list(self._ticker_events[-35:]),
            }
