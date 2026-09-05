"""
labor_politics.py — Political struggle over the working day and labor commodification.

Implements core political-economy dynamics of labor:
  1. Corporations never voluntarily reduce shift hours under competition.
     Shift hours only reduce when legally mandated by legislation (Ten-Hour Act).
  2. Popular uprisings, strike pressure, and sustained unrest force incumbents
     to concede workday caps and safety mandates to avoid revolution.
  3. Enacting pro-labor legislation enrages capitalists, who form a campaign PAC
     and fund opposition candidates to defeat reformist incumbents.
  4. Winning capitalist regimes repeal pro-labor laws, restoring 16h caps.
  5. Mass entertainment serves as a capitalist pacifier: it dampens protest energy
     and class consciousness, neutralizing rebellion risk.

Conservation: All political campaign donations and subsidies are strict within-tile
or within-nation transfers between agents or gov treasuries.
"""

from __future__ import annotations

from typing import Tuple, List, Dict, Any, Optional

#: Default statutory workday cap before reform
DEFAULT_WORKDAY_CAP = 16.0
#: Reformed workday cap (Ten-Hour Act)
REFORMED_WORKDAY_CAP = 10.0
#: Strike rate threshold triggering government panic
UPRISING_STRIKE_THRESHOLD = 0.20
#: Unrest threshold triggering government concessions
UPRISING_UNREST_THRESHOLD = 0.60


def evaluate_uprising_pressure(nation, t: int) -> List[Dict[str, Any]]:
    """Evaluate nationwide unrest and strike pressure, forcing concessions if critical."""
    events = []
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return events

    total_workers = 0
    total_strikers = 0
    total_unrest = 0.0
    total_consciousness = 0.0

    for tile in tiles:
        workers = [a for a in getattr(tile, 'agents', [])
                   if getattr(a, 'social_class', '') in ('proletarian', 'serf', 'tenant', 'dispossessed')
                   and getattr(a, 'alive', True)]
        total_workers += len(workers)
        strikers = [a for a in workers if getattr(a, 'is_striking', False)]
        total_strikers += len(strikers)
        total_unrest += getattr(tile, 'unrest_level', 0.0)
        c_vals = [getattr(a, 'class_consciousness', 0.0) for a in workers]
        if c_vals:
            total_consciousness += sum(c_vals) / len(c_vals)

    avg_unrest = total_unrest / len(tiles)
    strike_rate = (total_strikers / total_workers) if total_workers > 0 else 0.0
    avg_consciousness = total_consciousness / len(tiles)

    # Sustained uprising pressure triggers concessions from fearful incumbents
    is_crisis = (strike_rate >= UPRISING_STRIKE_THRESHOLD or avg_unrest >= UPRISING_UNREST_THRESHOLD)

    if is_crisis:
        # Step 1: Enact Ten-Hour Act if not already enacted
        if not getattr(nation, 'ten_hour_act', False):
            ok, msg = enact_ten_hour_act(nation)
            if ok:
                # Concession cools down worker unrest
                for tile in tiles:
                    tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.25)
                nation.legitimacy = min(1.0, getattr(nation, 'legitimacy', 0.5) + 0.15)
                ev = {
                    'kind': 'ten_hour_act_concession',
                    'turn': t,
                    'nation': nation.name,
                    'strike_rate': strike_rate,
                    'unrest': avg_unrest,
                    'msg': "Mass strikes and uprising forced the government to pass the Ten-Hour Act!",
                }
                events.append(ev)
                nation.regime_log.append(ev)
        # Step 2: If Ten-Hour Act already passed, enact Factory Safety Act
        elif not getattr(nation, 'factory_safety_act', False):
            ok, msg = enact_factory_safety_act(nation)
            if ok:
                for tile in tiles:
                    tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.20)
                nation.legitimacy = min(1.0, getattr(nation, 'legitimacy', 0.5) + 0.10)
                ev = {
                    'kind': 'factory_safety_concession',
                    'turn': t,
                    'nation': nation.name,
                    'strike_rate': strike_rate,
                    'msg': "Labor unrest forced the government to mandate Factory Safety Standards!",
                }
                events.append(ev)
                nation.regime_log.append(ev)

    return events


