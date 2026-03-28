import bisect
import random

from econsim_states import *
import econsim_trade_money as trade
from econsim import GetInputCom, GetOutputCom, Agent, InitAgent
from econsim_states import *
from goods import Goods
from logger import logdebug


def Live(t, agents):
    global dead_pop
    global deadstarve_pop
    global govCash
    global govInv
    global production_log
    new_agents = []
    #eat food/starve
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
        if agent.inv.get(Goods.food, 0) >= 4:
            agent.inv[Goods.food] -= 4
            numfood += 4
            agent.hungry_steps = 0
        elif agent.inv.get(Goods.food, 0) > 0:
            agent.inv[Goods.food] = 0
            agent.hungry_steps = 0
        else:
            numfood += agent.inv.get(Goods.food, 0)
            agent.inv[Goods.food] = 0
            agent.hungry_steps += 1
        
        # Career switching: EMERGENCY survival (> 5) or Economic Mobility (Cash < 20)
        if agent.hungry_steps > 5:
            if agent.output != Goods.food:
                logdebug(t, agent.name(), 'EMERGENCY! switching to farmer')
                agent.output = Goods.food
                agent.lastCareerSwitch = t
        elif agent.hungry_steps > 2 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
            if trade.mostDemand != Goods.gov and agent.output != trade.mostDemand:
                logdebug(t, agent.name(), 'hungry, switching to in-demand career:', profession[trade.mostDemand])
        elif agent.cash < 20 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
            if trade.mostDemand != Goods.gov and agent.output != trade.mostDemand:
                logdebug(t, agent.name(), 'poor, switching to in-demand career:', profession[trade.mostDemand])
                agent.output = trade.mostDemand
                agent.lastCareerSwitch = t
            
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
                #if aggregate output already at max, pick gov
                if output != Goods.gov and recipes[output]['maxtotalprod'] + 5 <= production_log[output][-1]:
                    output = Goods.gov
                #if NumAgents(agents, output) > 40:
                    #output = Goods.wood
                logdebug(t, "new agent of ", output)
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
                logdebug(t, agent.name(), 'has died due to age')
        else:
            logdebug(t, agent.name(), 'has starved to death')
            numdead += 1
            numdeadstarve += 1
            agent.alive = False
        
        if not agent.alive:
            livingDescendents = [agent for agent in agent.descendents if agent.alive]
            logdebug(t, agent.name(), 'died, has', agent.cash, ' #descendents:', len(livingDescendents),
                  [agent.name() for agent in livingDescendents])
            numdead += 1
            #find descendents
            #descendents = [agent for agent in agents if agent.parent == agent]
            #assert len(descendents) == len(agent.descendents), 'descdendents dont match!'
            wealth = agent.wealth()
            if wealth <= 0:
                continue
            if len(livingDescendents) > 0:
                inheritence = wealth / len(livingDescendents)
                govAgents = [agent for agent in agents if agent.output == Goods.gov]
                for descendent in livingDescendents:
                    descendent.cash += inheritence
                for good, amount in agent.inv.items():
                    profDescendents = [agent for agent in livingDescendents if agent.output == good]
                    if len(profDescendents) > 0:
                        inheritence = amount / len(profDescendents)
                        for descendent in profDescendents:
                            descendent.inv[good] += inheritence
                    else:
                        if len(govAgents) == 0:
                            continue
                        inheritance = amount / len(govAgents)
                        for govAgent in govAgents:
                            govAgent.inv[good] += inheritance
                    #govInv[good] += amount
            else:
                govCash += wealth
            
    if govCash > 0:
        logdebug(t, 'gov cash prev:', prevGovCash, 'now', govCash)
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
    logdebug(t, 'num dead', numdead)
    #dead_pop.append(sum(dead_pop)-numdead)

    logdebug("consumed ", numfood, "food", numwood, "wood", numFurn, "furn")
    return new_agents
