"""
Factions, grievances, and unrest metrics for a Region.
"""

from goods import Goods
from faction import Faction


def build_identity_factions(region):
    """Create one faction per M1 identity tag kind (ethnicity, religion, politics)."""
    from agent import _ETHNICITIES, _RELIGIONS, _POLITICS
    for pool in (_ETHNICITIES, _RELIGIONS, _POLITICS):
        for tag in pool:
            kind = ('ethnicity' if pool is _ETHNICITIES
                    else 'religion' if pool is _RELIGIONS
                    else 'political')
            f = Faction(tag.capitalize(), kind)
            if kind == 'ethnicity':
                f.add_demand('native_rights', weight=1.2)
            else:
                f.add_demand('welfare', weight=1.0)
                f.add_demand('tax_cut', weight=0.8)
                f.add_demand('tariff', weight=0.6)
                if kind == 'political':
                    f.add_demand('immigration', weight=0.9)
            region.factions.register(f)


def refresh_faction_membership(region):
    """Overwrite each identity faction's membership from live agent identity tags."""
    for f in region.factions.factions.values():
        f.membership = set()
    for a in region.agents:
        if not getattr(a, 'alive', True):
            continue
        for attr, kind in (('ethnicity', 'ethnicity'),
                           ('religion', 'religion'),
                           ('politics', 'political')):
            tag = getattr(a, attr, None)
            if tag is None:
                continue
            f = region.factions.get(tag.capitalize())
            if f is not None:
                f.membership.add(a.id)


def apply_policy_satisfaction(region):
    """Map the tile government's existing policy knobs to faction demand satisfaction."""
    gov = region.gov
    tax_sat = max(0.0, min(1.0, 1.0 - gov.tax_rate / 0.75))
    welfare_sat = 1.0 if getattr(gov, 'ubi_enabled', False) else 0.35
    tariff_sat = max(0.0, min(1.0, gov.import_tariff_rate / 0.15))
    imm_sat = 1.0 if getattr(gov, 'immigration_enabled', False) else 0.2
    native_sat = 0.3

    for f in region.factions.factions.values():
        for d in f.demands:
            if d.name == 'tax_cut':
                d.satisfied = tax_sat
            elif d.name == 'welfare':
                d.satisfied = welfare_sat
            elif d.name == 'tariff':
                d.satisfied = tariff_sat
            elif d.name == 'immigration':
                d.satisfied = imm_sat
            elif d.name == 'native_rights':
                d.satisfied = native_sat


def accumulate_grievances(region, t):
    """Add per-turn grievance sources to each faction (M2.3)."""
    agents = region.agents
    adds = {}
    if not agents:
        return adds
    # hunger
    hungry_now = sum(1 for a in agents
                     if not a.is_corporation and not a.is_government
                     and a.hungry_steps > 0)
    mem_hunger = sum(a.mem_avg('mem_hunger', 0.0)
                     for a in agents
                     if not a.is_corporation and not a.is_government)
    hunger_score = min(3.0, hungry_now / 30.0 + mem_hunger / 120.0)
    # repression memory
    trauma = sum(a.mem_avg('mem_casualties', 0.0)
                 + a.mem_avg('mem_promises', 0.0)
                 for a in agents
                 if not a.is_corporation and not a.is_government)
    trauma_score = min(2.0, trauma / 60.0)
    # gini
    gini = 0.0
    for g in (Goods.food, Goods.wood, Goods.furniture):
        vals = sorted(a.cash for a in agents if a.output == g)
        if len(vals) > 5:
            n = len(vals)
            s = sum(vals)
            if s > 0:
                wsum = sum((i + 1) * v for i, v in enumerate(vals))
                gini = max(gini, (2 * wsum) / (n * s) - (n + 1) / n)
    # tax (effective)
    tax = region.gov.tax_rate
    # unemployment
    adults = [a for a in agents
              if not a.is_corporation and not a.is_government
              and a.age(t) > 20]
    unemp = (sum(1 for a in adults if a.employer is None
                 and not a.is_trader) / max(1, len(adults)))

    for f in region.factions.factions.values():
        if f.kind == 'political':
            n_add = (hunger_score * 0.6 + gini * 1.2
                     + tax * 1.5 + unemp * 1.5 + trauma_score)
            f.add_grievance('hunger', hunger_score * 0.6)
            f.add_grievance('gini', gini * 1.2)
            f.add_grievance('tax', tax * 1.5)
            f.add_grievance('unemployment', unemp * 1.5)
            f.add_grievance('repression', trauma_score)
        else:
            n_add = hunger_score + gini + tax + unemp + trauma_score
            f.add_grievance('hunger', hunger_score)
            f.add_grievance('gini', gini)
            f.add_grievance('tax', tax)
            f.add_grievance('unemployment', unemp)
            f.add_grievance('repression', trauma_score)
        adds[f.name] = n_add
    return adds


def protest_energy(adds):
    """M2.4: per-tile protest score from the rate of fresh grievance."""
    if not adds:
        return 0.0
    avg = sum(adds.values()) / len(adds)
    score = min(10.0, avg * 2.0)
    return max(0.0, score)


def step_factions(region, t):
    """One turn of faction bookkeeping: membership, policy satisfaction, support, and grievances."""
    refresh_faction_membership(region)
    apply_policy_satisfaction(region)
    eligible = {a.id for a in region.agents if getattr(a, 'alive', True)}
    adds = accumulate_grievances(region, t)
    region.factions.step(eligible)
    snap = {name: f.support for name, f in region.factions.factions.items()}
    region.faction_support_log.append(snap)
    gv = {name: f.total_grievance() for name, f in region.factions.factions.items()}
    region.faction_grievance_log.append(gv)
    region.protest_energy_log.append(protest_energy(adds))
