import random
import matplotlib.pyplot as plt

# Initial populations
sheep = 100
wolves = [{'hungry_steps': 0} for _ in range(20)]

# Parameters
p_hunt = 0.03
p_birth_sheep = 0.08
p_birth_wolf = 0.11
wolf_starve_limit = 5
time_steps = 240

sheep_pop = []
wolf_pop = []

for t in range(time_steps):
    # Wolves hunt
    new_wolves = []
    sheep_eaten = 0
    # Adaptive hunt probability
    p_hunt = min(1.0,  sheep / 100.0) # * sheep / len(wolves))
    #p_hunt = min(1.0,  sheep / (sheep + len(wolves)))
    p_hunt *= p_hunt
    #p_hunt *= p_hunt
    #p_hunt *= p_hunt
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
        if wolf['hungry_steps'] < wolf_starve_limit:
            new_wolves.append(wolf)

    wolves = new_wolves

    # Sheep reproduce
    new_sheep = 0
    for _ in range(sheep):
        if random.random() < p_birth_sheep:
            new_sheep += 1
    sheep += new_sheep

    # Track population
    sheep_pop.append(sheep)
    wolf_pop.append(len(wolves))
    print( t, " sheeps: ", sheep, " wolves: ", len(wolves))
    #print( t, wolves)

# Plot results
plt.plot(sheep_pop, label='Sheep', color='green')
plt.plot(wolf_pop, label='Wolves', color='red')
plt.xlabel("Time Step")
plt.ylabel("Population")
plt.title("Stochastic Wolf-Sheep Simulation")
plt.legend()
plt.grid(True)
plt.show()
