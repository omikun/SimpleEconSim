"""
Shared Region class and helpers for single-region and multi-region simulations.
Orchestrates turn lifecycle and delegates subsystem logic to dedicated modules.
"""

import copy
import math
import random
from collections import defaultdict
from statistics import mean

from goods import Goods, profession
from econsim_states import (
    recipes, goods, probability_birth, probability_death, birth_gap,
    max_career_switches, starvation_limit,
)
from logger import loginfo, logwarning
from agent import Agent, initialize_agent, seed_traits
from province import make_bundle
from random_cache import rand
from faction import FactionSystem

# Subsystem modules
import region_labor as _labor
import region_production as _prod
import region_market as _market
import region_finance as _fin
import region_logistics as _logistics
import region_factions as _factions
import region_plotting as _plot


# =============================================================================
# Initialise recipes (normally done by econsim.py at module load)
# =============================================================================

_recipes_init = {
    Goods.food: {
        'commodity': Goods.food, 'production': 5, 'price': 1, 'numInput': 0,
        'maxtotalprod': 2000, 'maxinv': 20,
    },
    Goods.wood: {
        'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0,
        'maxtotalprod': 3000, 'maxinv': 10,
    },
    Goods.furniture: {
        'commodity': Goods.furniture, 'production': 1, 'input': Goods.wood,
        'numInput': 2, 'price': 25, 'maxtotalprod': 300, 'maxinv': 5,
    },
    Goods.transport: {
        'commodity': Goods.transport, 'production': 1, 'price': 1, 'numInput': 0,
        'maxtotalprod': 1000, 'maxinv': 1, 'capacity': 10,
    },
    Goods.gov: {
        'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1,
        'maxtotalprod': 0, 'maxinv': 0,
    },
}

for _g, _r in _recipes_init.items():
    recipes[_g] = _r

# Default profession distribution (fractions summing to <= 1.0, remainder -> gov)
DEFAULT_PROFESSION_DISTRIBUTION = {
    Goods.food: 0.72,
    Goods.wood: 0.05,
    Goods.furniture: 0.01,
    Goods.transport: 0.08,
}

# =============================================================================
# SoA constant: max pre-allocated slots
# =============================================================================

MAX_AGENTS = 500


# =============================================================================
# Shared helpers
# =============================================================================

def count_agents(agents, good):
    """Number of agents whose output is *good*."""
    return sum(agent.output == good for agent in agents)


def compute_gini(agents, good):
    """Gini coefficient over cash held by agents producing *good*."""
    vals = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(vals)
    if n == 0:
        return 0
    total = sum(vals)
    if total == 0:
        return 0
    weighted_sum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def get_total_cash(agents, bank=None):
    """Total cash in the system: agent cash + bank equity."""
    if bank is None:
        return sum(agent.cash for agent in agents)
    return sum(a.cash for a in agents) + bank.equity


