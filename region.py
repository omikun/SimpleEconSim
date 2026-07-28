"""
Shared Region class and helpers for single-region (econsim.py) and
two-region (econsim_two_region.py) simulations.
"""

import copy
import math
import random
from collections import defaultdict
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from goods import Goods, profession
from econsim_states import (
    recipes, goods, probability_birth, probability_death, birth_gap,
    max_career_switches, starvation_limit,
)
from logger import loginfo, logwarning, logdebug

import econsim_trade_money as _tm
import government as govmod
from agent import Agent, initialize_agent
from charity import Charity
from random_cache import rand
try:
    import region_core as _c
except ImportError:
    _c = None


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
    Goods.gov: {
        'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1,
        'maxtotalprod': 0, 'maxinv': 0,
    },
}
for _g, _r in _recipes_init.items():
    recipes[_g] = _r

# Default profession distribution (fractions summing to <= 1.0, remainder -> gov)
DEFAULT_PROFESSION_DISTRIBUTION = {
    Goods.food: 0.82,
    Goods.wood: 0.06,
    Goods.furniture: 0.02,
}


# =============================================================================
# SoA constant: max pre-allocated slots
# =============================================================================

MAX_AGENTS = 500


# =============================================================================
# Shared helpers (replacing duplicates in econsim.py / econsim_two_region.py)
# =============================================================================

def count_agents(agents, good):
    """Number of agents whose output is *good*."""
    return sum(agent.output == good for agent in agents)


def compute_gini(agents, good):
    """Gini coefficient over cash held by agents producing *good*.
    
    Uses O(n log n) algorithm instead of the naive O(n^2) double loop.
    """
    vals = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(vals)
    if n == 0:
        return 0
    total = sum(vals)
    if total == 0:
        return 0
    # G = (2 * sum((i+1) * y_i)) / (n * sum(y_i)) - (n+1)/n
    weighted_sum = sum((i + 1) * v for i, v in enumerate(vals))
    return (2 * weighted_sum) / (n * total) - (n + 1) / n


def get_total_cash(agents, bank=None):
    """Total cash in the system: agent cash + bank equity.
    
    *bank* defaults to the module-level *trade.bank* for backward compat
    with econsim.py (single-region).  Callers with per-region banks pass
    explicitly.
    """
    if bank is None:
        return sum(agent.cash for agent in agents)
    bank_equity = bank.total_deposits - bank.total_liabilities
    return sum(a.cash for a in agents) + bank_equity


# =============================================================================
# Region class
# =============================================================================

