# Rebellion Mechanics: Charismatic Agitation, Fermentation, and Martyrdom

## 1. Executive Summary & Historical Grounding

Rebellions and agrarian insurrections do not arise spontaneously out of undifferentiated misery. Instead, historical resistance emerges through an interplay between **material immiseration** (food starvation, land enclosure, wage suppression, debt peonage) and **coordination structures** that solve the classical *Collective Action Problem* (Olson).

### The Historical Archetypes
1. **The Charismatic Catalyst**:
   - Without leadership, individual peasants or workers face catastrophic asymmetry: participating in an uprising carries the penalty of execution, imprisonment, or eviction, while the benefits (open commons, lower taxes) are shared collectively.
   - A charismatic agitator (e.g. Wat Tyler & Priest John Ball in England 1381, Thomas Müntzer in Germany 1525, Robert Kett in Norfolk 1549, or Ahmed Urabi in Egypt 1882) acts as a coordination focal point. Through speeches, manifestos, moral framing, and personal magnetism, they drastically reduce coordination costs and lower individual risk thresholds.

2. **The Fermentation Phase**:
   - In the early stages, rebellions brew below the threshold of open military confrontation. Agitators organize secret nighttime assemblies, distribute pamphlets, and form clandestine brotherhoods.
   - Growth follows a diffusion process: broadcast agitation from the leader converts early adopters, while word-of-mouth peer-to-peer contagion spreads sympathy across working-class households.
   - Given sufficient time without intervention, deteriorating material conditions inevitably push the mobilized network toward critical mass.

3. **The Assassination Dilemma (Decapitation vs. Martyrdom)**:
   - When the state attempts targeted liquidation or execution of a rebel leader, history demonstrates a profound bifurcation governed by the movement's level of institutionalization:
     - **Decapitation (Immature / Fragile Stage)**: When eliminated early, before deep network ties and shared myths take root, the movement loses its sole coordination node. Fear, confusion, and state terror scatter the followers back into quiet compliance.
     - **Martyrdom (Mature / Institutionalized Stage)**: Once the movement achieves critical density, assassinating the leader backfires catastrophically. The fallible human is transmuted into an inviolable martyr (e.g. Jan Hus at Constance in 1415 sparking the Hussite Wars; the 1916 Easter Rising firing squads turning Irish opinion into full rebellion). Risk aversion collapses, uncommitted fence-sitters surge into the streets in moral outrage, and open insurrection explodes immediately.

---

## 2. Mathematical Formalization

The accumulation of rebel strength is modeled as a non-linear contagion and threshold system.

### Variables & Parameters
- $N$: Total working-class population eligible for mobilization in the region.
- $K \le N$: Carrying capacity of sympathizers (dispossessed, serfs, cottars, tenants, underpaid proletarians).
- $F(t) \in [0, K]$: Number of actively mobilized followers at turn $t$.
- $C_L \in [0, 1]$: Charisma and agitation power of leader $L$.
- $G(t) \in [0, 1]$: Local grievance intensity (caloric deficit, lost commons, tax burden, police brutality).
- $P$: Local state coercive garrison / constabulary strength.
- $k_{\text{ferment}}$: Global fermentation pace multiplier (tuning knob).
- $\alpha$: Broadcast recruitment coefficient (leader speech/manifesto).
- $\beta$: Peer-to-peer social contagion coefficient.
- $\delta$: Coercive deterrence drag coefficient.

### Differential Growth Equation

$$\frac{dF}{dt} = k_{\text{ferment}} \cdot \left[ \underbrace{\alpha \cdot C_L \cdot G(t) \cdot (K - F)}_{\text{Broadcast Speech Recruitment}} + \underbrace{\beta \cdot \left(\frac{F}{K}\right) \cdot G(t) \cdot (K - F)}_{\text{Peer-to-Peer Contagion}} - \underbrace{\delta \cdot P \cdot \left(\frac{F}{K}\right)}_{\text{Police / Garrison Intimidation}} \right]$$

