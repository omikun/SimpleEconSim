"""
Government class wrapping an Agent for proper money-conserving operations.
Supports multiple governments for future multi-nation simulation.
"""

import econsim_states
from econsim import Agent, InitAgent
from goods import Goods
from logger import loginfo, logwarning, logdebug
import econsim_trade_money as trade


class Government:
    """A government entity with its own Agent for proper bank interactions."""
    
    def __init__(self, name, t, initial_cash=0):
        self.name = name
        self.agent = Agent(t)
        self.agent.output = Goods.gov
        self.agent.is_corp = False
        self.agent.is_gov = True
        InitAgent(self.agent, Goods.gov, 0, 0, initial_cash)
        self.food_inventory = {}
        self.debt = 0  # Optional tracking of total borrowed (not needed for accounting)
    
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
        Uses bank.Borrow() instead of money-creation hack.
        
        Returns total cost of food aid provided.
        """
        total_cost = 0
        for agent in agents:
            if agent.is_corp:
                continue
            needs_food = 0
            # Newborns (age <= 10): 1 free food per turn
            if agent.age(t) <= 10:
                needs_food = 1
            # Starving > 3 days: emergency food (enough to eat 4 this turn)
            if agent.hungry_steps > 3:
                current_food = agent.inv.get(Goods.food, 0)
                needed_for_meal = max(0, 4 - current_food)
                # Don't double-count: newborns already get 1
                if agent.age(t) <= 10:
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
                    loginfo(t, agent.name(), f"received newborn food aid ({needs_food} food)")
        
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