# =============================================================================
# Region class
# =============================================================================

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
        self.supply_log: dict = {}
        self.demand_log: dict = {}
        self.per_capita_inventory: dict = {}
        self.cash_log: dict = {}
        self.gini_log: dict = {}
        self.total_cash_log: list = []
        self.bank_cash_log: list = []
        self.price_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: [], Goods.transport: []}
        self.sold_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: [], Goods.transport: []}
        self.bought_log: dict = {}
        self.gdp_log: list = []
        self.gdp_by_profession_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: [], Goods.transport: []}
        self.total_population: list = []
        self.population_change_rate_log: list = []
        self.dead_pop: list = [0]
        self.dead_starved_population: list = [0]

        # Trade logging
        self.export_vol: dict = {}
        self.export_val: dict = {}
        self.import_vol: dict = {}
        self.import_val: dict = {}
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

        for g in [Goods.food, Goods.wood, Goods.furniture, Goods.transport]:
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
        return self._institutions.bank

    @bank.setter
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
        profession_counts = {}
        total_assignable = 0
        for prof, fraction in self.profession_distribution.items():
            count = int(n * fraction)
            profession_counts[prof] = count
            total_assignable += count
        profession_counts[Goods.gov] = max(0, n - total_assignable)

        loginfo(t, f"Region '{self.name}' profession allocation: { {str(k): v for k, v in profession_counts.items()} }")

        agents = []
        for prof, count in profession_counts.items():
            for _ in range(count):
                agent = Agent(t)
                output = prof
                delta = 20
                cash = 120 + random.randint(-delta, delta)
                initialize_agent(agent, output, 10, 2, cash)
                seed_traits(agent)
                agent.region = self.name
                agent._bank_ref = self.bank
                agent.home_currency = self.home_currency
                agents.append(agent)

        trader_goods = [Goods.food, Goods.wood, Goods.furniture]
        for trade_good in trader_goods:
            for _ in range(self._number_of_traders):
                trader = Agent(t)
                trader.is_trader = True
                trader.output = Goods.food
                trader.trade_good = trade_good
                seed_traits(trader)
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

        if self._seat_gov_agent:
            agents.append(self.gov.agent)
            self.gov.agent.region = self.name
            self.gov.agent._bank_ref = self.bank
            self.gov.agent.home_currency = self.home_currency
        self.agents = agents

    def _register_citizens(self):
        for agent in self.agents:
            if agent != self.gov.agent:
                self.gov._add_citizen(agent)

    # ------------------------------------------------------------------
    # Main step
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
        legacy = getattr(self, 'province', None) is None

        rand.reset()
        food_price = self.recipes[Goods.food]['price']
        wood_price = self.recipes[Goods.wood]['price']
        furn_price = self.recipes[Goods.furniture]['price']
        self.cost_of_living = max(0.1, (4 * food_price + 1 * wood_price + 0.25 * furn_price)
                                  * self.col_multiplier)
        self.food_price = food_price
        self.all_goods_price = food_price + wood_price + furn_price
        self._record_start()
        self._audit_cash(t, "step_start")

        # Repoint traders to best-margin neighbor
        _logistics.repoint_traders(self)

        # Clear per-agent wealth caches
        for a in self.agents:
            a.clear_wealth_cache()

        # Charity donations
        if legacy:
            self.charity.collect_donations(t, self.agents, self.bank)
            self._audit_cash(t, "charity_done")

        # Labor market
        new_companies = _labor.run_labour(self, t)
        if new_companies:
            self.agents.extend(new_companies)
        self._audit_cash(t, "labour_done")

        # Production
        _prod.produce(self, t)
        self._audit_cash(t, "produce_done")

        # Trade & Route export posting
        _market.trade(self, t)
        _logistics.post_exports_to_route(self)
        self._audit_cash(t, "trade_done")

        # Wages & Profits
        _fin.pay_wages(self, t)
        self._audit_cash(t, "wages_done")

        _fin.distribute_profits(self, t)
        self._audit_cash(t, "profits_done")

        # Tax
        self._record_delta()
        _fin.collect_tax(self, t)
        self._audit_cash(t, "tax_done")

        self._log_gdp()

        if t > 0 and t % 10 == 0:
            _fin.recalculate_multipliers(self)

        # Demographics & Lifecycle
        self.agents = self._live(t)
        self.trader_agents = [a for a in self.agents if a.is_trader]
        self._audit_cash(t, "live_done")

        # Charity food distribution
        if legacy:
            self.charity.distribute_food(t, self.agents)
            self._audit_cash(t, "charity_food_done")

        # Metrics, Factions & Unrest
        self._log_metrics(t)
        self.migration_intent_log.append(_logistics.migration_intent_score(self))
        _factions.step_factions(self, t)

        from unrest import step_unrest
        ev = step_unrest(self, t)
        self.unrest_flag = ev['stage'] != 'calm'
        if legacy:
            self.gov.seal_income(t)

        self.total_population.append(sum(v[-1] for v in self.population_log.values()))
        self.cost_of_living_log.append(self.cost_of_living)
        self.bank_cash_log.append(self.bank.equity)
        self.total_cash_log.append(self._total_cash())
        self._log_population_rate()

        for p in self.goods:
            for g in self.goods:
                self.bought_log[p][g].append(0)

        if len(self.total_cash_log) >= 2:
            difference = math.fabs(self.total_cash_log[-2] - self.total_cash_log[-1])
            if difference > 1e-8:
                logwarning(t, f"Region '{self.name}' cash: {self.total_cash_log[-2]:.2f}->{self.total_cash_log[-1]:.2f} (d={difference:.2f})")

        if t % 100 == 0:
            circulating_cash = sum(a.cash for a in self.agents)
            print(f"--- Region '{self.name}' T={t}: circ=${circulating_cash:.0f}, "
                  f"dep=${self.bank.total_deposits:.0f}, "
                  f"liab=${self.bank.total_liabilities:.0f}, "
                  f"r={self.bank.total_deposits/max(1,circulating_cash):.1f}x")

    # ------------------------------------------------------------------
    # Cash audits & state snapshots
    # ------------------------------------------------------------------

    def _audit_cash(self, t, label):
        """Log all cash components when anomalies occur."""
        agent_cash = sum(a.cash for a in self.agents)
        deposits = self.bank.total_deposits
        liabilities = self.bank.total_liabilities
        bank_equity = self.bank.equity
        total = agent_cash + bank_equity
        if total < 0 or agent_cash < 0 or deposits < 0 or liabilities < 0:
            print(f"  CASH AUDIT [{label}] T={t}: "
                  f"agents=${agent_cash:.0f} "
                  f"deposits=${deposits:.0f} "
                  f"liabilities=${liabilities:.0f} "
                  f"bank_eq=${bank_equity:.0f} "
                  f"TOTAL=${total:.0f}")

    def _record_start(self):
        for a in self.agents:
            a._start_cash = a.cash
            a._start_deposits = self.bank.deposits.get(a, 0)

    def _record_delta(self):
        for a in self.agents:
            a._delta_cash = a.cash - a._start_cash
            a._delta_deposits = self.bank.deposits.get(a, 0) - a._start_deposits

    def _total_cash(self):
        """Total cash including agents, bank equity, and charity's hand cash."""
        return get_total_cash(self.agents, self.bank) + self.charity.agent.cash

    # ------------------------------------------------------------------
    # Demographics & Lifecycle
    # ------------------------------------------------------------------

    def _live(self, t):
        """Run life-cycle using LiveContext."""
        import econsim_live as _lm
        from econsim_live import LiveContext

        ctx = LiveContext(
            recipes=self.recipes,
            goods=self.goods,
            governments=[self.gov],
            default_gov=self.gov,
            hungry_log=self.hungry_log,
            dead_pop=self.dead_pop,
            deadstarve_pop=self.dead_starved_population,
            production_log=self.production_log,
            starve_limit=starvation_limit,
            profession=profession,
            max_career_switches=max_career_switches,
            p_birth=probability_birth,
            birth_gap=birth_gap,
            bank=self.bank,
            most_demand=self.most_demand,
            charity=self.charity,
            max_agents=self.max_agents,
            carrying_capacity=self.max_agents,
            cost_of_living=self.cost_of_living,
            food_price=self.food_price,
            source_region=self,
        )
        result = _lm.Live(t, self.agents, context=ctx)

        # Post-processing: trader exit + inheritance + career switching
        _logistics.process_trader_exits(self, t, result)

        if (self.neighbors or self.destination_region is not None) and t > 0:
            has_arbitrage = any(
                self.recipes[g]['price'] < other.recipes[g]['price'] * 0.95
                for g in [Goods.wood, Goods.furniture]
                for other in (list(self.neighbors.values()) or [self.destination_region])
            )
            trader_count = sum(1 for a in result if a.is_trader)
            max_traders = int(len(result) * 0.2)
            for agent in result:
                if agent.is_corporation:
                    continue
                parent = agent.parent
                if (parent is not None and parent.is_trader
                        and not agent.is_trader
                        and trader_count < max_traders
                        and rand.random() < 0.5):
                    _logistics.make_trader_internal(self, agent)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} inherited trader from parent {parent.name()}")
                elif (not agent.is_trader
                      and has_arbitrage
                      and (agent.cash < 20 or agent.hungry_steps > 0)
                      and trader_count < max_traders
                      and rand.random() < 0.003):
                    _logistics.make_trader_internal(self, agent)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} switched to trader (cash=${agent.cash:.0f})")

        return result

    # ------------------------------------------------------------------
    # Metrics logging
    # ------------------------------------------------------------------

    def _log_gdp(self):
        total = 0
        for g in self.goods:
            if g != Goods.gov:
                value = self.production_log[g][-1] * self.recipes[g]['price']
                total += value
                self.gdp_by_profession_log[g].append(value)
        self.gdp_log.append(total)

    def _log_metrics(self, t):
        agents = self.agents
        by_output = {g: [] for g in self.goods}
        by_output['trader'] = []
        food_agents = []
        total_cash_by_output = {g: 0.0 for g in self.goods}
        total_inv_by_output = {g: 0.0 for g in self.goods if g != Goods.gov}
        total_inv_trader = 0.0

        for a in agents:
            if a.is_trader:
                continue
            if a.output == Goods.food:
                food_agents.append(a)
                by_output[Goods.food].append(a)
                total_cash_by_output[Goods.food] += a.cash
                if Goods.food != Goods.gov:
                    total_inv_by_output[Goods.food] += a.inv_get(Goods.food, 0)
            elif a.output != Goods.gov:
                o = a.output
                by_output[o].append(a)
                total_cash_by_output[o] += a.cash
                if o != Goods.gov:
                    total_inv_by_output[o] += a.inv_get(o, 0)

        trader_agents = self.trader_agents
        by_output['trader'] = trader_agents
        for a in trader_agents:
            total_inv_trader += a.inv_get(Goods.food, 0) + a.inv_get(Goods.wood, 0) + a.inv_get(Goods.furniture, 0)

        compute_gini_this_turn = (t % 10 == 0)

        for g in self.goods:
            grp = by_output[g]
            pop = len(grp)
            self.population_log[g].append(pop)
            self.cash_log[g].append(total_cash_by_output.get(g, 0.0))
            if compute_gini_this_turn:
                self.gini_log[g].append(compute_gini(grp, g))
            else:
                self.gini_log[g].append(self.gini_log[g][-1] if self.gini_log[g] else 0)
            if g != Goods.gov:
                self.inventory_log[g].append(total_inv_by_output.get(g, 0.0))
                non_prod = [a.inv_get(g, 0) for a in agents if a.output != g and not a.is_trader]
                self.per_capita_inventory[g].append(mean(non_prod) if non_prod else 0)
                self.price_log[g].append(self.recipes[g]['price'])

        tr_len = len(trader_agents)
        self.population_log['trader'].append(tr_len)
        self.cash_log['trader'].append(sum(a.cash for a in trader_agents))
        if compute_gini_this_turn:
            self.gini_log['trader'].append(compute_gini(trader_agents, Goods.food))
        else:
            self.gini_log['trader'].append(self.gini_log['trader'][-1] if self.gini_log['trader'] else 0)
        self.hungry_log['trader'].append(sum(1 for a in trader_agents if a.hungry_steps > 0))
        self.inventory_log['trader'].append(total_inv_trader)
        non_trader = [a.inv_get(Goods.food, 0) for a in trader_agents if a.output != Goods.food]
        self.per_capita_inventory['trader'].append(mean(non_trader) if non_trader else 0)
        self.production_log['trader'].append(0)
        self.gdp_by_profession_log['trader'].append(0)

        self.trader_cash_log.append(sum(a.cash for a in trader_agents))
        pipeline_qty = 0
        for rt in _logistics.all_routes(self):
            pipeline_qty += sum(
                rt.in_transit_total(g)
                for g in [Goods.food, Goods.wood, Goods.furniture]
            )
        self.pipeline_depth_log.append(pipeline_qty)

    def _log_population_rate(self):
        if len(self.total_population) >= 10:
            pop_10_ago = self.total_population[-10]
            current_pop = self.total_population[-1]
            population_change_pct = ((current_pop - pop_10_ago) / pop_10_ago * 100) if pop_10_ago > 0 else 0
        else:
            population_change_pct = 0
        self.population_change_rate_log.append(population_change_pct)

    # ------------------------------------------------------------------
    # Plotting delegator
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