def capitalist_electoral_backlash(nation, candidates: list, t: int) -> float:
    """Capitalists pool money into a PAC to fund opposition and oust pro-labor incumbents.

    Returns total campaign funds donated by capitalists to the opposition candidate.
    """
    if not candidates:
        return 0.0

    # Only triggers if pro-labor legislation has threatened profits
    has_labor_laws = (getattr(nation, 'ten_hour_act', False) or
                      getattr(nation, 'factory_safety_act', False) or
                      getattr(nation, 'max_workday_hours', 16.0) < 14.0)
    if not has_labor_laws:
        return 0.0

    incumbent_faction = getattr(nation, '_incumbent_faction', None)
    # Find candidates who are NOT the incumbent faction (preferably backed by capitalists/merchants/lords)
    opponents = [c for c in candidates if c.backing_faction != incumbent_faction]
    if not opponents:
        opponents = candidates

    # Prefer opponent backed by conservative/capitalist faction, or highest charisma
    target_cand = max(opponents, key=lambda c: getattr(c.agent, 'charisma', 0.0))

    total_donations = 0.0
    for tile in getattr(nation, 'tiles', []):
        for a in getattr(tile, 'agents', []):
            if not getattr(a, 'alive', True):
                continue
            is_capitalist = (getattr(a, 'social_class', '') in ('capitalist', 'industrialist', 'landlord', 'lord')
                             or getattr(a, 'is_corporation', False))
            if is_capitalist and a.cash > 25.0:
                # Donate 15% of surplus liquid cash to defeat the reformist incumbent
                donation = round((a.cash - 20.0) * 0.15, 2)
                if donation > 0.5:
                    a.cash -= donation
                    target_cand.agent.cash += donation
                    curr = getattr(nation, 'currency', None)
                    if curr:
                        if getattr(a, 'wallets', None) and curr in a.wallets:
                            a.wallets[curr] -= donation
                        if getattr(target_cand.agent, 'wallets', None) and curr in target_cand.agent.wallets:
                            target_cand.agent.wallets[curr] += donation
                    # Popularity boost diluted by charisma
                    charisma = getattr(target_cand.agent, 'charisma', 0.5)
                    gain = donation * (0.5 + 0.5 * charisma) * (1.0 / 1500.0)
                    target_cand.popularity += gain
                    total_donations += donation

    if total_donations > 0:
        ev = {
            'kind': 'capitalist_pac_backlash',
            'turn': t,
            'amount': total_donations,
            'favored_candidate': getattr(target_cand.agent, 'id', -1),
            'target_faction': target_cand.backing_faction,
        }
        nation.regime_log.append(ev)

    return total_donations


def repeal_labor_laws(nation) -> Dict[str, Any]:
    """Repeal pro-labor legislation when a capitalist/reactionary regime takes power."""
    repealed = []
    if getattr(nation, 'ten_hour_act', False) or getattr(nation, 'max_workday_hours', 16.0) < 14.0:
        nation.ten_hour_act = False
        nation.max_workday_hours = DEFAULT_WORKDAY_CAP
        for tile in getattr(nation, 'tiles', []):
            tile.max_workday_hours = DEFAULT_WORKDAY_CAP
        repealed.append("Ten-Hour Act (workday restored to 16h)")

    if getattr(nation, 'factory_safety_act', False):
        nation.factory_safety_act = False
        for tile in getattr(nation, 'tiles', []):
            tile.factory_safety_act = False
        repealed.append("Factory Safety Standards (regulations dismantled)")

    return {
        'repealed': repealed,
        'msg': f"Capitalist regime repealed: {', '.join(repealed)}" if repealed else "No labor laws to repeal."
    }


def enact_ten_hour_act(target) -> Tuple[bool, str]:
    """Enact the Ten-Hour Act on a region or nation, capping daily factory shifts to 10h."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    for tile in tiles:
        tile.max_workday_hours = REFORMED_WORKDAY_CAP
        tile.ten_hour_act = True
    setattr(target, 'ten_hour_act', True)
    setattr(target, 'max_workday_hours', REFORMED_WORKDAY_CAP)
    return True, "Ten-Hour Act enacted: Workday capped at 10.0 hours!"


def enact_factory_safety_act(target) -> Tuple[bool, str]:
    """Mandate workplace safety regulations, reducing factory injury & mortality."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    for tile in tiles:
        tile.factory_safety_act = True
    setattr(target, 'factory_safety_act', True)
    return True, "Factory Safety Mandate enacted: Machinery guards required!"


def subsidize_mass_entertainment(target, cost: float = 50.0) -> Tuple[bool, str]:
    """Subsidize public entertainment to pacify unrest and dampen class organizing.

    Transfers funds from treasury to tile entertainment level (stifling protest energy).
    """
    gov_agent = None
    if hasattr(target, 'gov') and hasattr(target.gov, 'agent'):
        gov_agent = target.gov.agent
    elif hasattr(target, 'tiles') and target.tiles and hasattr(target.tiles[0], 'gov'):
        gov_agent = target.tiles[0].gov.agent

    if gov_agent is None or gov_agent.cash < cost:
        return False, "Insufficient government treasury funds for entertainment subsidy."

    # Conserved transfer: gov cash spent into local commerce / spectacle
    gov_agent.cash -= cost

    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    boost = 0.40 / len(tiles)
    for tile in tiles:
        cur = getattr(tile, 'entertainment_level', 0.0)
        tile.entertainment_level = min(1.0, cur + boost)
        # Immediate damping of protest energy
        tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.15)

    return True, f"Mass entertainment subsidized (${cost:.0f}): Pacified public unrest!"
