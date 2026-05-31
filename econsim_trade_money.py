import math
import bisect
import random
from collections import defaultdict
from goods import Goods
from logger import *
from econsim_states import *
import econsim_states

inventoryLimit = 10
def GetInputCom(agent, recipes):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', Goods.none)
    return inputCom
def GetOutputCom(agent):
    return agent.output
class Offer:
    def __init__(self, isBid, agent, price, quantity):
        self.isBid = isBid
        self.agent = agent
        self.price = price
        self.quantity = quantity

def lerp(a, b, t):
    return a + (b - a) * t

def clamp(x, minx, maxx):
    return max(minx, min(x, maxx))

class Loan:
    def __init__(self, bank, agent, principle, interest_rate):
        self.bank = bank
        self.agent = agent
        self.principle = principle
        self.interest_rate = interest_rate
        self.interest_paid = 0
        self.principle_paid = 0
        self.num_payments = 100

    def isPaid(self):
        return self.principle_paid >= self.principle

    def getInterest(self):
        remainingPrinciple = self.principle - self.principle_paid
        return self.interest_rate * remainingPrinciple
    def getPaymentAmount(self):
        remainingPrinciple = self.principle - self.principle_paid
        interest = self.getInterest()
        payment = interest + self.principle / self.num_payments
        return payment

    def pay(self, amount):
        interest_paid = min(self.getInterest(), amount)
        principlePaid = max(0, amount - interest_paid)
        self.principle_paid += principlePaid
        self.interest_paid += interest_paid
        bank.PayPrinciple(principlePaid)
        bank.PayInterest(interest_paid)

class Bank():
    def __init__(self):
        self.interest_rate = .001
        self.total_deposits = 200
        self.reserve_fraction = .1
        self.loans = []
        self.total_liabilities = 0
        self.deposits = defaultdict(int)
        
    def Borrow(self, t, agent, amount):
        borrowableAmount = self.total_deposits * (1-self.reserve_fraction) - self.total_liabilities
        amount = clamp(amount, 0, borrowableAmount)
        loginfo(t, "borrowing from bank with $", self.total_deposits, " deposit and $", self.total_liabilities, "borrowable: $", borrowableAmount, " lending: $", amount)
        if amount <= 0:
            return
        loan = Loan(self, agent, amount, self.interest_rate)
        
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount
        
    def PayPrinciple(self, amount):
        self.total_liabilities -= amount

    def PayInterest(self, amount):
        self.total_deposits += amount
        
    def Deposit(self, agent, amount):
        assert(agent.cash >= amount)
        agent.cash -= amount
        self.total_deposits += amount
        self.deposits[agent] += amount
    
    def Withdraw(self, agent, amount):
        amount = clamp(amount, 0, self.deposits[agent])
        agent.cash += amount
        self.total_deposits -= amount
        self.deposits[agent] -= amount

    def RequestBailout(self, t, loss_amount):
        """Request a government bailout when the bank can't absorb a loss.
        The bailout covers the immediate deficit plus a buffer of 20% of
        outstanding liabilities so another bailout won't be needed for 10+ turns."""
        deficit = max(0, loss_amount - self.total_deposits)
        buffer = self.total_liabilities * 0.2
        bailout_amount = deficit + buffer
        bailout_amount = max(bailout_amount, loss_amount)  # at minimum cover the loss

        approved, amount = gov_decide_bailout(t, self, bailout_amount)
        if approved and amount > 0:
            econsim_states.govCash -= amount
            self.total_deposits += amount
            logwarning(t, "BAILOUT: government injected $", round(amount, 2),
                       "into bank. govCash now $", round(econsim_states.govCash, 2))
        return approved


def gov_decide_bailout(t, bank, requested_amount):
    """Government decides whether to approve a bank bailout.
    Currently defaults to auto-approve. Returns (approved, amount)."""
    # Auto-approve: give the full requested amount even if govCash goes negative
    return True, requested_amount


