import random
import math
import matplotlib.pyplot as plt

# Initial populations
sheep = 100
wolves = [{'hungry_steps': 0} for _ in range(20)]

# Parameters
p_hunt = 0.03
p_birth_sheep = 0.275
p_birth_wolf = 0.11
wolf_starve_limit = 5
time_steps = 3000

sheep_pop = []
wolf_pop = []

for t in range(time_steps):
    if sheep > 10000:
        break
    # Wolves hunt
    new_wolves = []
    sheep_eaten = 0
    # Adaptive hunt probability
    #p_hunt = min(1.0,  sheep / 100.0) # * sheep / len(wolves))
    p_hunt = min(1.0,  sheep / (sheep + len(wolves) + 1))
    if sheep < 20:
        p_hunt *= sheep / 20;
    p_hunt **= 2.0
    num_wolves_hungry = 0
    for wolf in wolves:
        if sheep > 0 and random.random() < p_hunt:
            sheep -= 1
            sheep_eaten += 1
            wolf['hungry_steps'] = 0
            # Wolf reproduces
            if random.random() < p_birth_wolf:
                new_wolves.append({'hungry_steps': 0})
        else:
            wolf['hungry_steps'] += 1
            num_wolves_hungry += 1
        if wolf['hungry_steps'] < wolf_starve_limit:
            new_wolves.append(wolf)

    wolves = new_wolves

    # Sheep reproduce
    new_sheep = 0
    for _ in range(sheep):
        if random.random() < p_birth_sheep * min(1.0, 50/sheep):
            new_sheep += 1
    sheep += new_sheep

    # Track population
    sheep_pop.append(sheep)
    wolf_pop.append(len(wolves))
    print( t, " sheeps: ", sheep, " wolves: ", len(wolves), " num hungry wolves: ", num_wolves_hungry, " phunt: ", p_hunt)
    #print( t, wolves)

# Plot results
figure, axis = plt.subplots(2, 1)
figure.set_figwidth(10)
figure.set_figheight(10)
axis[1].plot(sheep_pop, label='Sheep', color='green')
axis[1].plot(wolf_pop, label='Wolves', color='red')
axis[1].set_xlabel("Time Step")
axis[1].set_ylabel("Population")
axis[1].set_title("Stochastic Wolf-Sheep Simulation")
axis[0].plot(sheep_pop, wolf_pop)
axis[0].set_xlabel("Sheep Population (x)")
axis[0].set_ylabel("Wolf Population (y)")
axis[0].set_title("Phase plot")
plt.legend()
plt.grid(True)
plt.show()
