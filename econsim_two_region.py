#!/usr/bin/env python3
"""
Two-region economic simulation.

Initializes two identical regions, each with its own Government, bank, agent
population, and logging state.  Each region runs an independent economic
simulation.  A separate plot image file is generated for each region.

Usage:
    python3 econsim_two_region.py [time_steps]
"""

import sys
import math
import random
import copy
from statistics import mean
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from goods import Goods
from econsim_states import (
    recipes, goods, profession, p_birth, p_death, birthGap,
    max_career_switches, starve_limit, agentid,
)
from logger import loginfo, logwarning, logdebug, logInit

import econsim_states as st
import econsim_trade_money as _tm


# =============================================================================
# Trader constant (acts like a Goods enum value but avoids enum extension issues)
# =============================================================================
TRADER_GOOD = Goods.none  # placeholder; traders use Goods.none as their output
# Override profession mapping for trader-type agents
profession[Goods.none] = 'T'  # traders show as 'T'

# =============================================================================
# Initialise recipes (normally done by econsim.py at module load)
# =============================================================================

recipes[Goods.food] = {
    'commodity': Goods.food, 'production': 5, 'price': 1, 'numInput': 0,
    'maxtotalprod': 10000, 'maxinv': 20,
}
recipes[Goods.wood] = {
    'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0,
    'maxtotalprod': 3000, 'maxinv': 10,
}
recipes[Goods.furn] = {
    'commodity': Goods.furn, 'production': 1, 'input': Goods.wood,
    'numInput': 2, 'price': 25, 'maxtotalprod': 300, 'maxinv': 5,
}
recipes[Goods.gov] = {
    'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1,
    'maxtotalprod': 0, 'maxinv': 0,
}
# Set default transport delay (turns) — future: configured per region-pair
TRANSPORT_DELAY = 3
TRADERS_PER_REGION = 5


# =============================================================================
# Global agent ID counter (shared across all regions)
# =============================================================================

_agentid_counter = [0]


def _next_agent_id() -> int:
    _agentid_counter[0] += 1
    return _agentid_counter[0]


# =============================================================================
# Minimal Agent class (avoids importing econsim.py which has circular deps)
# =============================================================================

class Agent:
    """Agent with all fields needed by the simulation."""

    def __init__(self, t):
        self.id = _next_agent_id()
        self.birthRound = t
        self.alive = True
        self.parent = None
        self.descendents = []
        self.bid = 0
        self.ask = 0
        self.output = Goods.none
        self.hungry_steps = 0
        self.cash = 0
        self.inv = {}
        self.cost_basis = {}
        self.lastCareerSwitch = 0
        self.lastRepro = 0
        self.loans = []
        self.employer = None
        self.employees = []
        self.is_corp = False
        self.wage = 0
        self.hiredAt = 0
        self.owner = None
        self.company_owned = None
        self.max_employees = 0
        self.consumption_mult = 1.0
        self.tax_loss_carryforward = 0.0
        self.retained_earnings = 0.0
        self.owner_loan = 0.0
        self._start_cash = 0
        self._start_deposits = 0
        self._delta_cash = 0
        self._delta_deposits = 0
        self.region = None
        self.is_gov = False
        # ---- Trader fields ----
        self.is_trader = False
        self.home_region = None
        self.inv_export = defaultdict(int)      # goods bought at home, waiting to be shipped
        self.transport_pipeline = []            # list of {'turns_left', 'good', 'qty'}
        self.inv_foreign = defaultdict(int)     # goods arrived abroad, ready to sell
        self.transport_delay = TRANSPORT_DELAY

    def name(self):
        return 'agent' + str(self.id) + '-' + profession[self.output]

    def age(self, t):
        return t - self.birthRound

    def wealth(self):
        inv_value = sum(
            amount * recipes[good]['price']
            for good, amount in self.inv.items()
            if good in recipes
        )
        debt_value = sum(loan.principle for loan in self.loans)
        bank = getattr(self, '_bank_ref', None)
        dep = bank.deposits.get(self, 0) if bank else 0
        return self.cash + dep + inv_value - debt_value

    def oweThisTurn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)


def InitAgent(agent, output, numInput, numFood, cash, delta=0):
    """Initialize agent inventory and output using global recipes."""
    agent.output = output
    agent.cash = cash
    recipe = recipes.get(output, {})
    input_com = recipe.get('input', Goods.none)
    for g in goods:
        agent.inv[g] = 0
    if input_com != Goods.none:
        agent.inv[input_com] = numInput
    agent.inv[Goods.food] = numFood


# =============================================================================
# Local helpers
# =============================================================================

def _local_num_agents(agents, good):
    return sum(agent.output == good for agent in agents)


def _local_compute_gini(agents, good):
    vals = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(vals)
    if n == 0:
        return 0
    mc = sum(vals) / n
    if mc == 0:
        return 0
    ds = 0
    for i in range(n):
        for j in range(n):
            ds += abs(vals[i] - vals[j])
    return ds / (2 * n * n * mc)


def _local_get_total_cash(agents, bank):
    bc = bank.total_deposits - bank.total_liabilities
    return sum(a.cash for a in agents) + bc


# =============================================================================
# Minimal Government class (replaces government.py to avoid circular imports)
# =============================================================================

