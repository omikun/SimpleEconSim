import bisect
import random
import math

import econsim_states
from econsim_states import *
import econsim_trade_money as trade
from econsim import GetInputCom, GetOutputCom, Agent, InitAgent
from goods import Goods
from logger import logdebug, loginfo


def ApplyEconomicPressure(t, agents):
    """Gradually increase distress in the population to create labor supply.
    Non-employees face random economic shocks and progressive poverty stress."""
    for agent in agents:
        if agent.employer is None and not agent.is_corp:
            # Random economic shocks: bad harvest, unexpected expense, etc.
            if random.random() < 0.02:  # 2% chance per turn
                loss = max(1, int(agent.cash * 0.1))
                agent.cash = max(0, agent.cash - loss)
                loginfo(t, agent.name(), 'hit by economic shock, lost', loss, 'cash')

            # Progressive distress: low cash makes agents hungry from poverty stress
            if agent.cash < 30 and agent.hungry_steps == 0:
                if random.random() < 0.05:  # 5% chance to get hungry from poverty stress
                    agent.hungry_steps += 1
                    loginfo(t, agent.name(), 'became hungry from economic stress')


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
    
    # GOVERNMENT FOOD AID (FIX: no one starves > 3 days; newborns get 1 food for 10 turns)
    food_price = recipes[Goods.food]['price']
    for agent in agents:
        if agent.is_corp:
            continue
        needs_food = 0
        # Newborns (age <= 10): 1 free food per turn
        if agent.age(t) <= 10:
            needs_food = 1
        # Starving > 3 days: emergency food (enough to eat 4 this turn)
        if agent.hungry_steps > 3:
            current_food = agent.inv.get(Goods.food, 0)
            needed_for_meal = max(0, 4 - current_food)
            # Don't double-count: newborns already get 1
            if agent.age(t) <= 10:
                needed_for_meal = max(0, needed_for_meal - 1)
            needs_food = max(needs_food, needed_for_meal)
        
        if needs_food > 0:
            cost = needs_food * food_price
            # Government borrows from bank if it doesn't have enough cash
            if econsim_states.govCash < cost:
                shortfall = cost - econsim_states.govCash
                trade.bank.total_deposits += shortfall  # Bank creates money
                econsim_states.govDebt += shortfall
                econsim_states.govCash += shortfall
                loginfo(t, "GOVERNMENT BORROWED $", round(shortfall, 2),
                        "from bank for food aid. Total govDebt: $", round(econsim_states.govDebt, 2))
            # Give food directly
            agent.inv[Goods.food] += needs_food
            econsim_states.govCash -= cost
            if agent.hungry_steps > 3:
                loginfo(t, agent.name(), f"received emergency food aid ({needs_food} food)")
            else:
                loginfo(t, agent.name(), f"received newborn food aid ({needs_food} food)")
    numSwitches = 0
    random.shuffle(agents)

    # Hoist bottleneck computation outside agent loop (Fix E)
    choices_list = [g for g in goods if g != Goods.gov]
    bottleneck_sector = Goods.none
    bottleneck_ratio = 0
    bottleneck_weights = [1] * len(choices_list)
    for candidate_good in goods:
        if candidate_good == Goods.gov:
            continue
        recipe = recipes.get(candidate_good)
        if recipe and recipe.get('numInput', 0) > 0:
            input_good = recipe['input']
            num_consumers = sum(1 for a in agents if GetInputCom(a) == input_good and not a.is_corp and a.employer is None)
            num_producers = sum(1 for a in agents if a.output == input_good and not a.is_corp and a.employer is None)
            pressure = (num_consumers * recipe['numInput']) / max(1, num_producers)
            if pressure > bottleneck_ratio and pressure > 2.0:
                bottleneck_ratio = pressure
                bottleneck_sector = input_good
    if bottleneck_sector != Goods.none:
        bottleneck_weights = [3 if g == bottleneck_sector else 1 for g in choices_list]

    for agent in agents:
        # Corps skip life-cycle entirely — preserve in population but skip eating/aging/repro
        if agent.is_corp:
            new_agents.append(agent)
            continue

        # Generalized luxury consumption for wealthy non-corp agents (Fix A)
        total_liquid = agent.cash + trade.bank.deposits.get(agent, 0)
        food_price = recipes.get(Goods.food, {}).get('price', 1)
        if total_liquid > food_price * 40:
            for luxury_good in goods:
                if luxury_good in (Goods.food, Goods.gov):
                    continue
                good_price = recipes.get(luxury_good, {}).get('price', 1)
                if agent.inv.get(luxury_good, 0) > 0 and GetOutputCom(agent) != luxury_good:
                    consumption_chance = 0.15 * (1.0 / max(1, good_price))
                    if random.random() < min(0.3, consumption_chance):
                        agent.inv[luxury_good] -= 1
                        if luxury_good == Goods.furn:
                            numFurn += 1
                        elif luxury_good == Goods.wood:
                            numwood += 1
                        loginfo(t, agent.name(), 'wealthy, consumed', profession[luxury_good])
        
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
        # Employees do NOT switch careers independently, as their profession is locked to their employer.
        is_employee = getattr(agent, 'employer', None) is not None
        if not is_employee and numSwitches < max_career_switches:
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
                # Fix E: Use hoisted bottleneck detection
                if random.random() < 0.1:
                    if choices_list:
                        agent.output = random.choices(choices_list, weights=bottleneck_weights, k=1)[0]
                        logdebug(t, agent.name(), 'poor, exploring random career:', profession[agent.output])
                        agent.lastCareerSwitch = t
                        numSwitches += 1
                elif trade.mostDemand != Goods.gov and agent.output != trade.mostDemand:
                    # Fix E: If mostDemand depends on a bottlenecked input, switch to input instead
                    target = trade.mostDemand
                    target_recipe = recipes.get(target)
                    if target_recipe and target_recipe.get('numInput', 0) > 0:
                        input_good = target_recipe['input']
                        num_consumers = sum(1 for a in agents if GetInputCom(a) == input_good and not a.is_corp and a.employer is None)
                        num_producers = sum(1 for a in agents if a.output == input_good and not a.is_corp and a.employer is None)
                        pressure = (num_consumers * target_recipe['numInput']) / max(1, num_producers)
                        if pressure > 2.0:
                            target = input_good
                            logdebug(t, agent.name(), 'redirected to bottleneck input:', profession[target])
                    agent.output = target
                    agent.lastCareerSwitch = t
                    numSwitches += 1
            
        # Active job-seeking: if independent and struggling, try to get hired
        if not is_employee and not getattr(agent, 'is_corp', False) and agent.company_owned is None:
            if agent.cash < 5 or agent.hungry_steps > 0:
                # Find a company with headroom within their own profession
                employers = [a for a in agents if a.is_corp 
                             and len(a.employees) < a.max_employees 
                             and a.output == agent.output
                             and a.cash > (len(a.employees) * a.wage + a.wage) * 2]
                if employers:
                    employer = random.choice(employers)
                    agent.employer = employer
                    agent.hiredAt = t
                    employer.employees.append(agent)
                    loginfo(t, agent.name(), 'sought employment at', employer.name(), 'wage', employer.wage)
                    
        if agent.hungry_steps == 0:
            if agent.lastRepro + birthGap < t and random.random() < p_birth and agent.cash > 20 and agent.inv.get(Goods.food, 0) >= 2:
                agent.lastRepro = t
                new_agent = Agent(t)
                new_agent.parent = agent
                agent.descendents.append(new_agent)
                giveFood = min(1, agent.inv[Goods.food])  # Lower birth seeds: only 1 food
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
                cash = min(1, agent.cash)  # Lower birth seeds: only 1 cash
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
                loginfo(t, agent.name(), 'has died due to age')
        else:
            logdebug(t, agent.name(), 'has starved to death')
            numdead += 1
            numdeadstarve += 1
            agent.alive = False
        
            agent.alive = False
        
        if not agent.alive:
            # Clean up corporation/employee links
            if getattr(agent, 'employer', None) is not None:
                # Remove from employer's employee list
                employer = agent.employer
                if hasattr(employer, 'employees') and agent in employer.employees:
                    employer.employees.remove(agent)
                agent.employer = None
            if getattr(agent, 'is_corp', False) and hasattr(agent, 'employees'):
                # Dissolve firm: set all employees' employer to None
                for emp in agent.employees:
                    emp.employer = None
                agent.employees = []
                agent.is_corp = False
                # Clear owner's company_owned reference
                if agent.owner is not None:
                    agent.owner.company_owned = None
                    agent.owner = None

            # Handle company ownership when founder dies
            if getattr(agent, 'company_owned', None) is not None:
                company = agent.company_owned
                living_descendents = [d for d in agent.descendents if d.alive]
                if len(living_descendents) > 0:
                    # Pass company to wealthiest descendant
                    heir = max(living_descendents, key=lambda d: d.cash)
                    company.owner = heir
                    heir.company_owned = company
                    logdebug(t, agent.name(), 'company', company.name(), 'inherited by', heir.name())
                else:
                    # No living descendants: pass company to longest-tenured employee, or dissolve if none
                    if company.alive and company.is_corp and len(company.employees) > 0:
                        oldest_emp = min(company.employees, key=lambda e: e.hiredAt)
                        company.owner = oldest_emp
                        oldest_emp.company_owned = company
                        logdebug(t, agent.name(), 'company', company.name(), 'inherited by oldest employee', oldest_emp.name())
                    elif company.alive and company.is_corp:
                        logdebug(t, agent.name(), 'company', company.name(), 'dissolved (no heirs, no employees)')
                        for emp in company.employees:
                            emp.employer = None
                        company.employees = []
                        company.is_corp = False
                        company.owner = None
                agent.company_owned = None

            livingDescendents = [agent for agent in agent.descendents if agent.alive]
            logdebug(t, agent.name(), 'died, has', agent.cash, ' #descendents:', len(livingDescendents),
                  [agent.name() for agent in livingDescendents])
            numdead += 1
            
            # --- MONEY CONSERVATION FIX ---
            # 1. Repay debt using agent's cash and deposits
            total_wealth = agent.cash + trade.bank.deposits.get(agent, 0)
            remaining_wealth = total_wealth
            total_paid = 0
            
            for loan in agent.loans:
                amount_to_clear = (loan.principle - loan.principle_paid) + loan.getInterest()
                payment = min(remaining_wealth, amount_to_clear)
                if payment > 0:
                    loan.pay(payment)
                    total_paid += payment
                    remaining_wealth -= payment
                    
            if total_paid > 0:
                if total_paid > agent.cash:
                    needed_from_bank = total_paid - agent.cash
                    trade.bank.Withdraw(agent, needed_from_bank)
                agent.cash -= total_paid
                
            agent.loans = [l for l in agent.loans if not l.isPaid()]
            
            # 2. Distribute remaining debt to heirs or bank takes the loss
            remaining_principle = sum(l.principle - l.principle_paid for l in agent.loans)
            if remaining_principle > 0:
                trade.bank.total_liabilities -= remaining_principle
                trade.bank.loans = [l for l in trade.bank.loans if l not in agent.loans]
                
                if len(livingDescendents) > 0:
                    principle_share = remaining_principle / len(livingDescendents)
                    for descendent in livingDescendents:
                        new_loan = trade.Loan(trade.bank, descendent, principle_share, trade.bank.interest_rate)
                        descendent.loans.append(new_loan)
                        trade.bank.loans.append(new_loan)
                        trade.bank.total_liabilities += principle_share
                else:
                    # No heirs: bank absorbs the loss
                    if remaining_principle > trade.bank.total_deposits:
                        trade.bank.RequestBailout(t, remaining_principle)
                    trade.bank.total_deposits -= remaining_principle
            
            # 3. Inherit Cash and Deposits (Whole units only)
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
                for good, amount in agent.inv.items():
                    econsim_states.govInv[good] += amount
            
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