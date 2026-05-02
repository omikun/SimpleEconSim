import bisect
import random

import econsim_states
from econsim_states import *
import econsim_trade_money as trade
from econsim import GetInputCom, GetOutputCom, Agent, InitAgent
from goods import Goods
from logger import logdebug


def Live(t, agents):
    global dead_pop
    global deadstarve_pop
    global production_log
    new_agents = []
    #eat food/starve
    numfood = 0
    numwood = 0
    numFurn = 0
    numdead = 0 #dead_pop[-1]
    numdeadstarve = deadstarve_pop[-1]
    prevGovCash = econsim_states.govCash
    numSwitches = 0
    random.shuffle(agents)
    for agent in agents:
        if agent.inv.get(Goods.wood, 0) > 2 and GetInputCom(agent) != Goods.wood and GetOutputCom(agent) != Goods.wood:
            agent.inv[Goods.wood] -= 1
            numwood += 1
        if agent.inv.get(Goods.furn, 0) > 0 and GetOutputCom(agent) != Goods.furn and random.random() < .066:
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
        
        # Career switching: EMERGENCY survival (> 2) or Economic Mobility (Cash < 20)
        if numSwitches < max_career_switches:
            if agent.hungry_steps > 2:
                if agent.output != Goods.food:
                    logdebug(t, agent.name(), 'EMERGENCY! switching to farmer')
                    agent.output = Goods.food
                    agent.lastCareerSwitch = t
                    numSwitches += 1
            if agent.hungry_steps > 1 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
                if trade.mostDemand != Goods.gov and agent.output != trade.mostDemand:
                    logdebug(t, agent.name(), 'hungry, switching to in-demand career:', profession[trade.mostDemand])
                    agent.output = trade.mostDemand
                    agent.lastCareerSwitch = t
                    numSwitches += 1
            elif agent.cash < 20 and (t - getattr(agent, 'lastCareerSwitch', 0) > 10):
                if random.random() < 0.1:
                    choices = [g for g in goods if g != Goods.gov]
                    if choices:
                        agent.output = random.choice(choices)
                        logdebug(t, agent.name(), 'poor, exploring random career:', profession[agent.output])
                        agent.lastCareerSwitch = t
                        numSwitches += 1
                elif trade.mostDemand != Goods.gov and agent.output != trade.mostDemand:
                    logdebug(t, agent.name(), 'poor, switching to in-demand career:', profession[trade.mostDemand])
                    agent.output = trade.mostDemand
                    agent.lastCareerSwitch = t
                    numSwitches += 1
            
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth and agent.cash > recipes[Goods.food]['price'] * 4 and len(agents) < 512:
                agent.lastRepro = t
                new_agent = Agent(t)
                new_agent.parent = agent
                agent.descendents.append(new_agent)
                giveFood = min(2, agent.inv[Goods.food]) ##potentiall food coming from thin air - need gov support
                agent.inv[Goods.food] -= giveFood
                #find the smallest number of professions and use that one, since no one makes money
                #output = FindSmallestTrade(agents)
                empty_professions = [g for g in goods if g != Goods.gov and sum(1 for a in agents if a.output == g) == 0]
                if empty_professions:
                    output = empty_professions[0]
                    logdebug(t, "seeding extinct profession:", profession[output])
                else:
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
        
            agent.alive = False
        
        if not agent.alive:
            livingDescendents = [agent for agent in agent.descendents if agent.alive]
            logdebug(t, agent.name(), 'died, has', agent.cash, ' #descendents:', len(livingDescendents),
                  [agent.name() for agent in livingDescendents])
            numdead += 1
            
            # --- MONEY CONSERVATION FIX ---
            # 1. Handle Debt: If the agent dies, the bank must write off the principle
            total_debt = sum(loan.principle for loan in agent.loans)
            if total_debt > 0:
                trade.bank.total_liabilities -= total_debt
                # Clean up bank's loan tracking
                trade.bank.loans = [l for l in trade.bank.loans if l.agent != agent]
            
            # 2. Inherit Cash and Deposits (Whole units only)
            inheritance_cash = agent.cash
            inheritance_deposits = trade.bank.deposits.get(agent, 0)
            
            if len(livingDescendents) > 0:
                # Distribute whole units of cash
                cash_share = int(inheritance_cash // len(livingDescendents))
                cash_remainder = inheritance_cash - (cash_share * len(livingDescendents))
                
                # Distribute whole units of bank deposits
                deposit_share = int(inheritance_deposits // len(livingDescendents))
                deposit_remainder = inheritance_deposits - (deposit_share * len(livingDescendents))
                
                for descendent in livingDescendents:
                    descendent.cash += cash_share
                    trade.bank.deposits[descendent] += deposit_share
                
                # Remainders go to the government
                econsim_states.govCash += cash_remainder
                econsim_states.govCash += deposit_remainder
                if deposit_remainder > 0:
                    trade.bank.total_deposits -= deposit_remainder
                
                # 3. Inherit physical inventory (Whole units only)
                for good, amount in agent.inv.items():
                    target_heirs = [agent for agent in livingDescendents if agent.output == good]
                    if not target_heirs:
                        target_heirs = livingDescendents # Fallback to all heirs if none match profession
                    
                    unit_share = int(amount // len(target_heirs))
                    unit_remainder = amount - (unit_share * len(target_heirs))
                    
                    for descendent in target_heirs:
                        descendent.inv[good] += unit_share
                    
                    # Decimal remainders of physical goods go to government stores
                    if unit_remainder > 0:
                        econsim_states.govInv[good] += unit_remainder
            else:
                # No heirs: assets go to government
                econsim_states.govCash += inheritance_cash
                # Gov doesn't have an agent object usually, so just add to govCash
                # CRITICAL: If we move deposits to govCash, we must remove it from the bank's total
                econsim_states.govCash += inheritance_deposits
                trade.bank.total_deposits -= inheritance_deposits
            
            # Clear the dead agent's bank account
            if agent in trade.bank.deposits:
                del trade.bank.deposits[agent]
            
    if econsim_states.govCash > 0:
        logdebug(t, 'gov cash prev:', prevGovCash, 'now', econsim_states.govCash)
        starving_agents = [agent for agent in new_agents if agent.hungry_steps > 0 ]
        if len(starving_agents) > 0:
            wellfare = econsim_states.govCash / len(starving_agents)
            assert(wellfare >= 0)
            for agent in starving_agents:
                agent.cash += wellfare
                econsim_states.govCash -= wellfare


    for good in goods:
        hungry_log[good].append(sum(1 for agent in agents if agent.output == good and agent.hungry_steps > 0))
        
    dead_pop.append(numdead)
    deadstarve_pop.append(numdeadstarve)
    logdebug(t, 'num dead', numdead)
    #dead_pop.append(sum(dead_pop)-numdead)

    logdebug("consumed ", numfood, "food", numwood, "wood", numFurn, "furn")
    return new_agents
