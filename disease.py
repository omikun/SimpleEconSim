"""
disease.py — REGNUM Phase 3 Epidemiological & Medical Economics Engine.

Models:
1. Disease contraction driven by environmental degradation and metabolic rift:
   - Malnutrition / Scurvy / Deficiency: Low food nutrition density (< 0.85) or hunger steps.
   - Waterborne Cholera / Dysentery: Contaminated water effluent (> 20.0).
   - Respiratory Smog / Black Lung: Atmospheric particulate smog (> 15.0).
   - Chemical Pesticide Toxicity: Synthetic pesticide handling and toxic residues (> 15.0).
2. Physiological & psychological damage:
   - Accelerated health attrition and despair.
   - Escalated mortality risks in demographics.
3. Medical economics strictly adhering to cash conservation (0 LEAK / 0 SUPPLY SHIFT):
   - Private care: Sick workers pay out-of-pocket medical bills to local clinics/doctors.
     Impoverished workers who cannot afford treatment remain sick and suffer severe attrition.
   - Public Healthcare Decrees: Municipal/provincial government subsidizes treatment directly
     from the treasury, providing free cures to citizens at public expense.
   - Technological breakthroughs: Germ theory, pharmaceutical chemistry, universal healthcare.
"""

from __future__ import annotations
import random
from goods import Goods

# Disease Identifiers
DIS_MALNUTRITION = 'malnutrition'
DIS_WATERBORNE = 'waterborne'
DIS_RESPIRATORY = 'respiratory'
DIS_CHEMICAL = 'chemical'
DIS_PESTILENCE = 'pestilence'

ALL_DISEASES = [DIS_MALNUTRITION, DIS_WATERBORNE, DIS_RESPIRATORY, DIS_CHEMICAL, DIS_PESTILENCE]

DISEASE_NAMES = {
    DIS_MALNUTRITION: "Malnutrition & Scurvy",
    DIS_WATERBORNE: "Waterborne Cholera",
    DIS_RESPIRATORY: "Smog Bronchitis & Black Lung",
    DIS_CHEMICAL: "Chemical Pesticide Toxicity",
    DIS_PESTILENCE: "The Great Pestilence (Black Death)",
}

DISEASE_DESCRIPTIONS = {
    DIS_MALNUTRITION: "Caused by synthetic fertilizer micronutrient dilution and caloric starvation.",
    DIS_WATERBORNE: "Contracted from drinking sewage-effluent and fertilizer-contaminated runoff.",
    DIS_RESPIRATORY: "Incurred through long-term inhalation of factory smoke and coal particulate smog.",
    DIS_CHEMICAL: "Neurological and organ damage caused by handling synthetic pesticides without bio-controls.",
    DIS_PESTILENCE: "A lethal, highly contagious epidemic traveling along commercial trade corridors, thriving on starvation and crowded habitations.",
}

# Base treatment fees ($)
BASE_TREATMENT_COST = 20.0


def _get_medical_provider(region, patient=None, is_public: bool = False):
    """Identify an agent in the region to act as medical practitioner/clinic recipient.

    Ensures 0 LEAK / 0 SUPPLY SHIFT: medical fees are transferred to living economic agents
    or municipal hospital funds, never minted or destroyed.
    """
    agents = getattr(region, 'agents', [])
    gov = getattr(region, 'gov', None)
    gov_agent = getattr(gov, 'agent', None) if gov and getattr(gov.agent, 'alive', True) else None

    # For public care: treatments are delivered through municipal hospital staff/doctors
    if is_public:
        for a in agents:
            if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and a != patient and a != gov_agent:
                if getattr(a, 'output', None) in (Goods.furniture, Goods.wood):
                    return a
        return gov_agent

    # For private care: patients pay local practitioners/apothecaries
    for a in agents:
        if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and a != patient:
            if getattr(a, 'output', None) == Goods.furniture:
                return a

    for a in agents:
        if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and a != patient:
            if getattr(a, 'output', None) == Goods.wood:
                return a

    if gov_agent and gov_agent != patient:
        return gov_agent

    for a in agents:
        if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False) and a != patient:
            return a

    return None


