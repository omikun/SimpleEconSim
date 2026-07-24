"""
Leaf-level Agent module with zero simulation imports.

Provides the Agent class and InitAgent helper shared by econsim.py,
econsim_live.py, government.py, and econsim_two_region.py.

This module MUST NOT import from econsim, econsim_live, econsim_states,
econsim_trade_money, government, or econsim_two_region — doing so would
introduce circular dependencies.
"""

from collections import defaultdict

from goods import Goods, profession
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
        self.birth_round = t
        self.alive = True
        self.parent = None
        self.descendants = []
        self.bid = 0
        self.ask = 0
        self.output = Goods.none
        self.hungry_steps = 0
        self.cash = 0
        self.inventory = {}
        self.cost_basis = {}
        self.last_career_switch = 0
        self.last_reproduction = 0
        self.loans = []
        self.employer = None
        self.employees = []
        self.is_corporation = False
        self.wage = 0
        self.hired_at = 0
        self.owner = None
        self.company_owned = None
        self.max_employees = 0
        self.consumption_multiplier = 1.0
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
        self.is_government = False
        # ---- Trader fields (two-region simulation) ----
        self.is_trader = False
        self.home_region = None
        self.destination_region = None
        self.inventory_export = defaultdict(int)          # goods bought at home, waiting to be shipped
        self.transport_pipeline = []                      # list of {'turns_left', 'good', 'quantity'}
        self.inventory_foreign = defaultdict(int)         # goods arrived abroad, ready to sell
        self.transport_delay = 1                          # default; overridden per region-pair

    def name(self):
        prof_label = profession.get(self.output, '-')
        return f'agent{self.id}-{prof_label}'

    def age(self, t):
        return t - self.birth_round

    def wealth(self):
        inventory_value = sum(
            amount * st.recipes[good]['price']
            for good, amount in self.inventory.items()
            if good in st.recipes
        )
        debt_value = sum(loan.principle for loan in self.loans)
        bank = self._bank_ref
        deposit = bank.deposits.get(self, 0) if bank else 0
        return self.cash + deposit + inventory_value - debt_value

    def owed_this_turn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)


# =============================================================================
# Helper: initialise an agent's inventory and output
# =============================================================================

def initialize_agent(agent, output, number_input, number_food, cash, delta=0):
    """Set an agent's output, cash, and inventory using the global recipes dict."""
    agent.output = output
    agent.cash = cash
    recipe = st.recipes.get(output, {})
    input_com = recipe.get('input', Goods.none)
    for g in st.goods:
        agent.inventory[g] = 0
    if input_com != Goods.none:
        agent.inventory[input_com] = number_input
    agent.inventory[Goods.food] = number_food


# =============================================================================
# Helpers used by econsim_live
# =============================================================================

def get_input_commodity(agent):
    """Return the input commodity required for *agent*'s output good."""
    recipe = st.recipes.get(agent.output, {})
    return recipe.get('input', Goods.none)


def get_output_commodity(agent):
    return agent.output