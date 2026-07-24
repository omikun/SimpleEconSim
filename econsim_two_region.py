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
    max_career_switches, starve_limit,
)
from logger import loginfo, logwarning, logdebug, logInit

import econsim_states as st
import econsim_trade_money as _tm
import government as govmod
from agent import Agent, InitAgent


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
TRANSPORT_DELAY = 1
TRADERS_PER_REGION = 5
MAX_TRADER_FRACTION = 0.2   # max fraction of population that can be traders

# Default profession distribution (fractions summing to ≤1.0, remainder → gov)
DEFAULT_PROFESSION_DIST = {
    Goods.food: 0.82,
    Goods.wood: 0.06,
    Goods.furn: 0.02,
}


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
# Helper: convert an agent to a trader
# =============================================================================

def _make_trader(agent, region):
    """Set an agent's fields to make them a trader."""
    agent.is_trader = True
    agent.home_region = region.name
    agent.dest_region = region.dest_region
    agent.output = Goods.food  # use food so they can survive
    agent.inv_export.clear()
    agent.transport_pipeline.clear()
    agent.inv_foreign.clear()
    _pip_fn = _agent_process_pipeline
    agent._process_pipeline = lambda: _pip_fn(agent)
    agent.transport_delay = TRANSPORT_DELAY
    agent.inv[Goods.food] = max(agent.inv.get(Goods.food, 0), 4)
    agent.employer = None  # quit any job
    loginfo(0, f"{agent.name()} became a trader in {region.name}")


# =============================================================================
# Region class
# =============================================================================

