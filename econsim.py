import random
import math
import matplotlib.pyplot as plt
import copy
import bisect

agentid = 0
class Agent:
    def __init__(self):
        global agentid
        self.id = agentid
        agentid += 1
        self.bid = 0
        self.ask = 0
        self.output = 'none'
        self.hungry_steps = 0
        self.cash = 10
        self.inv = {}
        self.lastRepro = 0

    def name(self):
        return 'agent'+str(self.id)

# Initial populations
#agent_template = {'profession': 'none','hungry_steps': 0, 'cash':10, 'inv': {}}
inventoryLimit = 10
num_agents = 20
recipes = {}
goods = ['food', 'wood', 'furniture']
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 2, 'numInput': 0}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20}
profession = {'food':'F', 'wood':'W', 'furniture':'C', 'none':'-'}
# Parameters
time_steps = 500
p_birth = .01
birthGap = 5
starve_limit = 6

food_pop = []
wood_pop = []
carp_pop = []
foodInv = []
woodInv = []
carpInv = []

#init
def GetInputCom(agent):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', 'none')
    return inputCom
def GetOutputCom(agent):
    return agent.output

def InitAgents(agents):
    for a in range(num_agents):
        agent = agents[a]
        output = 'none'

        if a < 7:
            output = 'food'
        elif a < 18:
            output = 'wood'
        elif a < 20:
            output = 'furniture'

        #init inventory
        InitAgent(agent, output, 10, 2)


def InitAgent(agent, output, numInput, numFood):
    agent.output = output
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', 'none')
    for good in goods:
        agent.inv[good] = 0
    if inputCom != 'none':
        agent.inv[inputCom] = numInput
    agent.inv['food'] = numFood
    print('init', agent.output, agent.inv)

def Produce(t, agents):
    i=0
    for agent in agents:
        output = agent.output
        print(t, agent.name(), agent.inv)
        recipe = recipes[output]
        #produce
        numOutput = 0
        if recipe['numInput'] == 0:
            numOutput = recipe['production'] 
        else:
            com = recipe['input']
            if agent.inv[com] >= recipe['numInput']:
                numOutput = recipe['production'] 
                agent.inv[com] -= recipe['numInput']

        #print("agent: ", agent)
        agent.inv[output] += numOutput
        print(t, agent.name(), 'built',numOutput, output, agent.inv)
        i+=1

def Trade(t, agents):
    #what if all trade are moneyless and communistic? take all food and redistribute
        #sum all demands, subtract from askers proportional to their inventory
        #if asks < bids, give to bidders with least units

    #take all wood and redistribute?
    #take all furnitures and redistribute?
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
            if GetInputCom(agent) == good:
                agent.bid = max(0, recipe['numInput'] - agent.inv.get(good, 0))
            elif agent.output != good:
                agent.bid = max(0, inventoryLimit - agent.inv.get(good,0)) / divisor
            print(t, agent.name(), 'bid', agent.bid, 'input', GetInputCom(agent), 'recipe for', recipe['commodity'], 'num input', recipe['numInput'], agent.inv[good])
            totalBids += agent.bid

            if agent.output == good:
                agent.ask = max(0, agent.inv.get(good, 0))
                totalAsks += agent.ask
            i += 1

        #take goods from askers
        totalTrades = min(totalAsks, totalBids)
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


def Live(t, agents):
    new_agents = []
    #eat food/starve
    print("living")
    numfood = 0
    numwood = 0
    numFurn = 0
    for agent in agents:
        if agent.inv.get('wood', 0) > 2 and GetInputCom(agent) != 'wood' and GetOutputCom(agent) != 'wood':
            agent.inv['wood'] -= 1
            numwood += 1
        if agent.inv.get('furniture', 0) > 2 and GetOutputCom(agent) != 'furniture':
            agent.inv['furniture'] -= 1
            numFurn += 1

        #life cycle
        if agent.output != 'food' and agent.inv['food'] > 0:
            food = agent.inv['food']
            bins = [5,10,15]
            foodRate = [1, 4, 6]
            #eatFood = 1 if (agent.inv['food'] < 10) else 3.5#1.25
            eatFood = foodRate[bisect.bisect(bins,food)]
            agent.inv['food'] -= eatFood
            numfood += 1
            agent.hungry_steps = 0
        elif agent.output != 'food':
            agent.hungry_steps += 1
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth:
                agent.lastRepro = t
                new_agent = Agent()
                giveFood = min(2, agent.inv['food'])
                agent.inv['food'] -= giveFood
                #find the smallest number of professions and use that one, since no one makes money
                output = FindSmallestTrade(agents)
                print(t, "new agent of ", output)
                numInput = 0
                InitAgent(new_agent, output, numInput, giveFood)
                new_agents.append(new_agent)
        if agent.hungry_steps < starve_limit:
            new_agents.append(agent)
        else:
            print(agent.name(), 'has starved to death')

    print("consumed ", numfood, "food", numwood, "wood", numFurn, "furnitures")
    return new_agents


def FindSmallestTrade(agents):
    counts = dict()
    for agent in agents:
        counts.setdefault(agent.output, 0)
        counts[agent.output] += 1
    return min(counts, key=counts.get)

def PrintStats(t, agents):
    msg = ""
    for agent in agents:
        msg += profession[agent.output] + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get('food',0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get('wood',0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get('furniture',0), 1)) + ','
    print(msg)

def main():
    agents = [Agent() for _ in range(num_agents)]
    InitAgents(agents)
    for t in range(time_steps):
        PrintStats(t, agents)
        Produce(t, agents)
        Trade(t, agents)
        agents = Live(t, agents)


        # Track population
        foodInv.append(sum(agent.inv.get('food', 0) for agent in agents))
        woodInv.append(sum(agent.inv.get('wood', 0) for agent in agents))
        carpInv.append(sum(agent.inv.get('furniture', 0) for agent in agents))
        food_pop.append(sum(agent.output == 'food' for agent in agents))
        wood_pop.append(sum(agent.output == 'wood' for agent in agents))
        carp_pop.append(sum(agent.output == 'furniture' for agent in agents))

    # Plot results
    figure, axis = plt.subplots(3, 1)
    figure.set_figwidth(10)
    figure.set_figheight(10)
    axis[1].plot(foodInv, label='FoodInv', color='green')
    axis[1].plot(woodInv, label='WoodInv', color='red')
    axis[1].plot(carpInv, label='carpInv', color='blue')
    axis[1].set_xlabel("Time Step")
    axis[1].set_ylabel("Inventory")
    axis[1].set_title("Inventory vs time ")

    axis[2].plot(food_pop, label='Food', color='green')
    axis[2].plot(wood_pop, label='Wood', color='red')
    axis[2].plot(carp_pop, label='carp', color='blue')
    axis[2].set_xlabel("Time Step")
    axis[2].set_ylabel("Population")
    axis[2].set_title("Population vs time")
    axis[0].plot(wood_pop, food_pop)
    axis[0].set_xlabel("wood Population (x)")
    axis[0].set_ylabel("food Population (y)")
    axis[0].set_title("Phase plot")
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()
