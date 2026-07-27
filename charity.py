"""
Charity: a non-government entity that collects donations from wealthy agents
and corporations, buys food at market price, and distributes it to the hungry
and young.

One Charity instance is created per Region.
"""

import math
from collections import defaultdict

from goods import Goods
from logger import loginfo


class Charity:
    """Independent charity that redistributes food to the needy."""

    def __init__(self, name, recipes):
        self.name = f"{name}-Charity"
        self.cash = 0.0
        self.food_inventory = 0
        self.recipes = recipes
        self.log = {"donations_collected": 0.0, "food_purchased": 0,
                     "food_distributed": 0, "recipients": 0}

        # Config
        self.low_cash_threshold_multiplier = 50       # food_price * 50 = low-cash threshold
        self.corp_donate_normal_pct = 0.05            # 5% of retained earnings
        self.corp_donate_emergency_pct = 0.10          # 10% if charity low on cash
        self.wealthy_donate_normal_pct = 0.02          # 2% of (wealth - threshold)
        self.wealthy_donate_emergency_pct = 0.04       # 4% if charity low on cash
        self.wealth_donation_threshold = 100.0         # only tax wealth above $100
        self.wealthy_fraction = 0.20                   # top 20% of non-corp agents
        self.max_food_per_agent = 1                    # max 1 food per agent per turn

    def collect_donations(self, t, agents, bank):
        """Collect donations from corporations and wealthy individuals."""
        food_price = self.recipes.get(Goods.food, {}).get('price', 1.0)
        low_cash = self.cash < food_price * self.low_cash_threshold_multiplier

        total_donated = 0.0

        # ---- Corporate donations ----
        corps = [a for a in agents if a.is_corporation]
        for corp in corps:
            retained = getattr(corp, 'retained_earnings', 0.0)
            if retained <= 0:
                continue
            donate_pct = self.corp_donate_emergency_pct if low_cash else self.corp_donate_normal_pct
            donation = retained * donate_pct
            # limit to what corp can actually pay from cash
            donation = min(donation, corp.cash)
            if donation > 0:
                corp.cash -= donation
                corp.retained_earnings -= donation
                self.cash += donation
                total_donated += donation
                loginfo(t, f"{self.name} received ${donation:.2f} corp donation from {corp.name()}")

        # ---- Wealthy individual donations ----
        non_corp = [a for a in agents
                    if not a.is_corporation
                    and not a.is_trader
                    and not a.is_government
                    and a.alive]
        # Sort by wealth descending
        non_corp.sort(key=lambda a: a.wealth(), reverse=True)
        top_n = max(1, int(len(non_corp) * self.wealthy_fraction))
        wealthy = non_corp[:top_n]

        for agent in wealthy:
            w = agent.wealth()
            if w <= self.wealth_donation_threshold:
                continue
            excess = w - self.wealth_donation_threshold
            donate_pct = self.wealthy_donate_emergency_pct if low_cash else self.wealthy_donate_normal_pct
            donation = excess * donate_pct
            # limit to cash on hand
            donation = min(donation, agent.cash + bank.deposits.get(agent, 0))
            # withdraw from bank if needed
            from_bank = min(donation, max(0, donation - agent.cash), bank.deposits.get(agent, 0))
            if from_bank > 0:
                bank.Withdraw(agent, from_bank)
            agent.cash -= donation
            self.cash += donation
            total_donated += donation
            loginfo(t, f"{self.name} received ${donation:.2f} donation from {agent.name()}")

        self.log["donations_collected"] += total_donated
        if total_donated > 0 and t % 50 == 0:
            print(f"  {self.name}: collected ${total_donated:.2f} in donations "
                  f"(charity cash: ${self.cash:.2f})")

    def bid_food(self, food_price, current_desired):
        """Return the quantity of food this charity wants to buy this turn.
        
        Acts as a normal food bidder during trade. Returns bid quantity
        limited by cash and available space.
        """
        max_inventory = 50  # charity can hold up to 50 food
        space = max_inventory - self.food_inventory
        if space <= 0 or self.cash < food_price:
            return 0
        affordable = self.cash // food_price
        return min(space, affordable, current_desired)

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity
        self.log["food_purchased"] += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased."""
        self.cash -= cost

    def distribute_food(self, t, agents):
        """Give 1 food per agent to hungry agents first, then young agents."""
        if self.food_inventory <= 0:
            return

        # Hungry agents (priority: most hungry first)
        hungry = [a for a in agents if a.alive and a.hungry_steps > 0
                  and not a.is_corporation]
        hungry.sort(key=lambda a: -a.hungry_steps)

        # Young agents (age <= 10, not already hungry)
        young = [a for a in agents if a.alive and a.age(t) <= 10
                 and a.hungry_steps == 0 and not a.is_corporation]

        recipients = 0
        food_given = 0

        for recipient in hungry + young:
            if self.food_inventory <= 0:
                break
            self.food_inventory -= 1
            recipient.inventory[Goods.food] = recipient.inventory.get(Goods.food, 0) + 1
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
                  f"(remaining food: {self.food_inventory}, cash: ${self.cash:.2f})")

    def print_summary(self):
        """Print summary stats for this charity."""
        print(f"  {self.name}:")
        print(f"    Cash: ${self.cash:.2f}")
        print(f"    Food inventory: {self.food_inventory}")
        print(f"    Total donations collected: ${self.log['donations_collected']:.2f}")
        print(f"    Total food purchased: {self.log['food_purchased']}")
        print(f"    Total food distributed: {self.log['food_distributed']}")
        print(f"    Total recipients served: {self.log['recipients']}")