class Region:
    """A self-contained region with its own government, bank, agents, and logs."""

    def __init__(self, name: str, t: int, num_agents: int = 110,
                 profession_distribution: dict = None, num_traders: int = None):
        self.name = name
        self.agents: list = []
        if profession_distribution is None:
            profession_distribution = dict(DEFAULT_PROFESSION_DIST)
        self.profession_distribution = profession_distribution.copy()
        if num_traders is None:
            num_traders = TRADERS_PER_REGION
        self._num_traders = num_traders

        # Deep-copy global config
        self.recipes = copy.deepcopy(recipes)
        self.goods = list(goods)

        # Own bank
        self.bank = _tm.Bank()

        # Own government
        self.gov = govmod.Government(name, t, initial_cash=200)
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
        self.price_spread_log: dict = {}    # price_spread_log[good] = [price_diff_turn, ...]
        self.dest_region = None             # other region for arbitrage checks
        # ---- Phase 2: Floating exchange rate ----
        self.exchange_rate = 1.0            # units of foreign currency per 1 unit of ours
        self.cumulative_trade_balance = 0.0 # positive = export surplus, negative = import deficit

        for g in [Goods.food, Goods.wood, Goods.furn]:
            self.export_vol[g] = []
            self.price_spread_log[g] = []
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
        # Add trader tracking to per-profession logs
        self.pop_log['trader'] = []
        self.hungry_log['trader'] = []
        self.inv_log['trader'] = []
        self.per_capita_inv['trader'] = []
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

        # Create agents
        self._create_agents(t, num_agents)
        self._register_citizens()

    # ------------------------------------------------------------------
    # Agent creation
    # ------------------------------------------------------------------

    def _create_agents(self, t: int, n: int):
        # Build profession counts from distribution fractions
        prof_counts = {}
        total_assignable = 0
        for prof, frac in self.profession_distribution.items():
            count = int(n * frac)
            prof_counts[prof] = count
            total_assignable += count
        # Any remaining agents become gov agents
        prof_counts[Goods.gov] = max(0, n - total_assignable)

        loginfo(t, f"Region '{self.name}' profession allocation: { {str(k): v for k, v in prof_counts.items()} }")

        # Create agents for each profession
        agents = []
        for prof, count in prof_counts.items():
            for _ in range(count):
                agent = Agent(t)
                output = prof
                delta = 20
                cash = 120 + random.randint(-delta, delta)
                InitAgent(agent, output, 10, 2, cash)
                agent.region = self.name
                agent._bank_ref = self.bank
                agents.append(agent)

        # Add traders
        for _ in range(self._num_traders):
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
            if a.employer or a.output == Goods.gov or getattr(a, 'is_trader', False):
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

        max_demand_ratio = 0
        most_demand_good = Goods.food
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
            if max_demand_ratio < dr and tb > 0:
                max_demand_ratio = dr
                most_demand_good = good
            price = self._set_price(dr, good)
            if min(ta, tb) == 0:
                continue
            tbought, tcp = self._buy(t, good, price, ta)
            askers = sorted(self.agents, key=lambda a: a.ask, reverse=True)
            tcs, tsold = self._sell(askers, good, price, t, tbought, tcp)
            if math.fabs(tcs - tcp) > 0.1:
                logwarning(t, f"Region '{self.name}' trade {good}: ${tcs - tcp:.2f}")
            self.sold_log[good].append(tsold)

        # Update mostDemand so career switching works correctly
        _tm.mostDemand = most_demand_good

        _tm.bank = ob

    def _decide_borrow_dep(self, agents, agp, fp, t):
        for a in agents:
            _tm.BorrowIfNeedTo(t, a)
            _tm.PayLoans(a)
            self._borrow_food(a, fp)
            self._borrow_inp(a)
            self._dep_excess(a, agp)
            # Trader survival borrowing: borrow enough to survive 3 turns only
            if getattr(a, 'is_trader', False):
                survival_cost = fp * 3  # 3 turns of food
                if a.cash < survival_cost:
                    self.bank.Borrow(t, a, survival_cost - a.cash)
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
            # Pre-purchase profitability: skip if destination price <= home price
            dest = getattr(agent, 'dest_region', None)
            if dest is not None:
                dest_ask = dest.recipes[good]['price'] * 0.95
                if dest_ask <= gp:
                    return 0  # not profitable to ship
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
                    if getattr(a, 'is_trader', False):
                        if good != Goods.food:
                            # Non-food: export only
                            a.inv_export[good] += bought
                        else:
                            # Food: reserve 8 for consumption, export the rest
                            food_needed = max(0, 8 - a.inv.get(good, 0))
                            keep = min(food_needed, bought)
                            export = bought - keep
                            a.inv[good] += keep
                            if export > 0:
                                a.inv_export[good] += export
                    else:
                        # Normal agent
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
        # mostDemand is already set by _trade() — do not clobber it

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

        # Post-processing: trader inheritance + career switching
        if self.dest_region is not None and t > 0:
            has_arbitrage = any(
                self.recipes[g]['price'] < self.dest_region.recipes[g]['price'] * 0.95
                for g in [Goods.wood, Goods.furn]
            )
            # Count current traders for cap check
            trader_count = sum(1 for a in result if getattr(a, 'is_trader', False))
            max_traders = int(len(result) * MAX_TRADER_FRACTION)
            for agent in result:
                if getattr(agent, 'is_corp', False):
                    continue
                # Trader inheritance: children of traders become traders (50% chance)
                parent = getattr(agent, 'parent', None)
                if (parent is not None and getattr(parent, 'is_trader', False)
                        and not getattr(agent, 'is_trader', False)
                        and trader_count < max_traders
                        and random.random() < 0.5):
                    _make_trader(agent, self)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} inherited trader from parent {parent.name()}")
                # Career switch to trader: struggling agents with arbitrage opportunity (0.3% chance)
                elif (not getattr(agent, 'is_trader', False)
                      and has_arbitrage
                      and (agent.cash < 20 or agent.hungry_steps > 0)
                      and trader_count < max_traders
                      and random.random() < 0.003):
                    _make_trader(agent, self)
                    trader_count += 1
                    loginfo(t, f"{agent.name()} switched to trader (cash=${agent.cash:.0f})")

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
        # Separate trader agents from food producers
        food_agents = [a for a in self.agents if a.output == Goods.food and not getattr(a, 'is_trader', False)]
        trader_agents = [a for a in self.agents if getattr(a, 'is_trader', False)]

        for g in self.goods:
            if g == Goods.food:
                self.pop_log[g].append(len(food_agents))
                self.cash_log[g].append(sum(a.cash for a in food_agents))
                self.gini_log[g].append(_local_compute_gini(food_agents, g))
            else:
                self.pop_log[g].append(sum(1 for a in self.agents if a.output == g))
                self.cash_log[g].append(sum(a.cash for a in self.agents if a.output == g))
                self.gini_log[g].append(_local_compute_gini(self.agents, g))
            if g != Goods.gov:
                if g == Goods.food:
                    self.inv_log[g].append(sum(a.inv.get(g, 0) for a in food_agents))
                    nl = [a.inv[g] for a in food_agents if a.output != g]
                else:
                    self.inv_log[g].append(sum(a.inv.get(g, 0) for a in self.agents))
                    nl = [a.inv[g] for a in self.agents if a.output != g]
                self.per_capita_inv[g].append(mean(nl) if nl else 0)
                self.price_log[g].append(self.recipes[g]['price'])

        # Log trader-specific metrics
        self.pop_log['trader'].append(len(trader_agents))
        self.cash_log['trader'].append(sum(a.cash for a in trader_agents))
        self.gini_log['trader'].append(_local_compute_gini(trader_agents, Goods.food))
        self.hungry_log['trader'].append(sum(1 for a in trader_agents if a.hungry_steps > 0))
        self.inv_log['trader'].append(sum(a.inv.get(g, 0) for a in trader_agents for g in [Goods.food, Goods.wood, Goods.furn]))
        nl_t = [a.inv.get(Goods.food, 0) for a in trader_agents if a.output != Goods.food]
        self.per_capita_inv['trader'].append(mean(nl_t) if nl_t else 0)
        self.production_log['trader'].append(0)
        self.gdp_by_profession_log['trader'].append(0)

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
        trader_cash = sum(a.cash for a in self.agents if getattr(a, 'is_trader', False))
        self.trader_cash_log.append(trader_cash)

        total_in_transit = 0
        for a in self.agents:
            if getattr(a, 'is_trader', False):
                for entry in getattr(a, 'transport_pipeline', []):
                    total_in_transit += entry['qty']
        self.pipeline_depth_log.append(total_in_transit)

        for g in [Goods.food, Goods.wood, Goods.furn]:
            if len(self.export_vol[g]) < t:
                self.export_vol[g].append(0)
                self.export_val[g].append(0.0)
                self.import_vol[g].append(0)
                self.import_val[g].append(0.0)

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

        colors = {Goods.food: 'green', Goods.wood: 'red', Goods.furn: 'blue', Goods.gov: 'yellow', 'trader': 'purple'}
        labels = {Goods.food: 'Food', Goods.wood: 'Wood', Goods.furn: 'carp', Goods.gov: 'gov', 'trader': 'Traders'}

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
        aid += 4

        # Trade analytics subplots (slots 20-23)
        self._plot_trade_balance(axis, aid); aid += 1
        self._plot_trade_volume(axis, aid, colors, labels); aid += 1
        self._plot_price_spread(axis, aid, colors, labels); aid += 1
        self._plot_trader_wealth_pipeline(axis, aid); aid += 1

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
        if 'trader' in self.pop_log and self.pop_log['trader']:
            axis[aid].plot(self.pop_log['trader'], label=labels['trader'], color=colors['trader'])
        axis[aid].plot(self.total_pop, label='total', color='black')
        axis[aid].plot([-x for x in self.deadstarve_pop], label='dead', color='purple')

    def _plot_inv(self, axis, aid, colors, labels):
        axis[aid].set_title("Inventory vs time")
        axis[aid].set_ylabel("Inventory")
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.inv_log[g], label=labels[g], color=colors[g])
        if 'trader' in self.inv_log and self.inv_log['trader']:
            axis[aid].plot(self.inv_log['trader'], label=labels['trader'], color=colors['trader'])

    def _plot_gini(self, axis, aid, colors, labels):
        axis[aid].set_title("Gini coefficient")
        axis[aid].set_ylabel("Cash")
        rg = [self.goods[-1]] + self.goods[:-1]
        for g in rg:
            axis[aid].plot(self.gini_log[g], label=labels[g], color=colors[g])
        if 'trader' in self.gini_log and self.gini_log['trader']:
            axis[aid].plot(self.gini_log['trader'], label=labels['trader'], color=colors['trader'])

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
        if 'trader' in self.production_log and self.production_log['trader']:
            axis[aid].plot(self.production_log['trader'], label=labels['trader'], color=colors['trader'], linestyle=':')

    def _plot_pci(self, axis, aid, colors, labels):
        axis[aid].set_title("Inventory Per capita (excl producers)")
        axis[aid].set_ylabel("Inv per cap")
        for g in self.goods:
            if g != Goods.gov:
                axis[aid].plot(self.per_capita_inv[g], label=labels[g], color=colors[g])
        if 'trader' in self.per_capita_inv and self.per_capita_inv['trader']:
            axis[aid].plot(self.per_capita_inv['trader'], label=labels['trader'], color=colors['trader'])

    def _plot_cash(self, axis, aid, colors, labels):
        axis[aid].set_title("Cash vs time")
        axis[aid].set_ylabel("Cash")
        axis[aid].set_yscale('log', base=2)
        for g in self.goods:
            axis[aid].plot(self.cash_log[g], label=labels[g], color=colors[g])
        if 'trader' in self.cash_log and self.cash_log['trader']:
            axis[aid].plot(self.cash_log['trader'], label=labels['trader'], color=colors['trader'])
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
        if 'trader' in self.hungry_log and self.hungry_log['trader']:
            axis[aid].plot(self.hungry_log['trader'], label=labels['trader'], color=colors['trader'])

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
        if 'trader' in self.gdp_by_profession_log and self.gdp_by_profession_log['trader']:
            axis[aid].plot(self.gdp_by_profession_log['trader'], label=labels['trader'], color=colors['trader'], linestyle=':')

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

    # ---- Trade analytics subplots ----

    def _plot_trade_balance(self, axis, aid):
        axis[aid].set_title("Trade Balance (net export value)")
        axis[aid].set_ylabel("$ per turn")
        axis[aid].axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        axis[aid].plot(self.trade_balance_log, color='black')

    def _plot_trade_volume(self, axis, aid, colors, labels):
        axis[aid].set_title("Trade Volume (export)")
        axis[aid].set_ylabel("Units")
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if self.export_vol.get(g):
                axis[aid].plot(self.export_vol[g], label=f"EXP {labels[g]}", color=colors[g], linestyle='-')
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if self.import_vol.get(g):
                axis[aid].plot(self.import_vol[g], label=f"IMP {labels[g]}", color=colors[g], linestyle=':')

    def _plot_price_spread(self, axis, aid, colors, labels):
        axis[aid].set_title("Price Spread (A-B abs diff)")
        axis[aid].set_ylabel("Price diff $")
        axis[aid].set_yscale('log', base=2)
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if self.price_spread_log.get(g):
                axis[aid].plot(self.price_spread_log[g], label=labels[g], color=colors[g])

    def _plot_trader_wealth_pipeline(self, axis, aid):
        axis[aid].set_title("Trader Wealth & Pipeline")
        axis[aid].set_ylabel("Cash $")
        ax2 = axis[aid].twinx()
        ax2.set_ylabel("Pipeline units", color='gray')
        axis[aid].plot(self.trader_cash_log, color='green', label='Trader cash')
        ax2.plot(self.pipeline_depth_log, color='orange', linestyle='--', label='Pipeline depth')
        lines1, labels1 = axis[aid].get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        axis[aid].legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize='x-small')
        ax2.tick_params(axis='y', colors='gray')


