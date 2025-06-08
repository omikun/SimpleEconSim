import random
import math
import matplotlib.pyplot as plt
import copy
import bisect
#import econsim_trade as trade
import econsim_trade_unity as trade

agentid = 0
class Agent:
    def __init__(self, t):
        global agentid
        self.id = agentid
        self.birthRound = t
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
    def age(self, t):
        return t - self.birthRound

# Initial populations
#agent_template = {'profession': 'none','hungry_steps': 0, 'cash':10, 'inv': {}}
num_agents = 20
recipes = {}
goods = ['food', 'wood', 'furniture']
overProductionDerate = .5
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0, 'maxtotalprod': 100}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 2, 'numInput': 0, 'maxtotalprod': 30}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20, 'maxtotalprod':400}
profession = {'food':'F', 'wood':'W', 'furniture':'C', 'none':'-'}
totalProd = dict()
# Parameters
time_steps = 400
p_birth = .01
birthGap = 7
starve_limit = 12

food_pop = []
dead_pop = [0]
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
    numFarmers = sum(1 if agent.output == 'food' else 0 for agent in agents)
    numLoggers = sum(1 if agent.output == 'wood' else 0 for agent in agents)
    totalProd.clear()
    for agent in agents:
        output = agent.output
        print(t, agent.name(), agent.inv, 'hungry_steps', agent.hungry_steps)
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
        age = t - agent.birthRound if output == 'food' else 0
        numOutput += math.log2(age+1)
        #derate factor based on overproduction
        if output == 'food':
            productionSlice = recipe['maxtotalprod'] / numFarmers
            if (numOutput > productionSlice):
                    numOutput = numOutput * overProductionDerate
        if output == 'wood':
            numOutput = min(numOutput, recipe['maxtotalprod'] / numLoggers)
        numOutput = math.floor(numOutput)

        agent.inv[output] += numOutput
        totalProd.setdefault(output, 0)
        totalProd[output] += numOutput
        print(t, agent.name(), 'built',numOutput, output, agent.inv)
        i+=1



def Live(t, agents):
    global dead_pop
    new_agents = []
    #eat food/starve
    print("living")
    numfood = 0
    numwood = 0
    numFurn = 0
    numdead = dead_pop[-1]
    for agent in agents:
        if agent.inv.get('wood', 0) > 2 and GetInputCom(agent) != 'wood' and GetOutputCom(agent) != 'wood':
            agent.inv['wood'] -= 1
            numwood += 1
        if agent.inv.get('furniture', 0) > 2 and GetOutputCom(agent) != 'furniture':
            agent.inv['furniture'] -= 1
            numFurn += 1

        #life cycle
        if agent.inv['food'] >= 1:
            food = agent.inv['food']
            bins = [5,10,15]
            foodRate = [1, 2, 5]
            #eatFood = 1 if (agent.inv['food'] < 10) else 3.5#1.25
            eatFood = foodRate[bisect.bisect(bins,food)]
            agent.inv['food'] -= eatFood
            numfood += eatFood
            agent.hungry_steps = 0
        elif agent.output != 'food':
            agent.hungry_steps += 1
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth:
                agent.lastRepro = t
                new_agent = Agent(t)
                giveFood = min(2, agent.inv['food'])
                agent.inv['food'] -= giveFood
                #find the smallest number of professions and use that one, since no one makes money
                #output = FindSmallestTrade(agents)
                output = trade.mostDemand
                if NumAgents(agents, output) > 40:
                    output = 'wood'
                print(t, "new agent of ", output)
                numInput = 0
                InitAgent(new_agent, output, numInput, giveFood)
                new_agents.append(new_agent)
        if agent.hungry_steps < starve_limit:
            #die of old age
            if random.random() > pow(agent.age(t) / 1000, 2):
                new_agents.append(agent)
            else:
                print(t, agent.name(), 'has died due to age')
                numdead += 1
        else:
            print(t, agent.name(), 'has starved to death')
            numdead += 1
 #"hungry_steps:",agent.hungry_steps)
    dead_pop.append(numdead)

    print("consumed ", numfood, "food", numwood, "wood", numFurn, "furnitures")
    return new_agents

def NumAgents(agents, good):
    return sum(1 if agent.output == good else 0 for agent in agents)

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
    agents = [Agent(0) for _ in range(num_agents)]
    InitAgents(agents)
    for t in range(time_steps):
        #PrintStats(t, agents)
        Produce(t, agents)
        trade.Trade(t, agents, recipes)
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
    figure.set_figheight(14)
    axis[1].plot(foodInv, label='FoodInv', color='green')
    axis[1].plot(woodInv, label='WoodInv', color='red')
    axis[1].plot(carpInv, label='carpInv', color='blue')
    axis[1].set_xlabel("Time Step")
    axis[1].set_ylabel("Inventory")
    axis[1].set_title("Inventory vs time ")

    axis[2].plot(food_pop, label='Food', color='green')
    axis[2].plot(wood_pop, label='Wood', color='red')
    axis[2].plot(carp_pop, label='carp', color='blue')
    axis[2].plot(dead_pop, label='dead', color='black')
    axis[2].set_xlabel("Time Step")
    axis[2].set_ylabel("Population")
    axis[2].set_title("Population vs time")
    axis[0].plot(food_pop, wood_pop)
    axis[0].plot(food_pop, carp_pop)
    axis[0].set_xlabel("food Population (x)")
    axis[0].set_ylabel("wood/carpenter Population (y)")
    axis[0].set_title("Phase plot")
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()
