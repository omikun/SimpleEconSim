import sys 
import random
import math
from statistics import mean
import matplotlib.pyplot as plt
from goods import Goods
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
        self.output = Goods.none
        self.hungry_steps = 0
        self.cash = 0
        self.inv = {}
        self.lastRepro = 0
        self.loans = []

    def name(self):
        return 'agent'+str(self.id)+'-'+profession[self.output]
    def age(self, t):
        return t - self.birthRound

# Initial populations
#agent_template = {'profession': Goods.none,'hungry_steps': 0, 'cash':10, 'inv': {}}
num_agents = 20
recipes = {}
goods = [Goods.food, Goods.wood, Goods.furn, Goods.gov]
overProductionDerate = .5
recipes[Goods.food] = {'commodity': Goods.food, 'production': 4, 'price': 1, 'numInput': 0, 'maxtotalprod': 200, 'maxinv': 20}
recipes[Goods.wood] = {'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0, 'maxtotalprod': 30, 'maxinv': 10}
recipes[Goods.furn] = {'commodity': Goods.furn, 'production': 1, 'input': Goods.wood, 'numInput': 10, 'price': 15, 'maxtotalprod':2, 'maxinv': 2}
recipes[Goods.gov] = {'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1, 'maxtotalprod':0, 'maxinv': 0}
profession = {Goods.food:'F', Goods.wood:'W', Goods.furn:'C', Goods.gov:'G', Goods.none:'-'}
totalProd = defaultdict(int)
# Parameters
time_steps = 300
p_birth = .04
p_death = .1
birthGap = 7
starve_limit = 20

dead_pop = [0]
deadstarve_pop = [0]
total_pop = []
pop_log = {}
inv_log = {}
hungry_log = {}
demands = dict()
perCapitaInv = dict()

for good in goods:
    pop_log[good] = []
    hungry_log[good] = []
    if good != Goods.gov:
        demands[good] = []
        inv_log[good] = []
        perCapitaInv[good] = []

#init
def GetInputCom(agent):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', Goods.none)
    return inputCom
def GetOutputCom(agent):
    return agent.output

def InitAgents(agents):
    for a in range(num_agents):
        agent = agents[a]
        output = Goods.none

        if a < 10:
            output = Goods.food
        elif a < 16:
            output = Goods.wood
        elif a < 20:
            output = Goods.furn
        elif a < 30:
            output = Goods.gov

        #init inventory
        InitAgent(agent, output, 10, 2, 60, 40)


def InitAgent(agent, output, numInput, numFood, cash, delta=0):
    agent.output = output
    agent.cash = cash + random.randint(-delta, delta)
    if agent.output in recipes:
        recipe = recipes[agent.output]
    else:
        print(profession[agent.output], 'not in dictionary', recipes)
        assert(False)
    inputCom = recipe.get('input', Goods.none)
    for good in goods:
        agent.inv[good] = 0
    if inputCom != Goods.none:
        agent.inv[inputCom] = numInput
    agent.inv[Goods.food] = numFood
    print('init', agent.output, agent.inv)

def Produce(t, agents):
    global goods
    numAgentsPerGoods = dict()
    for good in goods:
        numAgentsPerGoods[good] = NumAgents(agents, good)

    totalProd.clear()
    for agent in agents:
        output = agent.output
        print(t, agent.name(), agent.inv, 'hungry_steps', agent.hungry_steps)
        recipe = recipes[output]
        if (agent.inv[output] >= 20):
            continue
            
        #produce
        numOutput = 0
        if recipe['numInput'] == 0:
            numOutput = recipe['production'] 
        else:
            com = recipe['input']
            if (agent.inv[com] >= recipe['numInput']):
                numOutput = recipe['production'] 
                agent.inv[com] -= recipe['numInput']

        #print("agent: ", agent)
        age = t - agent.birthRound if output == Goods.food else 0
        numOutput += math.log10(age+1)
        
        if agent.hungry_steps > 0:
            numOutput *= 1 / agent.hungry_steps
        #derate factor based on overproduction
        if output == Goods.food or output == Goods.wood:
            numOutput = min(numOutput, recipe['maxtotalprod'] / numAgentsPerGoods[output])
        #numOutput = math.floor(numOutput)

        agent.inv[output] += numOutput
        totalProd[output] += numOutput
        print(t, agent.name(), 'built',numOutput, output, agent.inv)

    for good, produced in totalProd.items():
        print(t, numAgentsPerGoods[good],'produced', produced, good)


def Live(t, agents):
    global dead_pop
    global deadstarve_pop
    global govCash
    new_agents = []
    #eat food/starve
    print("living")
    numfood = 0
    numwood = 0
    numFurn = 0
    numdead = 0 #dead_pop[-1]
    numdeadstarve = deadstarve_pop[-1]
    prevGovCash = govCash
    for agent in agents:
        if agent.inv.get(Goods.wood, 0) > 2 and GetInputCom(agent) != Goods.wood and GetOutputCom(agent) != Goods.wood:
            agent.inv[Goods.wood] -= 1
            numwood += 1
        if agent.inv.get(Goods.furn, 0) > 0 and GetOutputCom(agent) != Goods.furn and random.random() < .02:
            agent.inv[Goods.furn] -= 1
            numFurn += 1

        #life cycle
        if agent.inv[Goods.food] >= 1:
            food = agent.inv[Goods.food]
            bins = [5,10,15]
            foodRate = [1, 2, 4, 8]
            #eatFood = 1 if (agent.inv[Goods.food] < 10) else 3.5#1.25
            eatFood = foodRate[bisect.bisect(bins,food)]
            agent.inv[Goods.food] -= eatFood
            numfood += eatFood
            agent.hungry_steps = 0
        elif agent.output != Goods.food:
            agent.hungry_steps += 1
            
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth and agent.cash > 5 and len(agents) < 512:
                agent.lastRepro = t
                new_agent = Agent(t)
                new_agent.parent = agent
                agent.descendents.append(new_agent)
                giveFood = min(2, agent.inv[Goods.food]) ##potentiall food coming from thin air - need gov support
                agent.inv[Goods.food] -= giveFood
                #find the smallest number of professions and use that one, since no one makes money
                #output = FindSmallestTrade(agents)
                output = trade.mostDemand
                #some fraction keeps parent's profession
                if output == Goods.food or random.random() < .5:
                    output = agent.output
                #if NumAgents(agents, output) > 40:
                    #output = Goods.wood
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
            numdeadstarve += 1
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
        print(t, 'gov cash prev:', prevGovCash, 'now', govCash)
        starving_agents = [agent for agent in new_agents if agent.hungry_steps > 0 ]
        if len(starving_agents) > 0:
            wellfare = govCash / len(starving_agents)
            for agent in starving_agents:
                agent.cash += wellfare
                govCash -= wellfare


    for good in goods:
        hungry_log[good].append(sum(1 for agent in agents if agent.output == good and agent.hungry_steps > 0))
        
    dead_pop.append(numdead)
    deadstarve_pop.append(numdeadstarve)
    print(t, 'num dead', numdead)
    #dead_pop.append(sum(dead_pop)-numdead)

    print("consumed ", numfood, "food", numwood, "wood", numFurn, "furn")
    return new_agents

def NumAgents(agents, good):
    return sum(agent.output == good for agent in agents)

def PrintStats(t, agents):
    msg = ""
    for agent in agents:
        msg += profession[agent.output] + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.food,0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.wood,0), 1)) + ','
    msg += "\n"
    for agent in agents:
        msg += str(round(agent.inv.get(Goods.furn,0), 1)) + ','
    print(msg)

