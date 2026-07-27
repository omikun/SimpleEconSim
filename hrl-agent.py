import numpy as np
import random
import matplotlib.pyplot as plt

# Simple environment with two contexts:
# threat = 0 (peaceful) or 1 (hostile)
# Each action (expand or defend) gives a reward depending on context
class CivEnvironment:
    def __init__(self):
        self.threat = 0  # start peaceful
    
    def step(self, action):
        # 0 = expand, 1 = defend
        if self.threat == 0:
            reward = 1.0 if action == 0 else 0.3  # expand better in peace
        else:
            reward = 1.0 if action == 1 else 0.2  # defend better in war
        
        # Threat level randomly changes
        if random.random() < 0.1:
            self.threat = 1 - self.threat
        return self.threat, reward


# Hierarchical RL agent with 2 sub-policies (expand / defend)
class HRLAgent:
    def __init__(self, n_states=2, n_policies=2, lr=0.1, gamma=0.9, temp=0.5):
        self.Q = np.zeros((n_states, n_policies))  # Q[state, policy]
        self.lr = lr
        self.gamma = gamma
        self.temp = temp
    
    def choose_policy(self, state):
        logits = self.Q[state]
        probs = np.exp(logits / self.temp) / np.sum(np.exp(logits / self.temp))
        policy = np.random.choice(len(probs), p=probs)
        return policy, probs
    
    def update(self, state, policy, reward, next_state):
        best_next = np.max(self.Q[next_state])
        td_target = reward + self.gamma * best_next
        self.Q[state, policy] += self.lr * (td_target - self.Q[state, policy])


# --- Training loop ---
env = CivEnvironment()
agent = HRLAgent()

n_episodes = 500
rewards = []
policy_trace = []

state = env.threat

for _ in range(n_episodes):
    policy, probs = agent.choose_policy(state)
    next_state, reward = env.step(policy)
    
    agent.update(state, policy, reward, next_state)
    
    rewards.append(reward)
    policy_trace.append(policy)
    state = next_state

# --- Plot results ---
plt.figure(figsize=(10,4))
plt.subplot(1,2,1)
plt.plot(rewards)
plt.title("Reward over time")
plt.xlabel("Step")
plt.ylabel("Reward")

plt.subplot(1,2,2)
plt.plot(policy_trace, '.', alpha=0.5)
plt.title("Policy chosen (0=Expand, 1=Defend)")
plt.xlabel("Step")
plt.ylabel("Policy")

plt.tight_layout()
plt.show()

print("Learned Q-values:")
print(agent.Q)
