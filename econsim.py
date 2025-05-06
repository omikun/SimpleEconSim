import random
import math
import matplotlib.pyplot as plt

# Initial populations
agent_template = {'profession': 'none','hungry_steps': 0, 'food': 2, 'output': 0, 'input': 8}
num_agents = 20
agents = [agent_template for _ in range(num_agents)]
recipes = {}
recipes['food'] = {'commodity': 'food', 'production': 4, 'price': 1, 'numInput': 0}
recipes['wood'] = {'commodity': 'wood', 'production': 2, 'price': 2, 'numInput': 0}
recipes['furniture'] = {'commodity': 'furniture', 'production': 1, 'input': 'wood', 'numInput': 8, 'price': 20}

# Parameters
time_steps = 3000
p_birth = .01
starve_limit = 3

food_pop = []
wood_pop = []
carp_pop = []

#init
for a in range(num_agents):
    if a < 10:
        agents[a]['profession'] = 'food'
    if a < 18:
        agents[a]['profession'] = 'wood'
    if a < 20:
        agents[a]['profession'] = 'furniture'


#main loop
for t in range(time_steps):
    new_agents = []
    for agent in agents:
        output = agents['profession']
        recipe = recipes[output]
        #produce
        numOutput = 0
        if recipe['numInput'] == 0:
            numOutput = recipe['production'] 
        else:
            com = recipe['input']
            if agent[com] >= recipe['numInput']:
                numOutput = recipe['production'] 

        agent['output'] += numOutput

        #life cycle
        if agent['food'] > 0:
            food -= 1
            agent['hungry_steps'] = 0
            if random.random() < p_birth:
                new_wolves.append(agent_template)
                new_wolves[-1]['profession'] = 'food'
        else:
            agent['hungry_steps'] += 1
        if agent['hungry_steps'] < starve_limit:
            new_agents.append(agent)

    agents = new_agents


    # Track population
    food_pop.append(sum(agent['profession'] == 'food' for agent in agents)
    wood_pop.append(sum(agent['profession'] == 'wood' for agent in agents)
    carp_pop.append(sum(agent['profession'] == 'carp' for agent in agents)

# Plot results
figure, axis = plt.subplots(2, 1)
figure.set_figwidth(10)
figure.set_figheight(10)
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