# =============================================================================
# Inter-region transport & foreign-sell
# =============================================================================

def process_transport(t, region_a, region_b):
    """Process transport pipelines for all traders in both regions."""
    for trader in region_a.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()
    for trader in region_b.agents:
        if not getattr(trader, 'is_trader', False):
            continue
        trader._process_pipeline()


def _agent_process_pipeline(self):
    new_pipeline = []
    for entry in self.transport_pipeline:
        entry['turns_left'] -= 1
        if entry['turns_left'] <= 0:
            self.inv_foreign[entry['good']] += entry['qty']
        else:
            new_pipeline.append(entry)
    self.transport_pipeline = new_pipeline
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
    traders = [a for a in source_region.agents
               if getattr(a, 'is_trader', False) and getattr(a, 'home_region', None) == source_region.name]
    total_sold_value = 0.0
    total_sold_qty = 0
    trade_volumes = defaultdict(int)
    trade_values = defaultdict(float)

    # Accumulators for recycling totals (printed once per call)
    total_trader_profit = 0.0
    total_bank_recycle = 0.0
    total_tariff = 0.0

    for trader in traders:
        for good in [Goods.food, Goods.wood, Goods.furn]:
            qty = trader.inv_foreign.get(good, 0)
            if qty <= 0:
                continue
            price = dest_region.recipes[good]['price']
            ask_price = price * 0.95
            # Phase 2: Exchange rate adjustment for source region's buyers
            # If source region's currency is weak (rate < 1.0), imports cost more
            fx = getattr(source_region, 'exchange_rate', 1.0)
            if fx != 1.0 and getattr(source_region.gov, 'floating_exchange_rate_enabled', True):
                ask_price = ask_price / fx
            buyers = [a for a in dest_region.agents
                      if not getattr(a, 'is_trader', False) and a.cash > ask_price]
            random.shuffle(buyers)
            remaining = qty
            for buyer in buyers:
                if remaining <= 0:
                    break
                max_buy = int(buyer.cash / ask_price)
                if max_buy <= 0:
                    continue
                bought = min(remaining, max_buy, 3)
                cash = bought * ask_price
                buyer.cash -= cash
                # Default: trader keeps all (no recycling)
                trader_share = cash
                bank_share = 0.0
                tariff_share = 0.0

                # Deduct 20% for trader profit recycling (gated by destination gov policy)
                if getattr(dest_region.gov, 'trader_recycling_enabled', True):
                    bank_share = cash * 0.20
                    trader_share -= bank_share

                # Deduct 10% for import tariff (gated by destination gov policy)
                if getattr(dest_region.gov, 'import_tariff_enabled', True):
                    tariff_share = cash * 0.10
                    trader_share -= tariff_share

                trader.cash += trader_share
                if bank_share > 0:
                    dest_region.bank.total_deposits += bank_share
                if tariff_share > 0:
                    dest_region.gov.agent.cash += tariff_share
                total_trader_profit += trader_share
                total_bank_recycle += bank_share
                total_tariff += tariff_share
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
              f"({dict(trade_volumes)})"
              f"  trader ${total_trader_profit:.2f}"
              f"  bank recycle ${total_bank_recycle:.2f}"
              f"  tariff ${total_tariff:.2f}")

    for good in [Goods.food, Goods.wood, Goods.furn]:
        vol_sold = trade_volumes[good]
        val_sold = trade_values[good]
        if vol_sold > 0:
            source_region.export_vol[good].append(vol_sold)
            source_region.export_val[good].append(val_sold)
            dest_region.import_vol[good].append(vol_sold)
            dest_region.import_val[good].append(val_sold)
        else:
            source_region.export_vol[good].append(0)
            source_region.export_val[good].append(0.0)
            dest_region.import_vol[good].append(0)
            dest_region.import_val[good].append(0.0)

    return total_sold_qty, total_sold_value


