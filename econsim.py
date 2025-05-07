import random
import math
import matplotlib.pyplot as plt

# Initial populations
agent_template = {'profession': 'none','hungry_steps': 0, 'cash':10, 'inv': {}}
num_agents = 20
agents = [agent_template for _ in range(num_agents)]
recipes = {}
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 2, 'numInput': 0}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20}
# Parameters
time_steps = 4
p_birth = .01
starve_limit = 3

food_pop = []
wood_pop = []
carp_pop = []
foodInv = []
woodInv = []
carpInv = []

#init
for a in range(num_agents):
    agent = agents[a]

    if a < 10:
        agent['profession'] = 'food'
    if a < 18:
        agent['profession'] = 'wood'
    if a < 20:
        agent['profession'] = 'furniture'

    #init inventory
    recipe = recipes[agent['profession']]
    inputCom = recipe.get('input', 'none')
    inv = agent['inv']
    if inputCom != 'none':
        inv[inputCom] = 10
    outputCom = agent['profession']
    inv[outputCom] = 0
    inv['food'] = 2



#main loop
for t in range(time_steps):
    new_agents = []
    for agent in agents:
        output = agent['profession']
        inv = agent['inv']
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

        inv[output] += numOutput

        #trade
        #what if all trade are moneyless and communistic? take all food and redistribute
        #take all wood and redistribute?
        #take all furnitures and redistribute?


        #life cycle
        if inv['food'] > 0:
            inv['food'] -= 1
            agent['hungry_steps'] = 0
            if random.random() < p_birth:
                new_agents.append(agent_template)
                new_agents[-1]['profession'] = 'food'
        else:
            agent['hungry_steps'] += 1
        if agent['hungry_steps'] < starve_limit:
            new_agents.append(agent)

    agents = new_agents


    # Track population
    foodInv.append(sum(agent['inv'].get('food', 0) for agent in agents))
    woodInv.append(sum(agent['inv'].get('wood', 0) for agent in agents))
    carpInv.append(sum(agent['inv'].get('furniture', 0) for agent in agents))
    food_pop.append(sum(agent['profession'] == 'food' for agent in agents))
    wood_pop.append(sum(agent['profession'] == 'wood' for agent in agents))
    carp_pop.append(sum(agent['profession'] == 'furniture' for agent in agents))

# Plot results
figure, axis = plt.subplots(2, 1)
figure.set_figwidth(10)
figure.set_figheight(10)
axis[1].plot(foodInv, label='FoodInv', color='green')
axis[1].plot(woodInv, label='WoodInv', color='red')
axis[1].plot(carpInv, label='carpInv', color='blue')
axis[1].plot(food_pop, label='Food', color='green')
axis[1].plot(wood_pop, label='Wood', color='red')
axis[1].plot(carp_pop, label='carp', color='blue')
axis[1].set_xlabel("Time Step")
axis[1].set_ylabel("Population")
axis[1].set_title("Stochastic Wolf-Sheep Simulation")
axis[0].plot(wood_pop, food_pop)
axis[0].set_xlabel("wood Population (x)")
axis[0].set_ylabel("food Population (y)")
axis[0].set_title("Phase plot")
plt.legend()
plt.grid(True)
plt.show()
