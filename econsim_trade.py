import math

inventoryLimit = 10
def GetInputCom(agent, recipes):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', 'none')
    return inputCom
def GetOutputCom(agent):
    return agent.output

mostDemand = 'none'
def Trade(t, agents, recipes):
    #what if all trade are moneyless and communistic? take all food and redistribute
        #sum all demands, subtract from askers proportional to their inventory
        #if asks < bids, give to bidders with least units

    #take all wood and redistribute?
    #take all furnitures and redistribute?
    global mostDemand
    maxExcessDemand = 0
    for good, _ in recipes.items():
        print(t, 'bids and asks for ', good)
        #get total bids and asks
        totalBids = 0
        totalAsks = 0
        i = 0
        for agent in agents:
            agent.bid = 0
            agent.ask = 0
            recipe = recipes[agent.output]
            divisor = 1 if (good == 'food') else 10
            if GetInputCom(agent, recipes) == good:
                agent.bid = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            elif agent.output != good:
                agent.bid = max(0, inventoryLimit - agent.inv.get(good,0)) / divisor
            print(t, agent.name(), 'bid', agent.bid, 'input', GetInputCom(agent, recipes), 'recipe for', recipe['commodity'], 'num input', recipe['numInput'], agent.inv[good])
            totalBids += agent.bid

            if agent.output == good:
                agent.ask = max(0, agent.inv.get(good, 0))
                totalAsks += agent.ask
            i += 1

        #take goods from askers
        totalTrades = min(totalAsks, totalBids)
        excessDemand = totalBids - totalTrades
        if (maxExcessDemand < excessDemand):# and totalProd[good] < recipes[good]['maxtotalprod']): #and limit not reached
            maxExcessDemand = excessDemand
            mostDemand = good
        print(t, "trading ", good, " asks: ", totalAsks, " bids: ", totalBids)

        if totalTrades == 0:
            continue

        totalHandout = 0
        i = 0
        for agent in agents:
            if agent.output == good:
                ask = agent.ask
                handout = ask / totalAsks * totalTrades
                agent.inv[good] -= handout
                totalHandout += handout

                print(t, 'trading ', good, ' id:', str(i), 'ask: ', ask, ' handout: ', handout)
            i+= 1
        assert math.isclose(totalHandout, totalTrades), 'handout-' + str(totalHandout) + ' not same as trades-' + str(totalTrades)

        #give goods to bidders
        totalReceived = 0
        i = 0
        for agent in agents:
            bid = agent.bid
            received = bid / totalBids * totalTrades
            if received > 0:
                print(t, 'trading ', good, ' id:', str(i), 'bid: ', bid, ' received: ', received)
                agent.inv[good] += received
                totalReceived += received
            i += 1
        assert math.isclose(totalHandout, totalReceived), 'handout-' + str(totalHandout) + ' not same as received-' + str(totalReceived)

        print(t, " trades: ", good, " traded: ", totalHandout)


def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)
