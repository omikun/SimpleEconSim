import sys 
import random
import math
import matplotlib.pyplot as plt
import copy
import bisect
#import econsim_trade as trade
#import econsim_trade_unity as trade
import econsim_trade_money as trade
from collections import defaultdict

agentid = 0
govCash = 0
class Agent:
    def __init__(self, t):
        global agentid
        self.id = agentid
        self.birthRound = t
        self.alive = True
        self.parent = None
        self.descendents = []
        agentid += 1
        self.bid = 0
        self.ask = 0
        self.output = 'none'
        self.hungry_steps = 0
        self.cash = 0
        self.inv = {}
        self.lastRepro = 0

    def name(self):
        return 'agent'+str(self.id)+'-'+self.output
    def age(self, t):
        return t - self.birthRound

# Initial populations
#agent_template = {'profession': 'none','hungry_steps': 0, 'cash':10, 'inv': {}}
num_agents = 20
recipes = {}
goods = ['food', 'wood', 'furniture']
overProductionDerate = .5
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0, 'maxtotalprod': 200, 'maxinv': 20}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 1, 'numInput': 0, 'maxtotalprod': 30, 'maxinv': 10}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20, 'maxtotalprod':400, 'maxinv': 2}
profession = {'food':'F', 'wood':'W', 'furniture':'C', 'none':'-'}
totalProd = defaultdict(int)
# Parameters
time_steps = 300
p_birth = .04
p_death = .1
birthGap = 7
starve_limit = 20

food_pop = []
dead_pop = [0]
total_pop = []
wood_pop = []
carp_pop = []
foodInv = []
woodInv = []
carpInv = []
demands = dict()
demands['food'] = []
demands['wood'] = []
demands['furniture'] = []

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
        InitAgent(agent, output, 10, 2, 60, 40)


def InitAgent(agent, output, numInput, numFood, cash, delta=0):
    agent.output = output
    agent.cash = cash + random.randint(-delta, delta)
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', 'none')
    for good in goods:
        agent.inv[good] = 0
    if inputCom != 'none':
        agent.inv[inputCom] = numInput
    agent.inv['food'] = numFood
    print('init', agent.output, agent.inv)

def Produce(t, agents):
    global goods
    numAgentsPerGood = dict()
    for good in goods:
        numAgentsPerGood[good] = NumAgents(agents, good)

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
            if agent.inv[com] >= recipe['numInput'] and agent.inv[output] < 20:
                numOutput = recipe['production'] 
                agent.inv[com] -= recipe['numInput']

        #print("agent: ", agent)
        age = t - agent.birthRound if output == 'food' else 0
        numOutput += math.log10(age+1)
        #derate factor based on overproduction
        if output == 'food' or output == 'wood':
            numOutput = min(numOutput, recipe['maxtotalprod'] / numAgentsPerGood[output])
        #numOutput = math.floor(numOutput)

        agent.inv[output] += numOutput
        totalProd[output] += numOutput
        print(t, agent.name(), 'built',numOutput, output, agent.inv)

    for good, produced in totalProd.items():
        print(t, numAgentsPerGood[good],'produced', produced, good)

hungry_log = {'food':[], 'wood':[], 'furniture':[]}

