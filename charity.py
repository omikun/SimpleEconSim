"""
Charity: a non-government entity that collects donations from wealthy agents
and corporations, buys food at market price, and distributes it to the hungry
and young.

Uses an Agent instance internally. All unspent cash is deposited in the bank
to keep total_deposits healthy. Cash is withdrawn as needed for food purchases.
"""

from goods import Goods
from logger import loginfo
from agent import Agent


class Charity:
    """Independent charity that redistributes food to the needy.

    Cash is held in an internal Agent (not in region.agents list).
    Unspent cash is deposited in the bank; it is withdrawn as needed
    for food purchases. _total_cash() adds charity.agent.cash to
    compensate for the bank deposit reduction when cash is in hand.
    """

    def __init__(self, name, recipes):
        self.name = f"{name}-Charity"
        self.recipes = recipes

        # Internal Agent for cash management. NOT added to region.agents.
        self.agent = Agent(0)
        self.agent.output = Goods.food
        self.agent.is_charity = True

        self.food_inventory = 0
        self.log = {"donations_collected": 0.0, "food_purchased": 0,
                     "food_distributed": 0, "recipients": 0}

        # Config
        self.low_cash_threshold_multiplier = 50
        self.corp_donate_normal_pct = 0.05
        self.corp_donate_emergency_pct = 0.10
        self.wealthy_donate_normal_pct = 0.02
        self.wealthy_donate_emergency_pct = 0.04
        self.wealth_donation_threshold = 100.0
        self.wealthy_fraction = 0.20
        self.max_food_per_agent = 1

    # ------------------------------------------------------------------
    # Cash helpers
    # ------------------------------------------------------------------

    @property
    def cash(self):
        """Current hand cash (agent.cash)."""
        return self.agent.cash

    @property
    def total_liquid(self):
        """Total liquid wealth including bank deposits."""
        bank = getattr(self.agent, '_bank_ref', None)
        deposit = bank.deposits.get(self.agent, 0) if bank else 0
        return self.agent.cash + deposit

    def deposit_all(self, bank):
        """Move all hand cash into bank deposits."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

    def withdraw_for_purchase(self, bank, needed):
        """Ensure agent has at least *needed* cash for a purchase."""
        if self.agent.cash >= needed:
            return
        shortfall = needed - self.agent.cash
        available = bank.deposits.get(self.agent, 0)
        if available > 0:
            bank.Withdraw(self.agent, min(available, shortfall))

    # ------------------------------------------------------------------
    # Donations
    # ------------------------------------------------------------------

    def collect_donations(self, t, agents, bank):
        """Collect donations from corporations and wealthy individuals.

        After collection, all cash is deposited into the bank
        (except what's needed for immediate food bidding).
        The _trade loop will withdraw cash when charity bids on food.
        """
        food_price = self.recipes.get(Goods.food, {}).get('price', 1.0)
        char_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        low_cash = char_wealth < food_price * self.low_cash_threshold_multiplier

        total_donated = 0.0

        # ---- Corporate donations ----
        corps = [a for a in agents if a.is_corporation]
        for corp in corps:
            retained = getattr(corp, 'retained_earnings', 0.0)
            if retained <= 0:
                continue
            donate_pct = self.corp_donate_emergency_pct if low_cash else self.corp_donate_normal_pct
            donation = min(retained * donate_pct, corp.cash)
            if donation > 0:
                corp.cash -= donation
                corp.retained_earnings -= donation
                self.agent.cash += donation
                total_donated += donation
                loginfo(t, f"{self.name} received ${donation:.2f} corp donation from {corp.name()}")

        # ---- Wealthy individual donations ----
        non_corp = [a for a in agents
                    if not a.is_corporation
                    and not a.is_trader
                    and not a.is_government
                    and a.alive]
        non_corp.sort(key=lambda a: a.wealth(), reverse=True)
        top_n = max(1, int(len(non_corp) * self.wealthy_fraction))
        wealthy = non_corp[:top_n]

        for agent in wealthy:
            w = agent.wealth()
            if w <= self.wealth_donation_threshold:
                continue
            excess = w - self.wealth_donation_threshold
            donate_pct = self.wealthy_donate_emergency_pct if low_cash else self.wealthy_donate_normal_pct
            donation = min(excess * donate_pct, agent.cash + bank.deposits.get(agent, 0))
            from_bank = min(donation, max(0, donation - agent.cash), bank.deposits.get(agent, 0))
            if from_bank > 0:
                bank.Withdraw(agent, from_bank)
            agent.cash -= donation
            self.agent.cash += donation
            total_donated += donation
            loginfo(t, f"{self.name} received ${donation:.2f} donation from {agent.name()}")

        # Store bank reference on agent so total_liquid property works
        self.agent._bank_ref = bank

        # Deposit all collected cash
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

        self.log["donations_collected"] += total_donated
        if total_donated > 0 and t % 50 == 0:
            char_wealth_after = self.agent.cash + bank.deposits.get(self.agent, 0)
            print(f"  {self.name}: collected ${total_donated:.2f} in donations "
                  f"(charity wealth: ${char_wealth_after:.2f})")

    # ------------------------------------------------------------------
    # Food bidding & purchase (called by region._trade)
    # ------------------------------------------------------------------

    def bid_food(self, food_price, current_desired, bank):
        """Return the quantity of food this charity wants to buy this turn.

        Withdraws enough cash from the bank to cover the bid if needed.
        """
        max_inventory = 50
        space = max_inventory - self.food_inventory
        if space <= 0:
            return 0

        char_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        if char_wealth < food_price:
            return 0

        affordable_from_wealth = char_wealth // food_price
        potential_bid = min(space, affordable_from_wealth, current_desired)
        if potential_bid <= 0:
            return 0

        # Withdraw enough to cover the bid
        needed = potential_bid * food_price
        self.withdraw_for_purchase(bank, needed)

        return potential_bid

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity
        self.log["food_purchased"] += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased (from agent's hand)."""
        self.agent.cash -= cost

    # ------------------------------------------------------------------
    # Post-trade deposit
    # ------------------------------------------------------------------

    def deposit_remaining(self, bank):
        """Deposit any leftover hand cash back into the bank."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

    # ------------------------------------------------------------------
    # Food distribution
    # ------------------------------------------------------------------

    def distribute_food(self, t, agents):
        """Give 1 food per agent to hungry agents first, then young agents."""
        if self.food_inventory <= 0:
            return

        hungry = [a for a in agents if a.alive and a.hungry_steps > 0
                  and not a.is_corporation]
        hungry.sort(key=lambda a: -a.hungry_steps)

        young = [a for a in agents if a.alive and a.age(t) <= 10
                 and a.hungry_steps == 0 and not a.is_corporation]

        recipients = 0
        food_given = 0

        for recipient in hungry + young:
            if self.food_inventory <= 0:
                break
            self.food_inventory -= 1
            recipient.inv_add(Goods.food, 1)
            food_given += 1
            recipients += 1
            if recipient.hungry_steps > 0:
                loginfo(t, f"{self.name} gave 1 food to hungry {recipient.name()} "
                        f"(hungry_steps={recipient.hungry_steps})")
            else:
                loginfo(t, f"{self.name} gave 1 food to young {recipient.name()} "
                        f"(age={recipient.age(t)})")

        self.log["food_distributed"] += food_given
        self.log["recipients"] += recipients

        if food_given > 0 and t % 50 == 0:
            print(f"  {self.name}: distributed {food_given} food to {recipients} agents "
                  f"(remaining food: {self.food_inventory}, cash: ${self.agent.cash:.2f})")

    def print_summary(self):
        """Print summary stats for this charity."""
        print(f"  {self.name}:")
        print(f"    Agent cash: ${self.agent.cash:.2f}")
        print(f"    Food inventory: {self.food_inventory}")
        print(f"    Total donations collected: ${self.log['donations_collected']:.2f}")
        print(f"    Total food purchased: {self.log['food_purchased']}")
        print(f"    Total food distributed: {self.log['food_distributed']}")
        print(f"    Total recipients served: {self.log['recipients']}")