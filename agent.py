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
# Number of goods (for pre-allocating arrays)
# =============================================================================

# IntEnum auto() assigns 1-based values.  We need max()+1 so index 5 is valid
# for Goods.none (value=5).
_NUM_GOODS = max(g.value for g in Goods) + 1


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
    """Agent with all fields needed by the simulation modules.

    inventory, inventory_export, inventory_foreign, and cost_basis are
    lists indexed by good.value (0–4), NOT dicts.  This eliminates the
    #1 profile hot spot: 617K dict.get() calls per turn.
    """

    __slots__ = (
        'id', 'birth_round', 'alive', 'parent', 'descendants',
        'bid', 'ask',
        'output',
        'hungry_steps', 'cash', 'remainingCash',
        'inventory', 'cost_basis',
        'last_career_switch', 'last_reproduction',
        'loans',
        'employer', 'employees', 'is_corporation', 'wage', 'hired_at',
        'owner', 'company_owned', 'max_employees',
        'consumption_multiplier',
        'tax_loss_carryforward', 'retained_earnings', 'owner_loan',
        '_start_cash', '_start_deposits', '_delta_cash', '_delta_deposits',
        'region', '_bank_ref', 'is_government',
        'is_charity', 'is_trader', 'home_region', 'destination_region',
        'inventory_export', 'transport_pipeline', 'inventory_foreign',
        'transport_delay',
        'wallets', 'home_currency',
        # ---- SoA slot index + cache ----
        # ---- Per-good bid/ask (set via setattr in region._trade) ----
        'bid_food', 'bid_wood', 'bid_furniture', 'bid_transport',
        'ask_food', 'ask_wood', 'ask_furniture', 'ask_transport',
        # ---- Inherited wealth protection (child of rich parent) ----
        '_birth_parent_wealth', '_birth_protection_until',
        # ---- SoA slot index + cache ----
        '_slot', '_cached_wealth',
        # ---- Trader revenue tracking ----
        '_trader_revenue', '_trader_revenue_check',
    )

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
        # Inventory as list indexed by good.value — not a dict
        self.inventory = [0] * _NUM_GOODS
        self.cost_basis = [0.0] * _NUM_GOODS
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
        self.inventory_export = [0] * _NUM_GOODS      # list, not defaultdict
        self.transport_pipeline = []                  # list of {'turns_left', 'good', 'quantity'}
        self.inventory_foreign = [0] * _NUM_GOODS     # list, not defaultdict
        self.transport_delay = 1                      # default; overridden per region-pair
        # ---- Multi-currency wallets (Phase 1 FX) ----
        self.wallets = defaultdict(float)             # currency -> balance (foreign only)
        self.home_currency = None                     # set by Region
        # ---- SoA slot index (assigned by Region) ----
        self._slot = -1
        self.remainingCash = 0
        self._cached_wealth = None
        self.bid_transport = 0
        self.ask_transport = 0
        self._trader_revenue = 0.0
        self._trader_revenue_check = 0.0

    def name(self):
        prof_label = profession.get(self.output, '-')
        return f'agent{self.id}-{prof_label}'

    def age(self, t):
        return t - self.birth_round

    # Note: _cached_wealth is initialized to None in __init__ (it's in __slots__)
    def wealth(self):
        if self._cached_wealth is not None:
            return self._cached_wealth
        r = st.recipes
        inv_val = 0.0
        inv = self.inventory
        for g_enum in Goods:
            gv = g_enum.value
            amount = inv[gv]
            if amount and g_enum in r:
                inv_val += amount * r[g_enum]['price']
        debt = 0.0
        for loan in self.loans:
            debt += loan.principle
        bank = self._bank_ref
        deposit = bank.deposits.get(self, 0) if bank else 0
        w = self.cash + deposit + inv_val - debt
        self._cached_wealth = w
        return w

    def clear_wealth_cache(self):
        self._cached_wealth = None

    def owed_this_turn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)

    # ---- Helper: get inventory value by good enum (replaces .get) ----
    def inv_get(self, good, default=0):
        """Return inventory[good.value] with a default fallback (like dict.get)."""
        val = self.inventory[good.value]
        return val if val else default

    def inv_set(self, good, value):
        """Set inventory[good.value]."""
        self.inventory[good.value] = value

    def inv_add(self, good, delta):
        """Add delta to inventory[good.value]."""
        self.inventory[good.value] += delta

    # ---- Same for cost_basis ----
    def cost_get(self, good, default=0.0):
        val = self.cost_basis[good.value]
        return val if val else default

    def cost_set(self, good, value):
        self.cost_basis[good.value] = value


# =============================================================================
# Helper: initialise an agent's inventory and output
# =============================================================================

def initialize_agent(agent, output, number_input, number_food, cash, delta=0):
    """Set an agent's output, cash, and inventory using the global recipes dict."""
    agent.output = output
    agent.cash = cash
    recipe = st.recipes.get(output, {})
    input_com = recipe.get('input', Goods.none)
    # Zero out all inventory slots, then set what's needed
    for g in Goods:
        agent.inventory[g.value] = 0
    if input_com != Goods.none:
        agent.inventory[input_com.value] = number_input
    agent.inventory[Goods.food.value] = number_food


# =============================================================================
# Helpers used by econsim_live
# =============================================================================

def get_input_commodity(agent):
    """Return the input commodity required for *agent*'s output good."""
    recipe = st.recipes.get(agent.output, {})
    return recipe.get('input', Goods.none)


def get_output_commodity(agent):
    return agent.output