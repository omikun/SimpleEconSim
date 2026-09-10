"""
alienation.py — Psychological alienation, physiological health attrition,
despair, and mass entertainment pacification for REGNUM.

Models the Marxian 4-dimensional alienation vector, cumulative bodily wear & tear,
and the cultural pacification role of mass entertainment for capital accumulation.
"""

from __future__ import annotations
from goods import Goods
from random_cache import rand


def compute_agent_alienation(agent, region, t: int) -> float:
    """Compute 4-dimensional alienation index (0.0 to 1.0) for an agent.

    Lords and capitalists who own property and command labor have low alienation.
    Wage workers stripped of commons access face maximum alienation.
    """
    if getattr(agent, 'is_lord', False) or getattr(agent, 'is_corporation', False):
        return 0.0

    employer = getattr(agent, 'employer', None)
    tenure = getattr(region, 'tenure', None)
    commons_access = getattr(tenure, 'commons_access', 1.0) if tenure else 1.0

    # 1. Product Alienation: Inability to afford commodities produced
    # If craftsman or worker produces furniture/goods they cannot buy with cash
    price = 1.0
    if hasattr(region, 'recipes') and agent.output in region.recipes:
        price = region.recipes[agent.output].get('price', 1.0)
    a_product = min(1.0, price / max(1.0, agent.cash))

    # 2. Process Alienation: Enforced shift length beyond customary 8 hours
    shift_hours = getattr(agent, 'shift_hours', 8.0)
    a_process = min(1.0, max(0.0, (shift_hours - 8.0) / 8.0))

    # 3. Nature Alienation: Dispossession from the soil and shared commons
    a_nature = max(0.0, min(1.0, 1.0 - commons_access))

    # 4. Species Alienation: Competition against the reserve army of unemployed
    # High unemployment pits workers against each other in wage deflation
    adults = [a for a in getattr(region, 'agents', [])
              if not getattr(a, 'is_corporation', False) and not getattr(a, 'is_government', False)
              and getattr(a, 'alive', True)]
    unemp_count = sum(1 for a in adults if getattr(a, 'employer', None) is None
                      and not getattr(a, 'is_trader', False) and not getattr(a, 'is_lord', False))
    a_species = min(1.0, unemp_count / max(1, len(adults)))

    if employer is not None:
        # Wage laborers experience heavy process and nature alienation
        score = 0.35 * a_process + 0.25 * a_product + 0.25 * a_nature + 0.15 * a_species
    elif commons_access > 0.5:
        # Customary serfs retain connection to nature and task-based cadence
        score = 0.10 * a_process + 0.20 * a_product + 0.10 * a_nature + 0.10 * a_species
    else:
        # Dispossessed landless unemployed: extreme despair and isolation
        score = 0.10 * a_process + 0.35 * a_product + 0.35 * a_nature + 0.20 * a_species

    return max(0.0, min(1.0, score))


def step_health_attrition(agent, region, t: int) -> float:
    """Accumulate physiological bodily wear & tear and workplace casualties.

    High shift hours, toxic conditions, and skimping on safety inflict
    permanent wear and roll for disabling factory accidents.
    """
    if getattr(agent, 'is_corporation', False) or not getattr(agent, 'alive', True):
        return 0.0

    shift_hours = getattr(agent, 'shift_hours', 8.0)
    safety_inv = getattr(agent, 'safety_investment', 0.0)
    current_attrition = getattr(agent, 'health_attrition', 0.0)
    agent.workplace_accident = False

    delta = 0.0

    # Overtime exhaustion penalty
    if shift_hours > 8.0:
        delta += 0.015 * (shift_hours - 8.0)

    # Low safety standard penalty (for employed factory/mine workers)
    if getattr(agent, 'employer', None) is not None:
        if getattr(region, 'factory_safety_act', False):
            safety_inv = max(safety_inv, 0.85)
        delta += 0.02 * max(0.0, 1.0 - min(1.0, safety_inv))

        # Roll for workplace accident (crushed fingers, mine cave-ins, lung rot)
        accident_prob = 0.015 * (shift_hours / 8.0) * max(0.1, 1.0 - min(1.0, safety_inv))
        if rand.random() < accident_prob:
            agent.workplace_accident = True
            delta += 0.20

    # Malnutrition / hunger penalty
    if getattr(agent, 'hungry_steps', 0) > 0:
        delta += 0.04 * agent.hungry_steps

    # P3: Depleted food nutritional density penalty (micronutrient deficiency)
    nutr = getattr(region, 'nutrition_density', 1.0)
    if nutr < 0.85:
        delta += 0.025 * (1.0 - nutr)

    # P3: Toxic environmental exposure (atmospheric smog, contaminated water, pesticide spray)
    p_air = getattr(region, 'pollution_air', 0.0)
    if p_air > 15.0:
        delta += 0.0015 * (p_air - 15.0)

    p_water = getattr(region, 'pollution_water', 0.0)
    if p_water > 20.0:
        delta += 0.0020 * (p_water - 20.0)

    use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)
    nation = getattr(region, 'owner_nation', None)
    has_clean_pest = 'biological_pest_control' in getattr(nation, 'unlocked_techs', set()) if nation else False
    if use_pest and not has_clean_pest and getattr(agent, 'output', None) == Goods.food:
        delta += 0.035  # Chemical pesticide handling wear on farmworkers

    # Rest and biological recovery on customary hours with food and clean environment
    if shift_hours <= 8.0 and getattr(agent, 'hungry_steps', 0) == 0 and nutr >= 0.85 and p_air <= 15.0 and p_water <= 20.0:
        delta -= 0.01

    new_attrition = max(0.0, min(2.5, current_attrition + delta))
    agent.health_attrition = new_attrition
    return new_attrition


