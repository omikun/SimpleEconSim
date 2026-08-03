import math

inventory_limit = 10

def get_input_commodity(agent, recipes):
    recipe = recipes[agent.output]
    input_com = recipe.get('input', 'none')
    return input_com

def get_output_commodity(agent):
    return agent.output

most_demand = 'none'

def Trade(t, agents, recipes):
    #what if all trade are moneyless and communistic? take all food and redistribute
        #sum all demands, subtract from askers proportional to their inventory
        #if asks < bids, give to bidders with least units

    #take all wood and redistribute?
    #take all furniture and redistribute?
    global most_demand
    max_excess_demand = 0
    for good, _ in recipes.items():
        print(t, 'bids and asks for ', good)
        #get total bids and asks
        total_bids = 0
        total_asks = 0
        i = 0
        for agent in agents:
            agent.bid = 0
            agent.ask = 0
            recipe = recipes[agent.output]
            divisor = 1 if (good == 'food') else 10
            #get bids
            if get_input_commodity(agent, recipes) == good:
                agent.bid = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            elif agent.output != good:
                agent.bid = max(0, inventory_limit - agent.inv.get(good, 0)) / divisor
            print(t, agent.name(), 'bid', agent.bid, 'input', get_input_commodity(agent, recipes), 'recipe for', recipe['commodity'], 'num input', recipe['numInput'], agent.inv[good])
            total_bids += agent.bid

            #get asks
            if agent.output == good:
                agent.ask = max(0, agent.inv.get(good, 0))
                total_asks += agent.ask
            i += 1

        #take goods from askers
        total_trades = min(total_asks, total_bids)
        excess_demand = total_bids - total_trades
        if (max_excess_demand < excess_demand):# and total_production[good] < recipes[good]['maxtotalprod']): #and limit not reached
            max_excess_demand = excess_demand
            most_demand = good
        print(t, "trading ", good, " asks: ", total_asks, " bids: ", total_bids)

        if total_trades == 0:
            continue

        total_handout = 0
        i = 0
        for agent in agents:
            if agent.output == good:
                ask = agent.ask
                handout = ask / total_asks * total_trades
                agent.inv[good] -= handout
                total_handout += handout

                print(t, 'trading ', good, ' id:', str(i), 'ask: ', ask, ' handout: ', handout)
            i += 1
        assert math.isclose(total_handout, total_trades), 'handout-' + str(total_handout) + ' not same as trades-' + str(total_trades)

        #give goods to bidders
        total_received = 0
        i = 0
        for agent in agents:
            bid = agent.bid
            received = bid / total_bids * total_trades
            if received > 0:
                print(t, 'trading ', good, ' id:', str(i), 'bid: ', bid, ' received: ', received)
                agent.inv[good] += received
                total_received += received
            i += 1
        assert math.isclose(total_handout, total_received), 'handout-' + str(total_handout) + ' not same as received-' + str(total_received)

        print(t, " trades: ", good, " traded: ", total_handout)


def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)