bank = Bank()

def Borrow(t, agent, foodPrice, bank):
    amount = foodPrice * 1.2
    bank.Borrow(t, agent, amount)
    
def BorrowIfNeedTo(t, agent):
    wealth = agent.wealth()
    if wealth < agent.oweThisTurn():
        needed = agent.oweThisTurn() - wealth
        Borrow(t, agent, needed * 2, bank)

def PayLoans(agent):
    # 1. Determine total liquid assets
    total_wealth = agent.cash + bank.deposits[agent]
    remaining_wealth = total_wealth
    total_paid = 0
    
    # 2. Calculate and apply payments based on REMAINING wealth
    for loan in agent.loans:
        payment = min(remaining_wealth, loan.getPaymentAmount())
        loan.pay(payment)
        total_paid += payment
        remaining_wealth -= payment
    
    # 3. Handle cash and bank withdrawals
    if total_paid > 0:
        if total_paid > agent.cash:
            # We need more than what's in pocket, withdraw from bank
            needed_from_bank = total_paid - agent.cash
            bank.Withdraw(agent, needed_from_bank)
            
        # 4. Now subtract the total amount from the (potentially updated) cash balance
        agent.cash -= total_paid
    # 5. Cleanup: Remove fully paid loans
    agent.loans = [l for l in agent.loans if not l.isPaid()]
        
        
mostDemand = Goods.none
def Trade(t, agents, recipes, demand_ratio_log, demand_log, supply_log, sold_log, bought_log):
    prevTotalCash = getTotalCash(agents)
    global bank
    #supply vs demand curve? but this curve is on the change in price, not the price it self
    # when demand > supply, price increases by 1-5%
    # when demand < supply, price stays same
    # when demand < supply/2, price drops 1-5%
    # when demand < supply/5, price drops by 5-10%
    
    global mostDemand
    mostDemand = Goods.gov
    maxDemandRatio = 0

    goods = [Goods.food, Goods.wood, Goods.furn]
    num_desired = 16
    allGoodsPrice = sum(recipes[good]['price'] for good in goods)
    foodPrice = recipes[Goods.food]['price']
    random.shuffle(agents)

    reportCash(t, agents, prevTotalCash, "pre borrow and deposit", True)
    #borrow and deposit
    DecideBorrowDeposit(agents, allGoodsPrice, bank, foodPrice, prevTotalCash, t)

    reportCash(t, agents, prevTotalCash, "post borrow and deposit")
    for good in goods:
        if good == Goods.food:
            current_desired = 16
        elif good == Goods.wood:
            current_desired = 10
        else:
            current_desired = max(1, int(16 / max(1, recipes[good]['price'])))
            
        loginfo(t, 'bids and asks for ', good)
        #get total bids and asks
        totalBids = 0
        totalAsks = 0
        price = recipes[good]['price']
        goodPrice = recipes[good]['price']
        totalAsks, totalBids = GatherBidsAsks(t, agents, good, goodPrice, current_desired, recipes, totalAsks, totalBids)

        #take goods from askers
        totalTrades = min(totalAsks, totalBids)

        if totalAsks == 0 and totalBids == 0:
            recipe = recipes[good]
            cost_to_make = 1.0
            if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
                input_cost = recipes[recipe['input']]['price']
                cost_to_make = (recipe['numInput'] * input_cost) / recipe['production']
            if recipe['price'] > cost_to_make * 1.05:
                recipe['price'] = max(cost_to_make, recipe['price'] * 0.95)
            
            recipe['price'] = max(cost_to_make, recipe['price'])
            continue
            
        demandRatio = 5.0 if totalAsks == 0 else totalBids / totalAsks
        
        if (maxDemandRatio < demandRatio) and totalBids > 0:
            maxDemandRatio = demandRatio
            mostDemand = good
        
        demand_ratio_log.setdefault(good, [])
        demand_ratio_log[good].append(demandRatio)
        demand_log[good].append(totalBids)
        supply_log[good].append(totalAsks)

        price = SetMarketPrice(demandRatio, good, recipes, agents)

        if totalTrades == 0:
            continue

        logdebug(t, "trading ", good, " at $", round(price, 2), "demandRatio:", round(demandRatio, 2) , 
              " asks: ", round(totalAsks, 2), " bids: ", round(totalBids, 2))
        
        # for agent in agents:
        #     if agent.output == good:
        #         ask = agent.ask
        #         handout = ask / totalAsks * totalTrades
        #         agent.inv[good] -= handout

        #give goods to bidders
        totalBought = 0
        totalBought, totalCashPurchase = BiddersBuyGood(t, agents, good, bought_log, price, totalAsks, totalBought)

        askers = sorted(agents, key=lambda a: a.ask, reverse=True)
        totalSold = 0
        totalCashSold = 0
        totalCashSold, totalSold = AskersSellGood(askers, good, price, t, totalBought, totalCashPurchase, totalCashSold,
                                                  totalSold)

        diff = math.fabs(totalCashSold - totalCashPurchase)
        if diff > .1:
            logwarning(t, "traded", good, "demand:", demandRatio, "price:", price, "trades: ", good, " traded: ", 0, "total bought", totalBought, "totalSold", totalSold, "cash bought $", totalCashPurchase, "cash sold $", totalCashSold, "diff", math.fabs(totalCashSold - totalCashPurchase))

        sold_log[good].append(totalSold)
        reportCash(t, agents, prevTotalCash, "post primary trade " + str(good))
        
        # Execute secondary market
        sec_traded, sec_value = SecondaryTrade(t, agents, good, price, recipes)
        if sec_traded > 0:
            logdebug(t, "secondary traded", good, "vol:", sec_traded, "value:$", round(sec_value, 2))
            
        reportCash(t, agents, prevTotalCash, "post secondary trade " + str(good))


