import math
import bisect

inventoryLimit = 10
def GetInputCom(agent, recipes):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', 'none')
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
    def __init__(self, agent, principle, interest_rate):
        self.agent = agent
        self.principle = principle
        self.interest_rate = interest_rate
        self.interest_paid = 0
        self.principle_paid = 0
        self.num_payments = 30

    def isPaid(self):
        return self.principle_paid >= self.principle

    def getInterest(self):
        return self.interest_rate * remainingPrinciple
    def getPaymentAmount(self):
        remainingPrinciple = self.principle - self.principle_paid
        interest = self.getInterest()
        payment = interest + self.principle / self.num_payments
        return payment

    def pay(self, amount):
        interest_paid = min(self.getInterest(), amount)
        self.principle_paid += max(0, amount - interest_paid)
        self.interest_paid += interest_paid

class Bank():
    def __init__(self):
        self.interest_rate = .1
        self.total_deposits = 200
        self.reserve_fraction = .1
        self.loans = []
        
bank = Bank()

mostDemand = 'none'
def Trade(t, agents, recipes, demands, sold_log, bought_log):
    global bank
    #supply vs demand curve? but this curve is on the change in price, not the price it self
    # when demand > supply, price increases by 1-5%
    # when demand < supply, price stays same
    # when demand < supply/2, price drops 1-5%
    # when demand < supply/5, price drops by 5-10%
    
    global mostDemand
    mostDemand = 'gov'
    maxExcessDemand = 0
    for agent in agents:
        agent.remainingCash = agent.cash

    goods = ['food', 'wood', 'furniture']
    num_desired = 16
    allGoodsPrice = sum(recipes[good]['price'] for good in goods)
    for good in goods:
        num_desired /= 4
    #for good, _ in recipes.items():
        print(t, 'bids and asks for ', good)
        #get total bids and asks
        totalBids = 0
        totalAsks = 0
        bids = list()
        asks = list()
        price = recipes[good]['price']
        goodPrice = recipes[good]['price']
        for agent in agents:
            recipe = recipes[agent.output]
            #divisor = 1 if (good == 'food') else 10
            #get bids
            if GetInputCom(agent, recipes) == good:
                agent.bid = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            elif agent.output != good and agent.remainingCash > goodPrice:
                # num_desired = clamp(4 / num_desired * (agent.remainingCash // allGoodsPrice), num_desired, num_desired*2)
                num_affordable = min(num_desired, agent.remainingCash // goodPrice)
                num_storable = max(0, recipes[good]['maxinv'] - agent.inv.get(good, 0))
                # if good == 'furniture':
                #     num_storable = recipes[good]['price'] / 4 / agent.remainingCash
                
                agent.bid = min(num_affordable, num_storable)
                #agent.bid = max(0, inventoryLimit - agent.inv.get(good,0)) / divisor
            else:
                agent.bid = 0

            #borrow money from bank
            if good == 'food' and agent.bid == 0 and agent.hungry_steps > 2:
                loan = price * 40
                agent.cash += loan
                agent.loans.append(Loan(agent, loan, bank.interest_rate))
                agent.bid = 1
                
            agent.remainingCash -= agent.bid * goodPrice
            print(t, agent.name(), 'bid', agent.bid, 'input', GetInputCom(agent, recipes), 'recipe for', recipe['commodity'], 'num input', recipe['numInput'], agent.inv[good])
            totalBids += agent.bid

            #get asks
            if agent.output == good:
                agent.ask = max(0, agent.inv.get(good, 0))
                totalAsks += agent.ask
            else:
                agent.ask = 0

        #take goods from askers
        totalTrades = min(totalAsks, totalBids)
        excessDemand = max(0, totalBids - totalTrades)
        if (maxExcessDemand < excessDemand):# and totalProd[good] < recipes[good]['maxtotalprod']): #and limit not reached
            maxExcessDemand = excessDemand
            mostDemand = good

        if totalTrades == 0:
            continue

        demandRatio = totalBids / totalAsks
        demands.setdefault(good, [])
        demands[good].append(demandRatio)
        
        recipe = recipes[good]
        price = recipe['price']
        if demandRatio >= 1:
            price *= lerp(1.01, 1.05, demandRatio - 1)
        elif demandRatio < .5:
            price *= lerp(.99, .95, demandRatio * 2)
        price = max(.01, price)
        recipe['price'] = price

        print(t, "trading ", good, " at $", round(price, 2), "demandRatio:", round(demandRatio, 2) , 
              " asks: ", round(totalAsks, 2), " bids: ", round(totalBids, 2))
        
        # for agent in agents:
        #     if agent.output == good:
        #         ask = agent.ask
        #         handout = ask / totalAsks * totalTrades
        #         agent.inv[good] -= handout

        #give goods to bidders
        totalBought = 0
        bidders = sorted(agents, key=lambda a: a.hungry_steps, reverse=True) #most demanding agent first
        totalCashTransfered = 0
        for agent in bidders:
            if totalAsks > totalBought:
                prevCash = agent.cash
                bid = agent.bid
                remaining = totalAsks - totalBought
                affordable = int(agent.cash / price)
                bought = min(bid, min(remaining, affordable))
                cash = bought * price
                agent.cash -= cash
                assert agent.cash >= 0, 'neg cash, bought $' + str(cash) + ' now has ' + str(agent.cash)
                totalCashTransfered += cash
                if bought > 0:
                    #print(t, agent.name(), 'bought ', bought, good, ', bid: ', bid)
                    print(t, agent.name(), 'had $', prevCash, 'now', agent.cash, 'bought ', bought, good, ', bid: ', bid, 'affordable: ', affordable, 'remaining:', remaining)
                    agent.inv[good] += bought
                    totalBought += bought
                    bought_log[agent.output][good][-1] += bought
                else:
                    print(t, agent.name(), 'had $', prevCash, 'now', agent.cash, 'bought ', bought, good, ', bid: ', bid, 'affordable: ', affordable, 'remaining:', remaining)

        askers = sorted(agents, key=lambda a: a.ask, reverse=True)
        totalSold = 0
        for agent in askers:
            if totalSold < totalBought and totalCashTransfered > 0:
                ask = agent.ask
                remaining = totalBought - totalSold
                sold = min(ask, remaining)
                assert sold >= 0, 'neg sold ' + str(sold)
                totalSold += sold
                agent.cash += sold * price
                if sold > 0:
                    print(t, agent.name(), 'sold ', sold, good, ', ask: ', ask)

        print(t, "demand:", demandRatio, "price:", price, "trades: ", good, " traded: ", 0)
        sold_log[good].append(totalSold)


def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)
