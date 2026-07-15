"""
Government class wrapping an Agent for proper money-conserving operations.
Supports multiple governments for future multi-nation simulation.
Each Government has configurable population policy attributes that gate
pronatalist measures, enabling/disabling specific mechanisms at runtime.
"""

import math
import random

import econsim_states
from econsim import Agent, InitAgent
from goods import Goods
from logger import loginfo, logwarning, logdebug
import econsim_trade_money as trade


class Government:
    """A government entity with its own Agent for proper bank interactions.

    Population policy attributes (all disabled by default) can be tuned per
    Government instance, enabling different regions/nations to pursue
    different demographic strategies.
    """

    def __init__(self, name, t, initial_cash=0):
        self.name = name
        self.agent = Agent(t)
        self.agent.output = Goods.gov
        self.agent.is_corp = False
        self.agent.is_gov = True
        InitAgent(self.agent, Goods.gov, 0, 0, initial_cash)
        self.food_inventory = {}
        self.debt = 0  # Optional tracking of total borrowed (not needed for accounting)

        # ========== Multi-Region Support ==========
        # Set of agent IDs under this government's jurisdiction.
        # Populated when agents are born into or immigrate to a region.
        self.citizen_ids = set()
        # List of future Region objects (extensible for multi-nation sim).
        self.regions = []

        # ========== Pronatalist / Population Policy Configuration ==========
        # All default to off/neutral so existing simulation behavior is unchanged.

        # 1. Baby Bonus (Singapore / Hungary / France model)
        #     Direct cash transfer to parent upon birth.
        self.baby_bonus_enabled = False
        self.baby_bonus_amount = 50.0

        # 2. Universal Basic Income (Alaska Permanent Fund / Finland model)
        #     Per-turn cash to every non-corp citizen.
        self.ubi_enabled = False
        self.ubi_amount_per_turn = 2.0

        # 3. Extended Child Food Aid (Sweden / France model)
        #     Overrides the hardcoded age-10 cutoff in provide_food_aid.
        self.child_food_aid_max_age = 10  # default matches current hardcoded value

        # 4. Fertility Multiplier (direct pronatalist incentive)
        #     Scales p_birth for this government's citizens.
        self.fertility_multiplier = 1.0

        # 5. Immigration (Canada / Australia points-based model)
        #     Injects new Agent objects at fixed intervals.
        self.immigration_enabled = False
        self.immigration_per_interval = 5
        self.immigration_interval = 50
        self._last_immigration_turn = 0

        # 6. Child Tax Deduction (Hungary / France quotient familial model)
        #     Reduces taxable income per child (living descendant).
        self.child_tax_deduction_enabled = False
        self.child_tax_deduction_per_child = 10.0

        # 7. Parental Leave (Nordic model)
        #     Pays the parent a per-turn cash amount for a fixed duration after birth.
        self.parental_leave_enabled = False
        self.parental_leave_duration = 10          # turns
        self.parental_leave_amount_per_turn = 3.0

        # 8. Mortality Reduction (Universal Healthcare model)
        #     Multiplier applied to base death probability; < 1.0 lengthens lifespan.
        self.mortality_multiplier = 1.0

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _is_citizen(self, agent):
        """Check whether an agent is under this government's jurisdiction."""
        return agent.id in self.citizen_ids

    def _add_citizen(self, agent):
        """Register an agent as a citizen of this government."""
        self.citizen_ids.add(agent.id)

    # ------------------------------------------------------------------
    #  1. Baby Bonus  (Singapore / Hungary / France)
    # ------------------------------------------------------------------
    def provide_baby_bonus(self, t, parent, newborn):
        """Transfer a one-time cash bonus to the parent after childbirth.

        Args:
            parent: Agent who just reproduced.
            newborn: The newly created Agent.
        Returns:
            float: Amount actually transferred.
        """
        if not self.baby_bonus_enabled or self.baby_bonus_amount <= 0:
            return 0.0
        if self.agent.cash < self.baby_bonus_amount:
            loginfo(t, f"Government({self.name}) insufficient cash for baby bonus")
            return 0.0
        self.agent.cash -= self.baby_bonus_amount
        parent.cash += self.baby_bonus_amount
        loginfo(t, f"Government({self.name}) paid ${self.baby_bonus_amount:.2f} baby bonus to "
                f"{parent.name()} for newborn {newborn.name()}")
        return self.baby_bonus_amount

    # ------------------------------------------------------------------
    #  2. Universal Basic Income  (Alaska / Finland)
    # ------------------------------------------------------------------
    def distribute_ubi(self, t, agents):
        """Give every eligible non-corp citizen a per-turn cash amount.

        Args:
            agents: Full agent list (filtered internally by citizenship).
        Returns:
            float: Total UBI distributed this turn.
        """
        if not self.ubi_enabled or self.ubi_amount_per_turn <= 0:
            return 0.0

        total = 0.0
        for agent in agents:
            if agent.is_corp or agent.alive is False:
                continue
            if not self._is_citizen(agent):
                continue
            agent.cash += self.ubi_amount_per_turn
            total += self.ubi_amount_per_turn

        if total > 0 and self.agent.cash >= total:
            self.agent.cash -= total
            logdebug(t, f"Government({self.name}) distributed ${total:.2f} UBI "
                     f"to {len([a for a in agents if self._is_citizen(a) and not a.is_corp])} citizens")
        elif total > 0:
            # Gov can't fully fund — distribute whatever is available
            shortfall = total - self.agent.cash
            # Scale down proportionally
            if self.agent.cash > 0:
                scale = self.agent.cash / total
                for agent in agents:
                    if agent.is_corp or agent.alive is False:
                        continue
                    if not self._is_citizen(agent):
                        continue
                    agent.cash -= self.ubi_amount_per_turn  # undo
                    paid = self.ubi_amount_per_turn * scale
                    agent.cash += paid
            self.agent.cash = 0.0
            logwarning(t, f"Government({self.name}) UBI shortfall ${shortfall:.2f}, scaled payments")
            total -= shortfall
        return total

    # ------------------------------------------------------------------
    #  3. Child Food Aid Max Age  (Sweden / France)
    # ------------------------------------------------------------------
    def get_child_food_aid_max_age(self):
        """Return the maximum age (in turns) for automatic newborn food aid.

        Overrides the hardcoded value ``10`` in ``provide_food_aid``.
        """
        return self.child_food_aid_max_age

    # ------------------------------------------------------------------
    #  4. Fertility Multiplier
    # ------------------------------------------------------------------
    def get_fertility_multiplier(self):
        """Return the multiplier applied to the base ``p_birth`` probability."""
        return max(0.0, self.fertility_multiplier)

    # ------------------------------------------------------------------
    #  5. Immigration  (Canada / Australia points-based)
    # ------------------------------------------------------------------
    def spawn_immigrants(self, t):
        """Create new immigrant agents if the immigration interval has elapsed.

        Returns:
            list[Agent]: Newly created immigrant agents (empty list if interval
                         not reached or feature disabled).
        """
        if not self.immigration_enabled:
            return []

        if t - self._last_immigration_turn < self.immigration_interval:
            return []
        self._last_immigration_turn = t

        new_agents = []
        for _ in range(self.immigration_per_interval):
            # Pick a random non-gov profession
            professions = [g for g in econsim_states.goods if g != Goods.gov]
            output = random.choice(professions)

            immigrant = Agent(t)
            immigrant.output = output
            immigrant.cash = 50.0 + random.uniform(0, 30)
            immigrant.inv[Goods.food] = 4
            # Give a small inventory of their own profession's output
            immigrant.inv[output] = 2

            # Register as citizen
            self._add_citizen(immigrant)

            new_agents.append(immigrant)
            loginfo(t, f"Government({self.name}) accepted immigrant {immigrant.name()} "
                    f"with ${immigrant.cash:.2f}")

        return new_agents

    # ------------------------------------------------------------------
    #  6. Child Tax Deduction  (Hungary / France)
    # ------------------------------------------------------------------
    def compute_child_tax_deduction(self, agent):
        """Return the amount to subtract from an agent's taxable income
        based on number of living descendants.

        Only active when ``child_tax_deduction_enabled`` is ``True``.
        """
        if not self.child_tax_deduction_enabled:
            return 0.0
        living_descendents = [d for d in getattr(agent, 'descendents', []) if d.alive]
        num_children = len(living_descendents)
        deduction = num_children * self.child_tax_deduction_per_child
        return max(0.0, deduction)

    # ------------------------------------------------------------------
    #  7. Parental Leave  (Nordic model)
    # ------------------------------------------------------------------
    def grant_parental_leave(self, t, parent):
        """Mark a parent as eligible for parental leave cash transfers.

        Sets ``_parental_leave_turns_remaining`` on the parent agent.
        """
        if not self.parental_leave_enabled or self.parental_leave_duration <= 0:
            return

        parent._parental_leave_turns_remaining = self.parental_leave_duration
        loginfo(t, f"Government({self.name}) granted {self.parental_leave_duration} turns of "
                f"parental leave to {parent.name()}")

    def process_parental_leave(self, t, agents):
        """Pay parental leave cash to all eligible parents and decrement their counter.

        Returns:
            float: Total leave payments made this turn.
        """
        if not self.parental_leave_enabled:
            return 0.0

        total = 0.0
        for agent in agents:
            if agent.is_corp or agent.alive is False:
                continue
            remaining = getattr(agent, '_parental_leave_turns_remaining', 0)
            if remaining <= 0:
                continue

            pay = self.parental_leave_amount_per_turn
            if self.agent.cash < pay:
                pay = max(0.0, self.agent.cash)
            if pay > 0:
                self.agent.cash -= pay
                agent.cash += pay
                total += pay

            agent._parental_leave_turns_remaining = remaining - 1
            logdebug(t, f"Government({self.name}) paid ${pay:.2f} parental leave to "
                     f"{agent.name()} ({agent._parental_leave_turns_remaining} turns remaining)")

        return total

    # ------------------------------------------------------------------
    #  8. Mortality Reduction  (Universal Healthcare)
    # ------------------------------------------------------------------
    def get_death_probability(self, agent, base_probability):
        """Return the adjusted death probability for an agent.

        The base probability (from the age-based mortality table) is multiplied
        by ``mortality_multiplier``.  Values < 1.0 extend lifespan.

        Args:
            agent: The agent subject to death.
            base_probability: Value from the standard mortality table (0-1).
        Returns:
            float: Adjusted probability, clamped to [0, 1].
        """
        return max(0.0, min(1.0, base_probability * self.mortality_multiplier))

    # ==================================================================
    #  Existing methods (refactored to use config where applicable)
    # ==================================================================

    def __repr__(self):
        return f"Government({self.name})"

    def borrow(self, t, amount, bank):
        """Borrow from the bank with a proper loan. Returns actual amount borrowed."""
        if amount <= 0:
            return 0
        prev_cash = self.agent.cash
        pre_total_deposits = bank.total_deposits
        pre_total_liabilities = bank.total_liabilities
        bank.Borrow(t, self.agent, amount)
        actual_borrowed = self.agent.cash - prev_cash
        if actual_borrowed > 0:
            self.debt += actual_borrowed
            loginfo(t, f"Government({self.name}) borrowed ${actual_borrowed:.2f} from bank. "
                    f"Total gov debt: ${self.debt:.2f}")
        return actual_borrowed

    def collect_tax(self, t, amount):
        """Receive tax revenue. Returns amount received."""
        if amount > 0:
            self.agent.cash += amount
            loginfo(t, f"Government({self.name}) collected ${amount:.2f} in taxes")
        return amount

    def get_cash(self):
        return self.agent.cash

    def get_total_wealth(self):
        """Total liquid wealth (cash + bank deposits)."""
        return self.agent.cash + trade.bank.deposits.get(self.agent, 0)

    def provide_food_aid(self, t, agents, food_price):
        """Provide emergency food to starving agents and food to newborns.

        Uses ``child_food_aid_max_age`` (configurable) instead of a hardcoded
        age cutoff.

        Returns total cost of food aid provided.
        """
        child_max_age = self.get_child_food_aid_max_age()
        total_cost = 0
        for agent in agents:
            if agent.is_corp:
                continue
            needs_food = 0
            # Newborns / children: 1 free food per turn up to child_food_aid_max_age
            if agent.age(t) <= child_max_age:
                needs_food = 1
            # Starving > 3 days: emergency food (enough to eat 4 this turn)
            if agent.hungry_steps > 3:
                current_food = agent.inv.get(Goods.food, 0)
                needed_for_meal = max(0, 4 - current_food)
                # Don't double-count: children already get 1
                if agent.age(t) <= child_max_age:
                    needed_for_meal = max(0, needed_for_meal - 1)
                needs_food = max(needs_food, needed_for_meal)

            if needs_food > 0:
                # Give food directly at no cash cost (social service)
                # Food is created from thin air for emergency aid
                agent.inv[Goods.food] += needs_food
                total_cost += needs_food * food_price  # For accounting purposes only
                if agent.hungry_steps > 3:
                    loginfo(t, agent.name(), f"received emergency food aid ({needs_food} food)")
                else:
                    loginfo(t, agent.name(), f"received child food aid ({needs_food} food)")

        return total_cost

    def distribute_welfare(self, t, agents, min_reserve=0):
        """Distribute all excess cash above min_reserve to starving agents.

        Args:
            agents: list of agents to consider for welfare
            min_reserve: minimum cash to keep for next turn's food aid
        """
        distributable = max(0, self.agent.cash - min_reserve)
        if distributable <= 0:
            return 0

        starving_agents = [agent for agent in agents
                           if agent.hungry_steps > 0 and not agent.is_corp]
        if not starving_agents:
            return 0

        wellfare = distributable / len(starving_agents)
        total_distributed = 0
        for agent in starving_agents:
            agent.cash += wellfare
            total_distributed += wellfare

        self.agent.cash -= total_distributed
        logdebug(t, f"Government({self.name}) distributed ${total_distributed:.2f} welfare "
                    f"to {len(starving_agents)} agents")
        return total_distributed

    def inherit_remainders(self, t, remainder_cash, remainder_deposits, remainder_inv=None):
        """Receive remainder inheritance (when heirs get whole-unit shares)."""
        if remainder_cash > 0:
            self.agent.cash += remainder_cash
        if remainder_deposits > 0:
            trade.bank.Deposit(self.agent, remainder_deposits)
        if remainder_inv:
            for good, amount in remainder_inv.items():
                if amount > 0:
                    self.agent.inv[good] = self.agent.inv.get(good, 0) + amount


def create_default_government(t, initial_cash=200):
    """Create the default government for the simulation."""
    gov = Government("Default", t, initial_cash)
    econsim_states.governments.append(gov)
    econsim_states.default_gov = gov
    loginfo(t, f"Created default government with ${initial_cash:.2f}")
    return gov


# ======================================================================
#  Convenience: find the government responsible for an agent
# ======================================================================

def find_government_for_agent(agent):
    """Return the Government that claims the given agent as a citizen,
    or the default government if none do."""
    for gov in econsim_states.governments:
        if agent.id in gov.citizen_ids:
            return gov
    return econsim_states.default_gov