# =============================================================================
# MAIN
# =============================================================================

def main():
    time_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    logInit()
    print(f"Two-Region Simulation: {time_steps} time steps per region\n")

    random.seed(42)

    # Region A: food-surplus economy (2× food production)
    # 75% farmers, 11% woodcutters, 3.7% carpenters, ~10% gov
    region_a = Region("Region_A", t=0, num_agents=110,
                       profession_distribution={Goods.food: 0.753, Goods.wood: 0.110, Goods.furn: 0.037})
    # Region B: specialization-aligned distribution (2× wood production)
    # 50% farmers, 35% woodcutters, 5% carpenters, ~10% gov
    region_b = Region("Region_B", t=0, num_agents=110,
                       profession_distribution={Goods.food: 0.50, Goods.wood: 0.35, Goods.furn: 0.05})

    # Regional specialization
    region_a.recipes[Goods.food]['production'] *= 2
    region_b.recipes[Goods.wood]['production'] *= 2

    # Wire destination regions
    region_a.dest_region = region_b
    region_b.dest_region = region_a
    for trader in region_a.agents:
        if getattr(trader, 'is_trader', False):
            trader.dest_region = region_b
    for trader in region_b.agents:
        if getattr(trader, 'is_trader', False):
            trader.dest_region = region_a

    print(f"Region_A: {len(region_a.agents)} agents, Gov: ${region_a.gov.agent.cash:.2f}")
    print(f"Region_B: {len(region_b.agents)} agents, Gov: ${region_b.gov.agent.cash:.2f}")

    for t in range(1, time_steps + 1):
        region_a.step(t)
        region_b.step(t)
        process_transport(t, region_a, region_b)
        foreign_sell(t, region_a, region_b)
        foreign_sell(t, region_b, region_a)

        # Phase 2: Adjust exchange rates based on trade balance
        for region, other in [(region_a, region_b), (region_b, region_a)]:
            turn_export = sum(region.export_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if region.export_val[g])
            turn_import = sum(region.import_val[g][-1] for g in [Goods.food, Goods.wood, Goods.furn] if region.import_val[g])
            region.cumulative_trade_balance += (turn_export - turn_import)
            if getattr(region.gov, 'floating_exchange_rate_enabled', True):
                # 0.5% adjustment per unit of cumulative imbalance
                adj = region.cumulative_trade_balance * 0.000005
                region.exchange_rate *= (1 + adj)
                region.exchange_rate = max(0.1, min(10.0, region.exchange_rate))

        for g in [Goods.food, Goods.wood, Goods.furn]:
            pa = region_a.recipes[g]['price']
            pb = region_b.recipes[g]['price']
            spread = abs(pa - pb)
            region_a.price_spread_log[g].append(spread)
            region_b.price_spread_log[g].append(spread)

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

        total_export = sum(sum(v) for v in region.export_vol.values())
        total_import = sum(sum(v) for v in region.import_vol.values())
        total_export_val = sum(sum(v) for v in region.export_val.values())
        total_import_val = sum(sum(v) for v in region.import_val.values())
        print(f"  Total Exports: {total_export} units (${total_export_val:.2f})")
        print(f"  Total Imports: {total_import} units (${total_import_val:.2f})")
        net_trade = total_export_val - total_import_val
        sign = "+" if net_trade >= 0 else ""
        print(f"  Net Trade Balance: {sign}${net_trade:.2f}")
        avg_spread = {}
        for g in [Goods.food, Goods.wood, Goods.furn]:
            if region.price_spread_log.get(g) and len(region.price_spread_log[g]) > 0:
                avg_spread[g] = sum(region.price_spread_log[g]) / len(region.price_spread_log[g])
        if avg_spread:
            spread_str = ", ".join(f"{Goods(g).name}: ${s:.2f}" for g, s in avg_spread.items())
            print(f"  Avg Price Spread: {spread_str}")
        trader_roi = 0.0
        init_trader_cash = region.trader_cash_log[0] if region.trader_cash_log else 1
        final_trader_cash = region.trader_cash_log[-1] if region.trader_cash_log else 0
        if init_trader_cash > 0:
            trader_roi = (final_trader_cash - init_trader_cash) / init_trader_cash * 100
        print(f"  Trader ROI: {trader_roi:.1f}% (${init_trader_cash:.0f}→${final_trader_cash:.0f})")

    print("\nDone.")


if __name__ == "__main__":
    main()