def step_agent_disease_onset(agent, region, rand_gen=None) -> list[str]:
    """Evaluate disease contraction risks based on local environmental conditions."""
    if not getattr(agent, 'alive', True) or getattr(agent, 'is_corporation', False):
        return []

    r = rand_gen or random
    current_diseases = getattr(agent, 'diseases', [])
    if current_diseases is None:
        agent.diseases = []
        current_diseases = agent.diseases

    nation = getattr(region, 'owner_nation', None)
    unlocked = getattr(nation, 'unlocked_techs', set()) if nation else set()

    has_germ_theory = 'germ_theory_antisepsis' in unlocked
    has_pharma = 'pharmaceutical_chemistry' in unlocked
    has_biopest = 'biological_pest_control' in unlocked

    # 1. Malnutrition & Scurvy
    if DIS_MALNUTRITION not in current_diseases:
        nutr = getattr(region, 'nutrition_density', 1.0)
        hungry = getattr(agent, 'hungry_steps', 0)
        if nutr < 0.85 or hungry > 0:
            risk = 0.05 * max(0.0, 1.0 - nutr) + 0.08 * hungry
            if r.random() < min(0.60, risk):
                current_diseases.append(DIS_MALNUTRITION)

    # 2. Waterborne Cholera / Dysentery
    if DIS_WATERBORNE not in current_diseases:
        has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))
        if not has_sewer:
            p_water = getattr(region, 'pollution_water', 0.0)
            if p_water > 20.0:
                base_risk = (p_water - 20.0) * 0.0040
                if has_germ_theory:
                    base_risk *= 0.35  # 65% reduction from sanitation & antisepsis
                if r.random() < min(0.50, base_risk):
                    current_diseases.append(DIS_WATERBORNE)

    # 3. Respiratory Smog Bronchitis
    if DIS_RESPIRATORY not in current_diseases:
        p_air = getattr(region, 'pollution_air', 0.0)
        if p_air > 15.0:
            base_risk = (p_air - 15.0) * 0.0035
            if r.random() < min(0.50, base_risk):
                current_diseases.append(DIS_RESPIRATORY)

    # 4. Chemical Pesticide Toxicity
    if DIS_CHEMICAL not in current_diseases:
        use_pest = getattr(region, 'use_pesticides', False) or getattr(region, 'mandate_pesticides', False)
        residue = getattr(region, 'pesticide_residue', 0.0)
        is_farmworker = getattr(agent, 'output', None) == Goods.food

        if (use_pest or residue > 15.0) and not has_biopest:
            base_risk = 0.02
            if is_farmworker:
                base_risk += 0.05
            if residue > 25.0:
                base_risk += (residue - 25.0) * 0.002
            if has_pharma:
                base_risk *= 0.50
            if r.random() < min(0.60, base_risk):
                current_diseases.append(DIS_CHEMICAL)

    # 5. The Great Pestilence (Black Death) Contagion
    if DIS_PESTILENCE not in current_diseases:
        plague_cases = getattr(region, 'active_pestilence_count', 0)
        if plague_cases > 0:
            pop = len([x for x in getattr(region, 'agents', []) if getattr(x, 'alive', True) and not getattr(x, 'is_corporation', False)])
            cap = getattr(region, 'carrying_capacity', 100) or 100
            crowding = min(2.5, max(0.5, pop / max(1, cap)))

            nutr = getattr(region, 'nutrition_density', 1.0)
            hungry = getattr(agent, 'hungry_steps', 0)
            susceptibility = 1.0 + 0.40 * hungry + 0.80 * max(0.0, 0.85 - nutr)

            base_risk = 0.10 * (plague_cases / max(1, pop * 0.20)) * crowding * susceptibility

            has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))
            if has_sewer:
                base_risk *= 0.45
            if has_germ_theory:
                base_risk *= 0.25

            if r.random() < min(0.70, base_risk):
                current_diseases.append(DIS_PESTILENCE)

    # Compound health wear from all active diseases
    if current_diseases:
        extra_pest = 0.08 if DIS_PESTILENCE in current_diseases else 0.0
        wear = 0.025 * len(current_diseases) + extra_pest
        agent.health_attrition = min(2.5, getattr(agent, 'health_attrition', 0.0) + wear)
        agent.despair = min(1.0, getattr(agent, 'despair', 0.0) + 0.03 * len(current_diseases) + (0.10 if extra_pest else 0.0))

    return current_diseases