def AskersSellGood(askers, good, price, t, totalBought, totalCashPurchase, totalCashSold, totalSold):
    for agent in askers:
        if totalSold < totalBought and totalCashPurchase > totalCashSold:
            ask = agent.ask
            remaining = totalBought - totalSold
            sold = min(ask, remaining)
            assert sold >= 0, 'neg sold ' + str(sold)
            totalSold += sold
            agent.cash += sold * price
            agent.inv[good] -= sold
            totalCashSold += sold * price
            if sold > 0:
                loginfo(t, agent.name(), 'sold ', sold, good, ', ask: ', ask)
    return totalCashSold, totalSold


def BiddersBuyGood(t, agents, good, bought_log, price, totalAsks, totalBought):
    bidders = sorted(agents, key=lambda a: a.hungry_steps, reverse=True)  # most demanding agent first
    totalCashPurchase = 0
    for agent in bidders:
        if totalAsks > totalBought:
            prevCash = agent.cash
            bid = agent.bid
            remaining = totalAsks - totalBought
            affordable = int(agent.cash / price)
            bought = max(0, min(bid, min(remaining, affordable)))
            cash = bought * price
            agent.cash = max(0.0, agent.cash - cash)
            assert agent.cash >= -1e-5, 'neg cash, bought $' + str(cash) + ' of ' + str(good) + ' now has ' + str(agent.cash)
            totalCashPurchase += cash
            if bought > 0:
                # logdebug(t, agent.name(), 'bought ', bought, good, ', bid: ', bid)
                logdebug(t, agent.name(), 'had $', prevCash, 'now', agent.cash, 'bought ', bought, good, ', bid: ', bid,
                         'affordable: ', affordable, 'remaining:', remaining)
                # Update cost basis (weighted average of what agent actually paid)
                old_qty = agent.inv.get(good, 0)
                old_cost = agent.cost_basis.get(good, 0)
                total_qty = old_qty + bought
                if total_qty > 0:
                    agent.cost_basis[good] = (old_qty * old_cost + bought * price) / total_qty
                else:
                    agent.cost_basis[good] = price
                agent.inv[good] += bought
                totalBought += bought
                bought_log[agent.output][good][-1] += bought
            else:
                logdebug(t, agent.name(), 'had $', prevCash, 'now', agent.cash, 'bought ', bought, good, ', bid: ', bid,
                         'affordable: ', affordable, 'remaining:', remaining)
    return totalBought, totalCashPurchase