class Region:
    """A self-contained region with its own government, bank, agents, and logs."""

    def __init__(self, name: str, t: int, number_of_agents: int = 110,
                 profession_distribution: dict = None, number_of_traders: int = None,
                 transport_delay: int = 1):
        self.name = name
        self.agents: list = []          # compact list of living agents (no Nones)
        self.max_agents = MAX_AGENTS    # Population cap for LiveContext
        self.transport_delay = transport_delay
        if profession_distribution is None:
            profession_distribution = dict(DEFAULT_PROFESSION_DISTRIBUTION)
        self.profession_distribution = profession_distribution.copy()
        if number_of_traders is None:
            number_of_traders = 5
        self._number_of_traders = number_of_traders

        # Deep-copy global config
        self.recipes = copy.deepcopy(recipes)
        self.goods = list(goods)

        # Own bank
        self.bank = _tm.Bank()

        # Own government
        self.gov = govmod.Government(name, t, initial_cash=200)
        self.gov.agent.is_government = True
        self.bank.gov = self.gov  # wire gov reference for bailouts

        # Logging state (mirrors econsim_states globals)
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
        self.price_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: []}
        self.sold_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: []}
        self.bought_log: dict = {}
        self.gdp_log: list = []
        self.gdp_by_profession_log: dict = {Goods.food: [], Goods.wood: [], Goods.furniture: []}
        self.total_population: list = []
        self.population_change_rate_log: list = []
        self.dead_pop: list = [0]
        self.dead_starved_population: list = [0]

        # ---- Trade logging ----
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
        self.cumulative_trade_balance = 0.0

        for g in [Goods.food, Goods.wood, Goods.furniture]:
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

        # Charity (independent food redistribution)
        self.charity = Charity(name, self.recipes)

        # Create agents
        self._create_agents(t, number_of_agents)
        self._register_citizens()

    # ------------------------------------------------------------------
    # Agent creation
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
                agent.region = self.name
                agent._bank_ref = self.bank
                agents.append(agent)

        for _ in range(self._number_of_traders):
            trader = Agent(t)
            trader.is_trader = True
            trader.output = Goods.food
            trader.home_region = self.name
            trader.region = self.name
            trader.cash = 200.0
            trader._bank_ref = self.bank
            for g in Goods:
                if g == Goods.none:
                    continue
                trader.inventory[g.value] = 0
            trader.inventory[Goods.food.value] = 4
            agents.append(trader)

        agents.append(self.gov.agent)
        self.gov.agent.region = self.name
        self.gov.agent._bank_ref = self.bank
        self.agents = agents

    def _register_citizens(self):
        for agent in self.agents:
            if agent != self.gov.agent:
                self.gov._add_citizen(agent)

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------

    def step(self, t: int):
        rand.reset()
        self._record_start()
        self._audit_cash(t, "step_start")

        # Clear per-agent caches for this turn
        for a in self.agents:
            a.clear_wealth_cache()

        # Charity collects donations (before trade so it has cash to buy food)
        self.charity.collect_donations(t, self.agents, self.bank)
        self._audit_cash(t, "charity_done")

        new_companies = self._run_labour(t)
        if new_companies:
            self.agents.extend(new_companies)
        self._audit_cash(t, "labour_done")

        self._produce(t)
        self._audit_cash(t, "produce_done")

        self._trade(t)
        self._audit_cash(t, "trade_done")

        self._pay_wages(t)
        self._audit_cash(t, "wages_done")

        self._distribute_profits(t)
        self._audit_cash(t, "profits_done")

        self._record_delta()
        self._collect_tax(t)
        self._audit_cash(t, "tax_done")

        self._log_gdp()

        if t > 0 and t % 10 == 0:
            self._recalculate_multipliers()

        self.agents = self._live(t)
        self._audit_cash(t, "live_done")

        # Charity distributes food to hungry and young agents
        self.charity.distribute_food(t, self.agents)
        self._audit_cash(t, "charity_food_done")

        self._log_metrics(t)
        self.total_population.append(sum(v[-1] for v in self.population_log.values()))
        self.bank_cash_log.append(self.bank.total_deposits - self.bank.total_liabilities)
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

    # ---- Internal helpers ----

    def _audit_cash(self, t, label):
        """Log all cash components when anomalies occur (or sampled every 10 turns between 100-200)."""
        agent_cash = sum(a.cash for a in self.agents)
        deposits = self.bank.total_deposits
        liabilities = self.bank.total_liabilities
        bank_equity = deposits - liabilities
        total = agent_cash + bank_equity
        if total < 0 or agent_cash < 0 or deposits < 0 or liabilities < 0 or (100 <= t <= 200 and t % 10 == 0):
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
        """Total cash including agents, bank equity, and charity's hand cash.
        
        Charity's bank deposits are already in bank_equity via total_deposits.
        We just need to add charity's hand cash (which get_total_cash misses
        because the charity Agent is not in self.agents).
        """
        return get_total_cash(self.agents, self.bank) + self.charity.agent.cash

    # ---- Labour ----

    def _run_labour(self, t):
        self._cleanup()
        self._borrow_or_layoff(t)
        new_companies = self._incorporate(t)
        self._hire(t)
        self._adjust_wages(t)
        return new_companies

    def _cleanup(self):
        living_set = set(self.agents)
        for a in self.agents:
            if a.employer and a.employer not in living_set:
                a.employer = None
            if a.is_corporation:
                a.employees = [e for e in a.employees if e in living_set and e.employer == a]

    def _borrow_or_layoff(self, t):
        for a in self.agents:
            if not a.is_corporation or len(a.employees) == 0:
                continue
            total_wage = len(a.employees) * a.wage
            if a.cash < total_wage:
                self.bank.Borrow(t, a, total_wage - a.cash)
            while a.cash < total_wage and len(a.employees) > 0:
                e = a.employees.pop()
                e.employer = None
                total_wage = len(a.employees) * a.wage
            if len(a.employees) == 0:
                a.is_corporation = False
                if a.owner:
                    a.owner.company_owned = None

    def _incorporate(self, t):
        new_companies = []
        for a in self.agents:
            if a.employer or a.is_corporation or a.cash <= 400 or a.company_owned:
                continue
            food_price = self.recipes[Goods.food]['price']
            company = Agent(t)
            company.is_corporation = True
            company.output = a.output
            company.owner = a
            company._bank_ref = self.bank
            a.company_owned = company
            for g in self.goods:
                company.inventory[g.value] = a.inv_get(g, 0)
                a.inv_set(g, 0)
            equity = min(a.cash * 0.3, a.cash - 60)
            startup_target = max(300, food_price * 20)
            shortfall = max(0, startup_target - equity)
            if shortfall > 0:
                self.bank.Borrow(t, company, shortfall)
            a.cash -= equity
            company.cash = equity + shortfall
            sector_wages = [x.wage for x in self.agents if x.is_corporation and x.output == a.output and x.wage > 0]
            company.wage = max(sector_wages) * 1.05 if sector_wages else max(1.0, food_price * 1.5)
            company.max_employees = rand.randint(10, 25)
            new_companies.append(company)
        return new_companies

    def _hire(self, t):
        for a in self.agents:
            if not a.is_corporation or len(a.employees) >= a.max_employees:
                continue
            payroll = len(a.employees) * a.wage
            if a.cash <= (payroll + a.wage) * 2:
                continue
            candidates = [x for x in self.agents if x.employer is None and not x.is_corporation and x != a]
            distressed = [c for c in candidates if c.hungry_steps > 0 or c.cash < 40]
            if distressed:
                c = rand.choice(distressed)
                c.employer = a
                c.hired_at = t
                a.employees.append(c)
                c.output = a.output
            else:
                poachable = [e for e in self.agents if e.employer and e.employer != a
                             and e.employer.is_corporation and len(e.employer.employees) > 1]
                if poachable:
                    target = rand.choice(poachable)
                    old_employer = target.employer
                    offer_wage = max(old_employer.wage * 1.1, a.wage * 1.05)
                    if a.cash > (payroll + offer_wage) * 2:
                        old_employer.employees.remove(target)
                        target.employer = a
                        target.hired_at = t
                        target.output = a.output
                        a.employees.append(target)
                        a.wage = max(a.wage, offer_wage)

    def _adjust_wages(self, t):
        for a in self.agents:
            if not a.is_corporation or len(a.employees) == 0:
                continue
            payroll = len(a.employees) * a.wage
            if a.cash > payroll * 5 and len(a.employees) < a.max_employees:
                a.wage *= 1.02
            elif a.cash < payroll * 3:
                a.wage *= 0.95

    # ---- Production ----

    def _produce(self, t):
        # Compute counts once — avoid dict comprehension iteration per turn
        num_agents_per_good = {}
        for a in self.agents:
            if not a.is_trader and a.output != Goods.gov:
                num_agents_per_good[a.output] = num_agents_per_good.get(a.output, 0) + 1
        for g in self.goods:
            if g not in num_agents_per_good:
                num_agents_per_good[g] = 0
        local_total_production = defaultdict(int)
        for a in self.agents:
            if a.employer or a.output == Goods.gov or a.is_trader:
                continue
            r = self.recipes[a.output]
            if a.is_corporation and len(a.employees) > 0:
                self._produce_corporation(a, r, a.output, num_agents_per_good, local_total_production)
            else:
                self._produce_independent(a, r, a.output, num_agents_per_good, local_total_production)
        for g in self.goods:
            if g != Goods.gov:
                self.production_log[g].append(local_total_production[g])

    def _produce_corporation(self, agent, recipe, output, num_agents_per_good, local_total_production):
        num_employees = len(agent.employees)
        max_inventory = recipe['maxinv'] * (1 + num_employees)
        if agent.inv_get(output, 0) / max_inventory >= 1:
            return
        num_slots = num_employees
        if recipe.get('numInput', 0) > 0:
            available = agent.inv_get(recipe['input'], 0)
            active_slots = int(min(num_slots, available // recipe['numInput']))
        else:
            active_slots = int(num_slots)
        if active_slots <= 0 or recipe.get('production', 0) <= 0:
            return
        synergy = 1.0 + (0.15 if num_employees < 4 else 0.20 if num_employees < 8 else 0.25 if num_employees < 12 else 0.30) * num_employees
        base_production = recipe['production']
        production_per_slot = base_production * synergy
        chance = 1.0
        if agent.hungry_steps > 0:
            chance *= 1 / (1 + agent.hungry_steps * 0.2)
        if output in (Goods.food, Goods.wood):
            chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / base_production)
        chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
        vals = rand.random_n(active_slots)
        if _c is not None:
            successful_slots = _c.produce_corporation_slots(active_slots, chance, vals)
        else:
            successful_slots = sum(1 for v in vals if v < chance)
        if successful_slots:
            if recipe.get('numInput', 0) > 0:
                agent.inv_add(recipe['input'], -successful_slots * recipe['numInput'])
            num_output = int(successful_slots * production_per_slot) or 1
            agent.inv_add(output, num_output)
            local_total_production[output] += num_output

    def _produce_independent(self, agent, recipe, output, num_agents_per_good, local_total_production):
        max_inventory = recipe['maxinv']
        if agent.inv_get(output, 0) / max_inventory >= 1:
            return
        has_inputs = True
        if recipe['numInput'] > 0 and agent.inv_get(recipe['input'], 0) < recipe['numInput']:
            has_inputs = False
        num_output = 0
        if has_inputs and recipe.get('production', 0) > 0:
            chance = 1.0
            if agent.hungry_steps > 0:
                chance *= 1 / (1 + agent.hungry_steps * 0.2)
            if output in (Goods.food, Goods.wood):
                chance *= min(1.0, recipe['maxtotalprod'] / max(1, num_agents_per_good[output]) / recipe['production'])
            chance *= max(0, 1 - agent.inv_get(output, 0) / max_inventory)
            rand_val = rand.random()
            if _c is not None:
                made = _c.produce_independent_check(chance, rand_val)
            else:
                made = 1 if rand_val < chance else 0
            if made:
                if recipe['numInput'] > 0:
                    agent.inv_add(recipe['input'], -recipe['numInput'])
                num_output = recipe['production']
        agent.inv_add(output, num_output)
        local_total_production[output] += num_output

    # ---- Trade ----

    def _trade(self, t):
        trade_goods = [Goods.food, Goods.wood, Goods.furniture]
        all_goods_price = sum(self.recipes[g]['price'] for g in trade_goods)
        food_price = self.recipes[Goods.food]['price']
        self.bank.PayDepositInterest(self.agents)
        self._decide_borrow_deposit(self.agents, all_goods_price, food_price, t)

        # Single pass: gather bids/asks for all goods, stored per-good on agent
        recipes = self.recipes
        agents = self.agents
        desired_food = 16
        desired_wood = 10
        desired_furn = max(1, int(16 / max(1, recipes[Goods.furniture]['price'])))
        desires = {Goods.food: desired_food, Goods.wood: desired_wood, Goods.furniture: desired_furn}
        prices = {g: recipes[g]['price'] for g in trade_goods}
        total_asks = {g: 0 for g in trade_goods}
        total_bids = {g: 0 for g in trade_goods}
        for a in agents:
            ar = recipes[a.output]
            is_emp = a.employer is not None
            mult = a.consumption_multiplier
            for g in trade_goods:
                p = prices[g]
                d = desires[g]
                self._withdraw_if_needed(a, p, d)
                bid = self._calculate_bid(a, g, p, d, ar, is_emp, mult)
                a.bid = bid
                a.remainingCash -= bid * p
                total_bids[g] += bid
                ask = self._calculate_ask(a, g, p, is_emp)
                a.ask = ask
                total_asks[g] += ask
                # Store per-good bid/ask for _buy/_sell later
                setattr(a, f'bid_{g.name}', bid)
                setattr(a, f'ask_{g.name}', ask)

        max_demand_ratio = 0
        most_demand_good = Goods.food
        for good in trade_goods:
            ta = total_asks[good]
            tb = total_bids[good]
            if ta == 0 and tb == 0:
                self._price_decay(good)
                continue
            demand_ratio = 5.0 if ta == 0 else tb / ta
            self.demand_ratio_log[good].append(demand_ratio)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(ta)
            if max_demand_ratio < demand_ratio and tb > 0:
                max_demand_ratio = demand_ratio
                most_demand_good = good
            price = self._set_price(demand_ratio, good)
            if min(ta, tb) == 0:
                continue
            total_bought, total_cash_purchases = self._buy(t, good, price, ta)
            askers = sorted(agents, key=lambda a: a.ask, reverse=True)
            total_cash_sales, total_sold = self._sell(askers, good, price, t, total_bought, total_cash_purchases)
            self.sold_log[good].append(total_sold)

            # Charity food purchase
            if good == Goods.food:
                charity_bid = self.charity.bid_food(price, desires[good])
                if charity_bid > 0:
                    food_askers = [a for a in askers if a.output == Goods.food
                                   and a.inv_get(Goods.food, 0) > 2]
                    charity_bought = 0
                    for seller in food_askers:
                        if charity_bid <= 0 or self.charity.cash < price:
                            break
                        available = seller.inv_get(Goods.food, 0) - 2
                        if available <= 0:
                            continue
                        bought = min(charity_bid, available, int(self.charity.cash / price))
                        if bought > 0:
                            seller.inv_add(Goods.food, -bought)
                            seller.cash += bought * price
                            self.charity.pay_for_food(bought * price)
                            self.charity.receive_food(bought)
                            charity_bid -= bought
                            charity_bought += bought
                    if charity_bought > 0:
                        total_sold += charity_bought
                        self.sold_log[good][-1] += charity_bought
                        loginfo(t, f"{self.charity.name} bought {charity_bought} food at ${price:.2f}")

        self.most_demand = most_demand_good

    def _decide_borrow_deposit(self, agents, all_goods_price, food_price, t):
        for a in agents:
            _tm.borrow_if_needed(t, a, bank=self.bank)
            _tm.PayLoans(a, bank=self.bank)
            self._borrow_food(a, food_price)
            self._borrow_inputs(a)
            self._deposit_excess(a, all_goods_price)
            if a.is_trader:
                survival_cost = food_price * 3
                if a.cash < survival_cost:
                    self.bank.Borrow(t, a, survival_cost - a.cash)
            a.remainingCash = a.cash

    def _borrow_food(self, agent, food_price):
        if agent.output != Goods.food and agent.cash < food_price and agent.hungry_steps > 10:
            bank_balance = self.bank.deposits.get(agent, 0)
            if bank_balance > 0:
                self.bank.Withdraw(agent, min(bank_balance, food_price - agent.cash))
            if agent.cash < food_price:
                self.bank.Borrow(0, agent, food_price)

    def _borrow_inputs(self, agent):
        r = self.recipes.get(agent.output)
        if not r or r.get('numInput', 0) <= 0:
            return
        cost = self.recipes[r['input']]['price'] * r['numInput']
        if agent.cash >= cost:
            return
        bank_balance = self.bank.deposits.get(agent, 0)
        if bank_balance > 0:
            self.bank.Withdraw(agent, min(bank_balance, cost - agent.cash))
        if agent.cash < cost:
            self.bank.Borrow(0, agent, cost - agent.cash)

    def _deposit_excess(self, agent, all_goods_price):
        mult = agent.consumption_multiplier
        total_liquid = agent.cash + self.bank.deposits.get(agent, 0)
        current_deposits = self.bank.deposits.get(agent, 0)
        deposit_fraction = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
        cash_floor = int(all_goods_price * (100 / max(1.0, mult)))
        max_deposits = total_liquid * deposit_fraction
        excess = max(0, max_deposits - current_deposits)
        if agent.cash > cash_floor and excess > 0:
            self.bank.Deposit(agent, min(agent.cash - cash_floor, excess))

    def _gather_bids(self, agents, good, good_price, current_desired):
        total_asks = 0
        total_bids = 0
        for a in agents:
            agent_recipe = self.recipes[a.output]
            is_employee = a.employer is not None
            self._withdraw_if_needed(a, good_price, current_desired)
            mult = a.consumption_multiplier
            bid = self._calculate_bid(a, good, good_price, current_desired, agent_recipe, is_employee, mult)
            a.bid = bid
            a.remainingCash -= a.bid * good_price
            total_bids += a.bid
            ask = self._calculate_ask(a, good, good_price, is_employee)
            a.ask = ask
            total_asks += a.ask
        return total_asks, total_bids

    def _withdraw_if_needed(self, agent, good_price, current_desired):
        bank_balance = self.bank.deposits.get(agent, 0)
        if bank_balance > 0 and agent.remainingCash < good_price * current_desired:
            self.bank.Withdraw(agent, min(bank_balance, good_price * current_desired - agent.remainingCash))

    def _calculate_bid(self, agent, good, good_price, current_desired, agent_recipe, is_employee, mult):
        if agent.is_trader:
            destination = agent.destination_region
            if destination is not None:
                destination_ask = destination.recipes[good]['price'] * 0.95
                if destination_ask <= good_price:
                    return 0
            max_trader_inventory = agent_recipe['maxinv']
            total_holding = agent.inv_get(good, 0) + agent.inventory_export[good.value] + agent.inventory_foreign[good.value]
            for pipe in agent.transport_pipeline:
                if pipe['good'] == good:
                    total_holding += pipe['quantity']
            space = max(0, max_trader_inventory - total_holding)
            if space <= 0 or agent.remainingCash < good_price:
                return 0
            affordable = agent.remainingCash // good_price
            bid = min(space, affordable)
            return max(0, bid)
        if not is_employee and self._input_good(agent) == good:
            num_employees = len(agent.employees) if agent.is_corporation else 0
            desired = max(0, agent_recipe['numInput'] * (1 + num_employees) - agent.inv_get(good, 0))
            if mult > 1.0:
                desired = int(desired * mult)
            affordable = agent.remainingCash // good_price if good_price > 0 else desired
            return int(min(desired, affordable))
        elif (is_employee or agent.output != good) and agent.remainingCash > good_price:
            max_inventory_limit = agent_recipe['maxinv']
            if agent.is_corporation:
                max_inventory_limit *= (1 + len(agent.employees))
            if mult > 1.0:
                max_inventory_limit = int(max_inventory_limit * min(mult, 3.0))
            num_storable = max(0, max_inventory_limit - agent.inv_get(good, 0))
            base_desire = min(current_desired, agent.remainingCash // good_price)
            bid = min(int(base_desire * mult), num_storable)
            if mult > 2.0 and good != Goods.food:
                extra = min(int(current_desired * (mult - 1.0)), agent.remainingCash // good_price) if good_price > 0 else 0
                bid += min(extra, num_storable - bid)
            return max(0, min(bid, num_storable))
        return 0

    def _calculate_ask(self, agent, good, good_price, is_employee):
        if agent.is_trader:
            return 0
        if is_employee:
            return 0
        if agent.output != good and agent.output != Goods.gov:
            return 0 if agent.inv_get(good, 0) <= 0 else 0
        if agent.output == good or (agent.output == Goods.gov and agent.inv_get(good, 0) > 0):
            cost_to_make = 0.0
            agent_recipe = self.recipes.get(good, {})
            if agent.output == good and agent_recipe.get('numInput', 0) > 0 and agent_recipe.get('production', 0) > 0:
                cost_to_make = (agent_recipe['numInput'] * agent.cost_get(agent_recipe['input'], 0)) / agent_recipe['production']
            if good == Goods.food and agent.output == Goods.food:
                return max(0, agent.inv_get(good, 0) - 2)
            elif good_price >= cost_to_make:
                return max(0, agent.inv_get(good, 0))
        return 0

    def _input_good(self, agent):
        return self.recipes[agent.output].get('input', Goods.none)

    def _buy(self, t, good, price, total_asks):
        # Sort by hungry_steps once per turn (cached in _cached_hungry_sorted)
        if not hasattr(self, '_cached_hungry_sorted') or self._cached_hungry_turn != t:
            self._cached_hungry_sorted = sorted(self.agents, key=lambda a: a.hungry_steps, reverse=True)
            self._cached_hungry_turn = t
        bidders = self._cached_hungry_sorted
        total_bought = 0
        total_cash_purchases = 0.0
        for a in bidders:
            if total_asks > total_bought:
                # Use per-good bid stored during the single-pass gather
                agent_bid = getattr(a, f'bid_{good.name}', a.bid)
                bought = max(0, min(agent_bid, min(total_asks - total_bought, int(a.cash / price))))
                cash = bought * price
                a.cash = max(0.0, a.cash - cash)
                total_cash_purchases += cash
                if bought > 0:
                    if a.is_trader:
                        if good != Goods.food:
                            a.inventory_export[good.value] += bought
                        else:
                            food_needed = max(0, 8 - a.inv_get(good, 0))
                            keep = min(food_needed, bought)
                            export = bought - keep
                            a.inv_add(good, keep)
                            if export > 0:
                                a.inventory_export[good.value] += export
                    else:
                        old_quantity = a.inv_get(good, 0)
                        old_cost = a.cost_get(good, 0)
                        a.cost_set(good, ((old_quantity * old_cost + bought * price) / (old_quantity + bought)) if (old_quantity + bought) > 0 else price)
                        a.inv_add(good, bought)
                    total_bought += bought
                    self.bought_log[a.output][good][-1] += bought
        return total_bought, total_cash_purchases

    def _sell(self, askers, good, price, t, total_bought, total_cash_purchases):
        total_sold = 0
        total_cash_sales = 0.0
        for a in askers:
            if total_sold < total_bought and total_cash_purchases > total_cash_sales:
                # Use per-good ask stored during the single-pass gather
                agent_ask = getattr(a, f'ask_{good.name}', a.ask)
                sold = min(agent_ask, total_bought - total_sold)
                total_sold += sold
                a.cash += sold * price
                a.inv_add(good, -sold)
                total_cash_sales += sold * price
        return total_cash_sales, total_sold

    def _price_decay(self, good):
        r = self.recipes[good]
        cost_to_make = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            input_cost = self.recipes[r['input']]['price']
            cost_to_make = (r['numInput'] * input_cost) / r['production']
        if r['price'] > cost_to_make * 1.05:
            r['price'] = max(cost_to_make, r['price'] * 0.95)
        r['price'] = max(cost_to_make, r['price'])

    def _set_price(self, demand_ratio, good):
        r = self.recipes[good]
        price = r['price']
        fundamental_cost = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            input_cost = self.recipes[r['input']]['price']
            fundamental_cost = (r['numInput'] * input_cost) / r['production']
        food_price = self.recipes.get(Goods.food, {}).get('price', 1.0)
        living_cost_floor = (4 * food_price) / max(1, r.get('production', 1))

        def lerp(a, b, t):
            return a + (b - a) * t

        if demand_ratio >= 1:
            clamped_ratio = min(5.0, demand_ratio - 1)
            price *= lerp(1.01, 1.20, clamped_ratio / 5.0)
        elif demand_ratio < 0.2:
            price *= lerp(0.90, 0.95, demand_ratio / 0.2)
        elif demand_ratio < 0.5:
            price *= lerp(0.95, 1.0, (demand_ratio - 0.2) / 0.3)
        min_price_floor = fundamental_cost * 1.10 if r.get('numInput', 0) > 0 else max(living_cost_floor, 0.10)
        price = max(min_price_floor, price, 0.1)
        r['price'] = price
        return price

    # ---- Wages ----

    def _pay_wages(self, t):
        for a in self.agents:
            if a.is_corporation and len(a.employees) > 0:
                for e in a.employees:
                    wage_to_pay = min(a.cash, a.wage)
                    a.cash -= wage_to_pay
                    e.cash += wage_to_pay

    # ---- Owner profit ----

    def _distribute_profits(self, t):
        for a in self.agents:
            if not a.is_corporation or not a.alive:
                continue
            if a.owner is None or not a.owner.alive:
                continue
            owner = a.owner
            payroll = max(1, len(a.employees) * a.wage)
            self._repay_owner_loan(a, owner, payroll)
            profit = max(0, a._delta_cash + a._delta_deposits)
            if profit > 0 or a.cash > payroll * 2:
                a.retained_earnings += profit
            self._pay_base_salary(a, owner, payroll)
            self._pay_profit_share(a, owner, payroll)
            self._bailout_owner(a, owner, payroll)

    def _repay_owner_loan(self, agent, owner, payroll):
        if agent.owner_loan <= 0:
            return
        repay = min(agent.owner_loan, max(0, agent.cash - payroll * 2))
        if repay > 0:
            agent.cash -= repay
            owner.cash += repay
            agent.owner_loan -= repay

    def _pay_base_salary(self, agent, owner, payroll):
        if agent.cash > payroll * 2 + agent.wage:
            agent.cash -= agent.wage
            owner.cash += agent.wage

    def _pay_profit_share(self, agent, owner, payroll):
        if agent.retained_earnings <= 0 or agent.cash <= payroll * 2:
            return
        operating_expenses = payroll * 2
        ratio = agent.retained_earnings / operating_expenses
        share_rate = 0.25 * ratio / (ratio + 5)
        profit_draw = min(share_rate * agent.retained_earnings, max(0, agent.cash - payroll * 2))
        if profit_draw > 0:
            agent.cash -= profit_draw
            owner.cash += profit_draw
            agent.retained_earnings -= profit_draw

    def _bailout_owner(self, agent, owner, payroll):
        if agent.cash >= payroll:
            return
        food_price = self.recipes.get(Goods.food, {}).get('price', 1)
        inject = min(payroll - agent.cash, max(0, owner.cash - food_price * 4))
        if inject > 0:
            owner.cash -= inject
            agent.cash += inject
            agent.owner_loan += inject

    # ---- Tax ----

    def _collect_tax(self, t):
        living = [a for a in self.agents if a.alive]
        if len(living) <= 10:
            return
        sorted_agents = sorted(living, key=lambda a: a.wealth(), reverse=True)
        top_count = max(1, int(len(sorted_agents) * 0.1))
        top = sorted_agents[:top_count]
        total = 0.0
        for a in top:
            net_income = a._delta_cash + a._delta_deposits
            taxable = max(0.0, net_income + a.tax_loss_carryforward)
            if hasattr(self.gov, 'compute_child_tax_deduction'):
                taxable = max(0.0, taxable - self.gov.compute_child_tax_deduction(a))
            if taxable > 0:
                tax_amount = taxable * 0.5
                bank_balance = self.bank.deposits.get(a, 0)
                actual = min(tax_amount, a.cash + bank_balance)
                if actual > 0:
                    cash_taken = min(a.cash, actual)
                    a.cash -= cash_taken
                    deposit_taken = min(bank_balance, actual - cash_taken)
                    if deposit_taken > 0:
                        self.bank.Withdraw(a, deposit_taken)
                        a.cash -= deposit_taken
                a.tax_loss_carryforward = 0.0
                self.gov.collect_tax(t, actual)
                total += actual
            else:
                a.tax_loss_carryforward += net_income
        if total > 0 and t % 50 == 0:
            print(f"  Region '{self.name}' TAX: ${total:.2f} from top {top_count}, gov=${self.gov.agent.cash:.2f}")

    def _recalculate_multipliers(self):
        food_price = self.recipes.get(Goods.food, {}).get('price', 1)
        wood_price = self.recipes.get(Goods.wood, {}).get('price', 1)
        furn_price = self.recipes.get(Goods.furniture, {}).get('price', 1)
        cost_of_living = max(0.1, 4 * food_price + 1 * wood_price + 0.25 * furn_price)
        for a in self.agents:
            if not a.alive or a.is_corporation:
                continue
            wealth = a.wealth()
            a.consumption_multiplier = max(1.0, min(10.0, math.sqrt(wealth / cost_of_living))) if wealth > cost_of_living else 1.0

    def _live(self, t):
        """Run life-cycle using LiveContext (no global state patching needed)."""
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
            max_agents=self.max_agents,
            carrying_capacity=self.max_agents,
        )
        result = _lm.Live(t, self.agents, context=ctx)

        # Post-processing: trader inheritance + career switching (two-region only)
        if self.destination_region is not None and t > 0 and hasattr(self, 'destination_region'):
            has_arbitrage = any(
                self.recipes[g]['price'] < self.destination_region.recipes[g]['price'] * 0.95
                for g in [Goods.wood, Goods.furniture]
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
                    self._make_trader_internal(agent)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} inherited trader from parent {parent.name()}")
                elif (not agent.is_trader
                      and has_arbitrage
                      and (agent.cash < 20 or agent.hungry_steps > 0)
                      and trader_count < max_traders
                      and rand.random() < 0.003):
                    self._make_trader_internal(agent)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} switched to trader (cash=${agent.cash:.0f})")

        return result

    def _make_trader_internal(self, agent):
        """Set an agent's fields to make them a trader (internal version)."""
        agent.is_trader = True
        agent.home_region = self.name
        agent.destination_region = self.destination_region
        agent.output = Goods.food
        # Zero out export/foreign lists
        for g in Goods:
            if g == Goods.none:
                continue
            agent.inventory_export[g.value] = 0
            agent.inventory_foreign[g.value] = 0
        agent.transport_pipeline.clear()
        agent.transport_delay = 1  # TRANSPORT_DELAY
        agent.inv_set(Goods.food, max(agent.inv_get(Goods.food, 0), 4))
        agent.employer = None

    def _log_gdp(self):
        total = 0
        for g in self.goods:
            if g != Goods.gov:
                value = self.production_log[g][-1] * self.recipes[g]['price']
                total += value
                self.gdp_by_profession_log[g].append(value)
        self.gdp_log.append(total)

    def _log_metrics(self, t):
        # Single pass over agents: categorize by output and type
        agents = self.agents
        by_output = {g: [] for g in self.goods}
        by_output['trader'] = []
        food_agents = []
        trader_agents = []
        total_cash_by_output = {g: 0.0 for g in self.goods}
        total_inv_by_output = {g: 0.0 for g in self.goods if g != Goods.gov}
        total_inv_trader = 0.0

        for a in agents:
            if a.is_trader:
                trader_agents.append(a)
                by_output['trader'].append(a)
                total_inv_trader += a.inv_get(Goods.food, 0) + a.inv_get(Goods.wood, 0) + a.inv_get(Goods.furniture, 0)
                # Traders also counted as food producers — skip adding to goods by_output
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
                # Per-capita non-producer inventory (agents not producing this good)
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

    def _log_population_rate(self):
        if len(self.total_population) >= 10:
            pop_10_ago = self.total_population[-10]
            current_pop = self.total_population[-1]
            population_change_pct = ((current_pop - pop_10_ago) / pop_10_ago * 100) if pop_10_ago > 0 else 0
        else:
            population_change_pct = 0
        self.population_change_rate_log.append(population_change_pct)

    # ------------------------------------------------------------------
    # Trade logging
    # ------------------------------------------------------------------

    def _log_trade_metrics(self, t):
        trader_cash = sum(a.cash for a in self.agents if a.is_trader)
        self.trader_cash_log.append(trader_cash)

        total_in_transit = 0
        for a in self.agents:
            if a.is_trader:
                for entry in a.transport_pipeline:
                    total_in_transit += entry['quantity']
        self.pipeline_depth_log.append(total_in_transit)

        for g in [Goods.food, Goods.wood, Goods.furniture]:
            if len(self.export_vol[g]) < t:
                self.export_vol[g].append(0)
                self.export_val[g].append(0.0)
                self.import_vol[g].append(0)
                self.import_val[g].append(0.0)

        total_export_val = sum(self.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if self.export_val[g])
        total_import_val = sum(self.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furniture] if self.import_val[g])
        self.trade_balance_log.append(total_export_val - total_import_val)

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    @staticmethod
    def _smooth(data, window=5):
        """5-turn rolling average. First (window-1) points use raw values."""
        if len(data) < window:
            return data
        result = list(data[:window - 1])
        for i in range(window - 1, len(data)):
            result.append(sum(data[i - window + 1:i + 1]) / window)
        return result

    def _plot_population(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Population vs time")
        axis[axis_id].set_ylabel("Population")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            axis[axis_id].plot(self.population_log[g], label=labels[g],
                           color=colors[g])
        if 'trader' in self.population_log and any(v > 0 for v in self.population_log['trader']):
            axis[axis_id].plot(self.population_log['trader'], label='Trader',
                           color='orange')
        axis[axis_id].plot(self.total_population, label='total', color='black')
        axis[axis_id].plot([-x for x in self.dead_starved_population], label='dead', color='purple')

    def _plot_inventory(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Inventory vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Inventory")
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self._smooth(self.inventory_log[g]), label=labels[g],
                               color=colors[g])
        if 'trader' in self.inventory_log and any(v > 0 for v in self.inventory_log['trader']):
            axis[axis_id].plot(self._smooth(self.inventory_log['trader']), label='Trader',
                           color='orange')

    def _plot_gini(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Gini coefficient")
        axis[axis_id].set_ylabel("Cash")
        for g in self.goods:
            axis[axis_id].plot(self.gini_log[g], label=labels[g],
                           color=colors[g])

    def _plot_demand_ratio(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Demand Ratio vs time")
        axis[axis_id].set_ylabel("Demand Ratio (log scale)")
        axis[axis_id].set_yscale('log')
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self.demand_ratio_log[g], label=labels[g],
                               color=colors[g])

    def _plot_production(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Production vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Units/round")
        axis[axis_id].set_yscale('log')
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self._smooth(self.production_log[g]), label=labels[g],
                               color=colors[g])

    def _plot_per_capita_inventory(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Inventory Per capita (excl producers)")
        axis[axis_id].set_ylabel("Inv per cap")
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self.per_capita_inventory[g], label=labels[g],
                               color=colors[g])

    def _plot_cash(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Cash vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Cash")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            axis[axis_id].plot(self._smooth(self.cash_log[g]), label=labels[g],
                           color=colors[g])
        if 'trader' in self.cash_log and any(v > 0 for v in self.cash_log['trader']):
            axis[axis_id].plot(self._smooth(self.cash_log['trader']), label='Trader',
                           color='orange')
        axis[axis_id].plot(self._smooth(self.total_cash_log), label='total', color='black')
        axis[axis_id].plot(self._smooth(self.bank_cash_log), label='bank', color='purple')

    def _plot_demand(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Demand vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Demand (log)")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self._smooth(self.demand_log[g]), label=labels[g],
                               color=colors[g])

    def _plot_sold(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Sold vs time")
        axis[axis_id].set_ylabel("Sold (log)")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self.sold_log[g], label=labels[g],
                               color=colors[g])

    def _plot_price(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Price vs time")
        axis[axis_id].set_ylabel("Price")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self.price_log[g], label=labels[g],
                               color=colors[g])

    def _plot_hunger(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Hunger vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Num hungry")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            axis[axis_id].plot(self._smooth(self.hungry_log[g]), label=labels[g],
                           color=colors[g])
        if 'trader' in self.hungry_log and any(v > 0 for v in self.hungry_log['trader']):
            axis[axis_id].plot(self._smooth(self.hungry_log['trader']), label='Trader',
                           color='orange')

    def _plot_supply(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Supply vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Supply (log)")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self._smooth(self.supply_log[g]), label=labels[g],
                               color=colors[g])

    def _plot_population_change_rate(self, axis, axis_id):
        axis[axis_id].set_title("Pop Change Rate (per 10 turns %)")
        axis[axis_id].set_ylabel("% change")
        axis[axis_id].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        axis[axis_id].plot(self.population_change_rate_log, color='black')

    def _plot_gdp(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("GDP vs time (5-turn avg)")
        axis[axis_id].set_ylabel("Total GDP (value)")
        axis[axis_id].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[axis_id].plot(self._smooth(self.gdp_by_profession_log[g]), label=labels[g],
                               color=colors[g])
        if 'trader' in self.gdp_by_profession_log and any(v > 0 for v in self.gdp_by_profession_log['trader']):
            axis[axis_id].plot(self._smooth(self.gdp_by_profession_log['trader']), label='Trader',
                           color='orange')
        axis[axis_id].plot(self._smooth(self.gdp_log), label='All', color='black')

    def _plot_purchases(self, axis, axis_id, colors, labels):
        titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
        for i in range(len(titles)):
            axis[axis_id + i].set_title(titles[i] + " Purchases")
            axis[axis_id + i].set_ylabel("Bought")
        i = 0
        for prof in self.goods:
            for g in self.goods:
                axis[axis_id + i].plot(self.bought_log[prof][g], label=labels[g],
                                   color=colors[g])
            i += 1

    def _plot_trade_balance(self, axis, axis_id):
        axis[axis_id].set_title("Trade Balance")
        axis[axis_id].set_ylabel("Export - Import ($)")
        axis[axis_id].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        axis[axis_id].plot(self.trade_balance_log, color='black')

    def _plot_exchange_rate(self, axis, axis_id):
        axis[axis_id].set_title("Exchange Rate (5-turn avg)")
        axis[axis_id].set_ylabel("Rate")
        raw = [self.exchange_rate] * len(self.total_cash_log)
        axis[axis_id].plot(self._smooth(raw),
                          color='purple', marker='o', markersize=1)

    def _plot_trader_cash(self, axis, axis_id):
        axis[axis_id].set_title("Trader Cash")
        axis[axis_id].set_ylabel("Cash")
        axis[axis_id].set_yscale('log', base=2)
        axis[axis_id].plot(self.trader_cash_log, color='orange')

    def _plot_pipeline_depth(self, axis, axis_id):
        axis[axis_id].set_title("Pipeline Depth")
        axis[axis_id].set_ylabel("Units in transit")
        axis[axis_id].plot(self.pipeline_depth_log, color='brown')

    def _plot_price_spread(self, axis, axis_id, colors, labels):
        axis[axis_id].set_title("Price Spread (A-B)")
        axis[axis_id].set_ylabel("Spread ($)")
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            if self.price_spread_log.get(g):
                axis[axis_id].plot(self.price_spread_log[g], label=labels[g],
                               color=colors[g])

    # ------------------------------------------------------------------
    # Public plot entry point
    # ------------------------------------------------------------------

    def plot(self, filename: str):
        """Generate a 5x4 grid of plots for this region."""
        figure, axis = plt.subplots(5, 4)
        axis = axis.flatten()
        figure.patch.set_facecolor('lightgrey')
        figure.set_figwidth(20)
        figure.set_figheight(12)
        plt.subplots_adjust(top=0.95, bottom=0.04, hspace=0.35, wspace=0.25)
        colors = {
            Goods.food: 'green',
            Goods.wood: 'red',
            Goods.furniture: 'blue',
            Goods.gov: 'yellow',
        }
        labels = {
            Goods.food: 'Food',
            Goods.wood: 'Wood',
            Goods.furniture: 'Furniture',
            Goods.gov: 'Gov',
        }
        axis_id = 0
        self._plot_population(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_inventory(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_gini(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_demand_ratio(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_production(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_per_capita_inventory(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_cash(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_demand(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_sold(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_price(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_hunger(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_supply(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_population_change_rate(axis, axis_id)
        axis_id += 1
        self._plot_gdp(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_purchases(axis, axis_id, colors, labels)
        axis_id += 1
        self._plot_trade_balance(axis, axis_id)
        axis_id += 1
        self._plot_exchange_rate(axis, axis_id)
        axis_id += 1
        self._plot_trader_cash(axis, axis_id)
        axis_id += 1
        self._plot_pipeline_depth(axis, axis_id)
        axis_id += 1
        self._plot_price_spread(axis, axis_id, colors, labels)

        handles, labels_list = [], []
        for ax in axis:
            h, l = ax.get_legend_handles_labels()
            for hi, li in zip(h, l):
                if li not in labels_list:
                    handles.append(hi)
                    labels_list.append(li)
        figure.legend(handles, labels_list, loc='upper right', ncol=1, fontsize='small')
        plt.grid(True)
        for ax in axis:
            ax.set_facecolor('lightgrey')
        plt.savefig(filename)
        plt.close(figure)
        print(f"Plot saved to {filename}")