def step_medical_care(region, t: int, rand_gen=None) -> dict:
    """Administer private and public medical treatments across the region.

    Ensures strict cash conservation (0 LEAK / 0 SUPPLY SHIFT).
    """
    r = rand_gen or random
    agents = [a for a in getattr(region, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)]

    nation = getattr(region, 'owner_nation', None)
    unlocked = getattr(nation, 'unlocked_techs', set()) if nation else set()

    has_germ_theory = 'germ_theory_antisepsis' in unlocked
    has_pharma = 'pharmaceutical_chemistry' in unlocked
    has_universal = 'universal_healthcare_system' in unlocked

    # Treatment cost adjustments
    cost_per_cure = BASE_TREATMENT_COST
    if has_germ_theory:
        cost_per_cure *= 0.80
    if has_universal:
        cost_per_cure *= 0.70

    # Clinic presence in buildings gives bonus efficiency
    has_clinic = any(getattr(b, 'type', '') in ('municipal_clinic', 'sanatorium')
                     for b in getattr(region, 'buildings', []))
    cure_chance = 0.95 if (has_pharma or has_clinic) else 0.80

    is_public_healthcare = (
        getattr(region, 'public_healthcare_decree', False) or
        has_universal or
        getattr(getattr(region, 'province', None), 'public_healthcare_decree', False)
    )

    spending_priv = 0.0
    spending_pub = 0.0
    treated_count = 0
    untreated_count = 0

    gov = getattr(region, 'gov', None)
    gov_agent = getattr(gov, 'agent', None) if gov else None

    # Track disease breakdown this step
    counts = {DIS_MALNUTRITION: 0, DIS_WATERBORNE: 0, DIS_RESPIRATORY: 0, DIS_CHEMICAL: 0, DIS_PESTILENCE: 0}

    for a in agents:
        dis_list = getattr(a, 'diseases', [])
        if not dis_list:
            continue

        for dis in dis_list:
            counts[dis] = counts.get(dis, 0) + 1

        provider = _get_medical_provider(region, patient=a, is_public=is_public_healthcare)

        # Attempt to treat each active disease
        cured_this_turn = []
        for dis in list(dis_list):
            effective_cure = cure_chance
            if dis == DIS_PESTILENCE:
                if has_pharma or has_clinic:
                    effective_cure = 0.65
                elif has_germ_theory:
                    effective_cure = 0.40
                else:
                    effective_cure = 0.15

            if is_public_healthcare and gov_agent and gov_agent.cash >= cost_per_cure:
                # Publicly funded care: treasury pays, zero out-of-pocket for citizen
                gov_agent.cash -= cost_per_cure
                if provider and provider != gov_agent:
                    provider.cash += cost_per_cure
                else:
                    gov_agent.cash += cost_per_cure  # Self-administered municipal hospital

                spending_pub += cost_per_cure
                treated_count += 1
                a.medical_treatments_count = getattr(a, 'medical_treatments_count', 0) + 1

                if r.random() < effective_cure:
                    cured_this_turn.append(dis)
                    a.health_attrition = max(0.0, getattr(a, 'health_attrition', 0.0) - 0.15)
            elif a.cash >= cost_per_cure:
                # Private out-of-pocket medical bill: patient pays
                a.cash -= cost_per_cure
                if provider and provider != a:
                    provider.cash += cost_per_cure
                else:
                    a.cash += cost_per_cure  # Self-purchase of folk remedy

                spending_priv += cost_per_cure
                a.medical_expenses_paid = getattr(a, 'medical_expenses_paid', 0.0) + cost_per_cure
                treated_count += 1
                a.medical_treatments_count = getattr(a, 'medical_treatments_count', 0) + 1

                if r.random() < effective_cure:
                    cured_this_turn.append(dis)
                    a.health_attrition = max(0.0, getattr(a, 'health_attrition', 0.0) - 0.10)
            else:
                # Cannot afford treatment! Disease festers
                untreated_count += 1
                a.health_attrition = min(2.5, getattr(a, 'health_attrition', 0.0) + 0.04)
                a.despair = min(1.0, getattr(a, 'despair', 0.0) + 0.05)

        for c in cured_this_turn:
            if c in a.diseases:
                a.diseases.remove(c)

    # Record summary in region logs
    total_active = sum(counts.values())
    counts['total'] = total_active

    if not hasattr(region, 'disease_cases_log'):
        region.disease_cases_log = []
    if not hasattr(region, 'medical_spending_private_log'):
        region.medical_spending_private_log = []
    if not hasattr(region, 'medical_spending_public_log'):
        region.medical_spending_public_log = []
    if not hasattr(region, 'untreated_cases_log'):
        region.untreated_cases_log = []
    if not hasattr(region, 'disease_fatalities_log'):
        region.disease_fatalities_log = []

    fatalities = getattr(region, 'disease_fatalities_this_turn', 0)
    region.disease_fatalities_this_turn = 0

    region.disease_cases_log.append(counts)
    region.medical_spending_private_log.append(spending_priv)
    region.medical_spending_public_log.append(spending_pub)
    region.untreated_cases_log.append(untreated_count)
    region.disease_fatalities_log.append(fatalities)

    return {
        'cases': counts,
        'spending_private': spending_priv,
        'spending_public': spending_pub,
        'treated': treated_count,
        'untreated': untreated_count,
        'fatalities': fatalities,
    }


