"""Resident illness petitions and escalation; thresholds are gameplay settings.

The rate is active pollution-associated illness prevalence after treatment,
counting a resident once even with multiple diagnoses. It is not incidence.
"""
from collections import Counter

PETITION_RATE = 0.05
REVOLT_RATE = 0.20
POLLUTION_DISEASES = frozenset(('respiratory', 'waterborne', 'chemical'))


def assess_pollution_health(region, turn):
    residents = [a for a in getattr(region, 'agents', ())
                 if getattr(a, 'alive', True) and not getattr(a, 'is_corporation', False)
                 and not getattr(a, 'is_government', False)
                 and not getattr(a, 'military_unit_id', None)]
    affected = [a for a in residents if POLLUTION_DISEASES.intersection(
        getattr(a, 'diseases', ()) or ())]
    counts = Counter(d for a in affected for d in set(getattr(a, 'diseases', ()) or ())
                     if d in POLLUTION_DISEASES)
    rate = len(affected) / max(1, len(residents))
    petition = float(getattr(region, 'pollution_petition_rate', PETITION_RATE))
    revolt = float(getattr(region, 'pollution_revolt_rate', REVOLT_RATE))
    if not 0 < petition < revolt <= 1:
        raise ValueError('pollution thresholds must satisfy 0 < petition < revolt <= 1')
    stage = 'revolt' if rate >= revolt else 'petition' if rate >= petition else 'quiet'
    previous = getattr(region, 'pollution_health_state', {})
    rebels = [a.id for a in affected if not getattr(a, 'is_trader', False)
              and (not hasattr(a, 'age') or a.age(turn) >= 14)] if stage == 'revolt' else []
    state = {'turn': turn, 'stage': stage, 'rate': rate, 'resident_count': len(residents),
             'affected_count': len(affected), 'disease_counts': dict(counts),
             'petition_threshold': petition, 'revolt_threshold': revolt,
             'revolt_participant_ids': rebels}
    region.pollution_health_state = state
    region.pollution_revolt_ids = set(rebels)
    from run_trace import emit
    event_id = emit(region, kind='pollution_health_assessment', record_class='calculation',
                    subject={'type': 'tile', 'id': region.name},
                    metric_id='politics.pollution_illness_rate', unit='ratio',
                    after=rate, inputs={**state, 'affected_ids': [a.id for a in affected],
                    'rate_basis': 'unique living residents with active pollution-associated illness after treatment'})
    state['assessment_event_id'] = event_id
    if stage != previous.get('stage', 'quiet') or (
            stage != 'quiet' and turn - getattr(region, 'pollution_petition_turn', -5) >= 5):
        kind = 'pollution_control_petition' if stage != 'quiet' else 'pollution_petition_resolved'
        petition_id = emit(region, kind=kind, record_class='outcome',
                          subject={'type': 'tile', 'id': region.name},
                          metric_id='politics.pollution_petition', unit='stage',
                          before=previous.get('stage', 'quiet'), after=stage,
                          inputs=state, cause_event_ids=[event_id] if event_id else [])
        region.pollution_petition_turn = turn
        region.pollution_petition_event_id = petition_id
    return state


def pollution_investment(nation, turn, available_cash):
    """Select one affordable remedy, including during a food emergency.

    Uses normal BuildIntent construction, material acquisition and payments.
    Player nations reach this only through an enabled national AI.
    """
    from buildings import BUILDING_RECIPES
    from intents import BuildIntent
    considered = []
    for tile in sorted(nation.tiles, key=lambda t: -getattr(t, 'pollution_health_state', {}).get('rate', 0)):
        state = getattr(tile, 'pollution_health_state', {})
        if state.get('stage', 'quiet') == 'quiet':
            continue
        names = {b.name for b in getattr(tile, 'buildings', ())}
        counts = state.get('disease_counts', {})
        remedies = []
        if counts.get('respiratory', 0):
            remedies.append(('smoke_scrubber', counts['respiratory']))
        if counts.get('waterborne', 0):
            remedies.append(('water_filtration_plant', counts['waterborne']))
            remedies.append(('trunk_sewer', counts['waterborne']))
        if counts.get('chemical', 0):
            remedies.append(('municipal_clinic', counts['chemical']))
        for name, count in sorted(remedies, key=lambda item: -item[1]):
            if name in names:
                continue
            active = any(p.status in ('in_progress', 'stalled')
                         for p in getattr(tile, 'construction_projects', ()))
            pending = any(getattr(i, 'region_name', None) == tile.name
                          and getattr(i, 'building_type', None) is not None
                          and getattr(i, 'status', None) in ('pending_approval', 'approved')
                          for i in getattr(nation, 'intents', ()))
            cost = BUILDING_RECIPES[name].cost
            feasible = not active and not pending and available_cash >= cost
            considered.append({'candidate': 'pollution_control', 'tile': tile.name,
                               'building': name, 'illness_rate': state['rate'],
                               'cost': cost, 'treasury_total': available_cash,
                               'petition_event_id': getattr(tile, 'pollution_petition_event_id', None),
                               'feasible': feasible, 'reason_code': (
                                   'active_construction_project' if active else
                                   'remedy_already_pending' if pending else
                                   'treasury_below_project_cost' if available_cash < cost else
                                   'illness_petition_response')})
            if feasible:
                return BuildIntent(nation.name, tile.name, name, submitted_turn=turn,
                                   regime_type=nation.regime_type), considered
    return None, considered
