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
        
mostDemand = 'none'
def Trade(t, agents, recipes, demands, sold_log):
    #supply vs demand curve? but this curve is on the change in price, not the price it self
    # when demand > supply, price increases by 1-5%
    # when demand < supply, price stays same
    # when demand < supply/2, price drops 1-5%
    # when demand < supply/5, price drops by 5-10%
    
    global mostDemand
    maxExcessDemand = 0
    for agent in agents:
        agent.remainingCash = agent.cash

    goods = ['food', 'wood', 'furniture']
    num = 16
    for good in goods:
        num /= 4
    #for good, _ in recipes.items():
        print(t, 'bids and asks for ', good)
        #get total bids and asks
        totalBids = 0
        totalAsks = 0
        bids = list()
        asks = list()
        goodPrice = recipes[good]['price']
        for agent in agents:
            recipe = recipes[agent.output]
            #divisor = 1 if (good == 'food') else 10
            #get bids
            if GetInputCom(agent, recipes) == good:
                agent.bid = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            elif agent.output != good and agent.remainingCash > goodPrice:
                agent.bid = min(num, int(agent.remainingCash / goodPrice))
                agent.bid = min(agent.bid, max(0, recipes[good]['maxinv'] - agent.inv.get(good, 0)))
                #agent.bid = max(0, inventoryLimit - agent.inv.get(good,0)) / divisor
            else:
                agent.bid = 0
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
        excessDemand = totalBids - totalTrades
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