def evaluate_pestilence_genesis(region, t: int, rand_gen=None) -> bool:
    """Evaluate whether extreme famine and overcrowding trigger Patient Zero."""
    agents = [a for a in getattr(region, 'agents', []) if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)]
    if len(agents) < 10:
        return False

    granary = getattr(region, 'granary_stock', 10.0)
    nutr = getattr(region, 'nutrition_density', 1.0)
    starving_count = sum(1 for a in agents if getattr(a, 'hungry_steps', 0) >= 2)
    cap = getattr(region, 'carrying_capacity', None) or getattr(region, 'capacity', 100) or 100
    crowding = len(agents) / max(1, cap)

    # Severe famine condition: granaries empty, at least 15% chronic starvation, and nutrition < 0.75
    is_famine = (granary <= 1.0 and starving_count >= len(agents) * 0.15 and nutr < 0.75)
    is_crowded = (crowding >= 0.70)

    if is_famine and is_crowded:
        region.famine_outbreak_turns = getattr(region, 'famine_outbreak_turns', 0) + 1
    else:
        region.famine_outbreak_turns = max(0, getattr(region, 'famine_outbreak_turns', 0) - 1)
        return False

    # If severe famine persists for 2 or more consecutive turns:
    if region.famine_outbreak_turns >= 2:
        r = rand_gen or random
        outbreak_prob = min(0.90, 0.40 * (region.famine_outbreak_turns - 1))

        has_sewer = any(getattr(b, 'name', '') == 'trunk_sewer' for b in getattr(region, 'buildings', []))
        if has_sewer:
            outbreak_prob *= 0.40
        nation = getattr(region, 'owner_nation', None)
        unlocked = getattr(nation, 'unlocked_techs', set()) if nation else set()
        if 'germ_theory_antisepsis' in unlocked:
            outbreak_prob *= 0.20

        if r.random() < outbreak_prob:
            # Spawn Patient Zero
            candidates = [a for a in agents if getattr(a, 'hungry_steps', 0) >= 2 and DIS_PESTILENCE not in getattr(a, 'diseases', [])]
            if not candidates:
                candidates = agents
            patient_zero = r.choice(candidates)
            if not hasattr(patient_zero, 'diseases') or patient_zero.diseases is None:
                patient_zero.diseases = []
            patient_zero.diseases.append(DIS_PESTILENCE)
            region.active_pestilence_count = sum(1 for a in agents if DIS_PESTILENCE in getattr(a, 'diseases', []))
            region.pestilence_origin_turn = t
            return True

    return False


