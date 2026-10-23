"""
micro/region/core.py — Region class definition and subsystem orchestration.
"""

from __future__ import annotations
from treasury_composition import traced_membership_mutation
import copy
import random
from collections import defaultdict
from typing import Optional, List, Dict, Tuple, Any

from goods import Goods
from econsim_states import recipes, goods
from logger import loginfo
from agent import Agent, initialize_agent, seed_traits
from province import make_bundle
from faction import FactionSystem
from land_tenure import TileTenure, LandPlot, TenureStatus
from micro.region.helpers import (
    DEFAULT_PROFESSION_DISTRIBUTION,
    MAX_AGENTS,
    count_agents,
    compute_gini,
    get_total_cash,
)
import micro.region.stepper as _stepper

# Subsystem modules
import region_labor as _labor
import region_production as _prod
import region_market as _market
import region_finance as _fin
import region_logistics as _logistics
import region_factions as _factions
import region_plotting as _plot

class Region:
    """A self-contained region with its own government, bank, agents, and logs."""

    # Urgency & margin constants referenced by market module
    ASK_URGENCY_MIN = 0.7
    ASK_URGENCY_MAX = 1.8
    IMPORT_MARGIN_MIN = 0.05
    IMPORT_MARGIN_MAX = 0.10

    def __init__(self, name: str, t: int, number_of_agents: int = 110,
                 profession_distribution: dict = None, number_of_traders: int = None,
                 transport_delay: int = 1,
                 terrain: dict = None, climate: str = 'temperate',
                 wilderness: bool = False, wilderness_pop: int = None,
                 institutions=None, seat_gov=True):
        self.name = name
        self.wilderness = wilderness
        if wilderness:
            self.wilderness_pop = (random.randint(0, 50) if wilderness_pop is None
                                   else int(wilderness_pop))
        else:
            self.wilderness_pop = 0
        self.home_currency = name
        if wilderness:
            self.home_currency = None
        self.agents: list = []
        self.max_agents = MAX_AGENTS
        self.transport_delay = transport_delay
        self.terrain = terrain if terrain is not None else {}
        self.climate = climate
        self.col_multiplier = 1.2 if climate == 'cold' else 1.0
        if profession_distribution is None:
            profession_distribution = dict(DEFAULT_PROFESSION_DISTRIBUTION)
        self.profession_distribution = profession_distribution.copy()
        if number_of_traders is None:
            number_of_traders = 3
        self._number_of_traders = number_of_traders
        self.route = None
        self.neighbors = {}
        self.routes = {}
        self.forex_desks = {}
        self.owner_nation = None
        self.claims = {}
        self.buildings: list = []
        self.construction_projects: list = []
        self.elevation: float = 0.0
        self.elevation_meters: int = 0
        self.biome: str = 'plains'
        self.terrain_color: tuple = (65, 135, 75)
        self.hillshade: float = 1.0

        # Land tenure: feudal plots with customary rights (P1)
        self.tenure = TileTenure()
        self.tenure_log: list = []  # time-series of commons_access
        self.social_class_log: list = []  # time-series of class distribution
        self.food_foraged_log: list = []  # time-series of total food foraged
        self.food_purchased_log: list = []  # time-series of total food bought
        self.rent_collected_log: list = []  # time-series of cash rent collected
        self.rent_arrears_log: list = []  # time-series of rent unpaid
        self.enclosure_survey_debts: list = []  # active statutory survey debts
        self.workhouse_inmates_log: list = []  # time-series of workhouse inmate count
        self.pasture_fraction_log: list = []  # time-series of pasture fraction
        self.vagrancy_law_active: bool = False
        self.labor_laws: dict = {}
        self.labor_law_petitions: list = []
        self._next_law_petition_id: int = 1
        self.labor_law_events: list = []
        self.government_legitimacy: float = 0.5
        self.access_rights: dict = {}
        self._access_rights_seeded: bool = False
        self.access_events: list = []
        self.cash_obligations: list = []
        self._next_obligation_id: int = 1
        self.obligation_events: list = []
        # Corporation collective bargaining; entries use stable person/firm IDs.
        # The event sequence is retained for deterministic run reconstruction.
        self.collective_organizations: dict = {}
        self.collective_log: list = []
        self._next_collective_event_id: int = 1
        self.tenancy_agreements: list = []
        self.offtake_contracts: list = []
        self.offtake_events: list = []
        self._next_offtake_id: int = 1
        self.land_leases: list = []
        self.land_transfer_events: list = []
        self.water_rights: list = []
        self.water_rights_initialized: bool = False
        self.water_source_capacity: float = 0.0
        self.water_allocations: dict = {}
        self.water_allocation_events: list = []
        self.water_right_events: list = []
        self.market_charters: list = []
        self.market_trade_events: list = []
        self.concession_petitions: list = []
        self.concession_events: list = []
        self._next_concession_id: int = 1
        self.concession_enforcement: float = 0.65
        self.enforcement_cases: list = []
        self._next_case_id: int = 1
        self.production_receipts: list = []
        self.lien_events: list = []
        self.crop_share_events: list = []
        self.cash_tax_per_person: float = 0.0
        self.police_employed: int = 0
        self.workhouse_last_step_turn: int = -1
        self.labor_scheduler_last_turn: int = -1
        self.labor_decision_log: list = []
        self.forced_labor_hours: float = 0.0

        # P2: Labor commodification & surplus value
        self.workday_cap: float = 16.0  # legal maximum shift hours (defaults to unrestricted)
        self.safety_mandate: float = 0.0  # legal minimum safety spend per worker
        self.avg_shift_hours_log: list = []  # time-series of avg shift hours
        self.workday_cap_log: list = []  # effective legal workday cap used this turn
        self.surplus_value_log: list = []  # time-series of total surplus value extracted ($)
        self.rate_of_exploitation_log: list = []  # time-series of s/v exploitation rate
        self.entertainment_level: float = 0.0  # commercial/state entertainment pacifier
        self.avg_alienation_log: list = []  # time-series of avg 4D alienation (0-1)
        self.avg_health_attrition_log: list = []  # time-series of avg bodily wear & tear
        self.avg_consciousness_log: list = []  # time-series of worker class consciousness
        self.workplace_accidents_log: list = []  # time-series of disabling factory accidents
        self.entertainment_log: list = []  # time-series of entertainment investment
        self.strikers_log: list = []  # time-series of active striking workers
        self.broken_machinery_log: list = []  # time-series of broken factory machines
        self.sabotage_log: list = []  # time-series of machines sabotaged this turn
        self.tribute_collected_log: list = []  # time-series of in-kind tribute extracted ($ value)
        self.tax_distribution_log: list = []  # time-series of multi-tier tax splits {total, municipal, provincial, national}
        self.grievance_sources_log: list = []  # time-series of grievance source breakdowns

        # P3: Metabolic Rift & Externalities Engine
        self.soil_fertility: float = 1.0  # [0.20, 1.50], baseline 1.0 (degrades with monoculture)
        self.nutrition_density: float = 1.0  # [0.50, 1.0], baseline 1.0 (degrades with synthetic fertilizers)
        self.pollution_air: float = 0.0  # [0.0, 100.0], atmospheric smog/particulates
        self.pollution_water: float = 0.0  # [0.0, 100.0], industrial & nitrate river effluent
        self.pollution_soil: float = 0.0  # [0.0, 100.0], pesticide toxicity & chemical sludge
        self.use_fertilizer: bool = False  # municipal/landlord mandate for chemical fertilizers
        self.use_pesticides: bool = False  # municipal/landlord mandate for chemical pesticides
        self.fertilizer_stock: float = 12.0  # physical tons of chemical/mineral nitrate reserves
        self.fertilizer_consumed_last_turn: float = 0.0
        self.fertilizer_inflow_last_turn: float = 0.0
        self.is_nitrate_depleted: bool = False  # True during Turnip Winter harvest collapse
        self.fertilizer_rationing: bool = False  # wartime emergency rationing decree
        self.soil_fertility_log: list = []  # time-series of soil fertility
        self.nutrition_density_log: list = []  # time-series of food nutrition density
        self.pollution_air_log: list = []  # time-series of air pollution
        self.pollution_water_log: list = []  # time-series of water pollution
        self.pollution_soil_log: list = []  # time-series of soil toxicity
        self.disease_cases_log: list = []  # time-series of active disease cases by type
        self.medical_spending_private_log: list = []  # private out-of-pocket medical bills ($)
        self.medical_spending_public_log: list = []  # public healthcare subsidies ($)
        self.untreated_cases_log: list = []  # impoverished sick cases unable to pay
        self.disease_fatalities_log: list = []  # disease risk crossed the death threshold
        self.disease_fatalities_this_turn: int = 0
        self.infant_fatalities_this_turn: int = 0
        self.infant_fatalities_log: list = []
        self.deaths_this_turn: int = 0
        self.deaths_by_cause_this_turn: dict = {}
        self.granary_stock: float = 25.0  # physical buffer stock smoothing seasonal harvests
        self.farming_regime: str = 'rotation'  # 'rotation' (Four-Field) | 'intensive' (Monoculture) | 'feudal'
        self.public_healthcare_decree: bool = False  # municipal healthcare mandate

        self.recipes = copy.deepcopy(recipes)
        self.goods = list(goods)

        self.province = None
        self._seat_gov_agent = bool(seat_gov)
        if institutions is not None:
            self._institutions = institutions
        else:
            self._institutions = make_bundle(name, self.recipes, t=t,
                                             initial_cash=200.0,
                                             wilderness=wilderness)

        # Logging state
        self.population_log: dict = {}
        self.inventory_log: dict = {}
        self.hungry_log: dict = {}
        self.production_log: dict = {}
        self.demand_ratio_log: dict = {}
        # Turn-aligned chart copy; demand_ratio_log remains the sparse history
        # consumed by AI systems that only act when a market clears.
        self.market_demand_ratio_chart_log: dict = {}
        self.market_chart_goods = {
            Goods.food, Goods.wood, Goods.furniture, Goods.transport}
        self.supply_log: dict = {}
        self.demand_log: dict = {}
        self.per_capita_inventory: dict = {}
        self.cash_log: dict = {}
        self.gini_log: dict = {}
        self.total_cash_log: list = []
        self.bank_cash_log: list = []
        self.price_log: dict = {g: [] for g in self.goods}
        self.sold_log: dict = {g: [] for g in self.goods}
        self.bought_log: dict = {}
        self.gdp_log: list = []
        self.gdp_by_profession_log: dict = {g: [] for g in self.goods}
        self.total_population: list = []
        self.population_change_rate_log: list = []
        self.dead_pop: list = [0]
        self.dead_starved_population: list = [0]

        # Trade logging
        self.export_vol: dict = {}
        self.export_val: dict = {}
        self.import_vol: dict = {}
        self.import_val: dict = {}
        self.export_value_log: list = []
        self.import_value_log: list = []
        self.net_trade_value_log: list = []
        self.trade_balance_log: list = []
        self.pipeline_depth_log: list = []
        self.trader_cash_log: list = []
        self.price_spread_log: dict = {}
        self.destination_region = None
        self.exchange_rate = 1.0
        self.exchange_rate_log = []
        self.trade_flow_log = []
        self.cumulative_trade_balance = 0.0
        self.foreign_reserves_log = []
        self.migration_intent_log = []
        self.forage_log = []
        self.settlement_log = []

        # Factions & Unrest
        self.factions = FactionSystem()
        self.faction_support_log = []
        if not wilderness:
            self._build_identity_factions()
        self.protest_energy_log = []
        self.faction_grievance_log = []
        self.unrest_log = []
        self.unrest_flag = False

        for g in self.goods:
            self.export_vol[g] = []
            self.price_spread_log[g] = []
            self.export_val[g] = []
            self.import_vol[g] = []
            self.import_val[g] = []

        for g in self.goods:
            self.population_log[g] = []
            self.hungry_log[g] = []
            if g != Goods.gov:
                self.demand_ratio_log[g] = []
                self.market_demand_ratio_chart_log[g] = []
                self.demand_log[g] = []
                self.supply_log[g] = []
                self.inventory_log[g] = []
                self.per_capita_inventory[g] = []
                self.production_log[g] = []
        self.population_log['trader'] = []
        self.hungry_log['trader'] = []
        self.inventory_log['trader'] = []
        self.per_capita_inventory['trader'] = []
        self.production_log['trader'] = []

        for g in self.goods:
            self.cash_log[g] = []
            self.gini_log[g] = []
        self.cash_log['trader'] = []
        self.gini_log['trader'] = []
        self.gdp_by_profession_log['trader'] = []

        for prof in self.goods:
            self.bought_log[prof] = {}
            for g in self.goods:
                self.bought_log[prof][g] = [0]
        self.bought_log['trader'] = {}
        for g in self.goods:
            self.bought_log['trader'][g] = [0]

        self.cost_of_living = 11.25
        self.cost_of_living_log = []
        self.food_price = 1.0
        self.all_goods_price = 3.0
        self.trader_agents = []

        self.pending_imports = {}
        self._auction_import_sales = {}
        self._price_ref = {g: max(0.1, self.recipes[g].get('price', 1.0))
                           for g in self.goods
                           if g != Goods.gov and g != Goods.transport}
        self._trade_prices = defaultdict(list)

        if not wilderness:
            self._create_agents(t, number_of_agents)
            self._register_citizens()

    # ------------------------------------------------------------------
    # Institutions (v3 province model)
    # ------------------------------------------------------------------

    @property
    def bank(self):
        if getattr(self, '_institutions', None) is None:
            return None
        bank = self._institutions.bank
        if bank is not None:
            attached = getattr(bank, '_attached_regions', None)
            if attached is None:
                attached = []
                bank._attached_regions = attached
            if all(r is not self for r in attached):
                attached.append(self)
        return bank

    @bank.setter
    @traced_membership_mutation
    def bank(self, value):
        if getattr(self, '_institutions', None) is None:
            return
        self._institutions.bank = value

    @property
    def gov(self):
        if getattr(self, '_institutions', None) is None:
            return None
        return self._institutions.gov

    @gov.setter
    @traced_membership_mutation
    def gov(self, value):
        if getattr(self, '_institutions', None) is None:
            return
        self._institutions.gov = value

    @property
    def charity(self):
        if getattr(self, '_institutions', None) is None:
            return None
        return self._institutions.charity

    @charity.setter
    def charity(self, value):
        if getattr(self, '_institutions', None) is None:
            return
        self._institutions.charity = value

    # ------------------------------------------------------------------
    # Agent creation & registration
    # ------------------------------------------------------------------

    def _create_agents(self, t: int, n: int):
        """Create a feudal starting population: lords, serfs, artisans, traders.

        Lords (~3%) hold feudal title over the tile, collect in-kind tribute.
        Serfs (~90%) are the working population who depend on commons access.
        Artisans (~5%) are skilled crafts workers with moderate wealth.
        Traders (per existing logic) handle inter-tile commerce.
        """
        agents = []

        # ---- Lords: ~3% of population, wealthy, hold feudal title ----
        n_lords = max(1, int(n * 0.03))
        lord_fraction = 1.0 / n_lords
        for i in range(n_lords):
            lord = Agent(t)
            initialize_agent(lord, Goods.gov, 10, 2, 500 + random.randint(0, 300))
            seed_traits(lord)
            lord.is_lord = True
            lord.ambition = max(lord.ambition, 0.6)
            lord.founding_age_offset = 25 + ((int(lord.id) * 19) % 35)
            lord.region = self.name
            lord._bank_ref = self.bank
            lord.home_currency = self.home_currency
            from world_names import get_plot_name
            c_name = getattr(self, 'nation_display', 'Britain') or 'Britain'
            p_name = get_plot_name(c_name)
            plot = LandPlot(
                plot_id=f"{self.name}-lord-{i}",
                name=p_name,
                tile_name=self.name,
                lord_id=lord.id,
                fraction=lord_fraction,
                tenure=TenureStatus.FEUDAL,
                tribute_rate=0.5,
            )
            lord.land_plots = [plot.plot_id]
            self.tenure.add_plot(plot)
            agents.append(lord)

        # ---- Serfs: ~90% of population, poor, depend on commons ----
        n_serfs = n - n_lords - max(1, int(n * 0.05))
        serf_prof_counts = {}
        serf_total = 0
        for prof, fraction in self.profession_distribution.items():
            count = int(n_serfs * fraction)
            serf_prof_counts[prof] = count
            serf_total += count
        # Remaining serfs assigned to food production
        serf_prof_counts[Goods.food] = serf_prof_counts.get(Goods.food, 0) + max(0, n_serfs - serf_total)

        plot_list = self.tenure.plots
        plot_count = len(plot_list)
        serf_idx = 0
        for prof, count in serf_prof_counts.items():
            for _ in range(count):
                serf = Agent(t)
                cash = 40 + random.randint(0, 40)
                initialize_agent(serf, prof, 10, 2, cash)
                seed_traits(serf)
                serf.founding_age_offset = 18 + ((int(serf.id) * 17) % 38)
                serf.region = self.name
                serf._bank_ref = self.bank
                serf.home_currency = self.home_currency
                if plot_count > 0:
                    assigned_plot = plot_list[serf_idx % plot_count]
                    serf.assigned_plot_id = assigned_plot.plot_id
                    assigned_plot.tenant_ids.append(serf.id)
                    serf_idx += 1
                agents.append(serf)

        # ---- Artisans: ~5%, moderate wealth, skilled crafts ----
        n_artisans = max(1, int(n * 0.05))
        artisan_profs = [Goods.wood, Goods.furniture]
        for j in range(n_artisans):
            artisan = Agent(t)
            prof = artisan_profs[j % len(artisan_profs)]
            initialize_agent(artisan, prof, 10, 2, 100 + random.randint(0, 50))
            seed_traits(artisan)
            artisan.productivity = max(artisan.productivity, 0.6)
            artisan.founding_age_offset = 24 + ((int(artisan.id) * 13) % 34)
            artisan.region = self.name
            artisan._bank_ref = self.bank
            artisan.home_currency = self.home_currency
            agents.append(artisan)

        n_created = len(agents)
        loginfo(t, f"Region '{self.name}' feudal pop: {n_lords} lords, "
                   f"{n_serfs} serfs, {n_artisans} artisans = {n_created}")

        # ---- Traders (unchanged from existing logic) ----
        trader_goods = [Goods.food, Goods.wood, Goods.furniture]
        for trade_good in trader_goods:
            for _ in range(self._number_of_traders):
                trader = Agent(t)
                trader.is_trader = True
                trader.output = Goods.food
                trader.trade_good = trade_good
                seed_traits(trader)
                trader.founding_age_offset = 22 + ((int(trader.id) * 11) % 34)
                trader.home_region = self.name
                trader.region = self.name
                trader.cash = 200.0
                trader._bank_ref = self.bank
                trader.home_currency = self.home_currency
                for g in Goods:
                    if g == Goods.none:
                        continue
                    trader.inventory[g.value] = 0
                trader.inventory[Goods.food.value] = 4
                agents.append(trader)
                self.trader_agents.append(trader)

        # ---- Government agent (unchanged) ----
        if self._seat_gov_agent:
            agents.append(self.gov.agent)
            self.gov.agent.region = self.name
            self.gov.agent._bank_ref = self.bank
            self.gov.agent.home_currency = self.home_currency
        self.agents = agents
        from livelihood_access import seed_access_rights
        seed_access_rights(self)

    def _register_citizens(self):
        for agent in self.agents:
            if agent != self.gov.agent:
                self.gov._add_citizen(agent)

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Stepper and Lifecycle Delegations
    # ------------------------------------------------------------------

    def step(self, t: int):
        """Main step: delegates wilderness tiles or runs full economy."""
        if self.wilderness:
            import wilderness as _wd
            _wd.step_wilderness(self, t)
            return
        self.step_economy(t)

    def step_economy(self, t: int):
        """Per-tile economy and institutional flows."""
        return _stepper.step_economy(self, t)

    def _audit_cash(self, t, label):
        return _stepper.audit_cash(self, t, label)

    def _record_start(self):
        return _stepper.record_start(self)

    def _record_delta(self):
        return _stepper.record_delta(self)

    def _total_cash(self):
        return _stepper.total_cash(self)

    def _live(self, t):
        return _stepper.live(self, t)

    def _log_gdp(self):
        return _stepper.log_gdp(self)

    def _log_metrics(self, t):
        return _stepper.log_metrics(self, t)

    def _log_population_rate(self):
        return _stepper.log_population_rate(self)

    # ------------------------------------------------------------------

    def plot(self, filename: str):
        """Generate a 5x4 grid of plots for this region."""
        _plot.plot_region(self, filename)

    # ------------------------------------------------------------------
    # Backward-compatible Delegation Methods
    # ------------------------------------------------------------------

    def terrain_bonus(self, good):
        return _prod.terrain_bonus(self, good)

    def _produce(self, t):
        return _prod.produce(self, t)

    def _produce_corporation(self, agent, recipe, output, num_agents_per_good, local_total_production):
        return _prod.produce_corporation(self, agent, recipe, output, num_agents_per_good, local_total_production)

    def _produce_independent(self, agent, recipe, output, num_agents_per_good, local_total_production):
        return _prod.produce_independent(self, agent, recipe, output, num_agents_per_good, local_total_production)

    def _run_labour(self, t):
        return _labor.run_labour(self, t)

    def _cleanup(self):
        return _labor.cleanup_labor(self)

    def _borrow_or_layoff(self, t):
        return _labor.borrow_or_layoff(self, t)

    def _incorporate(self, t):
        return _labor.incorporate(self, t)

    def _hire(self, t):
        return _labor.hire_workers(self, t)

    def _adjust_wages(self, t):
        return _labor.adjust_wages(self, t)

    def _trade(self, t):
        return _market.trade(self, t)

    def _decide_borrow_deposit(self, agents, all_goods_price, food_price, t):
        return _market.decide_borrow_deposit(self, agents, all_goods_price, food_price, t)

    def _borrow_food(self, agent, food_price):
        return _market.borrow_food(self, agent, food_price)

    def _borrow_inputs(self, agent):
        return _market.borrow_inputs(self, agent)

    def _deposit_excess(self, agent, all_goods_price):
        return _market.deposit_excess(self, agent, all_goods_price)

    def _gather_bids(self, agents, good, good_price, current_desired):
        total_asks = 0
        total_bids = 0
        for a in agents:
            agent_recipe = self.recipes[a.output]
            is_employee = a.employer is not None
            _market.withdraw_if_needed(self, a, good_price, current_desired)
            mult = a.consumption_multiplier
            bid = _market.calculate_bid(self, a, good, good_price, current_desired, agent_recipe, is_employee, mult)
            a.bid = bid
            a.remainingCash -= a.bid * good_price
            total_bids += a.bid
            ask = _market.calculate_ask(self, a, good, good_price, is_employee)
            a.ask = ask
            total_asks += a.ask
        return total_asks, total_bids

    def _withdraw_if_needed(self, agent, good_price, current_desired):
        return _market.withdraw_if_needed(self, agent, good_price, current_desired)

    def _calculate_bid(self, agent, good, good_price, current_desired, agent_recipe, is_employee, mult):
        return _market.calculate_bid(self, agent, good, good_price, current_desired, agent_recipe, is_employee, mult)

    def _calculate_ask(self, agent, good, good_price, is_employee):
        return _market.calculate_ask(self, agent, good, good_price, is_employee)

    def _input_good(self, agent):
        return _market.input_good(self, agent)

    def _calculate_ask_price(self, agent, good, ref):
        return _market.calculate_ask_price(self, agent, good, ref)

    def _import_ask_price(self, trader, good):
        return _market.import_ask_price(self, trader, good)

    def _update_price_ref(self, good, demand_ratio):
        return _market.update_price_ref(self, good, demand_ratio)

    def _gather_import_pool(self, good):
        return _market.gather_import_pool(self, good)

    def _clear_discriminatory(self, good, ref, total_asks, total_bids, imp_pool, agents, t):
        return _market.clear_discriminatory(self, good, ref, total_asks, total_bids, imp_pool, agents, t)

    def _sell_imports(self, pool, good, price, remaining_qty):
        return _market.sell_imports(self, pool, good, price, remaining_qty)

    def _buy(self, t, good, price, total_asks):
        return _market.legacy_buy(self, t, good, price, total_asks)

    def _sell(self, askers, good, price, t, total_bought, total_cash_purchases):
        return _market.legacy_sell(self, askers, good, price, t, total_bought, total_cash_purchases)

    def _price_decay(self, good):
        return _market.price_decay(self, good)

    def _set_price(self, demand_ratio, good):
        return _market.set_price(self, demand_ratio, good)

    def _calculate_transport_bid(self, agent, transport_price):
        return _market.calculate_transport_bid(self, agent, transport_price)

    def _migration_intent_score(self):
        return _logistics.migration_intent_score(self)

    def add_neighbor(self, other, t=0):
        return _logistics.add_neighbor(self, other, t)

    def _all_routes(self):
        return _logistics.all_routes(self)

    def _repoint_traders(self):
        return _logistics.repoint_traders(self)

    def _transport_cost_per_unit(self):
        return _logistics.transport_cost_per_unit(self)

    def _post_exports_to_route(self):
        return _logistics.post_exports_to_route(self)

    def _liquidation_price(self, good, cost_basis):
        return _logistics.liquidation_price(good, cost_basis)

    def _exit_trader(self, agent):
        return _logistics.exit_trader(self, agent)

    def _give_goods(self, agent, good, qty, price):
        return _logistics.give_goods(agent, good, qty, price)

    def _process_trader_exits(self, t, agents):
        return _logistics.process_trader_exits(self, t, agents)

    def _make_trader_internal(self, agent):
        return _logistics.make_trader_internal(self, agent)

    def _pay_wages(self, t):
        return _fin.pay_wages(self, t)

    def _distribute_profits(self, t):
        return _fin.distribute_profits(self, t)

    def _credit_owner_pay(self, owner, amount):
        return _fin.credit_owner_pay(self, owner, amount)

    def _repay_owner_loan(self, agent, owner, payroll):
        return _fin.repay_owner_loan(self, agent, owner, payroll)

    def _pay_base_salary(self, agent, owner, payroll):
        return _fin.pay_base_salary(self, agent, owner, payroll)

    def _pay_profit_share(self, agent, owner, payroll):
        return _fin.pay_profit_share(self, agent, owner, payroll)

    def _bailout_owner(self, agent, owner, payroll):
        return _fin.bailout_owner(self, agent, owner, payroll)

    def _collect_tax(self, t):
        return _fin.collect_tax(self, t)

    def _recalculate_multipliers(self):
        return _fin.recalculate_multipliers(self)

    def _build_identity_factions(self):
        return _factions.build_identity_factions(self)

    def _refresh_faction_membership(self):
        return _factions.refresh_faction_membership(self)

    def _apply_policy_satisfaction(self):
        return _factions.apply_policy_satisfaction(self)

    def _step_factions(self, t):
        return _factions.step_factions(self, t)

    def _accumulate_grievances(self, t):
        return _factions.accumulate_grievances(self, t)

    @staticmethod
    def _protest_energy(adds):
        return _factions.protest_energy(adds)
