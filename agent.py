"""
Leaf-level Agent module with zero simulation imports.

Provides the Agent class and InitAgent helper shared by econsim.py,
econsim_live.py, government.py, and econsim_two_region.py.

This module MUST NOT import from econsim, econsim_live, econsim_states,
econsim_trade_money, government, or econsim_two_region — doing so would
introduce circular dependencies.
"""

import random
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
        'owner_payouts',
        '_start_cash', '_start_deposits', '_delta_cash', '_delta_deposits',
        'region', '_bank_ref', 'is_government',
        'is_charity', 'is_trader', 'home_region', 'destination_region',
        'trade_good',
        'inventory_export', 'transport_pipeline', 'inventory_foreign',
        'parked_foreign', 'transport_delay',
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
        # ---- M1.1 traits (birth-seeded, heritable +mutation) ----
        'ambition', 'loyalty', 'charisma', 'risk_tolerance',
        'bigotry', 'productivity', 'fertility', 'religiousness',
        # ---- M1.2 identity tags ----
        'ethnicity', 'religion', 'politics',
        # ---- M1.3 bounded memory buffers ----
        'memory',
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
        self.trade_good = None   # trader's export specialty (None for non-traders)
        self.inventory_export = [0] * _NUM_GOODS      # list, not defaultdict
        self.transport_pipeline = []                  # list of {'turns_left', 'good', 'quantity'}
        self.inventory_foreign = [0] * _NUM_GOODS     # list, not defaultdict
        self.parked_foreign = {}                      # T1: reg_name -> [0]*_NUM_GOODS
        self.transport_delay = 1                      # default; overridden per region-pair
        # ---- Multi-currency wallets (Phase 2: lazy, practical) ----
        # Only traders normally need foreign balances.  Non-traders keep this
        # as None (no empty-dict allocation); forex.fx_add() materializes a
        # dict lazily when a balance is actually needed (e.g. inheritance).
        self.wallets = None                           # dict | None
        self.home_currency = None                     # set by Region
        # ---- SoA slot index (assigned by Region) ----
        self._slot = -1
        self.remainingCash = 0
        self._cached_wealth = None
        self.bid_transport = 0
        self.ask_transport = 0
        self._trader_revenue = 0.0
        self._trader_revenue_check = 0.0
        # ---- M1.1 traits (seeded at birth via seed_traits; neutral defaults
        # here so corporations / government agents (created without seeding)
        # stay unaffected) ----
        self.ambition = 0.5
        self.loyalty = 0.5
        self.charisma = 0.5
        self.risk_tolerance = 0.5
        self.bigotry = {}                    # dict: group -> animosity [0,1]
        self.productivity = 0.5
        self.fertility = 0.5
        self.religiousness = 0.5
        # ---- M1.2 identity tags (seeded at birth) ----
        self.ethnicity = None
        self.religion = None
        self.politics = None
        # ---- M1.3 bounded memory buffers ----
        self.memory = {}                     # key -> capped list (32)

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

    # ---- T1: parked-foreign pool (per-destination) ----
    def parked_get(self, region_name, good, default=0):
        """Quantity of *good* parked at *region_name* (0 if none)."""
        bucket = self.parked_foreign.get(region_name)
        if not bucket:
            return default
        val = bucket[good.value]
        return val if val else default

    def parked_add(self, region_name, good, qty):
        """Add *qty* of *good* to the parked pool at *region_name*."""
        bucket = self.parked_foreign.get(region_name)
        if bucket is None:
            bucket = [0] * _NUM_GOODS
            self.parked_foreign[region_name] = bucket
        bucket[good.value] += qty

    def parked_sub(self, region_name, good, qty):
        """Remove *qty* of *good* from the parked pool at *region_name*."""
        bucket = self.parked_foreign.get(region_name)
        if bucket is None:
            return
        bucket[good.value] = max(0, bucket[good.value] - qty)
        if not any(bucket):
            self.parked_foreign.pop(region_name, None)

    def parked_total(self, good):
        """Total parked quantity of *good* across all regions."""
        total = 0
        for bucket in self.parked_foreign.values():
            total += bucket[good.value]
        return total

    # ---- M1.3 bounded memory ring buffer ----
    def mem_push(self, key, value):
        """Append *value* to the memory buffer under *key*.

        Each buffer is a bounded ring (cap 32): the oldest entries drop
        off first, so memory can never grow unbounded.
        """
        buf = self.memory.get(key)
        if buf is None:
            buf = []
            self.memory[key] = buf
        buf.append(value)
        if len(buf) > MEM_CAP:
            del buf[:len(buf) - MEM_CAP]
        return buf

    def mem_last(self, key, default=None):
        """Return the most recent memory entry under *key* (or *default*)."""
        buf = self.memory.get(key)
        return buf[-1] if buf else default

    def mem_avg(self, key, default=0.0):
        """Arithmetic mean of the memory buffer under *key* (or *default*)."""
        buf = self.memory.get(key)
        if not buf:
            return default
        try:
            return sum(buf) / len(buf)
        except TypeError:
            return default

    def mem_recent(self, key, n=8):
        """Return up to *n* most recent entries under *key* (oldest first)."""
        buf = self.memory.get(key)
        if not buf:
            return []
        return buf[-n:]


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