def step_trade_epidemic_transmission(tiles: list, t: int, world: dict | None = None, rand_gen=None) -> list[dict]:
    """Propagate the Great Pestilence across active inter-regional trade routes and traveling merchants."""
    events = []
    rng = rand_gen or random
    for r in tiles:
        routes = getattr(r, 'routes', {})
        active_pest = getattr(r, 'active_pestilence_count', 0)

        # 1. Loading Contagion onto Outgoing Routes
        if active_pest > 0:
            for partner_name, rt in routes.items():
                if rt.is_frozen or getattr(rt, 'is_quarantined', False):
                    continue
                inf_rate = active_pest / max(1, len(getattr(r, 'agents', [])))
                if rng.random() < min(0.95, 0.30 + inf_rate * 1.5):
                    rt.has_contagion = True

        # 2. Arrival & Infection at Destination
        for partner_name, rt in routes.items():
            if not getattr(rt, 'has_contagion', False):
                continue
            dst = rt.dst
            if dst is None:
                continue

            # Check if destination or route has active Quarantine / Cordon Sanitaire
            if getattr(dst, 'quarantine_active', False) or getattr(rt, 'is_quarantined', False):
                rt.has_contagion = False
                ev = {
                    't': t,
                    'type': 'QUARANTINE_BLOCK',
                    'src': r.name,
                    'dst': dst.name,
                    'message': f"QUARANTINE BLOCK: Sanitary patrol at {dst.name} turned back infected trade shipment from {r.name}!"
                }
                events.append(ev)
                continue

            # If arriving goods mature or route has in-transit cargo
            if getattr(rt, 'delivered_this_turn', None) or getattr(rt, 'in_transit', None):
                vulnerable = [a for a in getattr(dst, 'agents', [])
                              if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                              and DIS_PESTILENCE not in getattr(a, 'diseases', [])]
                if vulnerable:
                    patient = random.choice(vulnerable)
                    if not hasattr(patient, 'diseases') or patient.diseases is None:
                        patient.diseases = []
                    patient.diseases.append(DIS_PESTILENCE)
                    dst.active_pestilence_count = sum(1 for a in getattr(dst, 'agents', []) if DIS_PESTILENCE in getattr(a, 'diseases', []))
                    rt.has_contagion = False
                    ev = {
                        't': t,
                        'type': 'PLAGUE_TRANSMISSION',
                        'src': r.name,
                        'dst': dst.name,
                        'message': f"PLAGUE SHIP: The Great Pestilence has reached {dst.name} via merchant trade routes from {r.name}!"
                    }
                    events.append(ev)

    return events


def step_tile_diseases(region, t: int, rand_gen=None) -> dict:
    """Execute complete epidemiological cycle: disease onset + medical treatment."""
    agents = [a for a in getattr(region, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)]

    # Update active pestilence count before transmission
    active_pest = sum(1 for a in agents if DIS_PESTILENCE in getattr(a, 'diseases', []))
    region.active_pestilence_count = active_pest

    # Check for endogenous genesis if no active plague
    if active_pest == 0:
        evaluate_pestilence_genesis(region, t, rand_gen)

    for a in agents:
        step_agent_disease_onset(a, region, rand_gen)

    res = step_medical_care(region, t, rand_gen)

    # Re-count active pestilence after treatments
    region.active_pestilence_count = sum(1 for a in agents if getattr(a, 'alive', True) and DIS_PESTILENCE in getattr(a, 'diseases', []))
    return res
