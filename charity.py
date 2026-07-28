"""
Charity: a non-government entity that collects donations from wealthy agents
and corporations, buys food at market price, and distributes it to the hungry
and young.

Uses an Agent instance internally, keeping all unspent cash in the bank
deposit system so total cash tracking is accurate.
"""

from goods import Goods
from logger import loginfo
from agent import Agent


class Charity:
    """Independent charity that redistributes food to the needy.

    All cash is held via an internal Agent that uses the bank's deposit
    system, so total_cash() correctly reflects charity assets.
    """

    def __init__(self, name, recipes):
        self.name = f"{name}-Charity"
        self.recipes = recipes

        # Internal Agent used purely for cash/deposit management.
        # Not added to the region's agents list — it does not participate
        # in the life-cycle, labour, production, or trade (except for
        # a special post-trade food purchase).
        self.agent = Agent(0)
        self.agent.output = Goods.food
        self.agent.is_charity = True  # distinguishes it from regular agents

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
    # Cash helpers (thin wrappers around bank deposit/withdraw)
    # ------------------------------------------------------------------

    @property
    def cash(self):
        """Current spendable cash (what's in the agent's hand, not bank)."""
        return self.agent.cash

    def _deposit_all(self, bank):
        """Move all of the charity's agent cash into the bank."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

    def _withdraw_needed(self, bank, amount):
        """Ensure agent has at least *amount* cash, withdrawing from bank."""
        if self.agent.cash >= amount:
            return
        needed = amount - self.agent.cash
        available = bank.deposits.get(self.agent, 0)
        if available > 0:
            bank.Withdraw(self.agent, min(available, needed))

    # ------------------------------------------------------------------
    # Donations
    # ------------------------------------------------------------------

    def collect_donations(self, t, agents, bank):
        """Collect donations from corporations and wealthy individuals.

        Cash received is deposited into the bank immediately.
        """
        food_price = self.recipes.get(Goods.food, {}).get('price', 1.0)
        low_cash = self.agent.cash + bank.deposits.get(self.agent, 0) < food_price * self.low_cash_threshold_multiplier

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

        # Deposit all collected cash into the bank
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash)

        self.log["donations_collected"] += total_donated
        if total_donated > 0 and t % 50 == 0:
            total_liquid = self.agent.cash + bank.deposits.get(self.agent, 0)
            print(f"  {self.name}: collected ${total_donated:.2f} in donations "
                  f"(charity cash: ${total_liquid:.2f})")

    # ------------------------------------------------------------------
    # Food bidding & purchase (called by region._trade)
    # ------------------------------------------------------------------

    def bid_food(self, food_price, current_desired):
        """Return the quantity of food this charity wants to buy this turn."""
        max_inventory = 50
        space = max_inventory - self.food_inventory
        if space <= 0 or self.agent.cash < food_price:
            return 0
        affordable = self.agent.cash // food_price
        return min(space, affordable, current_desired)

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity
        self.log["food_purchased"] += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased (from agent's hand)."""
        self.agent.cash -= cost

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