cash_log = {}
gini_log = {}
for good in goods:
    cash_log[good] = []
    gini_log[good] = []
    
totalCash_log = []
price_log = {Goods.food:[], Goods.wood:[], Goods.furn:[]}
sold_log = {Goods.food:[], Goods.wood:[], Goods.furn:[]}
bought_log = dict()
for prof in goods:
    bought_log[prof] = dict()
    for good in goods:
        bought_log[prof][good] = [0]

def compute_gini(agents, good):
    values = sorted([agent.cash for agent in agents if agent.output == good])
    n = len(values)
    if n == 0:
        return 0
    mean_cash = sum(values) / n
    if mean_cash == 0:
        return 0
    diffsum = 0
    for i in range(n):
        for j in range(n):
            diffsum += abs(values[i] - values[j])
    gini = diffsum / (2 * n * n * mean_cash)
    return gini

def main():
    global govCash
    time_steps = int(sys.argv[1])
    agents = [Agent(0) for _ in range(num_agents)]
    InitAgents(agents)
    prevTotalCash = (sum(agent.cash for agent in agents) + govCash)
    for t in range(time_steps):
        if t == 800:
            recipes[Goods.food]['maxtotalprod'] = 50
        if t == 1300:
            recipes[Goods.food]['maxtotalprod'] = 400
        if t == 2300:
            recipes[Goods.food]['maxtotalprod'] = 100
        #PrintStats(t, agents)
        Produce(t, agents)
        #trade.Trade(t, agents, recipes)
        trade.Trade(t, agents, recipes, demands, sold_log, bought_log)
        agents = Live(t, agents)

        for good in goods:
            pop_log[good].append(sum(agent.output == good for agent in agents))
            cash_log[good].append(sum(agent.cash if agent.output == good else 0 for agent in agents ))
            gini_log[good].append(compute_gini(agents, good))
            if good != Goods.gov:
                inv_log[good].append(sum(agent.inv.get(good, 0) for agent in agents))
                perCapitaInv[good].append(mean(agent.inv[good] for agent in agents if agent.output != good))
                price_log[good].append(recipes[good]['price'])

        total_pop.append(sum(log[-1] for log in pop_log.values()))
        totalCash_log.append(sum(agent.cash for agent in agents) + govCash)

        for prof in goods:
            for good in goods:
                bought_log[prof][good].append(0)
                
        if math.fabs(prevTotalCash - totalCash_log[-1]) > 10:
            print(t, "total cash not matching", prevTotalCash, '!=', totalCash_log[-1])
            # break
        prevTotalCash = totalCash_log[-1]

    # Plot results
    figure, axis = plt.subplots(4, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(16)
    plt.subplots_adjust(top=0.98, bottom=0.02, hspace=0.05)

    #axis[0].set_title("Phase plot")
    #axis[0].set_xlabel("food Population (x)")
    #axis[0].set_ylabel("wood/carpenter Population (y)")
    #axis[0].plot(food_pop, wood_pop, color='red')
    #axis[0].plot(food_pop, carp_pop, color='blue')
    
    axisId = 0
    axis[axisId].set_title("Population vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Population")
    axis[axisId].set_yscale('log', base=2)
    colors = {Goods.food: 'green',
              Goods.wood: 'red',
              Goods.furn: 'blue',
              Goods.gov:  'yellow'
              }
    labels = {Goods.food: 'Food',
                Goods.wood: 'Wood',
                Goods.furn: 'carp',
                Goods.gov:  'gov'
                }
    for good in goods:
        axis[axisId].plot(pop_log[good], label=labels[good], color=colors[good])
    axis[axisId].plot(total_pop, label='total', color='black')
    axis[axisId].plot([-x for x in deadstarve_pop], label='dead', color='purple')

    axisId += 1
    axis[axisId].set_title("Inventory vs time ")
    #axis[1].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Inventory")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(inv_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Gini coefficient")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Cash")
    
    for good in goods:
        axis[axisId].plot(gini_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axisId += 1
    axis[axisId].set_title("Demands vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log')
    axis[axisId].plot(demands[Goods.food], label='Food', color='green')
    axis[axisId].plot(demands[Goods.wood], label='Wood', color='red')
    axis[axisId].plot(demands[Goods.furn], label='carp', color='blue')

    axisId += 1
    axis[axisId].set_title("Inventory Per capita (excluding producers)")
    #axis[0].set_xlabel("time ")
    axis[axisId].set_ylabel("Inventory per capita")
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(perCapitaInv[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Cash vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Cash")
    axis[axisId].plot(cash_log[Goods.food], label='Food', color='green')
    axis[axisId].plot(cash_log[Goods.wood], label='Wood', color='red')
    axis[axisId].plot(cash_log[Goods.furn], label='carp', color='blue')
    axis[axisId].plot(cash_log[Goods.gov], label='gov', color='yellow')
    axis[axisId].plot(totalCash_log, label='total', color='black')

    axisId += 1
    axisId += 1
    axis[axisId].set_title("Sold vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Sold")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(sold_log[Goods.food], label='Food', color='green')
    axis[axisId].plot(sold_log[Goods.wood], label='Wood', color='red')
    axis[axisId].plot(sold_log[Goods.furn], label='carp', color='blue')

    axisId += 1
    axis[axisId].set_title("Price vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Price")
    axis[axisId].set_yscale('log')
    axis[axisId].plot(price_log[Goods.food], label='Food', color='green')
    axis[axisId].plot(price_log[Goods.wood], label='Wood', color='red')
    axis[axisId].plot(price_log[Goods.furn], label='carp', color='blue')

    axisId += 1
    axis[axisId].set_title("Hunger vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Num hungry")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(hungry_log[Goods.food], label='Food', color='green')
    axis[axisId].plot(hungry_log[Goods.wood], label='Wood', color='red')
    axis[axisId].plot(hungry_log[Goods.furn], label='carp', color='blue')
    axis[axisId].plot(hungry_log[Goods.gov], label='gov', color='yellow')

    axisId += 1
    axisId += 1
    axis[axisId].set_title("Farmer Purchases")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Bought")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(bought_log[Goods.food][Goods.food], label='Food', color='green')
    axis[axisId].plot(bought_log[Goods.food][Goods.wood], label='Wood', color='red')
    axis[axisId].plot(bought_log[Goods.food][Goods.furn], label='carp', color='blue')
    axisId += 1
    axis[axisId].set_title("Logger Purchases")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Bought")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(bought_log[Goods.wood][Goods.food], label='Food', color='green')
    axis[axisId].plot(bought_log[Goods.wood][Goods.wood], label='Wood', color='red')
    axis[axisId].plot(bought_log[Goods.wood][Goods.furn], label='carp', color='blue')
    axisId += 1
    axis[axisId].set_title("Carpenter Purchases")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Bought")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(bought_log[Goods.furn][Goods.food], label='Food', color='green')
    axis[axisId].plot(bought_log[Goods.furn][Goods.wood], label='Wood', color='red')
    axis[axisId].plot(bought_log[Goods.furn][Goods.furn], label='carp', color='blue')
    axisId += 1
    axis[axisId].set_title("Gov agent Purchases")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Bought")
    # axis[axisId].set_yscale('log')
    axis[axisId].plot(bought_log[Goods.gov][Goods.food], label='Food', color='green')
    axis[axisId].plot(bought_log[Goods.gov][Goods.wood], label='Wood', color='red')
    axis[axisId].plot(bought_log[Goods.gov][Goods.furn], label='carp', color='blue')
    
    #plt.legend()
    # Get legend handles and labels from one axis (assuming they’re the same across all)
    handles, labels = axis[2].get_legend_handles_labels() #need label in that axis

    # Add a single global legend
    figure.legend(handles, labels, loc='upper right', ncol=1, fontsize='small') 
    
    plt.grid(True)
    for ax in axis:
        ax.set_facecolor('lightgrey')
    plt.show()

if __name__ == "__main__":
    main()
