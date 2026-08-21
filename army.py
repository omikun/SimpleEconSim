"""
army.py — Military units, garrisons, recruitment, and battle resolution for REGNUM (M4.5 / M5).

Provides:
- MilitaryUnit: represents a deployed army or garrison stationed on a tile.
- Strength formula: strength = soldiers * morale * equipment_quality.
- Recruitment from unemployed / poor agents, which drains protest energy.
- Conserved upkeep: wages paid from government treasury to soldiers (or regional economy),
  and food rations consumed from government food_inventory.
- Battle resolution: combat casualties, morale shifts, and tile contest resolution with 0 LEAK.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from goods import Goods


@dataclass
class MilitaryUnit:
    """A military unit or garrison stationed on a Region tile."""
    unit_id: str
    nation_name: str
    region_name: str
    soldiers: int
    morale: float = 1.0             # 0.0 to 1.0 (drops on unpaid wages / heavy losses)
    equipment_quality: float = 1.0  # 0.5 to 2.0 (boosted by weapons / armor)
    wage_per_soldier: float = 1.0   # cash paid per soldier per turn
    food_per_soldier: float = 0.1   # food units consumed per soldier per turn
    veteran_xp: float = 0.0         # combat experience (0.0 to 1.0)
    is_garrison: bool = False       # True if stationary defensive garrison

    @property
    def strength(self) -> float:
        """Effective combat strength: soldiers * morale * equipment_quality * (1 + 0.5 * xp)."""
        if self.soldiers <= 0:
            return 0.0
        return self.soldiers * max(0.1, self.morale) * max(0.5, self.equipment_quality) * (1.0 + 0.5 * self.veteran_xp)

    def pay_and_feed(self, gov, bank, t: int = 0) -> tuple[float, int, bool]:
        """Upkeep step: withdraws wages and consumes food rations.

        Returns (wages_paid, food_consumed, fully_supplied).
        Conserved: cash drawn from gov.agent.cash (or bank deposit), food from gov.food_inventory.
        """
        if self.soldiers <= 0:
            return 0.0, 0, True

        total_wage = self.soldiers * self.wage_per_soldier
        wages_paid = 0.0

        # Procure wage cash
        if gov.agent.cash >= total_wage:
            gov.agent.cash -= total_wage
            wages_paid = total_wage
        else:
            # Try withdrawing from bank
            if bank is not None:
                needed = total_wage - gov.agent.cash
                bank.Withdraw(gov.agent, min(needed, bank.deposits.get(gov.agent, 0.0)))
            
            payout = min(gov.agent.cash, total_wage)
            gov.agent.cash -= payout
            wages_paid = payout

        # Food ration consumption
        needed_food = int(self.soldiers * self.food_per_soldier)
        available_food = getattr(gov, 'food_inventory', 0)
        food_consumed = min(needed_food, available_food)
        gov.food_inventory = max(0, available_food - food_consumed)

        # Morale updates based on fulfillment
        wage_ratio = wages_paid / max(0.01, total_wage)
        food_ratio = food_consumed / max(1, needed_food) if needed_food > 0 else 1.0

        if wage_ratio >= 0.99 and food_ratio >= 0.99:
            self.morale = min(1.0, self.morale + 0.05)
            fully_supplied = True
        else:
            # Deficit penalizes morale
            penalty = (1.0 - wage_ratio) * 0.2 + (1.0 - food_ratio) * 0.2
            self.morale = max(0.1, self.morale - penalty)
            fully_supplied = False

        # Desertion risk if morale drops below 0.3
        deserters = 0
        if self.morale < 0.3:
            deserters = int(self.soldiers * 0.1)
            self.soldiers = max(0, self.soldiers - deserters)

        return wages_paid, food_consumed, fully_supplied, deserters


def recruit_unit(nation, region, soldier_count: int, wage: float = 1.0,
                 equipment: float = 1.0, t: int = 0) -> MilitaryUnit | None:
    """Recruit a new MilitaryUnit from the local region population.

    - Recruiting absorbs unemployed / low-wealth agents and lowers protest energy.
    - Upkeep is assigned to nation / region government.
    - Returns the created MilitaryUnit or None if population is insufficient.
    """
    if not hasattr(region, 'military_units'):
        region.military_units = []
    if not hasattr(nation, 'military_units'):
        nation.military_units = []

    # Check available eligible population (non-corporations, alive)
    eligible = [a for a in getattr(region, 'agents', [])
                if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                and not getattr(a, 'is_government', False)]
    
    if len(eligible) < soldier_count:
        soldier_count = max(5, len(eligible) // 4)
    if soldier_count <= 0:
        return None

    unit_id = f"unit_{nation.name[:3]}_{region.name}_{str(uuid.uuid4())[:6]}"
    unit = MilitaryUnit(
        unit_id=unit_id,
        nation_name=nation.name,
        region_name=region.name,
        soldiers=soldier_count,
        morale=1.0,
        equipment_quality=equipment,
        wage_per_soldier=wage
    )

    region.military_units.append(unit)
    nation.military_units.append(unit)

    # Recruiting drains protest energy in the region (strategic unrest dampening)
    if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
        drain = min(region.protest_energy_log[-1], soldier_count * 0.05)
        region.protest_energy_log[-1] = max(0.0, region.protest_energy_log[-1] - drain)

    return unit


def step_armies(tiles: list, nations: list, t: int = 0) -> list[dict]:
    """Process per-turn upkeep, supply, desertion reabsorption, and cleanup for military units."""
    import random
    from agent import Agent, seed_traits, initialize_agent
    import wilderness as wd

    events = []
    for n in nations:
        gov = n.government
        units = getattr(n, 'military_units', [])
        for unit in list(units):
            if unit.soldiers <= 0:
                units.remove(unit)
                # Remove from region list as well
                for r in tiles:
                    if r.name == unit.region_name and hasattr(r, 'military_units') and unit in r.military_units:
                        r.military_units.remove(unit)
                continue

            # Find matching region
            matching_regions = [r for r in tiles if r.name == unit.region_name]
            region = matching_regions[0] if matching_regions else None
            bank = getattr(region, 'bank', None) if region else getattr(gov, '_bank_ref', None)

            wages, food, supplied, deserters = unit.pay_and_feed(gov, bank, t)
            if not supplied:
                events.append({
                    't': t,
                    'unit_id': unit.unit_id,
                    'nation': n.name,
                    'region': unit.region_name,
                    'event': 'ARMY_SUPPLY_SHORTAGE',
                    'morale': unit.morale,
                    'soldiers': unit.soldiers
                })

            # Handle desertion reabsorption into civilian labor pool or wilderness homesteading
            if deserters > 0 and region is not None:
                # Look for adjacent wilderness tiles
                wild_neighbors = [other for other in region.neighbors.values()
                                  if getattr(other, 'wilderness', False)]

                for _ in range(deserters):
                    deserter_agent = Agent(t)
                    seed_traits(deserter_agent)
                    initialize_agent(deserter_agent, Goods.none, 0, 0, 0.0)
                    deserter_agent.origin_nation = n.name
                    # Record combat experience for future private military / mercenary hiring (M5.8 / M6)
                    deserter_agent.military_xp = min(1.0, max(0.2, unit.veteran_xp + 0.2))
                    deserter_agent.mem_push('promises', 1.0)

                    if wild_neighbors and random.random() < 0.5:
                        # Become homesteader in adjacent wilderness
                        wild_tile = random.choice(wild_neighbors)
                        deserter_agent.region = wild_tile.name
                        deserter_agent.home_currency = region.home_currency
                        wd.enter_wilderness(wild_tile, deserter_agent, t)
                        wild_tile.agents.append(deserter_agent)
                        events.append({
                            't': t,
                            'unit_id': unit.unit_id,
                            'event': 'DESERTER_HOMESTEAD',
                            'agent_id': deserter_agent.id,
                            'from_region': region.name,
                            'to_region': wild_tile.name,
                            'military_xp': deserter_agent.military_xp
                        })
                    else:
                        # Reabsorb into local region civilian labor pool
                        deserter_agent.region = region.name
                        deserter_agent.home_currency = region.home_currency
                        deserter_agent._bank_ref = getattr(region, 'bank', None)
                        deserter_agent.output = random.choice([Goods.food, Goods.wood, Goods.none])
                        region.agents.append(deserter_agent)
                        if hasattr(gov, '_add_citizen'):
                            gov._add_citizen(deserter_agent)
                        events.append({
                            't': t,
                            'unit_id': unit.unit_id,
                            'event': 'DESERTER_REABSORBED',
                            'agent_id': deserter_agent.id,
                            'region': region.name,
                            'military_xp': deserter_agent.military_xp
                        })
    return events


def resolve_battle(attackers: list[MilitaryUnit], defenders: list[MilitaryUnit],
                   defense_bonus: float = 1.2) -> dict:
    """Resolve combat between attacking units and defending garrison/units on a tile.

    Returns dict with winner, casualties, and conquest status.
    """
    atk_strength = sum(u.strength for u in attackers)
    def_strength = sum(u.strength for u in defenders) * defense_bonus

    if atk_strength <= 0 and def_strength <= 0:
        return {'winner': 'stalemate', 'atk_losses': 0, 'def_losses': 0, 'conquered': False}

    total_strength = atk_strength + def_strength
    atk_ratio = atk_strength / total_strength

    # Casualties scale with intensity
    atk_losses = 0
    def_losses = 0

    if atk_ratio > 0.55:
        # Attacker advantage
        winner = 'attacker'
        atk_loss_rate = max(0.05, 0.40 * (1.0 - atk_ratio))
        def_loss_rate = min(0.95, 0.50 * atk_ratio)
    elif atk_ratio < 0.45:
        # Defender advantage
        winner = 'defender'
        atk_loss_rate = min(0.95, 0.50 * (1.0 - atk_ratio))
        def_loss_rate = max(0.05, 0.40 * atk_ratio)
    else:
        # Close battle / stalemate
        winner = 'stalemate'
        atk_loss_rate = 0.25
        def_loss_rate = 0.25

    for u in attackers:
        lost = int(u.soldiers * atk_loss_rate)
        u.soldiers = max(0, u.soldiers - lost)
        u.morale = max(0.1, u.morale - (0.1 if winner != 'attacker' else 0.02))
        u.veteran_xp = min(1.0, u.veteran_xp + 0.1)
        atk_losses += lost

    for u in defenders:
        lost = int(u.soldiers * def_loss_rate)
        u.soldiers = max(0, u.soldiers - lost)
        u.morale = max(0.1, u.morale - (0.1 if winner != 'defender' else 0.02))
        u.veteran_xp = min(1.0, u.veteran_xp + 0.1)
        def_losses += lost

    remaining_def_strength = sum(u.strength for u in defenders)
    conquered = (winner == 'attacker' and remaining_def_strength < 5.0)

    return {
        'winner': winner,
        'atk_losses': atk_losses,
        'def_losses': def_losses,
        'remaining_atk_strength': sum(u.strength for u in attackers),
        'remaining_def_strength': remaining_def_strength,
        'conquered': conquered
    }
