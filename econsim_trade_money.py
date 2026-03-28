import math
import bisect
import random
from collections import defaultdict
from goods import Goods
from logger import *
from econsim_states import *

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
        if amount == 0:
            return
        loan = Loan(self, agent, amount, self.interest_rate)
        
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount
        
    def PayPrinciple(self, amount):
        self.total_liabilities -= amount
        
    def Deposit(self, agent, amount):
        agent.cash -= amount
        self.total_deposits += amount
        self.deposits[agent] += amount
    
    def Withdraw(self, agent, amount):
        amount = clamp(amount, 0, self.deposits[agent])
        agent.cash += amount
        self.total_deposits -= amount
        self.deposits[agent] -= amount
        
        
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
    wealth = agent.cash + bank.deposits[agent]
    paidAmount = 0
    for loan in agent.loans:
        payment = min(wealth, loan.getPaymentAmount())
        loan.pay(payment)
        paidAmount += payment
    withdrawAmount = paidAmount - agent.cash
    if withdrawAmount > 0:
        bank.Withdraw(agent, withdrawAmount)
    else:
        agent.cash -= paidAmount
        
        
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
    maxExcessDemand = 0

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
        excessDemand = max(0, totalBids - totalTrades)
        if (maxExcessDemand < excessDemand):# and totalProd[good] < recipes[good]['maxtotalprod']): #and limit not reached
            maxExcessDemand = excessDemand
            mostDemand = good

        if totalTrades == 0:
            continue

        demandRatio = totalBids / totalAsks
        demand_ratio_log.setdefault(good, [])
        demand_ratio_log[good].append(demandRatio)
        demand_log[good].append(totalBids)
        supply_log[good].append(totalAsks)

        price = SetMarketPrice(demandRatio, good, recipes)

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
        reportCash(t, agents, prevTotalCash, "post trade " + str(good))


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
            agent.cash -= cash
            assert agent.cash >= 0, 'neg cash, bought $' + str(cash) + ' now has ' + str(agent.cash)
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


def SetMarketPrice(demandRatio, good, recipes):
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
                    agent.ask = max(0, agent.ask - 4)
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

        if agent.cash > allGoodsPrice * 30:
            amount = agent.cash - allGoodsPrice * 30
            bank.Deposit(agent, amount)
            agent.cash -= amount
            reportCash(t, agents, prevTotalCash, agent.name() + " post deposit ")

        agent.remainingCash = agent.cash


def reportCash(t, agents, prevTotalCash, msg, print=False): 
    tempTotalCash = getTotalCash(agents)
    diff = math.fabs(tempTotalCash - prevTotalCash)
    epsilon = 1e-8
    if diff > epsilon or print:
        loginfo(t, msg, "total cash", prevTotalCash, '!=', tempTotalCash, diff)

def getTotalCash(agents):
    bankCash = bankCash_log[-1] if bankCash_log else 0
    return sum(agent.cash for agent in agents) + govCash + bankCash

def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)
