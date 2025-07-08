import sys 
import random
import math
from statistics import mean
import matplotlib.pyplot as plt

import econsim_live as Living
import econsim_states
from econsim_states import *
from goods import Goods
#import econsim_trade as trade
#import econsim_trade_unity as trade
import econsim_trade_money as trade
from logger import *


class Agent:
    def __init__(self, t):
        self.id = econsim_states.agentid
        self.birthRound = t
        self.alive = True
        self.parent = None
        self.descendents = []
        econsim_states.agentid += 1
        self.bid = 0
        self.ask = 0
        self.output = Goods.none
        self.hungry_steps = 0
        self.cash = 0
        self.inv = {}
        self.lastRepro = 0
        self.loans = []

    def name(self):
        return 'agent'+str(self.id)+'-'+ profession[self.output]
    def age(self, t):
        return t - self.birthRound
    
    def oweThisTurn(self):
        return sum(loan.getPaymentAmount() for loan in self.loans)

# Initial populations
#agent_template = {'profession': Goods.none,'hungry_steps': 0, 'cash':10, 'inv': {}}
recipes[Goods.food] = {'commodity': Goods.food, 'production': 4, 'price': 1, 'numInput': 0, 'maxtotalprod': 100, 'maxinv': 20}
recipes[Goods.wood] = {'commodity': Goods.wood, 'production': 2, 'price': 1, 'numInput': 0, 'maxtotalprod': 30, 'maxinv': 10}
recipes[Goods.furn] = {'commodity': Goods.furn, 'production': 1, 'input': Goods.wood, 'numInput': 10, 'price': 15, 'maxtotalprod':6, 'maxinv': 3}
recipes[Goods.gov] = {'commodity': Goods.gov, 'production': 0, 'numInput': 0, 'price': 1, 'maxtotalprod':0, 'maxinv': 0}
# Parameters

for good in goods:
    pop_log[good] = []
    hungry_log[good] = []
    if good != Goods.gov:
        demand_ratio_log[good] = []
        demand_log[good] = []
        supply_log[good] = []
        inv_log[good] = []
        perCapitaInv[good] = []
        production_log[good] = []

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
        logger.error(profession[agent.output], 'not in dictionary', recipes)
    inputCom = recipe.get('input', Goods.none)
    for good in goods:
        agent.inv[good] = 0
    if inputCom != Goods.none:
        agent.inv[inputCom] = numInput
    agent.inv[Goods.food] = numFood
    loginfo('init', agent.output, agent.inv)

def Produce(t, agents):
    numAgentsPerGoods = dict()
    for good in econsim_states.goods:
        numAgentsPerGoods[good] = NumAgents(agents, good)

    totalProd.clear()
    for agent in agents:
        output = agent.output
        loginfo(t, agent.name(), agent.inv, 'hungry_steps', agent.hungry_steps)
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
        loginfo(t, agent.name(), 'built',numOutput, output, agent.inv)

    for good in econsim_states.goods:
        if good != Goods.gov:
            production_log[good].append(totalProd[good])
    for good, produced in totalProd.items():
        loginfo(t, numAgentsPerGoods[good],'produced', produced, good)


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
    loginfo(msg)


for good in goods:
    cash_log[good] = []
    gini_log[good] = []

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
    logInit()
    time_steps = int(sys.argv[1])
    agents = [Agent(0) for _ in range(num_agents)]
    InitAgents(agents)
    prevTotalCash = (sum(agent.cash for agent in agents) + econsim_states.govCash)
    for t in range(time_steps):
        # if t == 800:
        #     recipes[Goods.food]['maxtotalprod'] = 50
        # if t == 1300:
        #     recipes[Goods.food]['maxtotalprod'] = 400
        # if t == 2300:
        #     recipes[Goods.food]['maxtotalprod'] = 100
        #PrintStats(t, agents)
        Produce(t, agents)
        #trade.Trade(t, agents, recipes)
        trade.Trade(t, agents, recipes, demand_ratio_log, demand_log, supply_log, sold_log, bought_log)
        agents = Living.Live(t, agents)

        for good in goods:
            pop_log[good].append(sum(agent.output == good for agent in agents))
            cash_log[good].append(sum(agent.cash if agent.output == good else 0 for agent in agents))
            gini_log[good].append(compute_gini(agents, good))
            if good != Goods.gov:
                inv_log[good].append(sum(agent.inv.get(good, 0) for agent in agents))
                newlist = [agent.inv[good] for agent in agents if agent.output != good]
                avgInv = mean(newlist) if newlist else 0
                perCapitaInv[good].append(avgInv)
                price_log[good].append(recipes[good]['price'])

        total_pop.append(sum(log[-1] for log in pop_log.values()))
        bankCash_log.append(trade.bank.total_deposits - trade.bank.total_liabilities)
        totalCash_log.append(sum(agent.cash for agent in agents) + econsim_states.govCash + bankCash_log[-1])

        for prof in goods:
            for good in goods:
                bought_log[prof][good].append(0)
                
        if math.fabs(prevTotalCash - totalCash_log[-1]) > 3:
            logwarning(t, "total cash not matching", prevTotalCash, '!=', totalCash_log[-1])
            # break
        prevTotalCash = totalCash_log[-1]

    # Plot results
    figure, axis = plt.subplots(4, 4)
    axis = axis.flatten()
    figure.patch.set_facecolor('lightgrey')
    figure.set_figwidth(20)
    figure.set_figheight(12)
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
    axis[axisId].set_title("Demands Ratio vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_ratio_log[good], label=labels[good], color=colors[good])

    axisId += 1
    #production
    axis[axisId].set_title("Production vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Units Produced per round")
    axis[axisId].set_yscale('log')
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(production_log[good], label=labels[good], color=colors[good])
    
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
    # axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(cash_log[good], label=labels[good], color=colors[good])
    axis[axisId].plot(totalCash_log, label='total', color='black')
    axis[axisId].plot(bankCash_log, label='bank', color='purple')

    axisId += 1
    axis[axisId].set_title("Demand vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Demands (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(demand_log[good], label=labels[good], color=colors[good])


    axisId += 1
    axis[axisId].set_title("Sold vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Sold")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(sold_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Price vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Price")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(price_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Hunger vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Num hungry")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        axis[axisId].plot(hungry_log[good], label=labels[good], color=colors[good])

    axisId += 1
    axis[axisId].set_title("Supply vs time")
    #axis[axisId].set_xlabel("Time Step")
    axis[axisId].set_ylabel("Supply (log scale)")
    axis[axisId].set_yscale('log', base=2)
    for good in goods:
        if good != Goods.gov:
            axis[axisId].plot(supply_log[good], label=labels[good], color=colors[good])

    axisId += 1
    #purchases
    titles = ["Farmer", "Logger", "Carpenter", "Gov agent"]
    for i in range(len(titles)):
        axis[axisId+i].set_title(titles[i]+" Purchases")
        axis[axisId+i].set_ylabel("Bought")
        axis[axisId].set_yscale('log', base=2)
    i = 0
    for prof in goods:
        for good in goods:
            if good != Goods.gov:
                axis[axisId+i].plot(bought_log[prof][good], label=labels[good], color=colors[good])
        i += 1
            
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