def SetMarketPrice(demandRatio, good, recipes, agents=None):
    recipe = recipes[good]
    price = recipe['price']
    if demandRatio >= 1:
        # Cap the max multiplier at 20% max increase per round to prevent ratchet effect
        clamped_ratio = min(5.0, demandRatio - 1)
        price *= lerp(1.01, 1.20, clamped_ratio / 5.0)
    elif demandRatio < 0.2:
        price *= lerp(0.90, 0.95, demandRatio / 0.2)  # 5-10% drop when very oversupplied
    elif demandRatio < .5:
        price *= lerp(0.95, 1.0, (demandRatio - 0.2) / 0.3)  # 0-5% drop
    
    # Enforce fundamental bankruptcy floor
    cost_to_make = 1.0
    if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
        input_cost = recipes[recipe['input']]['price']
        cost_to_make = (recipe['numInput'] * input_cost) / recipe['production']
        
    # Dynamic price floor adjustment based on producer poorness and hungriness
    if agents and good != Goods.gov:
        producers = [a for a in agents if a.output == good]
        if producers:
            total_multiplier = 0
            for a in producers:
                poor_factor = clamp(a.cash / 20.0, 0.2, 1.0)
                hungry_factor = max(0.1, 0.8 ** a.hungry_steps)
                total_multiplier += poor_factor * hungry_factor
            avg_multiplier = total_multiplier / len(producers)
            cost_to_make *= avg_multiplier
            
    price = max(cost_to_make, price)
    price = max(0.1, price)
    recipe['price'] = price
    return price