class MinGov:
    """Minimal government providing all methods called by econsim_live.Live()."""

    def __init__(self, name, t, initial_cash=200):
        self.name = name
        self.agent = Agent(t)
        self.agent.output = Goods.gov
        self.agent.is_corp = False
        self.agent.is_gov = True
        InitAgent(self.agent, Goods.gov, 0, 0, initial_cash)
        self.citizen_ids = set()
        # ---- Population policy config ----
        self.baby_bonus_enabled = False
        self.baby_bonus_amount = 50.0
        self.ubi_enabled = False
        self.ubi_amount_per_turn = 2.0
        self.child_food_aid_max_age = 10
        self.fertility_multiplier = 1.0
        self.immigration_enabled = False
        self.immigration_per_interval = 5
        self.immigration_interval = 50
        self._last_immigration_turn = 0
        self.child_tax_deduction_enabled = False
        self.child_tax_deduction_per_child = 10.0
        self.parental_leave_enabled = False
        self.parental_leave_duration = 10
        self.parental_leave_amount_per_turn = 3.0
        self.mortality_multiplier = 1.0

    def __repr__(self):
        return f"MinGov({self.name})"

    def _is_citizen(self, agent):
        return agent.id in self.citizen_ids

    def _add_citizen(self, agent):
        self.citizen_ids.add(agent.id)

    # ---- UBI ----
    def distribute_ubi(self, t, agents):
        if not self.ubi_enabled or self.ubi_amount_per_turn <= 0:
            return 0.0
        total = 0.0
        for a in agents:
            if a.is_corp or not a.alive:
                continue
            if not self._is_citizen(a):
                continue
            a.cash += self.ubi_amount_per_turn
            total += self.ubi_amount_per_turn
        if total > 0 and self.agent.cash >= total:
            self.agent.cash -= total
        elif total > 0:
            scale = self.agent.cash / total if total > 0 else 0
            for a in agents:
                if a.is_corp or not a.alive:
                    continue
                if not self._is_citizen(a):
                    continue
                a.cash -= self.ubi_amount_per_turn
                a.cash += self.ubi_amount_per_turn * scale
            self.agent.cash = 0.0
        return total

    # ---- Immigration ----
    def spawn_immigrants(self, t):
        if not self.immigration_enabled:
            return []
        if t - self._last_immigration_turn < self.immigration_interval:
            return []
        self._last_immigration_turn = t
        new_agents = []
        profs = [g for g in goods if g != Goods.gov]
        for _ in range(self.immigration_per_interval):
            output = random.choice(profs)
            immigrant = Agent(t)
            immigrant.output = output
            immigrant.cash = 50.0 + random.uniform(0, 30)
            immigrant.inv[Goods.food] = 4
            immigrant.inv[output] = 2
            self._add_citizen(immigrant)
            new_agents.append(immigrant)
        return new_agents

    # ---- Parental leave ----
    def grant_parental_leave(self, t, parent):
        if not self.parental_leave_enabled or self.parental_leave_duration <= 0:
            return
        parent._parental_leave_turns_remaining = self.parental_leave_duration

    def process_parental_leave(self, t, agents):
        if not self.parental_leave_enabled:
            return 0.0
        total = 0.0
        for a in agents:
            if a.is_corp or not a.alive:
                continue
            rem = getattr(a, '_parental_leave_turns_remaining', 0)
            if rem <= 0:
                continue
            pay = min(self.parental_leave_amount_per_turn, self.agent.cash)
            if pay > 0:
                self.agent.cash -= pay
                a.cash += pay
                total += pay
            a._parental_leave_turns_remaining = rem - 1
        return total

    # ---- Baby bonus ----
    def provide_baby_bonus(self, t, parent, newborn):
        if not self.baby_bonus_enabled or self.baby_bonus_amount <= 0:
            return 0.0
        if self.agent.cash < self.baby_bonus_amount:
            return 0.0
        self.agent.cash -= self.baby_bonus_amount
        parent.cash += self.baby_bonus_amount
        return self.baby_bonus_amount

    # ---- Food aid ----
    def provide_food_aid(self, t, agents, food_price):
        child_max_age = self.child_food_aid_max_age
        total_cost = 0
        for a in agents:
            if a.is_corp:
                continue
            needs = 0
            if a.age(t) <= child_max_age:
                needs = 1
            if a.hungry_steps > 3:
                cur = a.inv.get(Goods.food, 0)
                needed = max(0, 4 - cur)
                if a.age(t) <= child_max_age:
                    needed = max(0, needed - 1)
                needs = max(needs, needed)
            if needs > 0:
                a.inv[Goods.food] += needs
                total_cost += needs * food_price
        return total_cost

    # ---- Welfare ----
    def distribute_welfare(self, t, agents, min_reserve=0):
        distributable = max(0, self.agent.cash - min_reserve)
        if distributable <= 0:
            return 0
        starving = [a for a in agents if a.hungry_steps > 0 and not a.is_corp]
        if not starving:
            return 0
        wf = distributable / len(starving)
        total = 0
        for a in starving:
            a.cash += wf
            total += wf
        self.agent.cash -= total
        return total

    # ---- Tax ----
    def collect_tax(self, t, amount):
        if amount > 0:
            self.agent.cash += amount
        return amount

    # ---- Child tax deduction ----
    def compute_child_tax_deduction(self, agent):
        if not self.child_tax_deduction_enabled:
            return 0.0
        living = [d for d in getattr(agent, 'descendents', []) if d.alive]
        return len(living) * self.child_tax_deduction_per_child

    # ---- Fertility multiplier ----
    def get_fertility_multiplier(self):
        return max(0.0, self.fertility_multiplier)

    # ---- Mortality reduction ----
    def get_death_probability(self, agent, base_probability):
        return max(0.0, min(1.0, base_probability * self.mortality_multiplier))

    # ---- Convenience methods called by find_government_for_agent ----
    def provide_food_aid(self, t, agents, food_price):
        return self._provide_food_aid(t, agents, food_price)

    def _provide_food_aid(self, t, agents, food_price):
        """Duplicate to avoid method-override confusion; called from Live()."""
        child_max_age = self.child_food_aid_max_age
        total_cost = 0
        for a in agents:
            if a.is_corp:
                continue
            needs = 0
            if a.age(t) <= child_max_age:
                needs = 1
            if a.hungry_steps > 3:
                cur = a.inv.get(Goods.food, 0)
                needed = max(0, 4 - cur)
                if a.age(t) <= child_max_age:
                    needed = max(0, needed - 1)
                needs = max(needs, needed)
            if needs > 0:
                a.inv[Goods.food] += needs
                total_cost += needs * food_price
        return total_cost


# =============================================================================
# Convenience: find the government for an agent (used by econsim_live)
# =============================================================================

def find_gov_for_agent(agent):
    """Return the MinGov that claims *agent*, or the first available."""
    for gov in st.governments:
        if agent.id in gov.citizen_ids:
            return gov
    return st.default_gov


# Patch into econsim_states so _lm.Live() can find it
st.find_government_for_agent = find_gov_for_agent

# Also patch the module so that econsim_live's import of government works
# We need to ensure government.find_government_for_agent exists
import types
gov_shim = types.ModuleType('government')
gov_shim.find_government_for_agent = find_gov_for_agent
gov_shim.Government = MinGov
gov_shim.create_default_government = lambda t, initial_cash=200: None
sys.modules['government'] = gov_shim


# =============================================================================
# Region class
# =============================================================================

