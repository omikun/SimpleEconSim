import matplotlib.pyplot as plt
import numpy as np

#Lotka-Volterra equation based
# Simulation parameters
time_steps = 50000
dt = 0.02

# Initial populations
sheep = 40
wolves = 9

# Lists to store population over time
sheep_pop = [sheep]
wolf_pop = [wolves]

# Lotka-Volterra parameters
alpha = 0.1   # Birth rate of sheep
beta = 0.02   # Predation rate coefficient
delta = 0.01  # Growth rate of wolves per eaten sheep
gamma = 0.1   # Death rate of wolves

# Simulation loop
for _ in range(time_steps):
    ds = (alpha * sheep - beta * sheep * wolves) * dt
    dw = (delta * sheep * wolves - gamma * wolves) * dt

    sheep += ds
    wolves += dw

    sheep_pop.append(sheep)
    wolf_pop.append(wolves)

# Plotting
t = np.linspace(0, time_steps * dt, time_steps + 1)
#plt.plot(t, sheep_pop, label="Sheep")
#plt.plot(t, wolf_pop, label="Wolves")
#plt.xlabel("Time")
#plt.ylabel("Population")
#plt.title("Wolves and Sheep Population Over Time")
plt.plot(sheep_pop, wolf_pop)
plt.xlabel("Sheep Population (x)")
plt.ylabel("Wolf Population (y)")
plt.title("Phase plot")
plt.legend()
plt.grid(True)
plt.show()