# =============================================================================
# M1.1 Traits: birth-seeded, heritable with mutation
# =============================================================================

# Trait names that are plain floats in [0, 1].  bigotry is a dict and is
# handled separately (per-entry noise, keys preserved).
_TRAIT_SCALARS = (
    'ambition', 'loyalty', 'charisma', 'risk_tolerance',
    'productivity', 'fertility', 'religiousness',
)

# ---- M1.3 cap for every memory buffer ----
MEM_CAP = 32

# ---- M1.2 identity tag pools (small, stable sets) ----
_ETHNICITIES = ('yoro', 'kest', 'veln', 'omar')
_RELIGIONS = ('sol', 'luna', 'terra')
_POLITICS = ('conservative', 'liberal', 'populist')

# Small chance each identity tag mutates away from the parent's on birth.
_IDENTITY_MUTATION_P = 0.02


def _clamp01(x):
    return max(0.0, min(1.0, x))


def _gauss_noise(std=0.15):
    """Symmetric gaussian noise about 0, returned signed."""
    return random.gauss(0.0, std)


def _rand_identity(identity_pool):
    return identity_pool[random.randrange(len(identity_pool))]


def seed_identity(agent, parent=None):
    """Seed an agent's M1.2 identity tags.

    Without a parent (founders / immigrants / orphans): every tag is drawn
    uniform-random from its pool.  With a parent: each tag inherits by
    default, mutating to a random tag with probability ``_IDENTITY_MUTATION_P``.
    Pure state — no conservation impact.
    """
    pools = (_ETHNICITIES, _RELIGIONS, _POLITICS)
    attrs = ('ethnicity', 'religion', 'politics')
    for attr, pool in zip(attrs, pools):
        parent_tag = getattr(parent, attr, None) if parent is not None else None
        if parent_tag is None or random.random() < _IDENTITY_MUTATION_P:
            setattr(agent, attr, _rand_identity(pool))
        else:
            setattr(agent, attr, parent_tag)
    return agent


def seed_traits(agent, parent=None, groups=()):
    """Seed an agent's M1.1 trait fields AND M1.2 identity tags.

    *parent* is None for founders / immigrants / orphans: every scalar
    trait is drawn uniform-random; bigotry starts empty; identity tags
    are drawn uniform-random.

    With a parent, each scalar inherits ``clamp(parent + gauss(0, 0.15))``,
    the bigotry dict copies the parent's animosities with per-entry
    gaussian noise (entries absent in the parent stay 0), and identity
    tags inherit with a small mutation probability.

    *groups* is an iterable of identity groups (ethnicity / religion /
    politics) to pre-warm bigotry keys (animosity 0) so lookup never
    misses.  Pure state — no conservation impact.
    """
    seed_identity(agent, parent=parent)
    if parent is None:
        for name in _TRAIT_SCALARS:
            setattr(agent, name, random.random())
        agent.bigotry = {}
    else:
        for name in _TRAIT_SCALARS:
            setattr(agent, name, _clamp01(getattr(parent, name) + _gauss_noise(0.15)))
        parent_big = getattr(parent, 'bigotry', None) or {}
        agent.bigotry = {}
        for group, anim in parent_big.items():
            agent.bigotry[group] = _clamp01(anim + _gauss_noise(0.15))
    for group in groups:
        if group not in agent.bigotry:
            agent.bigotry[group] = 0.0
    return agent