class Region:
    """A self-contained region with its own government, bank, agents, and logs."""

    def __init__(self, name: str, t: int, num_agents: int = 110):
        self.name = name
        self.agents: list = []

        # Deep-copy global config
        self.recipes = copy.deepcopy(recipes)
        self.goods = list(goods)

        # Own bank
        self.bank = _tm.Bank()

        # Own government
        self.gov = MinGov(name, t, initial_cash=200)
        self.gov.agent.is_gov = True

        # Logging state (mirrors econsim_states globals)
        self.pop_log: dict = {}
        self.inv_log: dict = {}
        self.hungry_log: dict = {}
        self.production_log: dict = {}
        self.demand_ratio_log: dict = {}
        self.supply_log: dict = {}
        self.demand_log: dict = {}
        self.per_capita_inv: dict = {}
        self.cash_log: dict = {}
        self.gini_log: dict = {}
        self.total_cash_log: list = []
        self.bank_cash_log: list = []
        self.price_log: dict = {Goods.food: [], Goods.wood: [], Goods.furn: []}
        self.sold_log: dict = {Goods.food: [], Goods.wood: [], Goods.furn: []}
        self.bought_log: dict = {}
        self.gdp_log: list = []
        self.gdp_by_profession_log: dict = {Goods.food: [], Goods.wood: [], Goods.furn: []}
        self.total_pop: list = []
        self.pop_change_rate_log: list = []
        self.dead_pop: list = [0]
        self.deadstarve_pop: list = [0]
        # ---- Trade logging ----
        self.export_vol: dict = {}          # export_vol[good] = [qty_sent_this_turn, ...]
        self.export_val: dict = {}          # export_val[good] = [value_sent_this_turn, ...]
        self.import_vol: dict = {}          # import_vol[good] = [qty_received_this_turn, ...]
        self.import_val: dict = {}
        self.trade_balance_log: list = []   # net export value per turn (export_val_total - import_val_total)
        self.pipeline_depth_log: list = []  # total units in transit per turn
        self.trader_cash_log: list = []     # total cash held by traders in this region

        for g in [Goods.food, Goods.wood, Goods.furn]:
            self.export_vol[g] = []
            self.export_val[g] = []
            self.import_vol[g] = []
            self.import_val[g] = []

        for g in self.goods:
            self.pop_log[g] = []
            self.hungry_log[g] = []
            if g != Goods.gov:
                self.demand_ratio_log[g] = []
                self.demand_log[g] = []
                self.supply_log[g] = []
                self.inv_log[g] = []
                self.per_capita_inv[g] = []
                self.production_log[g] = []

        for g in self.goods:
            self.cash_log[g] = []
            self.gini_log[g] = []

        for prof in self.goods:
            self.bought_log[prof] = {}
            for g in self.goods:
                self.bought_log[prof][g] = [0]

        # Create agents
        self._create_agents(t, num_agents)
        self._register_citizens()

    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    def _create_agents(self, t: int, n: int):
        agents = [Agent(t) for _ in range(n)]
        for i, agent in enumerate(agents):
            if i < int(n * 0.82):
                output = Goods.food
            elif i < int(n * 0.88):
                output = Goods.wood
            elif i < int(n * 0.90):
                output = Goods.furn
            else:
                output = Goods.gov
            delta = 20
            cash = 120 + random.randint(-delta, delta)
            InitAgent(agent, output, 10, 2, cash)
            agent.region = self.name
            agent._bank_ref = self.bank

        # Add traders
        for _ in range(TRADERS_PER_REGION):
            trader = Agent(t)
            trader.is_trader = True
            trader.output = Goods.food  # use food so they can survive like normal agents
            trader.home_region = self.name
            trader.region = self.name
            trader.cash = 200.0
            trader._bank_ref = self.bank
            for g in goods:
                trader.inv[g] = 0
            trader.inv[Goods.food] = 4  # food to survive
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
        _tm.bank = self.bank

        self._record_start()

        new_cos = self._run_labour(t)
        if new_cos:
            self.agents.extend(new_cos)

        self._produce(t)
        self._trade(t)
        self._pay_wages(t)
        self._distribute_profits(t)
        self._record_delta()
        self._collect_tax(t)
        self._log_gdp()

        if t > 0 and t % 10 == 0:
            self._recalc_mult()

        cb = self._total_cash()
        self.agents = self._live(t)
        ca = self._total_cash()
        if abs(ca - cb) > 5.0:
            print(f"  Region '{self.name}' T={t}: CASH LEAK ${ca-cb:.2f}")

        self._log_metrics(t)
        self.total_pop.append(sum(v[-1] for v in self.pop_log.values()))
        self.bank_cash_log.append(self.bank.total_deposits - self.bank.total_liabilities)
        self.total_cash_log.append(self._total_cash())
        self._log_pop_rate()

        # ---- Log trade metrics ----
        self._log_trade_metrics(t)

        for p in self.goods:
            for g in self.goods:
                self.bought_log[p][g].append(0)

        if len(self.total_cash_log) >= 2:
            d = math.fabs(self.total_cash_log[-2] - self.total_cash_log[-1])
            if d > 1e-8:
                logwarning(t, f"Region '{self.name}' cash: {self.total_cash_log[-2]:.2f}->{self.total_cash_log[-1]:.2f} (d={d:.2f})")

        if t % 100 == 0:
            circ = sum(a.cash for a in self.agents)
            print(f"--- Region '{self.name}' T={t}: circ=${circ:.0f}, "
                  f"dep=${self.bank.total_deposits:.0f}, "
                  f"liab=${self.bank.total_liabilities:.0f}, "
                  f"r={self.bank.total_deposits/max(1,circ):.1f}x")

    # ---- Internal helpers ----

    def _record_start(self):
        for a in self.agents:
            a._start_cash = a.cash
            a._start_deposits = self.bank.deposits.get(a, 0)

    def _record_delta(self):
        for a in self.agents:
            a._delta_cash = a.cash - a._start_cash
            a._delta_deposits = self.bank.deposits.get(a, 0) - a._start_deposits

    def _total_cash(self):
        return _local_get_total_cash(self.agents, self.bank)

    # ---- Labour ----

    def _run_labour(self, t):
        self._cleanup()
        self._borrow_layoff(t)
        nc = self._incorporate(t)
        self._hire(t)
        self._wage_adj(t)
        return nc

    def _cleanup(self):
        l = set(self.agents)
        for a in self.agents:
            if a.employer and a.employer not in l:
                a.employer = None
            if a.is_corp:
                a.employees = [e for e in a.employees if e in l and e.employer == a]

    def _borrow_layoff(self, t):
        for a in self.agents:
            if not a.is_corp or len(a.employees) == 0:
                continue
            tw = len(a.employees) * a.wage
            if a.cash < tw:
                self.bank.Borrow(t, a, tw - a.cash)
            while a.cash < tw and len(a.employees) > 0:
                e = a.employees.pop()
                e.employer = None
                tw = len(a.employees) * a.wage
            if len(a.employees) == 0:
                a.is_corp = False
                if a.owner:
                    a.owner.company_owned = None

    def _incorporate(self, t):
        nc = []
        for a in self.agents:
            if a.employer or a.is_corp or a.cash <= 400 or a.company_owned:
                continue
            fp = self.recipes[Goods.food]['price']
            co = Agent(t)
            co.is_corp = True
            co.output = a.output
            co.owner = a
            co._bank_ref = self.bank
            a.company_owned = co
            for g in self.goods:
                co.inv[g] = a.inv.get(g, 0)
                a.inv[g] = 0
            eq = min(a.cash * 0.3, a.cash - 60)
            stt = max(300, fp * 20)
            sh = max(0, stt - eq)
            if sh > 0:
                self.bank.Borrow(t, a, sh)
            a.cash -= eq
            co.cash = eq + sh
            sw = [x.wage for x in self.agents if x.is_corp and x.output == a.output and x.wage > 0]
            co.wage = max(sw) * 1.05 if sw else max(1.0, fp * 1.5)
            co.max_employees = random.randint(10, 25)
            nc.append(co)
        return nc

    def _hire(self, t):
        for a in self.agents:
            if not a.is_corp or len(a.employees) >= a.max_employees:
                continue
            pl = len(a.employees) * a.wage
            if a.cash <= (pl + a.wage) * 2:
                continue
            cands = [x for x in self.agents if x.employer is None and not x.is_corp and x != a]
            dist = [c for c in cands if c.hungry_steps > 0 or c.cash < 40]
            if dist:
                c = random.choice(dist)
                c.employer = a
                c.hiredAt = t
                a.employees.append(c)
                c.output = a.output
            else:
                poach = [e for e in self.agents if e.employer and e.employer != a
                         and e.employer.is_corp and len(e.employer.employees) > 1]
                if poach:
                    tgt = random.choice(poach)
                    oe = tgt.employer
                    ow = max(oe.wage * 1.1, a.wage * 1.05)
                    if a.cash > (pl + ow) * 2:
                        oe.employees.remove(tgt)
                        tgt.employer = a
                        tgt.hiredAt = t
                        tgt.output = a.output
                        a.employees.append(tgt)
                        a.wage = max(a.wage, ow)

    def _wage_adj(self, t):
        for a in self.agents:
            if not a.is_corp or len(a.employees) == 0:
                continue
            pl = len(a.employees) * a.wage
            if a.cash > pl * 5 and len(a.employees) < a.max_employees:
                a.wage *= 1.02
            elif a.cash < pl * 3:
                a.wage *= 0.95

    # ---- Production ----

    def _produce(self, t):
        napg = {g: _local_num_agents(self.agents, g) for g in self.goods}
        ltp = defaultdict(int)
        for a in self.agents:
            if a.employer or a.output == Goods.gov:
                continue
            r = self.recipes[a.output]
            if a.is_corp and len(a.employees) > 0:
                self._prod_corp(a, r, a.output, napg, ltp)
            else:
                self._prod_indep(a, r, a.output, napg, ltp)
        for g in self.goods:
            if g != Goods.gov:
                self.production_log[g].append(ltp[g])

    def _prod_corp(self, agent, recipe, output, napg, ltp):
        ne = len(agent.employees)
        mi = recipe['maxinv'] * (1 + ne)
        if agent.inv.get(output, 0) / mi >= 1:
            return
        ns = ne
        if recipe.get('numInput', 0) > 0:
            avail = agent.inv.get(recipe['input'], 0)
            active = int(min(ns, avail // recipe['numInput']))
        else:
            active = int(ns)
        if active <= 0 or recipe.get('production', 0) <= 0:
            return
        syn = 1.0 + (0.15 if ne < 4 else 0.20 if ne < 8 else 0.25 if ne < 12 else 0.30) * ne
        bp = recipe['production']
        pps = bp * syn
        ch = 1.0
        if agent.hungry_steps > 0:
            ch *= 1 / (1 + agent.hungry_steps * 0.2)
        if output in (Goods.food, Goods.wood):
            ch *= min(1.0, recipe['maxtotalprod'] / max(1, napg[output]) / bp)
        ch *= max(0, 1 - agent.inv.get(output, 0) / mi)
        succ = sum(1 for _ in range(active) if random.random() < ch)
        if succ:
            if recipe.get('numInput', 0) > 0:
                agent.inv[recipe['input']] -= succ * recipe['numInput']
            no = int(succ * pps) or 1
            agent.inv[output] += no
            ltp[output] += no

    def _prod_indep(self, agent, recipe, output, napg, ltp):
        mi = recipe['maxinv']
        if agent.inv.get(output, 0) / mi >= 1:
            return
        hi = True
        if recipe['numInput'] > 0 and agent.inv.get(recipe['input'], 0) < recipe['numInput']:
            hi = False
        no = 0
        if hi and recipe.get('production', 0) > 0:
            ch = 1.0
            if agent.hungry_steps > 0:
                ch *= 1 / (1 + agent.hungry_steps * 0.2)
            if output in (Goods.food, Goods.wood):
                ch *= min(1.0, recipe['maxtotalprod'] / max(1, napg[output]) / recipe['production'])
            ch *= max(0, 1 - agent.inv.get(output, 0) / mi)
            if random.random() < ch:
                if recipe['numInput'] > 0:
                    agent.inv[recipe['input']] -= recipe['numInput']
                no = recipe['production']
        agent.inv[output] += no
        ltp[output] += no

    # ---- Trade ----

    def _trade(self, t):
        ob = _tm.bank
        _tm.bank = self.bank

        tg = [Goods.food, Goods.wood, Goods.furn]
        agp = sum(self.recipes[g]['price'] for g in tg)
        fp = self.recipes[Goods.food]['price']
        random.shuffle(self.agents)
        self.bank.PayDepositInterest(self.agents)
        self._decide_borrow_dep(self.agents, agp, fp, t)

        for good in tg:
            cdes = 16 if good == Goods.food else 10 if good == Goods.wood else max(1, int(16 / max(1, self.recipes[good]['price'])))
            price = self.recipes[good]['price']
            ta, tb = self._gather_bids(self.agents, good, price, cdes)
            if ta == 0 and tb == 0:
                self._price_decay(good)
                continue
            dr = 5.0 if ta == 0 else tb / ta
            self.demand_ratio_log[good].append(dr)
            self.demand_log[good].append(tb)
            self.supply_log[good].append(ta)
            price = self._set_price(dr, good)
            if min(ta, tb) == 0:
                continue
            tbought, tcp = self._buy(t, good, price, ta)
            askers = sorted(self.agents, key=lambda a: a.ask, reverse=True)
            tcs, tsold = self._sell(askers, good, price, t, tbought, tcp)
            if math.fabs(tcs - tcp) > 0.1:
                logwarning(t, f"Region '{self.name}' trade {good}: ${tcs - tcp:.2f}")
            self.sold_log[good].append(tsold)

        _tm.bank = ob

    def _decide_borrow_dep(self, agents, agp, fp, t):
        for a in agents:
            _tm.BorrowIfNeedTo(t, a)
            _tm.PayLoans(a)
            self._borrow_food(a, fp)
            self._borrow_inp(a)
            self._dep_excess(a, agp)
            a.remainingCash = a.cash

    def _borrow_food(self, agent, fp):
        if agent.output != Goods.food and agent.cash < fp and agent.hungry_steps > 10:
            bb = self.bank.deposits.get(agent, 0)
            if bb > 0:
                self.bank.Withdraw(agent, min(bb, fp - agent.cash))
            if agent.cash < fp:
                self.bank.Borrow(0, agent, fp)

    def _borrow_inp(self, agent):
        r = self.recipes.get(agent.output)
        if not r or r.get('numInput', 0) <= 0:
            return
        cost = self.recipes[r['input']]['price'] * r['numInput']
        if agent.cash >= cost:
            return
        bb = self.bank.deposits.get(agent, 0)
        if bb > 0:
            self.bank.Withdraw(agent, min(bb, cost - agent.cash))
        if agent.cash < cost:
            self.bank.Borrow(0, agent, cost - agent.cash)

    def _dep_excess(self, agent, agp):
        mult = getattr(agent, 'consumption_mult', 1.0)
        tl = agent.cash + self.bank.deposits.get(agent, 0)
        cd = self.bank.deposits.get(agent, 0)
        df = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
        cf = int(agp * (100 / max(1.0, mult)))
        md = tl * df
        ex = max(0, md - cd)
        if agent.cash > cf and ex > 0:
            self.bank.Deposit(agent, min(agent.cash - cf, ex))

    def _gather_bids(self, agents, good, gp, cdes):
        ta = 0
        tb = 0
        for a in agents:
            ar = self.recipes[a.output]
            ie = a.employer is not None
            self._wd(a, gp, cdes)
            mult = getattr(a, 'consumption_mult', 1.0)
            bid = self._calc_bid(a, good, gp, cdes, ar, ie, mult)
            a.bid = bid
            a.remainingCash -= a.bid * gp
            tb += a.bid
            ask = self._calc_ask(a, good, gp, ie)
            a.ask = ask
            ta += a.ask
        return ta, tb

    def _wd(self, agent, gp, cdes):
        bb = self.bank.deposits.get(agent, 0)
        if bb > 0 and agent.remainingCash < gp * cdes:
            self.bank.Withdraw(agent, min(bb, gp * cdes - agent.remainingCash))

    def _calc_bid(self, agent, good, gp, cdes, ar, ie, mult):
        # ---- Trader: bid into inv_export ----
        if getattr(agent, 'is_trader', False):
            max_trader_inv = ar['maxinv']
            total_holding = agent.inv.get(good, 0) + agent.inv_export.get(good, 0) + agent.inv_foreign.get(good, 0)
            for pipe in agent.transport_pipeline:
                if pipe['good'] == good:
                    total_holding += pipe['qty']
            space = max(0, max_trader_inv - total_holding)
            if space <= 0 or agent.remainingCash < gp:
                return 0
            affordable = agent.remainingCash // gp
            bid = min(space, affordable, 5)  # at most 5 units per good per turn
            return max(0, bid)
        # ---- Normal agent ----
        if not ie and self._inp(agent) == good:
            ne = len(agent.employees) if agent.is_corp else 0
            des = max(0, ar['numInput'] * (1 + ne) - agent.inv.get(good, 0))
            if mult > 1.0:
                des = int(des * mult)
            aff = agent.remainingCash // gp if gp > 0 else des
            return int(min(des, aff))
        elif (ie or agent.output != good) and agent.remainingCash > gp:
            ml = ar['maxinv']
            if agent.is_corp:
                ml *= (1 + len(agent.employees))
            if mult > 1.0:
                ml = int(ml * min(mult, 3.0))
            ns = max(0, ml - agent.inv.get(good, 0))
            bd = min(cdes, agent.remainingCash // gp)
            bid = min(int(bd * mult), ns)
            if mult > 2.0 and good != Goods.food:
                extra = min(int(cdes * (mult - 1.0)), agent.remainingCash // gp) if gp > 0 else 0
                bid += min(extra, ns - bid)
            return max(0, min(bid, ns))
        return 0

    def _calc_ask(self, agent, good, gp, ie):
        # ---- Traders do NOT ask in home region (they ask in foreign region) ----
        if getattr(agent, 'is_trader', False):
            return 0
        if ie:
            return 0
        if agent.output != good and agent.output != Goods.gov:
            return 0 if agent.inv.get(good, 0) <= 0 else 0
        if agent.output == good or (agent.output == Goods.gov and agent.inv.get(good, 0) > 0):
            cm = 0.0
            ar = self.recipes.get(good, {})
            if agent.output == good and ar.get('numInput', 0) > 0 and ar.get('production', 0) > 0:
                cm = (ar['numInput'] * agent.cost_basis.get(ar['input'], 0)) / ar['production']
            if good == Goods.food and agent.output == Goods.food:
                return max(0, agent.inv.get(good, 0) - 2)
            elif gp >= cm:
                return max(0, agent.inv.get(good, 0))
        return 0

    def _inp(self, agent):
        return self.recipes[agent.output].get('input', Goods.none)

    def _buy(self, t, good, price, total_asks):
        bidders = sorted(self.agents, key=lambda a: a.hungry_steps, reverse=True)
        tb = 0
        tcp = 0.0
        for a in bidders:
            if total_asks > tb:
                bought = max(0, min(a.bid, min(total_asks - tb, int(a.cash / price))))
                cash = bought * price
                a.cash = max(0.0, a.cash - cash)
                tcp += cash
                if bought > 0:
                    if getattr(a, 'is_trader', False) and good != Goods.food:
                        # Trader export inventory
                        a.inv_export[good] += bought
                    else:
                        # Normal agent or trader buying food
                        oq = a.inv.get(good, 0)
                        oc = a.cost_basis.get(good, 0)
                        a.cost_basis[good] = ((oq * oc + bought * price) / (oq + bought)) if (oq + bought) > 0 else price
                        a.inv[good] += bought
                    tb += bought
                    self.bought_log[a.output][good][-1] += bought
        return tb, tcp

    def _sell(self, askers, good, price, t, tb, tcp):
        ts = 0
        tcs = 0.0
        for a in askers:
            if ts < tb and tcp > tcs:
                sold = min(a.ask, tb - ts)
                ts += sold
                a.cash += sold * price
                a.inv[good] -= sold
                tcs += sold * price
        return tcs, ts

    def _price_decay(self, good):
        r = self.recipes[good]
        cm = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            ic = self.recipes[r['input']]['price']
            cm = (r['numInput'] * ic) / r['production']
        if r['price'] > cm * 1.05:
            r['price'] = max(cm, r['price'] * 0.95)
        r['price'] = max(cm, r['price'])

    def _set_price(self, dr, good):
        r = self.recipes[good]
        price = r['price']
        fc = 1.0
        if r.get('numInput', 0) > 0 and r.get('production', 0) > 0:
            ic = self.recipes[r['input']]['price']
            fc = (r['numInput'] * ic) / r['production']
        fpri = self.recipes.get(Goods.food, {}).get('price', 1.0)
        lcf = (4 * fpri) / max(1, r.get('production', 1))

        def lerp(a, b, t):
            return a + (b - a) * t

        if dr >= 1:
            cl = min(5.0, dr - 1)
            price *= lerp(1.01, 1.20, cl / 5.0)
        elif dr < 0.2:
            price *= lerp(0.90, 0.95, dr / 0.2)
        elif dr < 0.5:
            price *= lerp(0.95, 1.0, (dr - 0.2) / 0.3)
        mpf = fc * 1.10 if r.get('numInput', 0) > 0 else max(lcf, 0.10)
        price = max(mpf, price, 0.1)
        r['price'] = price
        return price

    # ---- Wages ----

    def _pay_wages(self, t):
        for a in self.agents:
            if a.is_corp and len(a.employees) > 0:
                for e in a.employees:
                    wtp = min(a.cash, a.wage)
                    a.cash -= wtp
                    e.cash += wtp

    # ---- Owner profit ----

    def _distribute_profits(self, t):
        for a in self.agents:
            if not a.is_corp or not a.alive:
                continue
            if a.owner is None or not getattr(a.owner, 'alive', False):
                continue
            ow = a.owner
            pl = max(1, len(a.employees) * a.wage)
            self._repay_own_loan(a, ow, pl)
            profit = max(0, a._delta_cash + a._delta_deposits)
            if profit > 0 or a.cash > pl * 2:
                a.retained_earnings += profit
            self._pay_base(a, ow, pl)
            self._pay_share(a, ow, pl)
            self._bailout_owner(a, ow, pl)

    def _repay_own_loan(self, agent, owner, pl):
        if agent.owner_loan <= 0:
            return
        repay = min(agent.owner_loan, max(0, agent.cash - pl * 2))
        if repay > 0:
            agent.cash -= repay
            owner.cash += repay
            agent.owner_loan -= repay

    def _pay_base(self, agent, owner, pl):
        if agent.cash > pl * 2 + agent.wage:
            agent.cash -= agent.wage
            owner.cash += agent.wage

    def _pay_share(self, agent, owner, pl):
        if agent.retained_earnings <= 0 or agent.cash <= pl * 2:
            return
        oe = pl * 2
        ratio = agent.retained_earnings / oe
        sr = 0.25 * ratio / (ratio + 5)
        pd = min(sr * agent.retained_earnings, max(0, agent.cash - pl * 2))
        if pd > 0:
            agent.cash -= pd
            owner.cash += pd
            agent.retained_earnings -= pd

    def _bailout_owner(self, agent, owner, pl):
        if agent.cash >= pl:
            return
        fp = self.recipes.get(Goods.food, {}).get('price', 1)
        inject = min(pl - agent.cash, max(0, owner.cash - fp * 4))
        if inject > 0:
            owner.cash -= inject
            agent.cash += inject
            agent.owner_loan += inject

    # ---- Tax ----

    def _collect_tax(self, t):
        living = [a for a in self.agents if a.alive]
        if len(living) <= 10:
            return
        sa = sorted(living, key=lambda a: a.wealth(), reverse=True)
        tc = max(1, int(len(sa) * 0.1))
        top = sa[:tc]
        total = 0.0
        for a in top:
            ni = a._delta_cash + a._delta_deposits
            taxable = max(0.0, ni + a.tax_loss_carryforward)
            if hasattr(self.gov, 'compute_child_tax_deduction'):
                taxable = max(0.0, taxable - self.gov.compute_child_tax_deduction(a))
            if taxable > 0:
                ta = taxable * 0.5
                bb = self.bank.deposits.get(a, 0)
                actual = min(ta, a.cash + bb)
                if actual > 0:
                    ct = min(a.cash, actual)
                    a.cash -= ct
                    dt = min(bb, actual - ct)
                    if dt > 0:
                        self.bank.Withdraw(a, dt)
                        a.cash -= dt
                a.tax_loss_carryforward = 0.0
                self.gov.collect_tax(t, actual)
                total += actual
            else:
                a.tax_loss_carryforward += ni
        if total > 0 and t % 50 == 0:
            print(f"  Region '{self.name}' TAX: ${total:.2f} from top {tc}, gov=${self.gov.agent.cash:.2f}")

    def _recalc_mult(self):
        fp = self.recipes.get(Goods.food, {}).get('price', 1)
        wp = self.recipes.get(Goods.wood, {}).get('price', 1)
        fup = self.recipes.get(Goods.furn, {}).get('price', 1)
        col = max(0.1, 4 * fp + 1 * wp + 0.25 * fup)
        for a in self.agents:
            if not a.alive or a.is_corp:
                continue
            w = a.wealth()
            a.consumption_mult = max(1.0, min(10.0, math.sqrt(w / col))) if w > col else 1.0

    def _live(self, t):
        """Run life-cycle by patching global state."""
        import econsim_live as _lm

        ob = _tm.bank
        _tm.bank = self.bank
        _tm.mostDemand = Goods.gov

        # Save
        og = st.governments
        od = st.default_gov
        o_pl = st.pop_log
        o_hl = st.hungry_log
        o_dp = st.dead_pop
        o_dsp = st.deadstarve_pop
        o_rec = st.recipes
        o_sl = st.starve_limit

        # Patch st globals
        st.governments = [self.gov]
        st.default_gov = self.gov
        st.pop_log = self.pop_log
        st.hungry_log = self.hungry_log
        st.dead_pop = self.dead_pop
        st.deadstarve_pop = self.deadstarve_pop
        st.recipes = self.recipes
        st.starve_limit = starve_limit

        # Also patch the live module's local references (imported via from econsim_states import *)
        _lm.production_log = self.production_log
        _lm.recipes = self.recipes
        _lm.pop_log = self.pop_log
        _lm.hungry_log = self.hungry_log
        _lm.dead_pop = self.dead_pop
        _lm.deadstarve_pop = self.deadstarve_pop
        _lm.starve_limit = starve_limit

        try:
            result = _lm.Live(t, self.agents)
        finally:
            st.governments = og
            st.default_gov = od
            st.pop_log = o_pl
            st.hungry_log = o_hl
            st.dead_pop = o_dp
            st.deadstarve_pop = o_dsp
            st.recipes = o_rec
            st.starve_limit = o_sl
            _tm.bank = ob

            # Restore live module references
            _lm.production_log = st.production_log
            _lm.recipes = st.recipes
            _lm.pop_log = st.pop_log
            _lm.hungry_log = st.hungry_log
            _lm.dead_pop = st.dead_pop
            _lm.deadstarve_pop = st.deadstarve_pop
            _lm.starve_limit = st.starve_limit

        return result

    def _log_gdp(self):
        total = 0
        for g in self.goods:
            if g != Goods.gov:
                v = self.production_log[g][-1] * self.recipes[g]['price']
                total += v
                self.gdp_by_profession_log[g].append(v)
        self.gdp_log.append(total)

    def _log_metrics(self, t):
        for g in self.goods:
            self.pop_log[g].append(sum(1 for a in self.agents if a.output == g))
            self.cash_log[g].append(sum(a.cash for a in self.agents if a.output == g))
            self.gini_log[g].append(_local_compute_gini(self.agents, g))
            if g != Goods.gov:
                self.inv_log[g].append(sum(a.inv.get(g, 0) for a in self.agents))
                nl = [a.inv[g] for a in self.agents if a.output != g]
                self.per_capita_inv[g].append(mean(nl) if nl else 0)
                self.price_log[g].append(self.recipes[g]['price'])

    def _log_pop_rate(self):
        if len(self.total_pop) >= 10:
            p10 = self.total_pop[-10]
            cur = self.total_pop[-1]
            pct = ((cur - p10) / p10 * 100) if p10 > 0 else 0
        else:
            pct = 0
        self.pop_change_rate_log.append(pct)

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def _log_trade_metrics(self, t):
        """Log current trade metrics for this region."""
        # Trader cash
        trader_cash = sum(a.cash for a in self.agents if getattr(a, 'is_trader', False))
        self.trader_cash_log.append(trader_cash)

        # Pipeline depth
        total_in_transit = 0
        for a in self.agents:
            if getattr(a, 'is_trader', False):
                for entry in getattr(a, 'transport_pipeline', []):
                    total_in_transit += entry['qty']
        self.pipeline_depth_log.append(total_in_transit)

        # Export/import volumes: these are populated by foreign_sell via the region references
        # Ensure every good has an entry for this turn
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if len(self.export_vol[g]) < t:
                self.export_vol[g].append(0)
                self.export_val[g].append(0.0)
                self.import_vol[g].append(0)
                self.import_val[g].append(0.0)

        # Trade balance = total export value this turn - total import value this turn
        total_export_val = sum(self.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if self.export_val[g])
        total_import_val = sum(self.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if self.import_val[g])
        self.trade_balance_log.append(total_export_val - total_import_val)

    def plot(self, output_path: str, other_region=None):
        fig, axis = plt.subplots(6, 4)
        axis = axis.flatten()
        fig.patch.set_facecolor('lightgrey')
        fig.set_figwidth(20)
        fig.set_figheight(12)
        plt.subplots_adjust(top=0.98, bottom=0.02, hspace=0.05)

        colors = {Goods.food: 'green', Goods.wood: 'red', Goods.furn: 'blue', Goods.gov: 'yellow'}
        labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furn: 'carp', Goods.gov: 'gov'}

        aid = 0
        self._plot_pop(axis, aid, colors, labels); aid += 1
        self._plot_inv(axis, aid, colors, labels); aid += 1
        self._plot_gini(axis, aid, colors, labels); aid += 1
        self._plot_dr(axis, aid, colors, labels); aid += 1
        self._plot_prod(axis, aid, colors, labels); aid += 1
        self._plot_pci(axis, aid, colors, labels); aid += 1
        self._plot_cash(axis, aid, colors, labels); aid += 1
        self._plot_dem(axis, aid, colors, labels); aid += 1
        self._plot_sold(axis, aid, colors, labels); aid += 1
        self._plot_price(axis, aid, colors, labels); aid += 1
        self._plot_hunger(axis, aid, colors, labels); aid += 1
        self._plot_supply(axis, aid, colors, labels); aid += 1
        self._plot_pcr(axis, aid); aid += 1
        self._plot_gdp(axis, aid); aid += 1
        self._plot_gdp_prof(axis, aid, colors, labels); aid += 1
        self._plot_purchases(axis, aid, colors, labels)

        lh, ll = axis[2].get_legend_handles_labels()
        fig.legend(lh, ll, loc='upper right', ncol=1, fontsize='small')
        plt.grid(True)
        for ax in axis:
            ax.set_facecolor('lightgrey')
        fig.suptitle(f"Region: {self.name}", fontsize=16, y=0.99)
        plt.savefig(output_path)
        plt.close(fig)
        print(f"  Saved plot: {output_path}")

    def _plot_pop(self, axis, aid, colors, labels):
        axis[aid].set_title("Population vs time")
        axis[aid].set_ylabel("Population")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            axis[aid].plot(self.pop_log[g], label=labels[g], color=colors[g])
        axis[aid].plot(self.total_pop, label='total', color='black')
        axis[aid].plot([-x for x in self.deadstarve_pop], label='dead', color='purple')

    def _plot_inv(self, axis, aid, colors, labels):
        axis[aid].set_title("Inventory vs time")
        axis[aid].set_ylabel("Inventory")
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.inv_log[g], label=labels[g], color=colors[g])

    def _plot_gini(self, axis, aid, colors, labels):
        axis[aid].set_title("Gini coefficient")
        axis[aid].set_ylabel("Cash")
        rg = [self.goods[-1]] + self.goods[:-1]
        for g in rg:
            axis[aid].plot(self.gini_log[g], label=labels[g], color=colors[g])

    def _plot_dr(self, axis, aid, colors, labels):
        axis[aid].set_title("Demands Ratio vs time")
        axis[aid].set_ylabel("Demands (log scale)")
        axis[aid].set_yscale('log')
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.demand_ratio_log[g], label=labels[g], color=colors[g])

    def _plot_prod(self, axis, aid, colors, labels):
        axis[aid].set_title("Production vs time")
        axis[aid].set_ylabel("Units/round")
        axis[aid].set_yscale('log')
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.production_log[g], label=labels[g], color=colors[g])

    def _plot_pci(self, axis, aid, colors, labels):
        axis[aid].set_title("Inventory Per capita (excl producers)")
        axis[aid].set_ylabel("Inv per cap")
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.per_capita_inv[g], label=labels[g], color=colors[g])

    def _plot_cash(self, axis, aid, colors, labels):
        axis[aid].set_title("Cash vs time")
        axis[aid].set_ylabel("Cash")
        for g in self.goods:
            axis[aid].plot(self.cash_log[g], label=labels[g], color=colors[g])
        axis[aid].plot(self.total_cash_log, label='total', color='black')
        axis[aid].plot(self.bank_cash_log, label='bank', color='purple')

    def _plot_dem(self, axis, aid, colors, labels):
        axis[aid].set_title("Demand vs time")
        axis[aid].set_ylabel("Demands (log)")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.demand_log[g], label=labels[g], color=colors[g])

    def _plot_sold(self, axis, aid, colors, labels):
        axis[aid].set_title("Sold vs time")
        axis[aid].set_ylabel("Sold (log)")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.sold_log[g], label=labels[g], color=colors[g])

    def _plot_price(self, axis, aid, colors, labels):
        axis[aid].set_title("Price vs time")
        axis[aid].set_ylabel("Price")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.price_log[g], label=labels[g], color=colors[g])

    def _plot_hunger(self, axis, aid, colors, labels):
        axis[aid].set_title("Hunger vs time")
        axis[aid].set_ylabel("Num hungry")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            axis[aid].plot(self.hungry_log[g], label=labels[g], color=colors[g])

    def _plot_supply(self, axis, aid, colors, labels):
        axis[aid].set_title("Supply vs time")
        axis[aid].set_ylabel("Supply (log)")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.supply_log[g], label=labels[g], color=colors[g])

    def _plot_pcr(self, axis, aid):
        axis[aid].set_title("Pop Change Rate (per 10 turns %)")
        axis[aid].set_ylabel("% change")
        axis[aid].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        axis[aid].plot(self.pop_change_rate_log, color='black')

    def _plot_gdp(self, axis, aid):
        axis[aid].set_title("GDP vs time (total)")
        axis[aid].set_ylabel("GDP (value)")
        axis[aid].set_yscale('log', base=2)
        axis[aid].plot(self.gdp_log, color='black')

    def _plot_gdp_prof(self, axis, aid, colors, labels):
        axis[aid].set_title("GDP vs time (by profession)")
        axis[aid].set_ylabel("GDP (value)")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.gdp_by_profession_log[g], label=labels[g], color=colors[g])

    def _plot_purchases(self, axis, aid, colors, labels):
        titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
        for i in range(len(titles)):
            axis[aid + i].set_title(titles[i] + " Purchases")
            axis[aid + i].set_ylabel("Bought")
        i = 0
        for prof in self.goods:
            for g in self.goods:
                if g != Goods.gov:
                    axis[aid + i].plot(self.bought_log[prof][g], label=labels[g], color=colors[g])
            i += 1


