"""
disease.py — Call of Capital Phase 3 Epidemiological & Medical Economics Engine.

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
from treasury_trace import begin_public_change, finish_public_change
from finance_trace import emit_public_account_flow
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
    attrition_before = float(getattr(agent, 'health_attrition', 0.0))
    risk_checks = {}
    diseases_before = list(current_diseases)

    def test_risk(disease, risk, cap):
        draw = r.random()
        bounded_risk = min(cap, risk)
        risk_checks[disease] = {'risk': risk, 'capped_risk': bounded_risk,
                                'draw': draw, 'contracted': draw < bounded_risk}
        return draw < bounded_risk

    # 1. Malnutrition & Scurvy
    if DIS_MALNUTRITION not in current_diseases:
        nutr = getattr(region, 'nutrition_density', 1.0)
        hungry = getattr(agent, 'hungry_steps', 0)
        if nutr < 0.85 or hungry > 0:
            risk = 0.05 * max(0.0, 1.0 - nutr) + 0.08 * hungry
            if test_risk(DIS_MALNUTRITION, risk, 0.60):
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
                if test_risk(DIS_WATERBORNE, base_risk, 0.50):
                    current_diseases.append(DIS_WATERBORNE)

    # 3. Respiratory Smog Bronchitis
    if DIS_RESPIRATORY not in current_diseases:
        p_air = getattr(region, 'pollution_air', 0.0)
        if p_air > 15.0:
            base_risk = (p_air - 15.0) * 0.0035
            if test_risk(DIS_RESPIRATORY, base_risk, 0.50):
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
            if test_risk(DIS_CHEMICAL, base_risk, 0.60):
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

            if test_risk(DIS_PESTILENCE, base_risk, 0.70):
                current_diseases.append(DIS_PESTILENCE)

    # Compound health wear from all active diseases
    if current_diseases:
        extra_pest = 0.08 if DIS_PESTILENCE in current_diseases else 0.0
        wear = 0.025 * len(current_diseases) + extra_pest
        agent.health_attrition = min(2.5, getattr(agent, 'health_attrition', 0.0) + wear)
        agent.despair = min(1.0, getattr(agent, 'despair', 0.0) + 0.03 * len(current_diseases) + (0.10 if extra_pest else 0.0))

    newly_contracted = [disease for disease in current_diseases
                        if disease not in diseases_before]
    if risk_checks or newly_contracted or current_diseases:
        from run_trace import emit
        emit(region, kind='disease_onset_assessment', record_class='outcome',
             subject={'type': 'tile', 'id': region.name,
                      'agent_id': getattr(agent, 'id', None)},
             metric_id='health.disease_incidence', unit='cases',
             before=len(diseases_before), after=len(current_diseases),
             inputs={'risk_checks': risk_checks, 'newly_contracted': newly_contracted,
                     'active_diseases': list(current_diseases),
                     'nutrition_density': getattr(region, 'nutrition_density', 1.0),
                     'hungry_steps': getattr(agent, 'hungry_steps', 0),
                     'water_pollution': getattr(region, 'pollution_water', 0.0),
                     'air_pollution': getattr(region, 'pollution_air', 0.0),
                     'pesticide_residue': getattr(region, 'pesticide_residue', 0.0),
                     'sewer': any(getattr(b, 'name', '') == 'trunk_sewer'
                                  for b in getattr(region, 'buildings', [])),
                     'germ_theory': has_germ_theory, 'pharmaceutical_chemistry': has_pharma,
                     'biological_pest_control': has_biopest},
             formula_id='disease.exposure_risk.v1')
    attrition_after = float(getattr(agent, 'health_attrition', 0.0))
    if attrition_after != attrition_before:
        from run_trace import emit
        emit(region, kind='disease_health_attrition', record_class='calculation',
             subject={'type': 'tile', 'id': region.name,
                      'agent_id': getattr(agent, 'id', None)},
             metric_id='health.attrition', unit='attrition_points',
             before=attrition_before, after=attrition_after,
             formula_id='disease.compound_wear.v1',
             inputs={'active_diseases': list(current_diseases),
                     'disease_count': len(current_diseases),
                     'pestilence_extra_wear': 0.08 if DIS_PESTILENCE in current_diseases else 0.0,
                     'wear_cap': 2.5})

    return current_diseases


def step_medical_care(region, t: int, rand_gen=None) -> dict:
    """Administer private and public medical treatments across the region.

    Ensures strict cash conservation (0 LEAK / 0 SUPPLY SHIFT).
    """
    r = rand_gen or random
    from finance_trace import (account_ref, cash_transfer_contract,
                               emit_cash_transfer)
    from run_trace import emit

    def trace_medical_payment(payer, payee, patient, disease, amount,
                              payer_type, payer_before, payee_before,
                              operation_id, journal_event, account_event_ids=()):
        currency = (getattr(region, 'home_currency', None)
                    or 'local_currency')
        payer_currency = (getattr(payer, 'home_currency', None)
                          or currency)
        payee_currency = (getattr(payee, 'home_currency', None)
                          or currency)
        contract = cash_transfer_contract(
            operation_id, 'medical_care_payment', amount=float(amount),
            currency=currency,
            payer_account=account_ref(
                'government_wallet' if payer_type == 'public' else 'agent_wallet',
                str(payer.id), payer_currency, agent_id=str(payer.id),
                tile=region.name, balance_before=float(payer_before),
                balance_after=float(payer.cash), balance_scope='cash_wallet'),
            payee_account=account_ref(
                'medical_provider_wallet', str(payee.id), payee_currency,
                agent_id=str(payee.id), tile=region.name,
                balance_before=float(payee_before),
                balance_after=float(payee.cash), balance_scope='cash_wallet'),
            counterparty_leg_status='both_cash_balances_captured',
            payer_type=payer_type, patient_id=str(patient.id),
            disease=disease)
        return emit_cash_transfer(
            region, kind='medical_care_payment', contract=contract,
            phase='healthcare',
            subject={'type': 'tile/operation', 'id': operation_id,
                     'tile': region.name},
            inputs={'turn': int(t), 'payer_type': payer_type,
                    'patient_id': str(patient.id), 'disease': disease,
                    'provider_id': str(payee.id),
                    'operation_id': operation_id,
                    'actor_account_event_id': journal_event['id']
                    if journal_event is not None else None},
            cause_event_ids=list(account_event_ids) or None)

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
    public_treated_count = 0
    untreated_count = 0
    public_transfers = 0.0
    private_transfers = 0.0
    non_transfer_treatments = 0
    public_transfer_event_ids = []
    medical_transfer_event_ids = []
    untreated_case_rows = []
    untreated_event_ids = []

    gov = getattr(region, 'gov', None)
    gov_agent = getattr(gov, 'agent', None) if gov else None

    # Track disease breakdown this step
    counts = {DIS_MALNUTRITION: 0, DIS_WATERBORNE: 0, DIS_RESPIRATORY: 0, DIS_CHEMICAL: 0, DIS_PESTILENCE: 0}
    case_ids_before_treatment={disease:[a.id for a in agents if disease in (getattr(a,'diseases',[]) or [])]
                               for disease in ALL_DISEASES}

    for a in agents:
        dis_list = getattr(a, 'diseases', [])
        if not dis_list:
            continue

        for dis in dis_list:
            counts[dis] = counts.get(dis, 0) + 1

        provider = _get_medical_provider(region, patient=a, is_public=is_public_healthcare)

        # Attempt to treat each active disease
        cured_this_turn = []
        for disease_index, dis in enumerate(list(dis_list)):
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
                cash_transfer_event_id = None
                actor_account_event = None
                operation_id = (f'medical-care:{region.name}:{int(t)}:'
                                f'{a.id}:{dis}:{disease_index}:public')
                account_event_ids = []
                cash_settlement = 'self_administered_no_net_cash_transfer'
                payer_cash_before = float(gov_agent.cash)
                public_change = begin_public_change(region, gov_agent)
                gov_agent.cash -= cost_per_cure
                account_event_ids.extend(finish_public_change(
                    public_change, 'public_medical_payment_debit',
                    inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                if provider and provider != gov_agent:
                    provider_cash_before = float(provider.cash)
                    public_change = begin_public_change(region, provider)
                    provider.cash += cost_per_cure
                    account_event_ids.extend(finish_public_change(
                        public_change, 'medical_provider_receipt',
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                    emit_public_account_flow(
                        region, provider, kind='medical_public_provider_receipt',
                        signed_amount=cost_per_cure,
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis},
                        cause_event_ids=account_event_ids or None)
                    public_transfers += cost_per_cure
                    from economy.actor_accounts import record as record_economic_event
                    operation_id = (f'medical-care:{region.name}:{int(t)}:'
                                    f'{a.id}:{dis}:{disease_index}:public')
                    actor_account_event = record_economic_event(
                        region, 'medical_care', turn=t,
                        payer_id=gov_agent.id, recipient_id=provider.id,
                        amount=cost_per_cure,
                        source_id=operation_id,
                        detail={'patient_id': a.id, 'disease': dis,
                                'payer': 'government'})
                    cash_transfer_event_id = trace_medical_payment(
                        gov_agent, provider, a, dis, cost_per_cure, 'public',
                        payer_cash_before, provider_cash_before, operation_id,
                        actor_account_event, account_event_ids)
                    cash_settlement = 'government_to_provider_cash_transfer'
                    if cash_transfer_event_id is not None:
                        public_transfer_event_ids.append(cash_transfer_event_id)
                        medical_transfer_event_ids.append(cash_transfer_event_id)
                else:
                    public_change = begin_public_change(region, gov_agent)
                    gov_agent.cash += cost_per_cure  # Self-administered municipal hospital
                    account_event_ids.extend(finish_public_change(
                        public_change, 'public_medical_self_refund',
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                    non_transfer_treatments += 1

                spending_pub += cost_per_cure
                treated_count += 1
                public_treated_count += 1
                a.medical_treatments_count = getattr(a, 'medical_treatments_count', 0) + 1

                cure_draw = r.random()
                cured = cure_draw < effective_cure
                emit(region, kind='medical_treatment', record_class='outcome',
                     subject={'type': 'tile', 'id': region.name,
                              'agent_id': getattr(a, 'id', None), 'disease': dis},
                     metric_id='health.medical_treatment', unit='treatment',
                     before=1, after=0 if cured else 1,
                     formula_id='medicine.cure_chance.v1',
                     inputs={'payer': 'public', 'treatment_cost': cost_per_cure,
                             'effective_cure_chance': effective_cure,
                             'cure_draw': cure_draw, 'provider_id': getattr(provider, 'id', None),
                             'provider_is_treasury': provider == gov_agent,
                             'cash_settlement': cash_settlement,
                             'cash_transfer_event_id': cash_transfer_event_id,
                             'operation_id': operation_id,
                             'actor_account_event_id': actor_account_event['id']
                             if actor_account_event is not None else None},
                     cause_event_ids=([cash_transfer_event_id]
                                      if cash_transfer_event_id else account_event_ids or None))
                if cured:
                    cured_this_turn.append(dis)
                    a.health_attrition = max(0.0, getattr(a, 'health_attrition', 0.0) - 0.15)
            elif a.cash >= cost_per_cure:
                # Private out-of-pocket medical bill: patient pays
                cash_transfer_event_id = None
                actor_account_event = None
                operation_id = (f'medical-care:{region.name}:{int(t)}:'
                                f'{a.id}:{dis}:{disease_index}:private')
                account_event_ids = []
                cash_settlement = 'no_external_provider_cash_transfer'
                payer_cash_before = float(a.cash)
                public_change = begin_public_change(region, a)
                a.cash -= cost_per_cure
                account_event_ids.extend(finish_public_change(
                    public_change, 'medical_patient_payment_debit',
                    inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                if provider and provider != a:
                    provider_cash_before = float(provider.cash)
                    public_change = begin_public_change(region, provider)
                    provider.cash += cost_per_cure
                    account_event_ids.extend(finish_public_change(
                        public_change, 'medical_provider_receipt',
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                    emit_public_account_flow(
                        region, provider, kind='medical_public_provider_receipt',
                        signed_amount=cost_per_cure,
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis},
                        cause_event_ids=account_event_ids or None)
                    from economy.actor_accounts import record as record_economic_event
                    operation_id = (f'medical-care:{region.name}:{int(t)}:'
                                    f'{a.id}:{dis}:{disease_index}:private')
                    actor_account_event = record_economic_event(
                        region, 'medical_care', turn=t,
                        payer_id=a.id, recipient_id=provider.id,
                        amount=cost_per_cure,
                        source_id=operation_id,
                        detail={'patient_id': a.id, 'disease': dis,
                                'payer': 'patient'})
                    cash_transfer_event_id = trace_medical_payment(
                        a, provider, a, dis, cost_per_cure, 'private',
                        payer_cash_before, provider_cash_before, operation_id,
                        actor_account_event, account_event_ids)
                    private_transfers += cost_per_cure
                    if cash_transfer_event_id is not None:
                        medical_transfer_event_ids.append(cash_transfer_event_id)
                    cash_settlement = 'patient_to_provider_cash_transfer'
                else:
                    public_change = begin_public_change(region, a)
                    a.cash += cost_per_cure  # Self-purchase of folk remedy
                    account_event_ids.extend(finish_public_change(
                        public_change, 'medical_patient_self_refund',
                        inputs={'operation_id': operation_id, 'patient_id': a.id, 'disease': dis}))
                    non_transfer_treatments += 1

                spending_priv += cost_per_cure
                a.medical_expenses_paid = getattr(a, 'medical_expenses_paid', 0.0) + cost_per_cure
                treated_count += 1
                a.medical_treatments_count = getattr(a, 'medical_treatments_count', 0) + 1

                cure_draw = r.random()
                cured = cure_draw < effective_cure
                emit(region, kind='medical_treatment', record_class='outcome',
                     subject={'type': 'tile', 'id': region.name,
                              'agent_id': getattr(a, 'id', None), 'disease': dis},
                     metric_id='health.medical_treatment', unit='treatment',
                     before=1, after=0 if cured else 1,
                     formula_id='medicine.cure_chance.v1',
                     inputs={'payer': 'patient', 'treatment_cost': cost_per_cure,
                             'effective_cure_chance': effective_cure,
                             'cure_draw': cure_draw, 'provider_id': getattr(provider, 'id', None),
                             'cash_settlement': cash_settlement,
                             'cash_transfer_event_id': cash_transfer_event_id,
                             'operation_id': operation_id,
                             'actor_account_event_id': actor_account_event['id']
                             if actor_account_event is not None else None},
                     cause_event_ids=([cash_transfer_event_id]
                                      if cash_transfer_event_id else account_event_ids or None))
                if cured:
                    cured_this_turn.append(dis)
                    a.health_attrition = max(0.0, getattr(a, 'health_attrition', 0.0) - 0.10)
            else:
                # Cannot afford treatment! Disease festers
                untreated_count += 1
                a.health_attrition = min(2.5, getattr(a, 'health_attrition', 0.0) + 0.04)
                a.despair = min(1.0, getattr(a, 'despair', 0.0) + 0.05)
                untreated_event_id = emit(
                    region, kind='medical_treatment_unaffordable',
                    record_class='outcome',
                    subject={'type': 'tile', 'id': region.name,
                             'agent_id': getattr(a, 'id', None), 'disease': dis},
                    metric_id='health.medical_treatment', unit='treatment',
                    before=1, after=1,
                    inputs={'treatment_cost': cost_per_cure,
                            'patient_cash': float(a.cash),
                            'public_care_available': is_public_healthcare,
                            'public_funds_available': float(
                                gov_agent.cash if gov_agent else 0.0),
                            'reason': 'patient_and_available_public_funds_below_cost'})
                untreated_case_rows.append({
                    'patient_id': getattr(a, 'id', None), 'disease': dis,
                    'treatment_cost': float(cost_per_cure),
                    'patient_cash': float(a.cash),
                    'public_care_available': bool(is_public_healthcare),
                    'public_funds_available': float(
                        gov_agent.cash if gov_agent else 0.0),
                    'reason': 'unaffordable',
                    'event_id': untreated_event_id,
                })
                if untreated_event_id is not None:
                    untreated_event_ids.append(untreated_event_id)

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
    from health_trace import record_fatalities
    record_fatalities(region, t, fatalities)

    from run_trace import emit
    for disease, case_ids in case_ids_before_treatment.items():
        emit(region, kind='disease_cases_observed', record_class='calculation',
             subject={'type': 'tile', 'id': region.name, 'disease': disease},
             metric_id='health.disease_cases', unit='people', after=len(case_ids),
             formula_id='disease.count_active_cases.v1',
             inputs={'disease': disease, 'counted_after_treatment': False,
                     'sample_point':'pre_treatment_history','case_agent_ids':case_ids})
    emit(region, kind='medical_care_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='health.medical_spending', unit='local_currency',
         after=spending_priv + spending_pub,
         formula_id='medicine.regional_spending.v1',
         inputs={'private_spending': spending_priv, 'public_spending': spending_pub,
                 'public_transfer_outflow': public_transfers,
                 'private_transfer_outflow': private_transfers,
                 'actual_cash_transfer_outflow': public_transfers + private_transfers,
                 'non_transfer_treatment_count': non_transfer_treatments,
                 'treated_cases': treated_count, 'untreated_cases': untreated_count,
                 'disease_cases_before_treatment': counts,
                 'cost_per_cure': cost_per_cure, 'cure_chance': cure_chance,
                 'public_healthcare': is_public_healthcare,
                 'germ_theory': has_germ_theory, 'pharmaceutical_chemistry': has_pharma,
                 'universal_healthcare': has_universal, 'clinic_present': has_clinic},
         cause_event_ids=medical_transfer_event_ids or None)
    emit(region, kind='disease_untreated_cases_observed', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='health.untreated_cases', unit='cases', after=untreated_count,
         formula_id='health.untreated_case_rollup.v1',
         inputs={'public_healthcare': is_public_healthcare,
                 'cost_per_cure': cost_per_cure, 'public_funds_available':
                 gov_agent.cash if gov_agent else 0.0,
                 'untreated_patients': untreated_case_rows,
                 'replay_count': len(untreated_case_rows),
                 'replay_matches': len(untreated_case_rows) == untreated_count},
         cause_event_ids=untreated_event_ids or None)
    if public_transfers and nation:
        emit(region, kind='public_healthcare_spending', record_class='transfer',
             subject={'type': 'nation', 'id': nation.name},
             metric_id='finance.treasury_flow', unit=nation.currency,
             after=-public_transfers,
             inputs={'region': region.name, 'treated_cases': public_treated_count,
                     'provider_transfers': public_transfers},
             cause_event_ids=public_transfer_event_ids or None)

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
                load_probability = min(0.95, 0.30 + inf_rate * 1.5)
                load_draw = rng.random()
                contagion_before = bool(getattr(rt, 'has_contagion', False))
                if load_draw < load_probability:
                    rt.has_contagion = True
                try:
                    from run_trace import emit
                    emit(r, kind='trade_contagion_loading', record_class='calculation',
                         phase='disease_transmission',
                         subject={'type': 'tile/route', 'id': f'{r.name}->{partner_name}'},
                         metric_id='health.trade_contagion', unit='probability',
                         before=contagion_before, after=bool(getattr(rt, 'has_contagion', False)),
                         formula_id='disease.trade_contagion_load.v1',
                         inputs={'active_infected_people': active_pest,
                                 'source_population': len(getattr(r, 'agents', [])),
                                 'infection_rate': inf_rate,
                                 'load_probability': load_probability,
                                 'random_draw': load_draw,
                                 'route_frozen': bool(getattr(rt, 'is_frozen', False)),
                                 'route_quarantined': bool(getattr(rt, 'is_quarantined', False))})
                except (TypeError, ValueError):
                    pass

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
                try:
                    from run_trace import emit
                    emit(dst, kind='trade_contagion_quarantine_block', record_class='outcome',
                         phase='disease_transmission',
                         subject={'type': 'tile/route', 'id': f'{r.name}->{dst.name}'},
                         metric_id='health.trade_contagion', unit='state', before=True, after=False,
                         formula_id='disease.trade_quarantine_block.v1',
                         inputs={'source_region': r.name, 'destination_region': dst.name,
                                 'destination_quarantine': bool(getattr(dst, 'quarantine_active', False)),
                                 'route_quarantine': bool(getattr(rt, 'is_quarantined', False)),
                                 'delivered_this_turn': bool(getattr(rt, 'delivered_this_turn', None)),
                                 'in_transit': bool(getattr(rt, 'in_transit', None))})
                except (TypeError, ValueError):
                    pass
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
                    try:
                        from run_trace import emit
                        emit(dst, kind='trade_transmitted_infection', record_class='outcome',
                             phase='disease_transmission',
                             subject={'type': 'tile/agent', 'id': str(getattr(patient, 'id', 'unknown'))},
                             metric_id='health.trade_infection', unit='cases', before=0, after=1,
                             formula_id='disease.trade_cargo_transmission.v1',
                             inputs={'source_region': r.name, 'destination_region': dst.name,
                                     'route_id': f'{r.name}->{dst.name}',
                                     'cargo_delivered': bool(getattr(rt, 'delivered_this_turn', None)),
                                     'cargo_in_transit': bool(getattr(rt, 'in_transit', None)),
                                     'vulnerable_people': len(vulnerable),
                                     'infected_people_at_source': active_pest,
                                     'patient_id': str(getattr(patient, 'id', 'unknown')),
                                     'infected_people_after': dst.active_pestilence_count})
                    except (TypeError, ValueError):
                        pass
                    ev = {
                        't': t,
                        'type': 'PLAGUE_TRANSMISSION',
                        'src': r.name,
                        'dst': dst.name,
                        'message': f"PLAGUE SHIP: The Great Pestilence has reached {dst.name} via merchant trade routes from {r.name}!"
                    }
                    events.append(ev)
                    try:
                        from economy.true_cost_ledger import get_true_cost_ledger
                        traders = [a for a in getattr(r, 'trader_agents', []) if getattr(a, 'destination_region', None) is dst]
                        if traders:
                            for tr in traders:
                                get_true_cost_ledger().record_merchant(
                                    tr, r, t,
                                    gross_arbitrage=0.0,
                                    tolls_and_transport=0.0,
                                    infected_seeds=1.0 / len(traders)
                                )
                    except Exception:
                        pass

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
