"""
Government class wrapping an Agent for proper money-conserving operations.
Supports multiple governments for future multi-nation simulation.
Each Government has configurable population policy attributes that gate
pronatalist measures, enabling/disabling specific mechanisms at runtime.
"""

import math
import random

import econsim_states
from agent import Agent, initialize_agent, seed_traits
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
        self.agent.is_corporation = False
        self.agent.is_government = True
        initialize_agent(self.agent, Goods.gov, 0, 0, initial_cash)
        self.food_inventory = 0   # food units gov has purchased and stored
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
        #     Scales probability_birth for this government's citizens.
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

        # ========== Trade Policy Configuration ==========
        # All default to enabled for backward compatibility.

        # 9. Import Tariff (revenue on foreign goods entering the region)
        #     When enabled, a fraction of each import sale goes to the
        #     destination government.  Reduced from 10% to 3% (trade
        #     liberalization / FTA-style tariff cut).
        self.import_tariff_enabled = True
        self.import_tariff_rate = 0.03   # fraction of import sale to gov

        # 9b. Duty Drawback (tariff recycling)
        #     Real-world: importing firms get refunds on duties when the
        #     goods are re-sold (US duty drawback, EU bonded warehouses).
        #     The seller keeps this fraction of the tariff; only the
        #     remainder is government revenue.  Reduced tariff income AND
        #     better trader margins.
        self.import_drawback_enabled = True
        self.import_drawback_rate = 0.70  # fraction of tariff refunded to seller

        # 12. Probate Fee (heirless estates)
        #     Real-world: people without family leave bequests to charity;
        #     the state only takes a probate fee (bona vacantia escheat is a
        #     last resort).  The government keeps this fraction of each
        #     heirless estate; the rest goes to the regional charity.
        self.probate_fee_rate = 0.30  # fraction of heirless estate to gov

        # 10. Trader Profit Recycling (capital controls / reserve requirement)
        #     When enabled, a fraction of each import sale is deposited
        #     directly into the destination region's bank to keep liquidity
        #     in the local economy (currently 20% in foreign_sell).
        self.trader_recycling_enabled = True
        self.trader_recycling_rate = 0.20  # fraction of import sale to bank

        # 11. FX regime (Phase 1: central-bank quote with reserves)
        #     'fixed'    - mid pinned at parity; convertibility reserve-capped.
        #     'managed'  (default) - reserve-pressure rule moves the mid.
        #     'floating' - Phase 3 order book; for now behaves like managed.
        self.floating_exchange_rate_enabled = True  # legacy alias
        self.fx_regime = 'managed'

        # ========== Food Aid / Welfare Configuration ==========

        # Number of food units the gov tries to keep in inventory as a buffer
        # for lean turns. Combined with cash reserve, this ensures gov can
        # provide emergency food for at least ~10 turns at low revenue.
        self.target_food_reserve = 100
        # Minimum fraction of starving agents to feed (even if low on funds)
        self.food_aid_min_coverage = 0.1
        # Maximum fraction to feed (capped even with ample funds)
        self.food_aid_max_coverage = 0.5

        # ========== Fiscal Policy Configuration ==========
        # Tax rate applied to top 10% taxable income (0.05 - 0.75 range).
        self.tax_rate = 0.25
        # How often (in turns) the government re-evaluates its tax rate.
        self.tax_adjust_interval = 100
        # Per-turn log of how much the gov borrowed (deficit financing).
        self.borrow_log = []
        # Log of (turn, tax_rate) after each adjustment.
        self.tax_rate_log = []
        # Per-turn income decomposition (monetary income credited to gov cash /
        # deposits).  Lists of {turn, tax, tariff, inheritance} dicts, one per
        # turn, appended by seal_income() at the end of each Region.step().
        self.income_log = []
        # Accumulators for the current turn (reset by seal_income).
        self._income_pending = {}

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
            if agent.is_corporation or agent.alive is False:
                continue
            if not self._is_citizen(agent):
                continue
            agent.cash += self.ubi_amount_per_turn
            total += self.ubi_amount_per_turn

        if total > 0 and self.agent.cash >= total:
            self.agent.cash -= total
            logdebug(t, f"Government({self.name}) distributed ${total:.2f} UBI "
                     f"to {len([a for a in agents if self._is_citizen(a) and not a.is_corporation])} citizens")
        elif total > 0:
            # Gov can't fully fund — distribute whatever is available
            shortfall = total - self.agent.cash
            # Scale down proportionally
            if self.agent.cash > 0:
                scale = self.agent.cash / total
                for agent in agents:
                    if agent.is_corporation or agent.alive is False:
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
        """Return the multiplier applied to the base ``probability_birth`` probability."""
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
            seed_traits(immigrant)
            immigrant.cash = 50.0 + random.uniform(0, 30)
            immigrant.inv_set(Goods.food, 4)
            # Give a small inventory of their own profession's output
            immigrant.inv_set(output, 2)

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
        living_descendants = [d for d in getattr(agent, 'descendants', []) if d.alive]
        num_children = len(living_descendants)
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
            if agent.is_corporation or agent.alive is False:
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

    def get_trade_fee_multiplier(self):
        """Return the net fraction of a trader's sale price they actually keep
        after all destination-region fees (recycling, tariff, ask discount).

        A region's traders use this when deciding whether a cross-region
        trade is profitable.
        """
        m = 0.95  # base ask discount (sell at 95% of dest price)
        if self.trader_recycling_enabled:
            m *= (1 - self.trader_recycling_rate)
        if self.import_tariff_enabled:
            # Net tariff hit after duty drawback: the trader pays the tariff
            # on the sale but is refunded the drawback rate of it, so the
            # actual cost is tariff_rate x (1 - drawback_rate).
            net_tariff = self.import_tariff_rate * (1.0 - self.import_drawback_rate)
            m *= (1.0 - net_tariff)
        return m

    def collect_tax(self, t, amount):
        """Receive tax revenue. Returns amount received."""
        if amount > 0:
            self.agent.cash += amount
            self.record_income(t, 'tax', amount)
            loginfo(t, f"Government({self.name}) collected ${amount:.2f} in taxes")
        return amount

    def receive_tariff(self, t, amount):
        """Credit import-tariff revenue to the government and log it.

        Called from Region._clear_discriminatory when an import sale is
        settled; the buyer's payment is split between the trader's
        destination-currency wallet and this tariff share.
        """
        if amount > 0:
            self.agent.cash += amount
            self.record_income(t, 'tariff', amount)

    def record_income(self, t, source, amount):
        """Accumulate a per-turn income amount under *source*.

        Sources: 'tax', 'tariff', 'inheritance'.  Amounts are summed into
        _income_pending for the current turn and snapshotted by seal_income().
        """
        if amount <= 0:
            return
        pending = self._income_pending
        pending[source] = pending.get(source, 0.0) + amount

    def seal_income(self, t):
        """Append this turn's income snapshot to income_log and reset.

        Must be called exactly once per turn, after every income source for
        that turn has recorded (Region.step() calls this at the very end of
        the turn body).
        """
        pending = self._income_pending
        snapshot = {
            'turn': t,
            'tax': pending.get('tax', 0.0),
            'tariff': pending.get('tariff', 0.0),
            'inheritance': pending.get('inheritance', 0.0),
        }
        self.income_log.append(snapshot)
        self._income_pending = {}
        return snapshot

    # ==================================================================
    #  Food Purchasing (called by region._trade, like charity)
    # ==================================================================

    def bid_food(self, food_price, current_desired, bank):
        """Return the quantity of food this government wants to buy this turn.

        Gov tries to maintain target_food_reserve as a buffer. Withdraws
        cash from bank as needed.
        """
        max_inventory = self.target_food_reserve * 2  # cap at 2x target
        space = max_inventory - self.food_inventory
        if space <= 0:
            return 0

        gov_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        if gov_wealth < food_price:
            return 0

        affordable = gov_wealth // food_price
        needed = max(0, self.target_food_reserve - self.food_inventory)
        potential_bid = min(space, affordable, current_desired, needed)
        if potential_bid <= 0:
            return 0

        # Withdraw enough cash from bank to cover the bid
        needed_cash = potential_bid * food_price
        if self.agent.cash < needed_cash:
            from_bank = min(needed_cash - self.agent.cash,
                            bank.deposits.get(self.agent, 0))
            if from_bank > 0:
                bank.Withdraw(self.agent, from_bank)

        return potential_bid

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased."""
        self.agent.cash -= cost

    def deposit_remaining(self, bank):
        """Deposit leftover hand cash back into bank."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

    # ==================================================================
    #  Food Aid (post-lifecycle, uses inventory + scales by funds)
    # ==================================================================

    def provide_food_aid(self, t, agents, food_price):
        """Give 1 food per starving agent, scaled by available reserves.

        Coverage ranges from food_aid_min_coverage (0.1) to
        food_aid_max_coverage (0.5) depending on how much excess
        food inventory + cash the government has above its target reserve.

        Children under child_food_aid_max_age get 1 food unconditionally
        if inventory permits.

        Returns total food given.
        """
        child_max_age = self.get_child_food_aid_max_age()

        # Separate candidates: children and starving agents
        candidates = [a for a in agents
                      if not a.is_corporation and not a.is_government]
        children = [a for a in candidates
                    if a.age(t) <= child_max_age and a.hungry_steps == 0]
        starving = [a for a in candidates if a.hungry_steps > 0]

        total_food_given = 0

        # 1. Children: feed all if we have enough food
        for child in children:
            if self.food_inventory <= 0:
                break
            self.food_inventory -= 1
            child.inv_add(Goods.food, 1)
            total_food_given += 1
            loginfo(t, f"Government({self.name}) child food aid to {child.name()}")

        # 2. Determine how many starving to feed based on available surplus
        if self.food_inventory > 0 and starving:
            # Compute surplus: food + cash reserves above target
            cash_above_reserve = max(0, self.agent.cash
                                     - self.target_food_reserve * food_price)
            food_surplus = self.food_inventory + (cash_above_reserve // food_price)
            desired_feed = len(starving)

            if food_surplus >= desired_feed:
                # Ample funds: feed max_coverage
                feed_count = max(1, int(desired_feed * self.food_aid_max_coverage))
            elif food_surplus >= desired_feed * self.food_aid_min_coverage:
                # Moderate: feed proportionally
                coverage = self.food_aid_min_coverage + 0.4 * (
                    food_surplus / (desired_feed * self.food_aid_max_coverage)
                )
                feed_count = max(1, min(desired_feed,
                                        int(desired_feed * coverage)))
            else:
                # Low reserves: feed min_coverage
                feed_count = max(1, int(desired_feed * self.food_aid_min_coverage))

            feed_count = min(int(feed_count), self.food_inventory, len(starving))

            # Randomly select starving agents to feed
            if feed_count < len(starving):
                random.shuffle(starving)
            fed = starving[:int(feed_count)]

            for agent in fed:
                self.food_inventory -= 1
                agent.inv_add(Goods.food, 1)
                total_food_given += 1
                loginfo(t, f"Government({self.name}) food aid to {agent.name()} "
                        f"(hungry_steps={agent.hungry_steps})")

        if total_food_given > 0:
            loginfo(t, f"Government({self.name}) distributed {total_food_given} food "
                    f"(remaining inventory: {self.food_inventory}, "
                    f"cash: ${self.agent.cash:.2f})")

        return total_food_given

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
                           if agent.hungry_steps > 0 and not agent.is_corporation]
        if not starving_agents:
            return 0

        welfare = distributable / len(starving_agents)
        total_distributed = 0
        for agent in starving_agents:
            agent.cash += welfare
            total_distributed += welfare

        self.agent.cash -= total_distributed
        logdebug(t, f"Government({self.name}) distributed ${total_distributed:.2f} welfare "
                    f"to {len(starving_agents)} agents")
        return total_distributed


def create_default_government(t, initial_cash=200):
    """Create the default government for the simulation."""
    gov = Government("Default", t, initial_cash)
    econsim_states.governments.append(gov)
    econsim_states.default_government = gov
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
    return econsim_states.default_government