def process_despair_spending(agent, region, t: int):
    """Workers suffering acute despair spend discretionary cash on escapist vices.

    Money moves from worker to local merchant/artisan (conserved).
    """
    if not getattr(agent, 'alive', True) or getattr(agent, 'is_corporation', False):
        return

    alienation = getattr(agent, 'alienation', 0.0)
    hunger = 1.0 if getattr(agent, 'hungry_steps', 0) > 0 else 0.0
    despair = max(0.0, min(1.0, alienation * 0.6 + hunger * 0.4))
    agent.despair = despair

    # If in acute despair with spare pennies, buy cheap escapism (gin, lotteries, opium)
    if despair > 0.45 and agent.cash >= 2.0:
        spend = min(1.5, agent.cash - 1.0)
        if spend > 0:
            agent.cash -= spend
            # Find a local non-corp merchant or artisan (tavern keeper / apothecary)
            recipients = [a for a in getattr(region, 'agents', [])
                          if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                          and getattr(a, 'employer', None) is None
                          and (getattr(a, 'is_trader', False) or getattr(a, 'output', None) == Goods.furniture)
                          and a != agent]
            if recipients:
                target = recipients[rand.randint(0, len(recipients) - 1)]
                target.cash += spend
            elif getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                region.gov.agent.cash += spend
            else:
                agent.cash += spend  # refund if nowhere to transfer


def update_class_consciousness(agent, region, entertainment_level: float, t: int) -> float:
    """Update development of political class consciousness among living workers.

    Grows through factory concentration, eviction memory, and workplace casualties.
    Critically stifled and atomized by mass entertainment.
    """
    if getattr(agent, 'is_lord', False) or getattr(agent, 'is_corporation', False):
        return 0.0

    current_c = getattr(agent, 'class_consciousness', 0.0)
    growth = 0.0

    # 1. Workplace solidarity from concentrated factory employment
    employer = getattr(agent, 'employer', None)
    if employer is not None and len(getattr(employer, 'employees', [])) >= 4:
        growth += 0.015

    # 2. Grievance memories: evictions and wage cuts
    if hasattr(agent, 'mem_avg') and agent.mem_avg('mem_eviction', 0.0) > 0.1:
        growth += 0.025

    # 3. Traumatic workplace casualties witnessed or suffered
    if getattr(agent, 'workplace_accident', False):
        growth += 0.05

    # 4. Stifling effect of Mass Entertainment / Spectacle
    # User requirement: mass entertainment isolates people, stifles rebellion energy
    # and reduces organizing capacity (good for capitalists).
    if entertainment_level > 0.0:
        damping = min(0.85, entertainment_level * 0.85)
        growth *= (1.0 - damping)
        # Sustained mass distraction actively erodes existing political consciousness
        current_c = max(0.0, current_c - 0.01 * entertainment_level)

    new_c = max(0.0, min(1.0, current_c + growth))
    agent.class_consciousness = new_c
    return new_c


def apply_mass_entertainment_pacifier(region, t: int):
    """Mass entertainment directly drains protest energy and pacifies organizing.

    Also collects entertainment spending from workers, recycling wages to capital.
    """
    ent_level = getattr(region, 'entertainment_level', 0.0)
    if ent_level <= 0.0:
        return

    # Drain protest energy directly
    if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
        drain = min(region.protest_energy_log[-1], ent_level * 1.5)
        region.protest_energy_log[-1] = max(0.0, region.protest_energy_log[-1] - drain)

    # Collect ticket / spectacle fees from workers who attended entertainment
    # (conserved: worker cash -> firm owners or gov treasury)
    for a in getattr(region, 'agents', [])[:20]:
        if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and a.cash >= 3.0:
            fee = min(0.50, a.cash - 2.0)
            if fee > 0:
                a.cash -= fee
                # Transfer fee to entertainment venue owner or gov
                if getattr(region, 'gov', None) and getattr(region.gov, 'agent', None):
                    region.gov.agent.cash += fee
                else:
                    a.cash += fee


def step_tile_alienation(region, t: int):
    """Step psychology, health attrition, and mass entertainment across a tile."""
    agents = [a for a in getattr(region, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)]
    if not agents:
        region.avg_alienation_log.append(0.0)
        region.avg_health_attrition_log.append(0.0)
        region.avg_consciousness_log.append(0.0)
        region.workplace_accidents_log.append(0)
        region.entertainment_log.append(getattr(region, 'entertainment_level', 0.0))
        return

    ent_level = getattr(region, 'entertainment_level', 0.0)
    apply_mass_entertainment_pacifier(region, t)

    total_alienation = 0.0
    total_attrition = 0.0
    total_consciousness = 0.0
    total_accidents = 0

    for a in agents:
        alien = compute_agent_alienation(a, region, t)
        a.alienation = alien
        total_alienation += alien

        attr = step_health_attrition(a, region, t)
        total_attrition += attr
        if getattr(a, 'workplace_accident', False):
            total_accidents += 1

        process_despair_spending(a, region, t)
        c = update_class_consciousness(a, region, ent_level, t)
        total_consciousness += c

    n = len(agents)
    region.avg_alienation_log.append(total_alienation / n)
    region.avg_health_attrition_log.append(total_attrition / n)
    region.avg_consciousness_log.append(total_consciousness / n)
    region.workplace_accidents_log.append(total_accidents)
    region.entertainment_log.append(ent_level)