# =============================================================================
# Inter-region transport & foreign-sell
# =============================================================================

def process_transport(t, region_a, region_b):
    """Process transport pipelines for all traders in both regions.
    Decrements turns_left, moves completed shipments to inv_foreign,
    then pushes new exports (inv_export) into the pipeline."""
    for trader in region_a.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()
    for trader in region_b.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()


# Add _process_pipeline method to Agent via monkey-patching
def _agent_process_pipeline(self):
    """Decrement pipeline, move arrived goods to inv_foreign,
    then push current inv_export into new pipeline entries."""
    # Step 1: decrement and move arrived goods
    new_pipeline = []
    for entry in self.transport_pipeline:
        entry['turns_left'] -= 1
        if entry['turns_left'] <= 0:
            self.inv_foreign[entry['good']] += entry['qty']
        else:
            new_pipeline.append(entry)
    self.transport_pipeline = new_pipeline
    # Step 2: push inv_export into pipeline
    for good, qty in list(self.inv_export.items()):
        if qty > 0:
            self.transport_pipeline.append({
                'turns_left': self.transport_delay,
                'good': good,
                'qty': qty,
            })
            self.inv_export[good] = 0
Agent._process_pipeline = _agent_process_pipeline


def foreign_sell(t, dest_region, source_region):
    """Traders from source_region sell their inv_foreign goods
    into dest_region's market at dest_region's prices.
    Cash flows from dest_region buyers → source_region trader cash."""
    # Find traders from source_region who have inv_foreign
    traders = [a for a in source_region.agents
               if getattr(a, 'is_trader', False) and getattr(a, 'home_region', None) == source_region.name]
    total_sold_value = 0.0
    total_sold_qty = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furn]:
            qty = trader.inv_foreign.get(good, 0)
            if qty <= 0:
                continue
            price = dest_region.recipes[good]['price']
            # Price discount to ensure sale
            ask_price = price * 0.95
            # Find buyers in dest_region (agents with remaining cash)
            buyers = [a for a in dest_region.agents
                      if not getattr(a, 'is_trader', False) and a.cash > ask_price]
            random.shuffle(buyers)
            remaining = qty
            for buyer in buyers:
                if remaining <= 0:
                    break
                # Buyer can afford at most their cash / ask_price
                max_buy = int(buyer.cash / ask_price)
                if max_buy <= 0:
                    continue
                bought = min(remaining, max_buy, 3)  # at most 3 per buyer
                cash = bought * ask_price
                buyer.cash -= cash
                trader.cash += cash
                # Goods go to buyer's inv
                oq = buyer.inv.get(good, 0)
                oc = buyer.cost_basis.get(good, 0)
                buyer.cost_basis[good] = ((oq * oc + bought * ask_price) / (oq + bought)) if (oq + bought) > 0 else ask_price
                buyer.inv[good] += bought
                remaining -= bought
                total_sold_qty += bought
                total_sold_value += cash
                trade_volumes[good] += bought
                trade_values[good] += cash
            trader.inv_foreign[good] = remaining

    if total_sold_qty > 0:
        print(f"  TRADE {source_region.name}→{dest_region.name}: "
              f"sold {total_sold_qty} units worth ${total_sold_value:.2f} "
              f"({dict(trade_volumes)})")

    return total_sold_qty, total_sold_value


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Two-Region Simulation: {time_steps} time steps per region\n")

    random.seed(42)

    region_a = Region("Region_A", t=0, num_agents=110)
    region_b = Region("Region_B", t=0, num_agents=110)

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        # Inter-region trade: transport -> foreign sell both directions
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)  # B's traders sell in A
        foreign_sell(t, region_b, region_a)  # A's traders sell in B
        if t % 50 == 0:
            print(f"Progress: turn {t}/{time_steps}")

    print("\nGenerating plots...")
    region_a.plot("region_a_output.png")
    region_b.plot("region_b_output.png")

    print("\n" + "=" * 60)
    print("FINAL SUMMARY =")
    print("=" * 60)

    for region in (region_a, region_b):
        print(f"\n--- {region.name} ---")
        lab = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furn: 'carp', Goods.gov: 'gov'}
        for g in region.goods:
            pop = region.pop_log.get(g, [0])[-1] if region.pop_log.get(g) else 0
            price = (region.price_log.get(g, [1.0])[-1] if g != Goods.gov and region.price_log.get(g) else 1.0)
            inv = (region.inv_log.get(g, [0])[-1] if g != Goods.gov and region.inv_log.get(g) else 0)
            cash = region.cash_log.get(g, [0])[-1] if region.cash_log.get(g) else 0
            print(f"  {lab[g]}: Pop={pop}, Price={price:.2f}, Inv={inv:.2f}, Cash={cash:.2f}")
        tp = region.total_pop[-1] if region.total_pop else 0
        ds = region.deadstarve_pop[-1] if region.deadstarve_pop else 0
        print(f"  Total Pop: {tp}, Dead/Starved: {ds}")
        gdp = region.gdp_log[-1] if region.gdp_log else 0
        print(f"  Final GDP/turn: ${gdp:.2f}")

    print("\nDone.")


if __name__ == "__main__":
    main()