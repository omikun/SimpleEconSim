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

ALL_DISEASES = [DIS_MALNUTRITION, DIS_WATERBORNE, DIS_RESPIRATORY, DIS_CHEMICAL]

DISEASE_NAMES = {
    DIS_MALNUTRITION: "Malnutrition & Scurvy",
    DIS_WATERBORNE: "Waterborne Cholera",
    DIS_RESPIRATORY: "Smog Bronchitis & Black Lung",
    DIS_CHEMICAL: "Chemical Pesticide Toxicity",
}

DISEASE_DESCRIPTIONS = {
    DIS_MALNUTRITION: "Caused by synthetic fertilizer micronutrient dilution and caloric starvation.",
    DIS_WATERBORNE: "Contracted from drinking sewage-effluent and fertilizer-contaminated runoff.",
    DIS_RESPIRATORY: "Incurred through long-term inhalation of factory smoke and coal particulate smog.",
    DIS_CHEMICAL: "Neurological and organ damage caused by handling synthetic pesticides without bio-controls.",
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

    # Compound health wear from all active diseases
    if current_diseases:
        wear = 0.025 * len(current_diseases)
        agent.health_attrition = min(2.5, getattr(agent, 'health_attrition', 0.0) + wear)
        agent.despair = min(1.0, getattr(agent, 'despair', 0.0) + 0.03 * len(current_diseases))

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
    counts = {DIS_MALNUTRITION: 0, DIS_WATERBORNE: 0, DIS_RESPIRATORY: 0, DIS_CHEMICAL: 0}

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

                if r.random() < cure_chance:
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

                if r.random() < cure_chance:
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


def step_tile_diseases(region, t: int, rand_gen=None) -> dict:
    """Execute complete epidemiological cycle: disease onset + medical treatment."""
    agents = [a for a in getattr(region, 'agents', [])
              if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)]

    for a in agents:
        step_agent_disease_onset(a, region, rand_gen)

    return step_medical_care(region, t, rand_gen)