### Critical Transition Thresholds
1. **Decapitation vs. Martyrdom Boundary ($F_{\text{crit}}$)**:
   $$F_{\text{crit}} = \max\left(2, \; \lfloor \rho_{\text{crit}} \cdot K \rfloor\right), \quad \rho_{\text{crit}} \approx 0.35$$
2. **Open Eruption Threshold ($T_{\text{rebel}}$)**:
   $$T_{\text{rebel}} = \lfloor \rho_{\text{erupt}} \cdot K \rfloor, \quad \rho_{\text{erupt}} \approx 0.70$$

When $F(t) \ge T_{\text{rebel}}$, the movement transitions from covert fermentation into overt confrontation (`marching` $\to$ `protest` $\to$ `leveling` / `barricades`).

---

## 3. Variable-Time Assassination Plots

State liquidation of rebel leaders is not an instantaneous single-click cheat. It is an operational covert action subject to delay, intelligence friction, and leak hazards:

1. **Plot Inception & Cost**:
   - The state issues a "Shadow Warrant" on the agitator.
   - Cost: Conserved funds (e.g. \$75 cash) transferred from the municipal or national treasury directly to operative agents/constables.
2. **Variable Striking Window ($T_{\text{plot}}$)**:
   $$T_{\text{plot}} = T_{\text{base}} + \Delta t(\text{leader evasion, local terrain, police presence}) \in [2, 5] \text{ turns}$$
3. **Turn-by-Turn Operational Risk**:
   - Each turn the plot is active, there is an operational leak risk ($p_{\text{leak}} \approx 12\%$).
   - If compromised: The plot is blown, the leader escapes, their charisma surges (+0.15), and outrage rapidly recruits fence-sitters.
4. **Resolution on Strike ($t = t_{\text{strike}}$)**:
   - Leader is killed (`alive = False`), personal wealth is conserved (escheated to charity or heirs).
   - If $F(t_{\text{strike}}) < F_{\text{crit}}$: **Decapitation**. Followers disband, movement is neutralized, and a multi-turn terror cooldown prevents reorganization.
   - If $F(t_{\text{strike}}) \ge F_{\text{crit}}$: **Martyrdom Cascade**. Leader becomes a martyr, `martyrdom_multiplier` increases sharply, uncommitted workers surge into the movement, and the tile instantly enters an armed standoff.

---

## 4. Tuning Fermentation Duration

Game designers and scenario builders can tune the fermentation duration using the `RebellionConfig` structure:

| Parameter | Default | Effect |
|---|---|---|
| `fermentation_pace` | `1.0` | Global speed scaler. `0.2` = multi-decade slow burn; `2.5` = immediate powder keg. |
| `alpha_broadcast` | `0.08` | Agitator oratorical conversion rate. |
| `beta_contagion` | `0.12` | Word-of-mouth radicalization speed. |
| `f_crit_ratio` | `0.35` | The tipping point where assassination flips from Decapitation to Martyrdom. |
| `eruption_ratio` | `0.70` | Sympathizer mobilization required to trigger open street actions. |

---

## 5. UI & Player Experience: The Fog of War

To ensure strategic tension, the player UI obscures exact underlying variables. The player must make high-stakes decisions under genuine uncertainty:

- **Public Atmosphere**: Qualitative signals such as *"Discontent in taverns"*, *"Secret oaths sworn at midnight"*, or *"Agitator venerated as a holy deliverer"*.
- **Estimated Window**: Assassination indicates an estimated completion window (e.g., *"2 to 5 turns"*), during which the movement continues to grow. Ordering a strike close to the suspected tipping point creates gripping suspense over whether the assassin will strike before the movement crosses into martyrdom territory.

---

## 6. Developer & Balancing Debug Monitor

For testing, automated verification, and balance telemetry, the simulation provides an un-obscured debug inspect function `get_rebellion_debug_info(tile)` detailing:
- Living status, ID, Charisma, and Ambition of the active leader.
- Current followers $F$, total sympathizers $K$, and net recruitment velocity $dF/dt$.
- The exact $F_{\text{crit}}$ and $T_{\text{rebel}}$ thresholds.
- Current active assassination plot status, turns remaining, and projected strike outcome.
- Accumulated martyrdom multiplier and terror cooldown.