def Live(t, agents):
    global dead_pop
    global govCash
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
        if agent.inv.get('furniture', 0) > 0 and GetOutputCom(agent) != 'furniture' and random.random() < .02:
            agent.inv['furniture'] -= 1
            numFurn += 1

        #life cycle
        if agent.inv['food'] >= 1:
            food = agent.inv['food']
            bins = [5,10,15]
            foodRate = [1, 2, 4, 5]
            #eatFood = 1 if (agent.inv['food'] < 10) else 3.5#1.25
            eatFood = foodRate[bisect.bisect(bins,food)]
            agent.inv['food'] -= eatFood
            numfood += eatFood
            agent.hungry_steps = 0
        elif agent.output != 'food':
            agent.hungry_steps += 1
            
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth and agent.cash > 5:
                agent.lastRepro = t
                new_agent = Agent(t)
                new_agent.parent = agent
                agent.descendents.append(new_agent)
                giveFood = min(2, agent.inv['food']) ##potentiall food coming from thin air - need gov support
                agent.inv['food'] -= giveFood
                #find the smallest number of professions and use that one, since no one makes money
                #output = FindSmallestTrade(agents)
                output = trade.mostDemand
                #some fraction keeps parent's profession
                if random.random() < .5:
                    output = agent.output
                #if NumAgents(agents, output) > 40:
                    #output = 'wood'
                print(t, "new agent of ", output)
                numInput = 0
                cash = min(4, agent.cash)
                agent.cash -= cash
                InitAgent(new_agent, output, numInput, giveFood, cash)
                new_agents.append(new_agent)
                
        if agent.hungry_steps < starve_limit:
            #die of old age
            #if random.random() > math.exp(-agent.age(t) / 80) / 50: #pow(agent.age(t) / 1000, 2):
            #if random.random() > pow(agent.age(t) / 2000, 2):
            if random.random() > [0.0002,0.0003,0.0007,0.0013,0.0025,0.006,0.013,0.027,0.06,0.13][min(agent.age(t)//30, 9)]:
                new_agents.append(agent)
            else:
                agent.alive = False
                print(t, agent.name(), 'has died due to age')
        else:
            print(t, agent.name(), 'has starved to death')
            numdead += 1
            agent.alive = False
        
        if not agent.alive:
            livingDescendents = [agent for agent in agent.descendents if agent.alive]
            print(t, agent.name(), 'died, has', agent.cash, ' #descendents:', len(livingDescendents),
                  [agent.name() for agent in livingDescendents])
            numdead += 1
            #find descendents
            #descendents = [agent for agent in agents if agent.parent == agent]
            #assert len(descendents) == len(agent.descendents), 'descdendents dont match!'
            if len(livingDescendents) > 0:
                inheritence = agent.cash / len(livingDescendents)
                for descendent in livingDescendents:
                    descendent.cash += inheritence
            else:
                govCash += agent.cash
            
    if govCash > 0:
        starving_agents = [agent for agent in agents if agent.hungry_steps > 0 ]
        if len(starving_agents) > 0:
            wellfare = govCash / len(starving_agents)
            for agent in starving_agents:
                agent.cash += wellfare
            govCash = 0


    for good in goods:
        hungry_log[good].append(sum(1 for agent in agents if agent.output == good and agent.hungry_steps > 0))
        
    dead_pop.append(numdead)

    print("consumed ", numfood, "food", numwood, "wood", numFurn, "furnitures")
    return new_agents

def NumAgents(agents, good):
    return sum(agent.output == good for agent in agents)

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

cash_log = {'food':[], 'wood':[], 'furniture':[], 'gov':[]}
totalCash_log = []
price_log = {'food':[], 'wood':[], 'furniture':[]}
sold_log = {'food':[], 'wood':[], 'furniture':[]}

def main():
    global govCash
    time_steps = int(sys.argv[1])
    agents = [Agent(0) for _ in range(num_agents)]
    InitAgents(agents)
    prevTotalCash = (sum(agent.cash for agent in agents) + govCash)
    for t in range(time_steps):
        if t == 800:
            recipes['food']['maxtotalprod'] = 50
        if t == 1300:
            recipes['food']['maxtotalprod'] = 400
        if t == 2300:
            recipes['food']['maxtotalprod'] = 100
        #PrintStats(t, agents)
        Produce(t, agents)
        #trade.Trade(t, agents, recipes)
        trade.Trade(t, agents, recipes, demands, sold_log)
        agents = Live(t, agents)

        # Track population
        foodInv.append(sum(agent.inv.get('food', 0) for agent in agents))
        woodInv.append(sum(agent.inv.get('wood', 0) for agent in agents))
        carpInv.append(sum(agent.inv.get('furniture', 0) for agent in agents))
        
        food_pop.append(sum(agent.output == 'food' for agent in agents))
        wood_pop.append(sum(agent.output == 'wood' for agent in agents))
        carp_pop.append(sum(agent.output == 'furniture' for agent in agents))
        total_pop.append(food_pop[-1] + wood_pop[-1] + carp_pop[-1])
        
        cash_log['food'].append(sum(agent.cash if agent.output == 'food' else 0 for agent in agents ))
        cash_log['wood'].append(sum(agent.cash if agent.output == 'wood' else 0 for agent in agents ))
        cash_log['furniture'].append(sum(agent.cash if agent.output == 'furniture' else 0 for agent in agents ))
        cash_log['gov'].append(govCash)
        totalCash_log.append(sum(agent.cash for agent in agents) + govCash)
        
        price_log['food'].append(recipes['food']['price'])
        price_log['wood'].append(recipes['wood']['price'])
        price_log['furniture'].append(recipes['furniture']['price'])
        
        if math.fabs(prevTotalCash - totalCash_log[-1]) > 10:
            print(t, "total cash not matching", prevTotalCash, '!=', totalCash_log[-1])
            # break
        prevTotalCash = totalCash_log[-1]

    # Plot results
    figure, axis = plt.subplots(4, 2)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(14)
    figure.set_figheight(16)
    plt.subplots_adjust(top=0.95, bottom=0.05, hspace=0.3)

    axis[0].set_title("Phase plot")
    axis[0].set_xlabel("food Population (x)")
    axis[0].set_ylabel("wood/carpenter Population (y)")
    axis[0].plot(food_pop, wood_pop, color='red')
    axis[0].plot(food_pop, carp_pop, color='blue')

    axis[1].set_title("Inventory vs time ")
    #axis[1].set_xlabel("Time Step")
    axis[1].set_ylabel("Inventory")
    axis[1].plot(foodInv, label='FoodInv', color='green')
    axis[1].plot(woodInv, label='WoodInv', color='red')
    axis[1].plot(carpInv, label='carpInv', color='blue')

    axis[2].set_title("Population vs time")
    #axis[2].set_xlabel("Time Step")
    axis[2].set_ylabel("Population")
    # axis[2].set_yscale('log')
    axis[2].plot(food_pop, label='Food', color='green')
    axis[2].plot(wood_pop, label='Wood', color='red')
    axis[2].plot(carp_pop, label='carp', color='blue')
    axis[2].plot(total_pop, label='total', color='black')
    #axis[2].plot(dead_pop, label='dead', color='black')

    axis[3].set_title("Demands vs time")
    #axis[3].set_xlabel("Time Step")
    axis[3].set_ylabel("Demands (log scale)")
    axis[3].set_yscale('log')
    axis[3].plot(demands['food'], label='Food', color='green')
    axis[3].plot(demands['wood'], label='Wood', color='red')
    axis[3].plot(demands['furniture'], label='carp', color='blue')

    axis[4].set_title("Cash vs time")
    #axis[4].set_xlabel("Time Step")
    axis[4].set_ylabel("Cash")
    axis[4].plot(cash_log['food'], label='Food', color='green')
    axis[4].plot(cash_log['wood'], label='Wood', color='red')
    axis[4].plot(cash_log['furniture'], label='carp', color='blue')
    axis[4].plot(cash_log['gov'], label='gov', color='yellow')
    axis[4].plot(totalCash_log, label='total', color='black')

    axis[5].set_title("Price vs time")
    #axis[5].set_xlabel("Time Step")
    axis[5].set_ylabel("Price")
    axis[5].set_yscale('log')
    axis[5].plot(price_log['food'], label='Food', color='green')
    axis[5].plot(price_log['wood'], label='Wood', color='red')
    axis[5].plot(price_log['furniture'], label='carp', color='blue')

    axis[6].set_title("Sold vs time")
    #axis[6].set_xlabel("Time Step")
    axis[6].set_ylabel("Sold")
    # axis[6].set_yscale('log')
    axis[6].plot(sold_log['food'], label='Food', color='green')
    axis[6].plot(sold_log['wood'], label='Wood', color='red')
    axis[6].plot(sold_log['furniture'], label='carp', color='blue')

    axis[7].set_title("Hunger vs time")
    #axis[7].set_xlabel("Time Step")
    axis[7].set_ylabel("Num hungry")
    # axis[7].set_yscale('log')
    axis[7].plot(hungry_log['food'], label='Food', color='green')
    axis[7].plot(hungry_log['wood'], label='Wood', color='red')
    axis[7].plot(hungry_log['furniture'], label='carp', color='blue')
    
    #plt.legend()
    # Get legend handles and labels from one axis (assuming they’re the same across all)
    handles, labels = axis[2].get_legend_handles_labels() #need label in that axis

    # Add a single global legend
    figure.legend(handles, labels, loc='center', ncol=1, fontsize='small') 
    
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
    plt.show()

if __name__ == "__main__":
    main()
