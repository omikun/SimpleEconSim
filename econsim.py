import random
import math
import matplotlib.pyplot as plt
import copy

# Initial populations
agent_template = {'profession': 'none','hungry_steps': 0, 'cash':10, 'inv': {}}
inventoryLimit = 10
num_agents = 20
agents = [copy.deepcopy(agent_template) for _ in range(num_agents)]
recipes = {}
goods = ['food', 'wood', 'furniture']
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 2, 'numInput': 0}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20}
profession = {'food':'F', 'wood':'W', 'furniture':'C', 'none':'-'}
# Parameters
time_steps = 10
p_birth = .01
starve_limit = 3

food_pop = []
wood_pop = []
carp_pop = []
foodInv = []
woodInv = []
carpInv = []

#init
def GetInputCom(agent):
    recipe = recipes[agent['profession']]
    inputCom = recipe.get('input', 'none')
    return inputCom

def InitAgents(agents):
    for a in range(num_agents):
        agent = agents[a]

        if a < 10:
            agent['profession'] = 'food'
        elif a < 18:
            agent['profession'] = 'wood'
        elif a < 20:
            agent['profession'] = 'furniture'

        #init inventory
        recipe = recipes[agent['profession']]
        inputCom = recipe.get('input', 'none')
        inv = agent['inv']
        for good in goods:
            inv[good] = 0
        if inputCom != 'none':
            inv[inputCom] = 10
        inv['food'] = 2

    for agent in agents:
        print(agent['profession'], agent['inv'])

def Produce(t, agents):
    i=0
    for agent in agents:
        output = agent['profession']
        inv = agent['inv']
        print(t, 'agent', i, inv)
        recipe = recipes[output]
        #produce
        numOutput = 0
        if recipe['numInput'] == 0:
            numOutput = recipe['production'] 
        else:
            com = recipe['input']
            if inv[com] >= recipe['numInput']:
                numOutput = recipe['production'] 
                inv[com] -= recipe['numInput']

        #print("agent: ", agent)
        inv[output] += numOutput
        print(t, 'agent', i, 'built',numOutput, output, inv)
        i+=1

def Trade(t, agents):
    #what if all trade are moneyless and communistic? take all food and redistribute
        #sum all demands, subtract from askers proportional to their inventory
        #if asks < bids, give to bidders with least units
    
    #take all wood and redistribute?
    #take all furnitures and redistribute?
    for good, recipe in recipes.items():
        #get total bids and asks
        totalBids = 0
        for agent in agents:
            inv = agent['inv']
            if GetInputCom(agent) == good:
                totalBids += max(0, recipe['numInput'] - inv.get(good, 0))
            elif agent['profession'] != good:
                totalBids += max(0, inventoryLimit - inv.get(good,0))

        totalAsks = 0
        for agent in agents:
            inv = agent['inv']
            if agent['profession'] == good:
                totalAsks += max(0, inv.get(good, 0))

        #take goods from askers
        totalTrades = min(totalAsks, totalBids)
        print(t, "trading ", good, " asks: ", totalAsks, " bids: ", totalBids)

        if totalTrades == 0:
            continue

        totalHandout = 0
        i = 0
        for agent in agents:
            if agent['profession'] == good:
                inv = agent['inv']
                ask = inv.get(good,0)
                handout = ask / totalAsks * totalTrades
                inv[good] -= handout
                totalHandout += handout
                
                print(t, 'trading ', good, ' id:', str(i), 'ask: ', ask, ' handout: ', handout)
            i+= 1
        assert totalHandout == totalTrades, 'handout-' + str(totalHandout) + ' not same as trades-' + str(totalTrades)

        #give goods to bidders
        totalReceived = 0
        i = 0
        for agent in agents:
            bid = 0
            inv = agent['inv']
            if GetInputCom(agent) == good:
                bid = max(0, recipe['numInput'] - inv.get(good, 0))
            elif agent['profession'] != good:
                bid += max(0, inventoryLimit - inv.get(good,0))
            received = bid / totalBids * totalTrades
            if received > 0:
                print(t, 'trading ', good, ' id:', str(i), 'bid: ', bid, ' received: ', received)
                inv[good] += received
                totalReceived += received
            i += 1
        assert math.isclose(totalHandout, totalReceived), 'handout-' + str(totalHandout) + ' not same as received-' + str(totalReceived)

        print(t, " trades: ", good, " traded: ", totalHandout)


def Live(t, agents):
    new_agents = []
    #eat food/starve
    print("living")
    for agent in agents:
        inv = agent['inv']
        #life cycle
        if inv['food'] > 0:
            inv['food'] -= 1
            agent['hungry_steps'] = 0
            if random.random() < p_birth:
                new_agents.append(agent_template)
                new_agents[-1]['profession'] = 'food'
        else:
            agent['hungry_steps'] += 1
        if inv.get('wood', 0) > 2:
            inv['wood'] -= 1
        if inv.get('furniture', 0) > 5:
            inv['furniture'] -= 1
        if agent['hungry_steps'] < starve_limit:
            new_agents.append(agent)

    agents = new_agents

def PrintStats(t, agents):
    msg = ""
    for agent in agents:
        msg += profession[agent['profession']] + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent['inv'].get('food',0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent['inv'].get('wood',0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent['inv'].get('furniture',0), 1)) + ','
    print(msg)

def main():
    InitAgents(agents)
    for t in range(time_steps):
        PrintStats(t, agents)
        Produce(t, agents)
        Trade(t, agents)
        Live(t, agents)


        # Track population
        foodInv.append(sum(agent['inv'].get('food', 0) for agent in agents))
        woodInv.append(sum(agent['inv'].get('wood', 0) for agent in agents))
        carpInv.append(sum(agent['inv'].get('furniture', 0) for agent in agents))
        food_pop.append(sum(agent['profession'] == 'food' for agent in agents))
        wood_pop.append(sum(agent['profession'] == 'wood' for agent in agents))
        carp_pop.append(sum(agent['profession'] == 'furniture' for agent in agents))

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