def GatherBidsAsks(t, agents, good, goodPrice, num_desired, recipes, totalAsks, totalBids):
    for agent in agents:
        recipe = recipes[agent.output]
        # divisor = 1 if (good == Goods.food) else 10
        # get bids
        if GetInputCom(agent, recipes) == good:
            desired = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            affordable = agent.remainingCash // goodPrice if goodPrice > 0 else desired
            agent.bid = int(min(desired, affordable))
        elif agent.output != good and agent.remainingCash > goodPrice:
            num_affordable = min(num_desired, agent.remainingCash // goodPrice)
            num_storable = max(0, recipes[good]['maxinv'] - agent.inv.get(good, 0))

            agent.bid = min(num_affordable, num_storable)
            
            # Consumption-based demand: wealthy agents occasionally buy non-essentials
            if good != Goods.food and agent.remainingCash > goodPrice * 4:
                discretionary = min(1, agent.remainingCash // (goodPrice * 4))
                agent.bid += min(discretionary, num_storable - agent.bid)
                agent.bid = max(0, min(agent.bid, num_storable))
        else:
            agent.bid = 0

        agent.remainingCash -= agent.bid * goodPrice
        loginfo(t, agent.name(), 'bid', agent.bid, 'input', GetInputCom(agent, recipes), 'recipe for',
                recipe['commodity'], 'num input', recipe['numInput'], agent.inv[good])
        totalBids += agent.bid

        # get asks
        if agent.output == good or (agent.output == Goods.gov and agent.inv.get(good, 0) > 0):
            cost_to_make = 0
            if agent.output == good and recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
                input_com = recipe['input']
                input_cost = agent.cost_basis.get(input_com, 0)
                cost_to_make = (recipe['numInput'] * input_cost) / recipe['production']
                
            if good == Goods.food and agent.output == Goods.food:
                    agent.ask = max(0, agent.inv.get(good, 0) - 2)
            elif goodPrice >= cost_to_make:
                agent.ask = max(0, agent.inv.get(good, 0))
            else:
                agent.ask = 0
                
            totalAsks += agent.ask
        else:
            agent.ask = 0
    return totalAsks, totalBids


def DecideBorrowDeposit(agents, allGoodsPrice, bank, foodPrice, prevTotalCash, t):
    for agent in agents:
        BorrowIfNeedTo(t, agent)
        PayLoans(agent)
        if (agent.output != Goods.food
                and agent.cash < foodPrice and agent.hungry_steps > 10):
            Borrow(t, agent, foodPrice, bank)
            reportCash(t, agents, prevTotalCash, agent.name() + " post borrow ")

        if agent.output in recipes and recipes[agent.output].get('numInput', 0) > 0:
            input_com = recipes[agent.output]['input']
            input_price = recipes[input_com]['price']
            num_input = recipes[agent.output]['numInput']
            cost = input_price * num_input
            if agent.cash < cost:
                amount_needed = cost - agent.cash
                bank.Borrow(t, agent, amount_needed)
                reportCash(t, agents, prevTotalCash, agent.name() + " post business borrow ")

        if agent.cash > allGoodsPrice * 30:
            amount = agent.cash - allGoodsPrice * 30
            bank.Deposit(agent, amount)
            reportCash(t, agents, prevTotalCash, agent.name() + " post deposit ")

        agent.remainingCash = agent.cash


def SecondaryTrade(t, agents, good, current_market_price, recipes):
    """
    Executes a secondary market for the good after the primary market clears.
    Sellers (with excess inventory) set their own discounted prices based on distress.
    Buyers bid higher based on their hunger or low inventory.
    """
    # 1. Gather Secondary Asks
    secondary_asks = []
    for agent in agents:
        # Check if agent has excess inventory to sell
        remaining_inv = agent.inv.get(good, 0)
        
        # Determine how much they want to keep vs sell
        # Farmers keep 2 food. Others sell all excess.
        keep_amount = 2 if (good == Goods.food and agent.output == Goods.food) else 0
        sellable = max(0, remaining_inv - keep_amount)
        
        if sellable > 0 and agent.output == good:
            # Determine asking price. Distressed agents discount more heavily.
            poor_factor = clamp(agent.cash / 20.0, 0.2, 1.0)
            hungry_factor = max(0.1, 0.8 ** agent.hungry_steps)
            distress_factor = poor_factor * hungry_factor
            
            # Floor asking price at the fundamental cost_to_make adjusted by distress
            recipe = recipes[good]
            cost_to_make = 1.0
            if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
                input_cost = recipes[recipe['input']]['price']
                cost_to_make = (recipe['numInput'] * input_cost) / recipe['production']
                
            min_ask = max(0.1, cost_to_make * distress_factor)
            
            # Ask price is discounted from market price based on distress, but no lower than min_ask
            ask_price = max(min_ask, current_market_price * distress_factor)
            
            secondary_asks.append(Offer(False, agent, ask_price, sellable))

    # 2. Gather Secondary Bids
    secondary_bids = []
    recipe = recipes[good]
    for agent in agents:
        if agent.output == good:
            continue # Producers don't buy their own good
            
        desired = 0
        if GetInputCom(agent, recipes) == good:
            desired = max(0, recipe['numInput'] - agent.inv.get(good, 0))
        else:
            num_storable = max(0, recipe['maxinv'] - agent.inv.get(good, 0))
            if good == Goods.food:
                desired = min(16, num_storable) # Food is always desired
            elif agent.remainingCash > current_market_price * 2:
                # Occasional buyers
                desired = min(1, num_storable)
        
        if desired > 0 and agent.remainingCash > 0:
            # Determine max willing to pay. 
            # If hungry, willing to pay more for food. If low inventory, willing to pay more.
            premium = 1.0
            if good == Goods.food and agent.hungry_steps > 0:
                premium = min(5.0, 1.0 + 0.5 * agent.hungry_steps) # Pay up to 5x for food if starving
            elif GetInputCom(agent, recipes) == good and agent.inv.get(good, 0) == 0:
                premium = 1.5 # Pay 50% premium for critical inputs
                
            max_willing_to_pay = current_market_price * premium
            
            # They bid up to their max_willing_to_pay, but bounded by their actual cash
            affordable_qty = agent.remainingCash / max_willing_to_pay
            if affordable_qty >= 1:
                bid_qty = min(desired, int(affordable_qty))
                secondary_bids.append(Offer(True, agent, max_willing_to_pay, bid_qty))
            elif agent.remainingCash >= current_market_price * 0.5:
                # If they can't afford a full unit at max_willing_to_pay, but have some cash,
                # they place a lowball bid for 1 unit with whatever cash they have.
                secondary_bids.append(Offer(True, agent, agent.remainingCash, 1))

    # 3. Match Orders (Simplistic continuous double auction)
    # Sort asks lowest price first
    secondary_asks.sort(key=lambda x: x.price)
    # Sort bids highest price first
    secondary_bids.sort(key=lambda x: x.price, reverse=True)
    
    total_secondary_traded = 0
    total_secondary_value = 0
    
    ask_idx = 0
    bid_idx = 0
    
    while ask_idx < len(secondary_asks) and bid_idx < len(secondary_bids):
        ask = secondary_asks[ask_idx]
        bid = secondary_bids[bid_idx]
        
        if bid.price >= ask.price:
            # Match! Trade clears at the midpoint price
            clear_price = (bid.price + ask.price) / 2.0
            trade_qty = min(ask.quantity, bid.quantity)
            
            # Ensure buyer can actually afford the clear_price * trade_qty
            max_affordable = int(bid.agent.remainingCash / clear_price) if clear_price > 0 else trade_qty
            trade_qty = min(trade_qty, max_affordable)
            
            if trade_qty > 0:
                cost = trade_qty * clear_price
                
                # Execute trade
                bid.agent.remainingCash -= cost
                bid.agent.cash -= cost
                ask.agent.cash += cost
                
                bid.agent.inv[good] += trade_qty
                ask.agent.inv[good] -= trade_qty
                
                # Update cost basis for buyer
                old_qty = bid.agent.inv.get(good, 0) - trade_qty
                old_cost = bid.agent.cost_basis.get(good, 0)
                if bid.agent.inv[good] > 0:
                    bid.agent.cost_basis[good] = (old_qty * old_cost + cost) / bid.agent.inv[good]
                
                total_secondary_traded += trade_qty
                total_secondary_value += cost
                
                # Update remaining quantities
                ask.quantity -= trade_qty
                bid.quantity -= trade_qty
                
                loginfo(t, "SECONDARY TRADE:", bid.agent.name(), "bought", trade_qty, good, "from", ask.agent.name(), "at $", round(clear_price, 2))
                
        if ask.quantity <= 0:
            ask_idx += 1
        if bid.quantity <= 0 or bid.price < ask.price:
            bid_idx += 1
            
    return total_secondary_traded, total_secondary_value


def reportCash(t, agents, prevTotalCash, msg, print=False): 
    tempTotalCash = getTotalCash(agents)
    diff = math.fabs(tempTotalCash - prevTotalCash)
    epsilon = 1e-8
    if diff > epsilon or print:
        loginfo(t, msg, "total cash", prevTotalCash, '!=', tempTotalCash, diff)

def getTotalCash(agents):
    bankCash = bank.total_deposits - bank.total_liabilities
    return sum(agent.cash for agent in agents) + govCash + bankCash

def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)
