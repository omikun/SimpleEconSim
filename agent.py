"""
Leaf-level Agent module with zero simulation imports.

Provides the Agent class and InitAgent helper shared by econsim.py,
econsim_live.py, government.py, and econsim_two_region.py.

This module MUST NOT import from econsim, econsim_live, econsim_states,
econsim_trade_money, government, or econsim_two_region — doing so would
introduce circular dependencies.
"""

from collections import defaultdict

from goods import Goods
import econsim_states as st


# =============================================================================
# Global agent ID counter (shared across all modules)
# =============================================================================

_agentid_counter = [0]


def _next_agent_id() -> int:
    _agentid_counter[0] += 1
    return _agentid_counter[0]


# =============================================================================
# Agent class
# =============================================================================

class Agent:
    """Agent with all fields needed by the simulation modules."""

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
        # ---- Region / government fields ----
        self.region = None
        self._bank_ref = None
        self.is_gov = False
        # ---- Trader fields (two-region simulation) ----
        self.is_trader = False
        self.home_region = None
        self.dest_region = None
        self.inv_export = defaultdict(int)          # goods bought at home, waiting to be shipped
        self.transport_pipeline = []                # list of {'turns_left', 'good', 'qty'}
        self.inv_foreign = defaultdict(int)         # goods arrived abroad, ready to sell
        self.transport_delay = 1                    # default; overridden per region-pair

    def name(self):
        prof_label = st.profession.get(self.output, '-')
        return f'agent{self.id}-{prof_label}'

    def age(self, t):
        return t - self.birthRound

    def wealth(self):
        inv_value = sum(
            amount * st.recipes[good]['price']
            for good, amount in self.inv.items()
            if good in st.recipes
        )
        debt_value = sum(loan.principle for loan in self.loans)
        bank = self._bank_ref
        dep = bank.deposits.get(self, 0) if bank else 0
        return self.cash + dep + inv_value - debt_value

    def oweThisTurn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)


# =============================================================================
# Helper: initialise an agent's inventory and output
# =============================================================================

def InitAgent(agent, output, numInput, numFood, cash, delta=0):
    """Set an agent's output, cash, and inventory using the global recipes dict."""
    agent.output = output
    agent.cash = cash
    recipe = st.recipes.get(output, {})
    input_com = recipe.get('input', Goods.none)
    for g in st.goods:
        agent.inv[g] = 0
    if input_com != Goods.none:
        agent.inv[input_com] = numInput
    agent.inv[Goods.food] = numFood


# =============================================================================
# Helpers used by econsim_live
# =============================================================================

def GetInputCom(agent):
    """Return the input commodity required for *agent*'s output good."""
    recipe = st.recipes.get(agent.output, {})
    return recipe.get('input', Goods.none)


def GetOutputCom(agent):
    return agent.output