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
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

from typing import Tuple, List, Dict, Any, Optional
from goods import Goods

#: Default statutory workday cap before reform
DEFAULT_WORKDAY_CAP = 16.0
#: Reformed workday cap (Ten-Hour Act)
REFORMED_WORKDAY_CAP = 10.0
#: Strike rate threshold triggering government panic
UPRISING_STRIKE_THRESHOLD = 0.20
#: Unrest threshold triggering government concessions
UPRISING_UNREST_THRESHOLD = 0.60


def _labor_trace_context(target, action_id):
    """Find a trace host and stable operation ID for a policy mutation."""
    candidates = [target]
    candidates.extend(getattr(target, 'tiles', ()))
    region = next((tile for tile in candidates
                   if (getattr(tile, '_run_trace', None) is not None
                       and getattr(tile, '_collective_trace_clock', None)
                       is not None)), None)
    if region is None:
        return None, int(getattr(target, '_last_turn', 0)), None
    clock = region._collective_trace_clock
    turn = int(clock.get('turn', getattr(target, '_last_turn', 0)))
    operation_id = (f"policy:{action_id}:{getattr(target, 'name', 'unnamed')}:"
                    f"{turn}:{int(clock.get('next', 0))}")
    return region, turn, operation_id


def _emit_labor_policy_event(region, *, kind, subject, metric_id, unit,
                             after, inputs, before=None,
                             cause_event_ids=None, record_class='outcome'):
    if region is None:
        return None
    from run_trace import emit
    row = {'kind': kind, 'record_class': record_class,
           'phase': 'policy_action', 'subject': subject,
           'metric_id': metric_id, 'unit': unit, 'after': after,
           'inputs': inputs}
    if before is not None:
        row['before'] = before
    if cause_event_ids:
        row['cause_event_ids'] = cause_event_ids
    return emit(region, **row)


def evaluate_uprising_pressure(nation, t: int) -> List[Dict[str, Any]]:
    """Evaluate nationwide unrest and strike pressure, forcing concessions if critical."""
    events = []
    tiles = getattr(nation, 'tiles', [])
    if not tiles:
        return events

    trace_region, trace_turn, operation_id = _labor_trace_context(
        nation, 'uprising_pressure')

    total_workers = 0
    total_strikers = 0
    total_unrest = 0.0
    total_consciousness = 0.0
    tile_trace_before = []

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
        if trace_region is not None:
            tile_trace_before.append({
                'tile': tile,
                'worker_count': len(workers),
                'striker_count': len(strikers),
                'unrest': float(getattr(tile, 'unrest_level', 0.0)),
                'class_consciousness_average':
                    sum(c_vals) / len(c_vals) if c_vals else 0.0,
            })

    avg_unrest = total_unrest / len(tiles)
    strike_rate = (total_strikers / total_workers) if total_workers > 0 else 0.0
    avg_consciousness = total_consciousness / len(tiles)

    # Crisis evaluated against Coercive Strikebreaking Capacity:
    is_crisis = (strike_rate >= UPRISING_STRIKE_THRESHOLD or avg_unrest >= UPRISING_UNREST_THRESHOLD)

    pressure_event_id = None
    if trace_region is not None:
        pressure_event_id = _emit_labor_policy_event(
            trace_region, kind='uprising_pressure_gate',
            record_class='decision',
            subject={'type': 'nation', 'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.uprising_gate', unit='triggered',
            before=False, after=bool(is_crisis),
            inputs={'operation_id': operation_id, 'turn': int(t),
                    'trace_clock_turn': trace_turn,
                    'worker_count': total_workers,
                    'striker_count': total_strikers,
                    'strike_rate': strike_rate,
                    'strike_rate_threshold': UPRISING_STRIKE_THRESHOLD,
                    'strike_rate_triggered':
                    strike_rate >= UPRISING_STRIKE_THRESHOLD,
                    'average_unrest': avg_unrest,
                    'average_unrest_threshold': UPRISING_UNREST_THRESHOLD,
                    'average_unrest_triggered':
                    avg_unrest >= UPRISING_UNREST_THRESHOLD,
                    'average_class_consciousness': avg_consciousness,
                    'class_consciousness_used_in_gate': False,
                    'tiles': [{'tile_id': row['tile'].name,
                               'workers': row['worker_count'],
                               'strikers': row['striker_count'],
                               'unrest': row['unrest'],
                               'class_consciousness_average':
                               row['class_consciousness_average']}
                              for row in tile_trace_before],
                    'reason': ('strike_or_unrest_threshold_reached'
                               if is_crisis else 'below_both_thresholds')})

    if not is_crisis:
        if trace_region is not None:
            response_id = _emit_labor_policy_event(
                trace_region, kind='uprising_response_decision',
                record_class='decision',
                subject={'type': 'nation',
                         'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.uprising_response', unit='response',
                after='no_crisis',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'trace_clock_turn': trace_turn,
                        'reason': 'pressure_gate_not_triggered'},
                cause_event_ids=([pressure_event_id]
                                 if pressure_event_id else None))
            _emit_labor_policy_event(
                trace_region, kind='uprising_response_outcome',
                subject={'type': 'nation',
                         'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.uprising_outcome', unit='action_result',
                after='no_action',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'trace_clock_turn': trace_turn,
                        'legacy_events_emitted': 0},
                cause_event_ids=([response_id] if response_id else None))
        return events

    if is_crisis:
        ruling = getattr(nation, 'ruling_faction', '')
        # Capitalist/landlord regimes attempt armed strikebreaking if forces are available
        eligible_units = [u for u in getattr(nation, 'military_units', [])
                          if getattr(u, 'soldiers', 0) > 0
                          and getattr(u, 'morale', 1.0) >= 0.40]
        total_military_strength = sum(u.strength for u in eligible_units)
        police_strength = sum(getattr(tile, 'police_employed', 0) * 3.0 for tile in tiles)
        strikebreaker_force = total_military_strength + police_strength
        strike_force = total_strikers * 1.5
        use_armed_repression = (
            ruling in ('Bourgeoisie', 'Gentry')
            and strikebreaker_force >= strike_force
            and strikebreaker_force > 15.0)
        if use_armed_repression:
            planned_response = 'armed_strikebreaking'
            response_reason = 'capitalist_force_threshold_met'
        elif not getattr(nation, 'ten_hour_act', False):
            planned_response = 'ten_hour_act_concession'
            response_reason = 'strikebreaking_unavailable_or_ruling_faction_concedes'
        elif not getattr(nation, 'factory_safety_act', False):
            planned_response = 'factory_safety_concession'
            response_reason = 'ten_hour_act_active_and_safety_mandate_available'
        else:
            planned_response = 'no_additional_concession_available'
            response_reason = 'labor_concessions_already_enacted'
        response_decision_id = None
        if trace_region is not None:
            response_decision_id = _emit_labor_policy_event(
                trace_region, kind='uprising_response_decision',
                record_class='decision',
                subject={'type': 'nation',
                         'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.uprising_response', unit='response',
                after=planned_response,
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'ruling_faction': ruling,
                        'military_strength_eligible': total_military_strength,
                        'eligible_military_units': [
                            {'unit_id': str(getattr(unit, 'name',
                                                    getattr(unit, 'id', 'unit'))),
                             'strength': float(unit.strength),
                             'soldiers': int(getattr(unit, 'soldiers', 0)),
                             'morale': float(getattr(unit, 'morale', 1.0))}
                            for unit in eligible_units],
                        'police_strength': police_strength,
                        'police_contributions': [
                            {'tile_id': tile.name,
                             'officers': int(getattr(tile, 'police_employed', 0)),
                             'strength': float(getattr(tile, 'police_employed', 0)) * 3.0}
                            for tile in tiles],
                        'strikebreaker_force': strikebreaker_force,
                        'strike_force': strike_force,
                        'force_sufficient': strikebreaker_force >= strike_force,
                        'minimum_force_required': 15.0,
                        'ten_hour_act_active':
                        bool(getattr(nation, 'ten_hour_act', False)),
                        'factory_safety_act_active':
                        bool(getattr(nation, 'factory_safety_act', False)),
                        'reason': response_reason},
                cause_event_ids=([pressure_event_id]
                                 if pressure_event_id else None))

        # If capitalist regime has superior force, crush strike with armed strikebreaking
        if use_armed_repression:
            tile_event_ids = []
            for index, tile in enumerate(tiles):
                unrest_before = (tile_trace_before[index]['unrest']
                                 if trace_region is not None else None)
                from collective_politics import record_authority_incident
                affected = [a.id for a in getattr(tile, 'agents', [])
                            if getattr(a, 'is_striking', False) and getattr(a, 'alive', True)]
                authority_affected_count = 0
                if affected:
                    authority_affected_count = record_authority_incident(
                        tile, t, f'{nation.name}:{t}:armed_strikebreaking', nation,
                        affected, repression=.5, attribution=1.0)
                cleared_strike_ids = []
                for a in getattr(tile, 'agents', []):
                    if getattr(a, 'is_striking', False):
                        cleared_strike_ids.append(str(a.id))
                        a.is_striking = False
                        a.mem_push('mem_casualties', 1.0)
                        a.mem_push('mem_promises', 1.0)
                tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.15)
                if trace_region is not None:
                    workers_after = [a for a in getattr(tile, 'agents', [])
                                     if getattr(a, 'social_class', '') in (
                                         'proletarian', 'serf', 'tenant',
                                         'dispossessed')
                                     and getattr(a, 'alive', True)]
                    strikers_after = sum(
                        1 for worker in workers_after
                        if getattr(worker, 'is_striking', False))
                    before = tile_trace_before[index]
                    strike_event_id = _emit_labor_policy_event(
                        trace_region, kind='uprising_strikebreaking_tile_effect',
                        subject={'type': 'tile', 'id': tile.name},
                        metric_id='labor.strikers', unit='people',
                        before=before['striker_count'], after=strikers_after,
                        inputs={'operation_id': operation_id, 'turn': int(t),
                                'eligible_workers': before['worker_count'],
                                'strike_statuses_cleared': len(cleared_strike_ids),
                                'cleared_agent_ids': cleared_strike_ids,
                                'casualty_memory_seeded': len(cleared_strike_ids),
                                'promise_memory_seeded': len(cleared_strike_ids),
                                'authority_incident_affected_residents':
                                authority_affected_count,
                                'authority_repression': 0.5},
                        cause_event_ids=([response_decision_id]
                                         if response_decision_id else None))
                    unrest_event_id = _emit_labor_policy_event(
                        trace_region, kind='uprising_strikebreaking_unrest_effect',
                        subject={'type': 'tile', 'id': tile.name},
                        metric_id='politics.unrest_level', unit='ratio',
                        before=unrest_before,
                        after=float(getattr(tile, 'unrest_level', 0.0)),
                        inputs={'operation_id': operation_id, 'turn': int(t),
                                'requested_reduction': 0.15,
                                'floor': 0.0,
                                'actual_change': float(tile.unrest_level)
                                - unrest_before},
                        cause_event_ids=([response_decision_id]
                                         if response_decision_id else None))
                    tile_event_ids.extend(event_id for event_id in
                                          (strike_event_id, unrest_event_id)
                                          if event_id)
            ev = {
                'kind': 'armed_strikebreaking',
                'turn': t,
                'nation': nation.name,
                'strikebreaker_force': strikebreaker_force,
                'strike_force': strike_force,
                'msg': f"ARMED REPRESSION: {nation.name} deployed troops and police to crush mass strikes! (Force: {strikebreaker_force:.1f} vs Strikers: {strike_force:.1f})",
            }
            from collective_trace_clock import stamp
            stamp(tiles[0], ev)
            events.append(ev)
            nation.regime_log.append(ev)
            if trace_region is not None:
                _emit_labor_policy_event(
                    trace_region, kind='uprising_response_outcome',
                    subject={'type': 'nation',
                             'id': getattr(nation, 'name', 'unnamed')},
                    metric_id='scenario.uprising_outcome',
                    unit='action_result', after='armed_strikebreaking_applied',
                    inputs={'operation_id': operation_id, 'turn': int(t),
                            'response': planned_response,
                            'tile_count': len(tiles),
                            'strikers_cleared': total_strikers,
                            'legacy_events_emitted': 1},
                    cause_event_ids=([response_decision_id] + tile_event_ids
                                     if response_decision_id else
                                     tile_event_ids or None))
        else:
            # State lacks coercive capacity to break the strike, or has pro-worker ruling faction -> Concession!
            response_applied = False
            response_message = None
            unrest_reduction = 0.0
            legitimacy_change = 0.0
            authority_reform_residents = 0
            legitimacy_before = (float(getattr(nation, 'legitimacy', 0.5))
                                 if trace_region is not None else None)
            # Step 1: Enact Ten-Hour Act if not already enacted
            if not getattr(nation, 'ten_hour_act', False):
                prior_hours = {a.id: float(getattr(a, 'shift_hours', 8.0))
                               for tile in tiles for a in getattr(tile, 'agents', [])
                               if getattr(a, 'is_corporation', False)}
                ok, msg = enact_ten_hour_act(nation)
                if ok:
                    from collective_politics import record_authority_incident
                    for tile in tiles:
                        affected = [employee.id for firm in getattr(tile, 'agents', [])
                                    if getattr(firm, 'is_corporation', False)
                                    and float(getattr(firm, 'shift_hours', 8.0))
                                    < prior_hours.get(firm.id, 8.0)
                                    for employee in getattr(firm, 'employees', [])
                                    if getattr(employee, 'alive', True)]
                        if affected:
                            authority_reform_residents += record_authority_incident(
                                tile, t, f'{nation.name}:{t}:ten_hour_act', nation,
                                affected, reform=.5, attribution=1.0)
                    # Concession cools down worker unrest
                    for tile in tiles:
                        tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.25)
                    nation.legitimacy = min(1.0, getattr(nation, 'legitimacy', 0.5) + 0.15)
                    response_applied = True
                    response_message = msg
                    unrest_reduction = 0.25
                    legitimacy_change = 0.15
                    ev = {
                        'kind': 'ten_hour_act_concession',
                        'turn': t,
                        'nation': nation.name,
                        'strike_rate': strike_rate,
                        'unrest': avg_unrest,
                        'msg': "Mass strikes and economic paralysis forced the government to pass the Ten-Hour Act!",
                    }
                    from collective_trace_clock import stamp
                    stamp(tiles[0], ev)
                    events.append(ev)
                    nation.regime_log.append(ev)
            # Step 2: If Ten-Hour Act already passed, enact Factory Safety Act
            elif not getattr(nation, 'factory_safety_act', False):
                ok, msg = enact_factory_safety_act(nation)
                if ok:
                    for tile in tiles:
                        tile.unrest_level = max(0.0, getattr(tile, 'unrest_level', 0.0) - 0.20)
                    nation.legitimacy = min(1.0, getattr(nation, 'legitimacy', 0.5) + 0.10)
                    response_applied = True
                    response_message = msg
                    unrest_reduction = 0.20
                    legitimacy_change = 0.10
                    ev = {
                        'kind': 'factory_safety_concession',
                        'turn': t,
                        'nation': nation.name,
                        'strike_rate': strike_rate,
                        'msg': "Labor unrest forced the government to mandate Factory Safety Standards!",
                    }
                    from collective_trace_clock import stamp
                    stamp(tiles[0], ev)
                    events.append(ev)
                    nation.regime_log.append(ev)
            if trace_region is not None:
                effect_event_ids = []
                for index, tile in enumerate(tiles):
                    unrest_before = tile_trace_before[index]['unrest']
                    unrest_after = float(getattr(tile, 'unrest_level', 0.0))
                    event_id = _emit_labor_policy_event(
                        trace_region, kind='uprising_concession_unrest_effect',
                        subject={'type': 'tile', 'id': tile.name},
                        metric_id='politics.unrest_level', unit='ratio',
                        before=unrest_before, after=unrest_after,
                        inputs={'operation_id': operation_id, 'turn': int(t),
                                'response': planned_response,
                                'requested_reduction': unrest_reduction,
                                'floor': 0.0,
                                'actual_change': unrest_after - unrest_before,
                                'concession_applied': response_applied},
                        cause_event_ids=([response_decision_id]
                                         if response_decision_id else None))
                    if event_id:
                        effect_event_ids.append(event_id)
                if response_applied and legitimacy_change:
                    legitimacy_event_id = _emit_labor_policy_event(
                        trace_region, kind='uprising_concession_legitimacy_effect',
                        subject={'type': 'nation',
                                 'id': getattr(nation, 'name', 'unnamed')},
                        metric_id='politics.legitimacy', unit='ratio',
                        before=legitimacy_before,
                        after=float(getattr(nation, 'legitimacy', 0.5)),
                        inputs={'operation_id': operation_id, 'turn': int(t),
                                'response': planned_response,
                                'requested_increase': legitimacy_change,
                                'authority_reform_residents':
                                authority_reform_residents},
                        cause_event_ids=([response_decision_id]
                                         if response_decision_id else None))
                    if legitimacy_event_id:
                        effect_event_ids.append(legitimacy_event_id)
                outcome = (f'{planned_response}_applied' if response_applied
                           else 'concession_not_applied'
                           if planned_response != 'no_additional_concession_available'
                           else 'no_additional_concession_available')
                _emit_labor_policy_event(
                    trace_region, kind='uprising_response_outcome',
                    subject={'type': 'nation',
                             'id': getattr(nation, 'name', 'unnamed')},
                    metric_id='scenario.uprising_outcome',
                    unit='action_result', after=outcome,
                    inputs={'operation_id': operation_id, 'turn': int(t),
                            'response': planned_response,
                            'response_applied': response_applied,
                            'response_message': response_message,
                            'unrest_reduction_requested': unrest_reduction,
                            'legitimacy_increase_requested': legitimacy_change,
                            'legitimacy_after':
                            float(getattr(nation, 'legitimacy', 0.5)),
                            'ten_hour_act_active':
                            bool(getattr(nation, 'ten_hour_act', False)),
                            'factory_safety_act_active':
                            bool(getattr(nation, 'factory_safety_act', False)),
                            'legacy_events_emitted': len(events)},
                    cause_event_ids=([response_decision_id] + effect_event_ids
                                     if response_decision_id else
                                     effect_event_ids or None))

    return events


def capitalist_electoral_backlash(nation, candidates: list, t: int) -> float:
    """Capitalists pool money into a PAC to fund opposition and oust pro-labor incumbents.

    Returns total campaign funds donated by capitalists to the opposition candidate.
    """
    trace_region, trace_turn, operation_id = _labor_trace_context(
        nation, 'capitalist_electoral_backlash')
    # Only triggers if pro-labor legislation has threatened profits.
    has_candidates = bool(candidates)
    has_labor_laws = (getattr(nation, 'ten_hour_act', False) or
                      getattr(nation, 'factory_safety_act', False) or
                      getattr(nation, 'max_workday_hours', 16.0) < 14.0)
    gate_event_id = None
    if trace_region is not None:
        gate_event_id = _emit_labor_policy_event(
            trace_region, kind='capitalist_backlash_gate',
            record_class='decision',
            subject={'type': 'nation', 'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.capitalist_backlash_gate', unit='triggered',
            before=False, after=bool(has_candidates and has_labor_laws),
            inputs={'operation_id': operation_id, 'turn': int(t),
                    'trace_clock_turn': trace_turn,
                    'candidate_count': len(candidates),
                    'ten_hour_act_active':
                    bool(getattr(nation, 'ten_hour_act', False)),
                    'factory_safety_act_active':
                    bool(getattr(nation, 'factory_safety_act', False)),
                    'maximum_workday_hours': float(
                        getattr(nation, 'max_workday_hours', 16.0)),
                    'labor_law_trigger': bool(has_labor_laws),
                    'reason': ('no_candidates' if not has_candidates else
                               'no_pro_labor_laws' if not has_labor_laws else
                               'capitalist_backlash_available')})
    if not has_candidates:
        if trace_region is not None:
            _emit_labor_policy_event(
                trace_region, kind='capitalist_backlash_outcome',
                subject={'type': 'nation', 'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.capitalist_backlash_outcome', unit='result',
                after='no_candidates',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'total_donations': 0.0},
                cause_event_ids=([gate_event_id] if gate_event_id else None))
        return 0.0
    if not has_labor_laws:
        if trace_region is not None:
            _emit_labor_policy_event(
                trace_region, kind='capitalist_backlash_outcome',
                subject={'type': 'nation', 'id': getattr(nation, 'name', 'unnamed')},
                metric_id='scenario.capitalist_backlash_outcome', unit='result',
                after='blocked_no_pro_labor_laws',
                inputs={'operation_id': operation_id, 'turn': int(t),
                        'total_donations': 0.0},
                cause_event_ids=([gate_event_id] if gate_event_id else None))
        return 0.0

    incumbent_faction = getattr(nation, '_incumbent_faction', None)
    # Find candidates who are NOT the incumbent faction (preferably backed by capitalists/merchants/lords)
    opponents = [c for c in candidates if c.backing_faction != incumbent_faction]
    if not opponents:
        opponents = candidates

    # Prefer opponent backed by conservative/capitalist faction, or highest charisma
    target_cand = max(opponents, key=lambda c: getattr(c.agent, 'charisma', 0.0))

    selection_event_id = None
    if trace_region is not None:
        selection_event_id = _emit_labor_policy_event(
            trace_region, kind='capitalist_backlash_candidate_selection',
            record_class='decision',
            subject={'type': 'nation/candidate',
                     'id': str(getattr(target_cand.agent, 'id', 'candidate'))},
            metric_id='scenario.capitalist_backlash_selection', unit='selected',
            after='target_selected',
            inputs={'operation_id': operation_id, 'turn': int(t),
                    'incumbent_faction': incumbent_faction,
                    'opponent_candidate_count': len(opponents),
                    'all_candidates_were_incumbent_faction': not bool(
                        [c for c in candidates
                         if c.backing_faction != incumbent_faction]),
                    'selection_rule': 'highest_charisma_among_non_incumbent_candidates_or_all_candidates',
                    'candidates': [
                        {'agent_id': str(getattr(candidate.agent, 'id', 'candidate')),
                         'backing_faction': candidate.backing_faction,
                         'charisma': float(getattr(candidate.agent, 'charisma', 0.0)),
                         'popularity': float(candidate.popularity)}
                        for candidate in candidates],
                    'selected_candidate_id':
                    str(getattr(target_cand.agent, 'id', 'candidate')),
                    'selected_faction': target_cand.backing_faction},
            cause_event_ids=([gate_event_id] if gate_event_id else None))

    total_donations = 0.0
    currency = getattr(nation, 'currency', None)
    campaign_currency = currency or 'local_currency'
    transfer_event_ids = []
    popularity_event_ids = []
    donor_decision_event_ids = []
    candidate_receipt_event_ids = {'cash': None, 'wallet': None}
    donations_count = 0
    candidate_popularity_before = (float(target_cand.popularity)
                                   if trace_region is not None else None)

    def available_currency(agent):
        home = getattr(agent, 'home_currency', currency)
        if not currency or home == currency:
            return max(0.0, float(getattr(agent, 'cash', 0.0))), 'cash'
        from forex import fx_balance
        return max(0.0, float(fx_balance(agent, currency))), 'wallet'

    def debit_currency(agent, amount, holding):
        if holding == 'cash':
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash -= amount
            _trace_public_finish(_trace_cash_write, 'labor_politics:capitalist_electoral_backlash.debit_currency',
                                 inputs={"source_writer": 'labor_politics.py:capitalist_electoral_backlash.debit_currency:fbfa5fc13d12de52:1'})
        else:
            from forex import fx_sub
            fx_sub(agent, currency, amount)

    def credit_currency(agent, amount):
        home = getattr(agent, 'home_currency', currency)
        if not currency or home == currency:
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash += amount
            _trace_public_finish(_trace_cash_write, 'labor_politics:capitalist_electoral_backlash.credit_currency',
                                 inputs={"source_writer": 'labor_politics.py:capitalist_electoral_backlash.credit_currency:8563f56b467b33b3:1'})
        else:
            from forex import fx_add
            fx_add(agent, currency, amount)

    def holding_balance(agent, holding):
        if holding == 'cash':
            return float(getattr(agent, 'cash', 0.0))
        from forex import fx_balance
        return float(fx_balance(agent, currency))

    for tile in getattr(nation, 'tiles', []):
        for a in getattr(tile, 'agents', []):
            if not getattr(a, 'alive', True):
                continue
            is_capitalist = (getattr(a, 'social_class', '') in ('capitalist', 'industrialist', 'landlord', 'lord')
                             or getattr(a, 'is_corporation', False))
            liquid, holding = available_currency(a)
            donation = (round((liquid - 20.0) * 0.15, 2)
                        if is_capitalist and liquid > 25.0 else 0.0)
            donor_decision_id = None
            if trace_region is not None and is_capitalist:
                donor_decision_id = _emit_labor_policy_event(
                    trace_region, kind='capitalist_backlash_donor_decision',
                    record_class='decision',
                    subject={'type': 'agent', 'id': str(a.id), 'tile': tile.name},
                    metric_id='scenario.capitalist_backlash_donor',
                    unit=campaign_currency, after=donation if donation > 0.5 else 0.0,
                    inputs={'operation_id': operation_id, 'turn': int(t),
                            'donor_class': getattr(a, 'social_class', ''),
                            'is_corporation': bool(
                                getattr(a, 'is_corporation', False)),
                            'liquid_balance': liquid,
                            'holding': holding,
                            'liquid_balance_threshold': 25.0,
                            'surplus_reserve': 20.0,
                            'donation_rate': 0.15,
                            'minimum_donation': 0.5,
                            'calculated_donation': donation,
                            'eligible': bool(liquid > 25.0 and donation > 0.5),
                            'reason': ('capitalist_surplus_available'
                                       if liquid > 25.0 and donation > 0.5 else
                                       'liquidity_threshold_not_met'
                                       if liquid <= 25.0 else
                                       'donation_below_minimum'),
                            'target_candidate_id': str(
                                getattr(target_cand.agent, 'id', 'candidate'))},
                    cause_event_ids=([selection_event_id]
                                     if selection_event_id else None))
                if donor_decision_id:
                    donor_decision_event_ids.append(donor_decision_id)
            if is_capitalist and liquid > 25.0:
                # Donate 15% of surplus liquid cash to defeat the reformist incumbent
                if donation > 0.5:
                    source_balance_before = holding_balance(a, holding)
                    recipient_home = getattr(target_cand.agent, 'home_currency', currency)
                    recipient_holding = (
                        'cash' if not currency or recipient_home == currency
                        else 'wallet')
                    recipient_balance_before = holding_balance(
                        target_cand.agent, recipient_holding)
                    popularity_before = float(target_cand.popularity)
                    debit_currency(a, donation, holding)
                    credit_currency(target_cand.agent, donation)
                    source_balance_after = holding_balance(a, holding)
                    recipient_balance_after = holding_balance(
                        target_cand.agent, recipient_holding)
                    # Popularity boost diluted by charisma
                    charisma = getattr(target_cand.agent, 'charisma', 0.5)
                    gain = donation * (0.5 + 0.5 * charisma) * (1.0 / 1500.0)
                    target_cand.popularity += gain
                    total_donations += donation
                    donations_count += 1
                    if trace_region is not None:
                        from finance_trace import account_ref, transfer_contract
                        from run_trace import emit
                        transfer_id = (f'capitalist-backlash:{getattr(nation, "name", "nation")}:'
                                       f'{int(t)}:{a.id}:{target_cand.agent.id}')
                        contract = transfer_contract(
                            operation_id, 'capitalist_electoral_backlash',
                            side='payer', amount=donation,
                            amount_currency=campaign_currency,
                            payer_account=account_ref(
                                'agent_cash' if holding == 'cash' else 'agent_fx_wallet',
                                str(a.id), campaign_currency, tile=tile.name,
                                balance_before=source_balance_before,
                                balance_after=source_balance_after,
                                balance_scope=('cash' if holding == 'cash' else
                                               'wallet_balance')),
                            payee_account=account_ref(
                                'agent_cash' if recipient_holding == 'cash'
                                else 'agent_fx_wallet',
                                str(target_cand.agent.id), campaign_currency,
                                tile=tile.name,
                                balance_before=recipient_balance_before,
                                balance_after=recipient_balance_after,
                                balance_scope=('cash' if recipient_holding == 'cash'
                                               else 'wallet_balance')),
                            local_cash_leg_amount=donation,
                            local_cash_leg_currency=campaign_currency,
                            currency_conversion_applied=False,
                            counterparty_leg_status='both_account_balances_captured',
                            transfer_id=transfer_id,
                            source_tile=tile.name,
                            donor_holding=holding,
                            candidate_holding=recipient_holding,
                            source='capitalist_electoral_backlash', turn=int(t))
                        transfer_causes = []
                        if donor_decision_id:
                            transfer_causes.append(donor_decision_id)
                        prior_receipt_id = candidate_receipt_event_ids.get(
                            recipient_holding)
                        if prior_receipt_id:
                            transfer_causes.append(prior_receipt_id)
                        if not transfer_causes and selection_event_id:
                            transfer_causes.append(selection_event_id)
                        transfer_event_id = emit(
                            trace_region, kind='capitalist_backlash_donation',
                            record_class='transfer', phase='policy_action',
                            subject={'type': 'election_campaign',
                                     'id': transfer_id,
                                     'candidate_id': target_cand.agent.id,
                                     'tile': tile.name},
                            metric_id='finance.election_campaign',
                            unit=campaign_currency, after=donation,
                            inputs={'operation_id': operation_id,
                                    'transfer_contract': contract,
                                    'donor_id': str(a.id),
                                    'candidate_id': str(target_cand.agent.id),
                                    'donor_holding': holding,
                                    'candidate_holding': recipient_holding},
                            cause_event_ids=transfer_causes or None)
                        if transfer_event_id:
                            transfer_event_ids.append(transfer_event_id)
                            candidate_receipt_event_ids[
                                recipient_holding] = transfer_event_id
                        popularity_event_id = _emit_labor_policy_event(
                            trace_region,
                            kind='capitalist_backlash_popularity_effect',
                            subject={'type': 'nation/candidate',
                                     'id': str(target_cand.agent.id)},
                            metric_id='politics.candidate_popularity',
                            unit='points', before=popularity_before,
                            after=float(target_cand.popularity),
                            inputs={'operation_id': operation_id,
                                    'turn': int(t), 'donation': donation,
                                    'charisma': float(charisma),
                                    'charisma_dilution': 0.5 + 0.5 * charisma,
                                    'popularity_per_dollar': 1.0 / 1500.0,
                                    'popularity_gain': gain,
                                    'transfer_id': transfer_id},
                            cause_event_ids=([transfer_event_id,
                                              donor_decision_id]
                                             if transfer_event_id and
                                             donor_decision_id else
                                             [transfer_event_id]
                                             if transfer_event_id else
                                             [donor_decision_id]
                                             if donor_decision_id else None))
                        if popularity_event_id:
                            popularity_event_ids.append(popularity_event_id)

    if total_donations > 0:
        ev = {
            'kind': 'capitalist_pac_backlash',
            'turn': t,
            'amount': total_donations,
            'favored_candidate': getattr(target_cand.agent, 'id', -1),
            'target_faction': target_cand.backing_faction,
        }
        nation.regime_log.append(ev)

    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='capitalist_backlash_outcome',
            subject={'type': 'nation/candidate',
                     'id': str(target_cand.agent.id)},
            metric_id='scenario.capitalist_backlash_outcome', unit='result',
            after='contributions_received' if total_donations > 0
            else 'no_eligible_donations',
            inputs={'operation_id': operation_id, 'turn': int(t),
                    'candidate_id': str(target_cand.agent.id),
                    'target_faction': target_cand.backing_faction,
                    'donor_count': donations_count,
                    'total_donations': total_donations,
                    'donation_currency': campaign_currency,
                    'candidate_popularity_before': candidate_popularity_before,
                    'candidate_popularity_after':
                    float(target_cand.popularity),
                    'popularity_gain_total':
                    float(target_cand.popularity) - candidate_popularity_before,
                    'transfer_event_count': len(transfer_event_ids)},
            cause_event_ids=([selection_event_id] + donor_decision_event_ids
                             + transfer_event_ids + popularity_event_ids
                             if selection_event_id else
                             donor_decision_event_ids + transfer_event_ids
                             + popularity_event_ids or
                             ([gate_event_id] if gate_event_id else None)))

    return total_donations


def repeal_labor_laws(nation) -> Dict[str, Any]:
    """Repeal pro-labor legislation when a capitalist/reactionary regime takes power."""
    tiles = getattr(nation, 'tiles', [])
    trace_region, turn, operation_id = _labor_trace_context(
        nation, 'repeal_labor_laws')
    ten_hour_before = bool(getattr(nation, 'ten_hour_act', False))
    national_workday_before = float(getattr(nation, 'max_workday_hours', 16.0))
    safety_before = bool(getattr(nation, 'factory_safety_act', False))
    repeal_workday = (ten_hour_before or national_workday_before < 14.0)
    repeal_safety = safety_before
    other_law_state = {
        'statute_of_laborers_active': bool(
            getattr(nation, 'statute_of_laborers', False)),
        'maximum_wage_cap': (
            float(nation.maximum_wage_cap)
            if getattr(nation, 'maximum_wage_cap', None) is not None else None),
        'anti_truck_act_active': bool(
            getattr(nation, 'truck_act_enacted', False)),
    }
    tile_snapshots = []
    if trace_region is not None:
        for tile in tiles:
            tile_workday_before = float(getattr(
                tile, 'max_workday_hours', national_workday_before))
            tile_workday_cap_before = getattr(tile, 'workday_cap', None)
            if tile_workday_cap_before is None:
                tile_workday_cap_before = tile_workday_before
            tile_snapshots.append({
                'tile': tile,
                'workday_before': tile_workday_before,
                'workday_cap_before': float(tile_workday_cap_before),
                'ten_hour_act_before': bool(getattr(tile, 'ten_hour_act', False)),
                'safety_before': bool(getattr(tile, 'factory_safety_act', False)),
                'firms': [
                    (agent, float(agent.shift_hours))
                    for agent in getattr(tile, 'agents', [])
                    if getattr(agent, 'is_corporation', False)
                    and hasattr(agent, 'shift_hours')],
            })
    decision_event_id = None
    if trace_region is not None:
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='labor_law_repeal_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.labor_law_gate', unit='accepted',
            before=False, after=bool(repeal_workday or repeal_safety),
            inputs={'operation_id': operation_id, 'turn': turn,
                    'workday_repeal_triggered': repeal_workday,
                    'ten_hour_act_before': ten_hour_before,
                    'national_workday_before': national_workday_before,
                    'factory_safety_repeal_triggered': repeal_safety,
                    'factory_safety_act_before': safety_before,
                    'tile_count': len(tiles),
                    'other_laws_active_but_not_handled': other_law_state,
                    'reason': ('supported_labor_law_active'
                               if repeal_workday or repeal_safety else
                               'no_supported_labor_law_to_repeal')})

    repealed = []
    if repeal_workday:
        nation.ten_hour_act = False
        nation.max_workday_hours = DEFAULT_WORKDAY_CAP
        for tile in tiles:
            tile.max_workday_hours = DEFAULT_WORKDAY_CAP
        repealed.append("Ten-Hour Act (workday restored to 16h)")

    if repeal_safety:
        nation.factory_safety_act = False
        for tile in tiles:
            tile.factory_safety_act = False
        repealed.append("Factory Safety Standards (regulations dismantled)")

    if trace_region is not None:
        tile_event_ids = []
        firm_event_ids = []
        for snapshot in tile_snapshots:
            tile = snapshot['tile']
            if repeal_workday:
                tile_workday_after = float(getattr(
                    tile, 'max_workday_hours', DEFAULT_WORKDAY_CAP))
                tile_workday_cap_after = getattr(tile, 'workday_cap', None)
                if tile_workday_cap_after is None:
                    tile_workday_cap_after = tile_workday_after
                event_id = _emit_labor_policy_event(
                    trace_region, kind='labor_law_repeal_workday_tile_outcome',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='labor.statutory_workday', unit='hours',
                    before=snapshot['workday_before'],
                    after=float(getattr(tile, 'max_workday_hours', 16.0)),
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'national_ten_hour_act_before': ten_hour_before,
                            'national_ten_hour_act_after':
                            bool(getattr(nation, 'ten_hour_act', False)),
                            'tile_ten_hour_act_before':
                            snapshot['ten_hour_act_before'],
                            'tile_ten_hour_act_after':
                            bool(getattr(tile, 'ten_hour_act', False)),
                            'workday_cap_before': snapshot['workday_cap_before'],
                            'workday_cap_after':
                            float(tile_workday_cap_after),
                            'repeal_updates_workday_cap': False,
                            'reason': 'repeal_sets_max_workday_hours_only'},
                    cause_event_ids=([decision_event_id]
                                     if decision_event_id else None))
                if event_id:
                    tile_event_ids.append(event_id)
                for firm, shift_hours in snapshot['firms']:
                    firm_event_id = _emit_labor_policy_event(
                        trace_region, kind='labor_law_repeal_firm_shift_unchanged',
                        subject={'type': 'tile/corporation',
                                 'id': str(firm.id), 'tile': tile.name},
                        metric_id='labor.corporate_shift_hours', unit='hours',
                        before=shift_hours, after=float(firm.shift_hours),
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'shift_hours_changed':
                                float(firm.shift_hours) != shift_hours,
                                'reason':
                                'repeal_does_not_update_firm_shift_hours'},
                        cause_event_ids=([decision_event_id]
                                         if decision_event_id else None))
                    if firm_event_id:
                        firm_event_ids.append(firm_event_id)
            if repeal_safety:
                safety_event_id = _emit_labor_policy_event(
                    trace_region, kind='labor_law_repeal_safety_tile_outcome',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='labor.factory_safety_state', unit='enacted',
                    before=snapshot['safety_before'],
                    after=bool(getattr(tile, 'factory_safety_act', False)),
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'national_safety_before': safety_before,
                            'national_safety_after':
                            bool(getattr(nation, 'factory_safety_act', False))},
                    cause_event_ids=([decision_event_id]
                                     if decision_event_id else None))
                if safety_event_id:
                    tile_event_ids.append(safety_event_id)
        _emit_labor_policy_event(
            trace_region, kind='labor_law_repeal_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(nation, 'name', 'unnamed')},
            metric_id='scenario.labor_law_action', unit='policy_result',
            after='laws_repealed' if repealed else 'no_supported_laws_to_repeal',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'repealed': list(repealed),
                    'ten_hour_act_after':
                    bool(getattr(nation, 'ten_hour_act', False)),
                    'max_workday_hours_after': float(
                        getattr(nation, 'max_workday_hours', 16.0)),
                    'factory_safety_act_after':
                    bool(getattr(nation, 'factory_safety_act', False)),
                    'other_laws_active_but_not_repealed': other_law_state,
                    'tile_event_ids': tile_event_ids,
                    'firm_shift_event_ids': firm_event_ids},
            cause_event_ids=([decision_event_id] + tile_event_ids + firm_event_ids
                             if decision_event_id else
                             tile_event_ids + firm_event_ids or None))

    return {
        'repealed': repealed,
        'msg': f"Capitalist regime repealed: {', '.join(repealed)}" if repealed else "No labor laws to repeal."
    }


def adjust_workday_hours(target, delta_hours: float) -> Tuple[bool, str]:
    """Adjust statutory daily shift hours cap by delta_hours (e.g. +2.0h or -2.0h).

    Clamped within [8.0, 16.0] hours.
    - Reducing hours: Cuts worker health attrition & fatigue, boosts Labor/Peasant approval,
      reduces Bourgeoisie profits & approval. If <= 10h, activates ten_hour_act.
    - Increasing hours: Expands surplus value extraction (s/v), boosts Bourgeoisie approval,
      provokes Labor anger, raises protest energy. If > 10h, deactivates ten_hour_act.
    """
    cur_cap = getattr(target, 'max_workday_hours', 12.0)
    unbounded_cap = round(cur_cap + delta_hours, 1)
    new_cap = max(8.0, min(16.0, unbounded_cap))
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'workday_adjustment')
    gate_event_id = None

    if abs(new_cap - cur_cap) < 0.01:
        limit_txt = "minimum (8.0h)" if delta_hours < 0 else "maximum (16.0h)"
        if trace_region is not None:
            from run_trace import emit
            gate_event_id = emit(
                trace_region, kind='workday_adjustment_gate',
                record_class='decision', phase='policy_action',
                subject={'type': 'nation/action',
                         'id': getattr(target, 'name', 'unnamed')},
                metric_id='labor.workday_adjustment_gate', unit='applied',
                after=False,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'requested_delta_hours': float(delta_hours),
                        'workday_before': float(cur_cap),
                        'unbounded_target': unbounded_cap,
                        'clamped_target': float(new_cap),
                        'lower_limit_hours': 8.0, 'upper_limit_hours': 16.0,
                        'reason': 'statutory_boundary_already_reached'})
            emit(
                trace_region, kind='workday_adjustment_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'nation/action',
                         'id': getattr(target, 'name', 'unnamed')},
                metric_id='labor.workday_adjustment',
                before=float(cur_cap), after=float(cur_cap), unit='hours',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'applied': False, 'reason': 'statutory_boundary',
                        'requested_delta_hours': float(delta_hours)},
                cause_event_ids=([gate_event_id] if gate_event_id else None))
        return False, f"Workday already at statutory {limit_txt}."

    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    snapshots = []
    for tile in tiles:
        snapshot = {'tile': tile}
        if trace_region is not None:
            corporations = [agent for agent in getattr(tile, 'agents', [])
                            if getattr(agent, 'is_corporation', False)]
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            protest_log = getattr(tile, 'protest_energy_log', None)
            snapshot.update({
                'workday_before': float(getattr(tile, 'max_workday_hours', cur_cap)),
                'workday_cap_before': float(getattr(tile, 'workday_cap', cur_cap)),
                'ten_hour_act_before': bool(getattr(tile, 'ten_hour_act', False)),
                'corporations': [(agent, float(getattr(agent, 'shift_hours', 8.0)))
                                 for agent in corporations],
                'faction_support': {
                    name: float(faction.support)
                    for name, faction in factions.items()
                    if hasattr(faction, 'support')},
                'protest_before': (float(protest_log[-1])
                                   if delta_hours > 0 and protest_log else None),
            })
        snapshots.append(snapshot)

    if trace_region is not None:
        from run_trace import emit
        gate_event_id = emit(
            trace_region, kind='workday_adjustment_gate',
            record_class='decision', phase='policy_action',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='labor.workday_adjustment_gate', unit='applied',
            after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'requested_delta_hours': float(delta_hours),
                    'workday_before': float(cur_cap),
                    'unbounded_target': unbounded_cap,
                    'clamped_target': float(new_cap),
                    'clamped_by_statutory_limit': unbounded_cap != new_cap,
                    'lower_limit_hours': 8.0, 'upper_limit_hours': 16.0,
                    'tile_ids': [tile.name for tile in tiles],
                    'direction': 'worker_protective' if delta_hours < 0
                    else 'profit_expanding'})

    tile_event_ids = []
    for snapshot in snapshots:
        tile = snapshot['tile']
        tile.max_workday_hours = new_cap
        tile.workday_cap = new_cap
        tile.ten_hour_act = (new_cap <= 10.0)
        # Apply to corporations immediately
        for agent in getattr(tile, 'agents', []):
            if getattr(agent, 'is_corporation', False) and getattr(agent, 'shift_hours', 8.0) > new_cap:
                agent.shift_hours = new_cap

        # Class faction reactions
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        if delta_hours < 0:
            # Pro-labor reform
            for fname in ('Labor', 'Peasant'):
                if fname in factions:
                    factions[fname].support = min(1.0, factions[fname].support + 0.10)
            if 'Bourgeoisie' in factions:
                factions['Bourgeoisie'].support = max(0.0, factions['Bourgeoisie'].support - 0.08)
        else:
            # Pro-capital reform
            for fname in ('Labor', 'Peasant'):
                if fname in factions:
                    factions[fname].support = max(0.0, factions[fname].support - 0.12)
            if 'Bourgeoisie' in factions:
                factions['Bourgeoisie'].support = min(1.0, factions['Bourgeoisie'].support + 0.08)
            # Bump protest energy
            if hasattr(tile, 'protest_energy_log') and tile.protest_energy_log:
                tile.protest_energy_log[-1] = min(10.0, tile.protest_energy_log[-1] + 1.5)

        if trace_region is not None:
            from run_trace import emit
            tile_event_id = emit(
                trace_region, kind='workday_tile_limit_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='labor.statutory_workday',
                before=snapshot['workday_before'], after=float(new_cap),
                unit='hours',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'workday_cap_before': snapshot['workday_cap_before'],
                        'workday_cap_after': float(tile.workday_cap),
                        'ten_hour_act_before': snapshot['ten_hour_act_before'],
                        'ten_hour_act_after': bool(tile.ten_hour_act),
                        'requested_delta_hours': float(delta_hours)},
                cause_event_ids=([gate_event_id] if gate_event_id else None))
            if tile_event_id is not None:
                tile_event_ids.append(tile_event_id)

            for agent, shift_before in snapshot['corporations']:
                shift_after = float(getattr(agent, 'shift_hours', 8.0))
                if shift_before == shift_after:
                    continue
                emit(
                    trace_region, kind='workday_corporate_shift_outcome',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'corporation', 'id': str(agent.id),
                             'tile': tile.name},
                    metric_id='labor.corporate_shift_hours',
                    before=shift_before, after=shift_after, unit='hours',
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'workday_cap': float(new_cap),
                            'reason': 'corporate_shift_exceeded_new_legal_cap'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

            for name, support_before in snapshot['faction_support'].items():
                faction = factions.get(name)
                if faction is None:
                    continue
                support_after = float(faction.support)
                if support_before == support_after:
                    continue
                emit(
                    trace_region, kind='workday_faction_support_outcome',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile/faction', 'id': name,
                             'tile': tile.name},
                    metric_id='politics.faction_support',
                    before=support_before, after=support_after, unit='ratio',
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'requested_delta_hours': float(delta_hours),
                            'support_change': support_after - support_before},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

            protest_log = getattr(tile, 'protest_energy_log', None)
            protest_after = (float(protest_log[-1])
                             if delta_hours > 0 and protest_log else None)
            if (snapshot['protest_before'] is not None
                    and protest_after != snapshot['protest_before']):
                emit(
                    trace_region, kind='workday_protest_energy_outcome',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='politics.protest_energy',
                    before=snapshot['protest_before'], after=protest_after,
                    unit='score',
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'requested_increase': 1.5,
                            'reason': 'statutory_shift_expansion'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

    setattr(target, 'max_workday_hours', new_cap)
    setattr(target, 'ten_hour_act', (new_cap <= 10.0))

    if trace_region is not None:
        from run_trace import emit
        emit(
            trace_region, kind='workday_adjustment_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='labor.workday_adjustment',
            before=float(cur_cap), after=float(new_cap), unit='hours',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'applied': True, 'requested_delta_hours': float(delta_hours),
                    'unbounded_target': unbounded_cap,
                    'clamped_target': float(new_cap),
                    'tile_count': len(tiles),
                    'tile_outcome_event_ids': tile_event_ids},
            cause_event_ids=([gate_event_id] + tile_event_ids
                             if gate_event_id else tile_event_ids or None))

    action_word = "reduced" if delta_hours < 0 else "expanded"
    ten_note = " (Ten-Hour Act achieved!)" if new_cap <= 10.0 and cur_cap > 10.0 else ""
    return True, f"Statutory workday {action_word} to {new_cap:.1f}h/day{ten_note}."


def enact_ten_hour_act(target) -> Tuple[bool, str]:
    """Enact the Ten-Hour Act on a region or nation, capping daily factory shifts to 10h."""
    return adjust_workday_hours(target, 10.0 - getattr(target, 'max_workday_hours', 16.0))


def enact_factory_safety_act(target) -> Tuple[bool, str]:
    """Mandate workplace safety regulations, reducing factory injury & mortality."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'factory_safety_mandate')
    target_before = (bool(getattr(target, 'factory_safety_act', False))
                     if trace_region is not None else None)
    tile_before = ([bool(getattr(tile, 'factory_safety_act', False))
                    for tile in tiles] if trace_region is not None else [])
    decision_event_id = None
    if trace_region is not None:
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='factory_safety_mandate_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_gate', unit='accepted', after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_safety_mandate',
                    'tile_ids': [tile.name for tile in tiles],
                    'target_act_before': target_before,
                    'reason': 'factory_safety_mandate_applied'})
    for tile in tiles:
        tile.factory_safety_act = True
    setattr(target, 'factory_safety_act', True)
    tile_event_ids = []
    if trace_region is not None:
        for tile, before in zip(tiles, tile_before):
            event_id = _emit_labor_policy_event(
                trace_region, kind='factory_safety_tile_state_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='labor.factory_safety_state', unit='enacted',
                before=before, after=bool(tile.factory_safety_act),
                inputs={'operation_id': operation_id, 'turn': turn,
                        'hazard_guard_requirement': True},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))
            if event_id:
                tile_event_ids.append(event_id)
        _emit_labor_policy_event(
            trace_region, kind='factory_safety_mandate_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_action', unit='policy_result',
            before=target_before, after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'tile_count': len(tiles),
                    'tiles_newly_enacted': sum(not before for before in tile_before),
                    'target_act_before': target_before,
                    'target_act_after': True},
            cause_event_ids=([decision_event_id] + tile_event_ids
                             if decision_event_id else tile_event_ids or None))
    return True, "Factory Safety Mandate enacted: Machinery guards required!"


def enact_anti_truck_act(target) -> Tuple[bool, str]:
    """Enact the Statutory Anti-Truck Act: outlaw company scrip & Tommy shops, force payment in coin.

    - Sets nation/tile truck_act_enacted = True.
    - All corporate employers switch pay_mode = 'cash'.
    - All active peonage debt (company_debt) is discharged.
    - Factions: Labor/Peasant gain +15 approval, Bourgeoisie loses -10.
    """
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'anti_truck_act')
    target_before = bool(getattr(target, 'truck_act_enacted', False)) if trace_region is not None else None
    snapshots = []
    decision_event_id = None
    if trace_region is not None:
        for tile in tiles:
            agents = list(getattr(tile, 'agents', []))
            snapshots.append({
                'law_before': bool(getattr(tile, 'truck_act_enacted', False)),
                'corporate_pay_modes': [
                    (agent, getattr(agent, 'pay_mode', None))
                    for agent in agents
                    if getattr(agent, 'is_corporation', False)],
                'debtor_state': [
                    (agent, float(agent.company_debt),
                     float(getattr(agent, 'despair', 0.0)))
                    for agent in agents
                    if getattr(agent, 'company_debt', 0.0) > 0],
            })
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='anti_truck_act_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_gate', unit='accepted', after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_truck_act',
                    'law_active_before': target_before,
                    'tile_count': len(tiles),
                    'corporations_reviewed': sum(
                        len(row['corporate_pay_modes']) for row in snapshots),
                    'debtor_count': sum(len(row['debtor_state'])
                                        for row in snapshots),
                    'reason': 'anti_truck_decree_applied'})
    debt_discharged_total = 0.0
    peons_freed = 0
    corporate_payment_mode_changes = 0
    debt_event_ids = []
    tile_event_ids = []

    for index, tile in enumerate(tiles):
        tile_debt_event_ids = []
        tile.truck_act_enacted = True
        for a in getattr(tile, 'agents', []):
            if getattr(a, 'is_corporation', False):
                payment_mode_before = (getattr(a, 'pay_mode', None)
                                       if trace_region is not None else None)
                a.pay_mode = "cash"
                if (trace_region is not None
                        and payment_mode_before != a.pay_mode):
                    corporate_payment_mode_changes += 1
                    _emit_labor_policy_event(
                        trace_region, kind='anti_truck_payment_mode_outcome',
                        subject={'type': 'corporation', 'id': str(a.id),
                                 'tile': tile.name},
                        metric_id='labor.company_payment_mode', unit='pay_mode',
                        before=payment_mode_before, after='cash',
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'law': 'anti_truck_act',
                                'reason': 'company_scrip_outlawed'},
                        cause_event_ids=([decision_event_id]
                                         if decision_event_id else None))
            if getattr(a, 'company_debt', 0.0) > 0:
                debt_before = float(a.company_debt)
                despair_before = (float(getattr(a, 'despair', 0.0))
                                  if trace_region is not None else None)
                debt_discharged_total += debt_before
                a.company_debt = 0.0
                peons_freed += 1
                a.despair = max(0.0, getattr(a, 'despair', 0.0) - 0.20)
                a.mem_push('mem_promises', 1.0)
                creditor_id = getattr(getattr(a, 'employer', None), 'id', None)
                event_turn = (getattr(tile, '_collective_trace_clock', {}) or {}).get(
                    'turn', getattr(tile, '_last_turn', 0))
                from economy.actor_accounts import record as record_economic_event
                event = record_economic_event(
                    tile, 'company_debt_writeoff', turn=event_turn,
                    payer_id=a.id, recipient_id=creditor_id,
                    amount=debt_before,
                    asset_id=f'company-debt:{creditor_id or tile.name}:{a.id}',
                    detail={'debtor_id': a.id, 'creditor_id': creditor_id,
                            'law': 'anti_truck_act',
                            'company_debt_before': debt_before,
                            'company_debt_after': 0.0})
                from run_trace import emit
                debt_trace_event_id = emit(
                    tile, kind='company_store_debt_cancelled',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': tile.name,
                             'worker_id': a.id, 'creditor_id': creditor_id},
                    metric_id='finance.company_debt_writeoff',
                    unit=getattr(tile, 'home_currency', None) or 'local_currency',
                    before=debt_before, after=0.0,
                    inputs={'economic_event_id': event['id'],
                            'operation_id': operation_id,
                            'debtor_id': a.id, 'creditor_id': creditor_id,
                            'law': 'anti_truck_act'},
                    cause_event_ids=([decision_event_id]
                                     if decision_event_id else None))
                if debt_trace_event_id is not None:
                    debt_event_ids.append(debt_trace_event_id)
                    tile_debt_event_ids.append(debt_trace_event_id)
                if trace_region is not None:
                    _emit_labor_policy_event(
                        trace_region, kind='anti_truck_despair_outcome',
                        subject={'type': 'agent', 'id': str(a.id),
                                 'tile': tile.name},
                        metric_id='labor.despair', unit='ratio',
                        before=despair_before, after=float(a.despair),
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'company_debt_before': debt_before,
                                'company_debt_after': 0.0,
                                'despair_reduction_requested': 0.20,
                                'promise_memory_seeded': 1.0},
                        cause_event_ids=([debt_trace_event_id]
                                         if debt_trace_event_id else
                                         [decision_event_id]
                                         if decision_event_id else None))
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for fname in ('Labor', 'Peasant', 'Commoners'):
            if fname in factions:
                support_before = (float(factions[fname].support)
                                  if trace_region is not None else None)
                grievance_before = (float(factions[fname].grievances.get(
                    'truck_system', 0.0)) if trace_region is not None else None)
                factions[fname].support = min(1.0, factions[fname].support + 0.15)
                factions[fname].add_grievance('truck_system', -2.0)
                if trace_region is not None:
                    _emit_labor_policy_event(
                        trace_region, kind='anti_truck_faction_support_outcome',
                        subject={'type': 'tile/faction', 'id': fname,
                                 'tile': tile.name},
                        metric_id='politics.faction_support', unit='ratio',
                        before=support_before, after=float(factions[fname].support),
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'support_change':
                                float(factions[fname].support) - support_before,
                                'law': 'anti_truck_act'},
                        cause_event_ids=([decision_event_id]
                                         if decision_event_id else None))
                    grievance_after = float(factions[fname].grievances.get(
                        'truck_system', 0.0))
                    _emit_labor_policy_event(
                        trace_region, kind='anti_truck_grievance_outcome',
                        subject={'type': 'tile/faction', 'id': fname,
                                 'tile': tile.name},
                        metric_id='politics.grievance', unit='score',
                        before=grievance_before, after=grievance_after,
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'grievance_source': 'truck_system',
                                'requested_grievance_change': -2.0,
                                'actual_grievance_change':
                                grievance_after - grievance_before,
                                'negative_adjustment_accepted':
                                grievance_after != grievance_before,
                                'law': 'anti_truck_act'},
                        cause_event_ids=([decision_event_id]
                                         if decision_event_id else None))
        if 'Bourgeoisie' in factions:
            support_before = (float(factions['Bourgeoisie'].support)
                              if trace_region is not None else None)
            factions['Bourgeoisie'].support = max(0.0, factions['Bourgeoisie'].support - 0.10)
            if trace_region is not None:
                _emit_labor_policy_event(
                    trace_region, kind='anti_truck_faction_support_outcome',
                    subject={'type': 'tile/faction', 'id': 'Bourgeoisie',
                             'tile': tile.name},
                    metric_id='politics.faction_support', unit='ratio',
                    before=support_before,
                    after=float(factions['Bourgeoisie'].support),
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'support_change':
                            float(factions['Bourgeoisie'].support) - support_before,
                            'law': 'anti_truck_act'},
                    cause_event_ids=([decision_event_id]
                                     if decision_event_id else None))

        if trace_region is not None:
            snapshot = snapshots[index]
            tile_event_id = _emit_labor_policy_event(
                trace_region, kind='anti_truck_tile_state_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='labor.truck_act_state', unit='enacted',
                before=snapshot['law_before'], after=True,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'debt_discharged_on_tile': sum(
                            debt for agent, debt, _despair
                            in snapshot['debtor_state']),
                        'peons_freed_on_tile': len(snapshot['debtor_state'])},
                cause_event_ids=([decision_event_id] + tile_debt_event_ids
                                 if decision_event_id else
                                 tile_debt_event_ids or None))
            if tile_event_id:
                tile_event_ids.append(tile_event_id)

    setattr(target, 'truck_act_enacted', True)
    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='anti_truck_act_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.anti_truck_act', unit='policy_result',
            before=target_before, after='enacted',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'tile_count': len(tiles),
                    'corporate_payment_modes_changed':
                    corporate_payment_mode_changes,
                    'peons_freed': peons_freed,
                    'company_debt_discharged': debt_discharged_total,
                    'target_act_before': target_before,
                    'target_act_after': True,
                    'negative_truck_system_grievance_adjustment_effective': False},
            cause_event_ids=([decision_event_id] + tile_event_ids + debt_event_ids
                             if decision_event_id else tile_event_ids + debt_event_ids or None))
    return True, f"Anti-Truck Act enacted: Company scrip abolished! ({peons_freed} debt peons freed, ${debt_discharged_total:.0f} company debt cancelled)."


def subsidize_mass_entertainment(target, cost: float = 50.0) -> Tuple[bool, str]:
    """Subsidize public entertainment to pacify unrest and dampen class organizing.

    Transfers funds from treasury to tile entertainment level (stifling protest energy).
    """
    gov_agent = None
    source_type = None
    if hasattr(target, 'gov') and hasattr(target.gov, 'agent'):
        gov_agent = target.gov.agent
        source_type = 'target_government_treasury'
    elif hasattr(target, 'tiles') and target.tiles and hasattr(target.tiles[0], 'gov'):
        gov_agent = target.tiles[0].gov.agent
        source_type = 'first_tile_government_treasury'

    trace_candidates = [target]
    trace_candidates.extend(getattr(target, 'tiles', ()))
    trace_region = next((tile for tile in trace_candidates
                         if (getattr(tile, '_run_trace', None) is not None
                             and getattr(tile, '_collective_trace_clock', None)
                             is not None)), None)
    trace_clock = (getattr(trace_region, '_collective_trace_clock', {})
                   if trace_region is not None else {})
    turn = int(trace_clock.get('turn', getattr(target, '_last_turn', 0)))
    operation_id = None
    funding_event_id = None
    if trace_region is not None:
        operation_id = (
            f"policy:nat_subsidize_entertainment:"
            f"{getattr(target, 'name', 'unnamed')}:{turn}:"
            f"{int(trace_clock.get('next', 0))}")
        from run_trace import emit
        source_cash = float(gov_agent.cash) if gov_agent is not None else 0.0
        funding_event_id = emit(
            trace_region, kind='mass_entertainment_funding_decision',
            record_class='decision', phase='policy_action',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.mass_entertainment_funding', unit='funded',
            after=bool(gov_agent is not None and source_cash >= cost),
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_subsidize_entertainment',
                    'cost_requested': float(cost),
                    'source_type': source_type,
                    'source_cash_before': source_cash,
                    'cash_shortfall': max(0.0, float(cost) - source_cash),
                    'funded': bool(gov_agent is not None and source_cash >= cost),
                    'reason': ('treasury_funds_entertainment'
                               if gov_agent is not None and source_cash >= cost
                               else 'missing_government_treasury'
                               if gov_agent is None
                               else 'treasury_cash_below_cost')})

    if gov_agent is None or gov_agent.cash < cost:
        return False, "Insufficient government treasury funds for entertainment subsidy."

    # Conserved transfer: gov cash spent into local commerce / spectacle
    treasury_before = float(gov_agent.cash)
    _trace_cash_write = _trace_public_begin(None, gov_agent)
    gov_agent.cash -= cost
    _trace_public_finish(_trace_cash_write, 'labor_politics:subsidize_mass_entertainment',
                         inputs={"source_writer": 'labor_politics.py:subsidize_mass_entertainment:cbdf30831928c5e4:1'})
    treasury_after = float(gov_agent.cash)
    expenditure_event_id = None
    if trace_region is not None:
        from finance_trace import account_ref, transfer_contract
        from run_trace import emit
        currency = (getattr(target, 'currency', None)
                    or getattr(trace_region, 'home_currency', None)
                    or 'local_currency')
        treasury_id = str(getattr(gov_agent, 'id',
                                  getattr(target, 'name', 'treasury')))
        contract = transfer_contract(
            operation_id, 'mass_entertainment_subsidy', side='payer',
            amount=float(cost), amount_currency=currency,
            payer_account=account_ref(
                source_type or 'government_treasury', treasury_id, currency,
                nation_id=getattr(target, 'name', None),
                balance_before=treasury_before,
                balance_after=treasury_after,
                balance_scope='government_agent.cash'),
            payee_account={'type': 'public_entertainment_service',
                           'id': getattr(target, 'name', 'unnamed'),
                           'cash_balance_captured': False},
            local_cash_leg_amount=float(cost),
            local_cash_leg_currency=currency,
            counterparty_leg_status='policy_expenditure_no_cash_payee',
            source='nat_subsidize_entertainment', turn=turn)
        expenditure_event_id = emit(
            trace_region, kind='mass_entertainment_policy_expenditure',
            record_class='transfer', phase='policy_action',
            subject={'type': 'nation/treasury',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='finance.policy_expenditure', unit=currency,
            after=-float(cost),
            inputs={'operation_id': operation_id,
                    'treasury_balance_after': treasury_after,
                    'transfer_contract': contract},
            cause_event_ids=([funding_event_id]
                             if funding_event_id else None))

    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    boost = 0.40 / len(tiles)
    tile_outcomes = []
    effect_event_ids = []
    for tile in tiles:
        cur = float(getattr(tile, 'entertainment_level', 0.0))
        unrest_before = float(getattr(tile, 'unrest_level', 0.0))
        tile.entertainment_level = min(1.0, cur + boost)
        # Immediate damping of protest energy
        tile.unrest_level = max(0.0, unrest_before - 0.15)
        entertainment_after = float(tile.entertainment_level)
        unrest_after = float(tile.unrest_level)
        tile_row = {'tile': tile.name, 'entertainment_before': cur,
                    'entertainment_after': entertainment_after,
                    'entertainment_target_increase': boost,
                    'entertainment_actual_increase': entertainment_after - cur,
                    'unrest_before': unrest_before,
                    'unrest_after': unrest_after,
                    'unrest_change': unrest_after - unrest_before}
        tile_outcomes.append(tile_row)
        if trace_region is not None:
            from run_trace import emit
            entertainment_event_id = emit(
                trace_region, kind='mass_entertainment_tile_effect',
                record_class='outcome', phase='policy_action',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='society.entertainment_level',
                before=cur, after=entertainment_after, unit='ratio',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'per_tile_target_increase': boost,
                        'actual_increase': entertainment_after - cur,
                        'cap': 1.0,
                        'funding_event_id': funding_event_id,
                        'expenditure_event_id': expenditure_event_id},
                cause_event_ids=([expenditure_event_id]
                                 if expenditure_event_id else
                                 [funding_event_id] if funding_event_id else None))
            unrest_event_id = emit(
                trace_region, kind='mass_entertainment_unrest_effect',
                record_class='outcome', phase='policy_action',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='politics.unrest_level',
                before=unrest_before, after=unrest_after, unit='ratio',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'entertainment_effect': 'subtracts 0.15 unrest, floored at zero',
                        'funding_event_id': funding_event_id,
                        'expenditure_event_id': expenditure_event_id},
                cause_event_ids=([entertainment_event_id]
                                 if entertainment_event_id else
                                 [expenditure_event_id]
                                 if expenditure_event_id else None))
            effect_event_ids.extend(event_id for event_id in
                                    (entertainment_event_id, unrest_event_id)
                                    if event_id)

    if trace_region is not None:
        from run_trace import emit
        emit(
            trace_region, kind='mass_entertainment_subsidy_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.mass_entertainment_action',
            after='applied', unit='policy_result',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'cost_paid': float(cost),
                    'source_type': source_type,
                    'treasury_before': treasury_before,
                    'treasury_after': treasury_after,
                    'tile_count': len(tiles),
                    'tile_effects': tile_outcomes,
                    'entertainment_increases': sum(
                        row['entertainment_actual_increase']
                        for row in tile_outcomes),
                    'unrest_change_total': sum(row['unrest_change']
                                               for row in tile_outcomes),
                    'cash_recipient': None,
                    'expenditure_event_id': expenditure_event_id},
            cause_event_ids=([expenditure_event_id] + effect_event_ids
                             if expenditure_event_id else effect_event_ids
                             or ([funding_event_id] if funding_event_id else None)))

    return True, f"Mass entertainment subsidized (${cost:.0f}): Pacified public unrest!"


def enact_statute_of_laborers(target, wage_cap: float = 1.20) -> Tuple[bool, str]:
    """Enact the Statutory Maximum Wage Cap (Statute of Laborers / Wage Freeze).

    Cartelizes employers and legally caps wages to protect landlord and capitalist profit margins.
    - Sets statute_of_laborers = True and maximum_wage_cap = wage_cap.
    - Clamps all corporate/firm wages to <= wage_cap immediately.
    - Gentry & Bourgeoisie support rises (+0.15), and wage inflation panic is pacified.
    - Labor & Peasant support falls (-0.20), and if living costs exceed wage_cap,
      triggers popular resistance, strikes, and bread riots.
    """
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'statute_of_laborers')
    target_before = bool(getattr(target, 'statute_of_laborers', False)) if trace_region is not None else None
    target_cap_before = getattr(target, 'maximum_wage_cap', None) if trace_region is not None else None
    snapshots = []
    if trace_region is not None:
        for tile in tiles:
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            snapshots.append({
                'tile': tile,
                'law_before': bool(getattr(tile, 'statute_of_laborers', False)),
                'cap_before': getattr(tile, 'maximum_wage_cap', None),
                'firm_wages': [(agent, float(getattr(agent, 'wage', 0.0)))
                               for agent in getattr(tile, 'agents', [])
                               if getattr(agent, 'is_corporation', False)],
                'faction_support': {
                    name: float(faction.support)
                    for name, faction in factions.items()
                    if hasattr(faction, 'support')},
            })
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='statute_of_laborers_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_gate', unit='accepted', after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_toggle_statute_of_laborers',
                    'wage_cap': float(wage_cap),
                    'target_law_before': target_before,
                    'target_cap_before': target_cap_before,
                    'tile_count': len(tiles),
                    'firm_count_before': sum(len(row['firm_wages'])
                                             for row in snapshots),
                    'wage_ceiling_enforced_immediately': True})
    else:
        decision_event_id = None
    firms_capped = 0
    total_wage_reduction = 0.0

    for index, tile in enumerate(tiles):
        tile.statute_of_laborers = True
        tile.maximum_wage_cap = wage_cap
        for a in getattr(tile, 'agents', []):
            if getattr(a, 'is_corporation', False) and getattr(a, 'wage', 0.0) > wage_cap:
                wage_before = float(a.wage) if trace_region is not None else None
                a.wage = wage_cap
                firms_capped += 1
                if trace_region is not None:
                    reduction = wage_before - float(a.wage)
                    total_wage_reduction += reduction
                    _emit_labor_policy_event(
                        trace_region, kind='statute_of_laborers_firm_wage_cap',
                        subject={'type': 'corporation', 'id': str(a.id),
                                 'tile': tile.name},
                        metric_id='labor.firm_wage', unit='local_currency',
                        before=wage_before, after=float(a.wage),
                        inputs={'operation_id': operation_id, 'turn': turn,
                                'wage_cap': float(wage_cap),
                                'wage_reduction': reduction,
                                'law': 'statute_of_laborers'},
                        cause_event_ids=([decision_event_id]
                                         if decision_event_id else None))

        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        if 'Gentry' in factions:
            factions['Gentry'].support = min(1.0, factions['Gentry'].support + 0.15)
        if 'Bourgeoisie' in factions:
            factions['Bourgeoisie'].support = min(1.0, factions['Bourgeoisie'].support + 0.15)
        for fname in ('Labor', 'Peasant', 'Commoners', 'Proletariat', 'Peasantry'):
            if fname in factions:
                factions[fname].support = max(0.0, factions[fname].support - 0.20)

        if trace_region is not None:
            snapshot = snapshots[index]
            tile_event_id = _emit_labor_policy_event(
                trace_region, kind='statute_of_laborers_tile_state_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='labor.statute_of_laborers_state', unit='active',
                before=snapshot['law_before'], after=True,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'wage_cap_before': snapshot['cap_before'],
                        'wage_cap_after': float(tile.maximum_wage_cap),
                        'wage_cap': float(wage_cap)},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))
            prior_support = snapshot['faction_support']
            for name, support_before in prior_support.items():
                faction = factions.get(name)
                if faction is None:
                    continue
                support_after = float(faction.support)
                if support_before == support_after:
                    continue
                _emit_labor_policy_event(
                    trace_region, kind='statute_of_laborers_faction_effect',
                    subject={'type': 'tile/faction', 'id': name,
                             'tile': tile.name},
                    metric_id='politics.faction_support', unit='ratio',
                    before=support_before, after=support_after,
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'support_change': support_after - support_before,
                            'law': 'statute_of_laborers'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

    setattr(target, 'statute_of_laborers', True)
    setattr(target, 'maximum_wage_cap', wage_cap)
    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='statute_of_laborers_action_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_action', unit='policy_result',
            before=target_before, after='enacted',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'wage_cap': float(wage_cap), 'tile_count': len(tiles),
                    'firms_capped': firms_capped,
                    'total_wage_reduction': total_wage_reduction,
                    'target_cap_before': target_cap_before,
                    'target_cap_after': float(wage_cap),
                    'faction_support_formula':
                    'Gentry/Bourgeoisie +0.15; Labor/Peasant/Commoners/Proletariat/Peasantry -0.20'},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
    return True, f"ROYAL DECREE: Statute of Laborers enacted! Maximum wage capped at ${wage_cap:.2f} across {len(tiles)} regions ({firms_capped} firms capped)."


def repeal_statute_of_laborers(target) -> Tuple[bool, str]:
    """Repeal the Statutory Maximum Wage Cap, restoring free wage bargaining."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'repeal_statute_of_laborers')
    target_before = bool(getattr(target, 'statute_of_laborers', False)) if trace_region is not None else None
    target_cap = getattr(target, 'maximum_wage_cap', None) if trace_region is not None else None
    snapshots = []
    if trace_region is not None:
        for tile in tiles:
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            snapshots.append({
                'tile': tile,
                'law_before': bool(getattr(tile, 'statute_of_laborers', False)),
                'cap_before': getattr(tile, 'maximum_wage_cap', None),
                'firm_wages': [(agent, float(getattr(agent, 'wage', 0.0)))
                               for agent in getattr(tile, 'agents', [])
                               if getattr(agent, 'is_corporation', False)],
                'faction_support': {
                    name: float(faction.support)
                    for name, faction in factions.items()
                    if hasattr(faction, 'support')},
            })
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='statute_of_laborers_repeal_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_gate', unit='accepted', after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_toggle_statute_of_laborers',
                    'law_active_before': target_before,
                    'retained_wage_cap_value': target_cap,
                    'repeal_restores_wages_automatically': False})
    else:
        decision_event_id = None
    for index, tile in enumerate(tiles):
        tile.statute_of_laborers = False
        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        for fname in ('Labor', 'Peasant', 'Commoners', 'Proletariat', 'Peasantry'):
            if fname in factions:
                factions[fname].support = min(1.0, factions[fname].support + 0.15)
        if 'Gentry' in factions:
            factions['Gentry'].support = max(0.0, factions['Gentry'].support - 0.10)
        if 'Bourgeoisie' in factions:
            factions['Bourgeoisie'].support = max(0.0, factions['Bourgeoisie'].support - 0.10)

        if trace_region is not None:
            snapshot = snapshots[index]
            tile_event_id = _emit_labor_policy_event(
                trace_region, kind='statute_of_laborers_repeal_tile_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='labor.statute_of_laborers_state', unit='active',
                before=snapshot['law_before'], after=False,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'wage_cap_before': snapshot['cap_before'],
                        'wage_cap_after': getattr(tile, 'maximum_wage_cap', None),
                        'wage_cap_value_retained':
                        getattr(tile, 'maximum_wage_cap', None),
                        'firm_wages_restored': 0},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))
            for name, support_before in snapshot['faction_support'].items():
                faction = factions.get(name)
                if faction is None:
                    continue
                support_after = float(faction.support)
                if support_before == support_after:
                    continue
                _emit_labor_policy_event(
                    trace_region, kind='statute_of_laborers_repeal_faction_effect',
                    subject={'type': 'tile/faction', 'id': name,
                             'tile': tile.name},
                    metric_id='politics.faction_support', unit='ratio',
                    before=support_before, after=support_after,
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'support_change': support_after - support_before,
                            'law': 'statute_of_laborers_repeal'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

    setattr(target, 'statute_of_laborers', False)
    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='statute_of_laborers_repeal_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.labor_law_action', unit='policy_result',
            before=target_before, after='repealed',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'tile_count': len(tiles),
                    'target_wage_cap_value_retained':
                    getattr(target, 'maximum_wage_cap', None),
                    'wages_restored': False,
                    'faction_support_formula':
                    'Labor/Peasant/Commoners/Proletariat/Peasantry +0.15; Gentry/Bourgeoisie -0.10'},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
    return True, "Statute of Laborers repealed: Statutory maximum wage ceiling abolished!"


def enact_trade_quarantine(target) -> Tuple[bool, str]:
    """Enact a Cordon Sanitaire / Trade Quarantine.

    Freezes all incoming and outgoing merchant transport routes to block plague transmission.
    - Sets quarantine_active = True on target and tiles.
    - Sets is_quarantined = True on all routes.
    - Protects population (+0.10 Commoner/Labor approval).
    - Freezes commercial profits (-0.15 Bourgeoisie approval).
    """
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'trade_quarantine')
    target_before = bool(getattr(target, 'quarantine_active', False)) if trace_region is not None else None
    snapshots = []
    if trace_region is not None:
        for tile in tiles:
            routes = getattr(tile, 'routes', {})
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            snapshots.append({
                'tile': tile,
                'quarantine_before': bool(getattr(tile, 'quarantine_active', False)),
                'routes': [(route, str(getattr(route, 'id',
                                             getattr(route, 'route_id',
                                                     f'{tile.name}:{index}'))),
                             bool(getattr(route, 'is_quarantined', False)))
                            for index, route in enumerate(routes.values())],
                'faction_support': {
                    name: float(faction.support)
                    for name, faction in factions.items()
                    if hasattr(faction, 'support')},
            })
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='trade_quarantine_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.trade_quarantine_gate', unit='accepted',
            after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_toggle_quarantine',
                    'quarantine_active_before': target_before,
                    'tile_count': len(tiles),
                    'route_count': sum(len(row['routes']) for row in snapshots),
                    'reason': 'quarantine_enacted'})
    else:
        decision_event_id = None
    routes_quarantined = 0

    for index, tile in enumerate(tiles):
        tile.quarantine_active = True
        routes = getattr(tile, 'routes', {})
        for rt in routes.values():
            rt.is_quarantined = True
            routes_quarantined += 1

        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        if 'Bourgeoisie' in factions:
            factions['Bourgeoisie'].support = max(0.0, factions['Bourgeoisie'].support - 0.15)
        for fname in ('Labor', 'Peasant', 'Commoners', 'Proletariat', 'Peasantry'):
            if fname in factions:
                factions[fname].support = min(1.0, factions[fname].support + 0.10)

        if trace_region is not None:
            snapshot = snapshots[index]
            tile_event_id = _emit_labor_policy_event(
                trace_region, kind='trade_quarantine_tile_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='trade.quarantine_state', unit='active',
                before=snapshot['quarantine_before'], after=True,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'route_count': len(snapshot['routes'])},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))
            for route, route_id, route_before in snapshot['routes']:
                _emit_labor_policy_event(
                    trace_region, kind='trade_route_quarantine_outcome',
                    subject={'type': 'route', 'id': route_id,
                             'tile': tile.name},
                    metric_id='trade.route_quarantine', unit='active',
                    before=route_before,
                    after=bool(getattr(route, 'is_quarantined', False)),
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'reason': 'cordon_sanitaire'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))
            for name, support_before in snapshot['faction_support'].items():
                faction = factions.get(name)
                if faction is None:
                    continue
                support_after = float(faction.support)
                if support_before == support_after:
                    continue
                _emit_labor_policy_event(
                    trace_region, kind='trade_quarantine_faction_effect',
                    subject={'type': 'tile/faction', 'id': name,
                             'tile': tile.name},
                    metric_id='politics.faction_support', unit='ratio',
                    before=support_before, after=support_after,
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'support_change': support_after - support_before,
                            'reason': 'trade_quarantine'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

    setattr(target, 'quarantine_active', True)
    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='trade_quarantine_action_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.trade_quarantine_action', unit='policy_result',
            before=target_before, after='enacted',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'target_quarantine_active_after': True,
                    'tile_count': len(tiles), 'routes_quarantined': routes_quarantined},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
    return True, f"CORDON SANITAIRE: Trade Quarantine enacted! {routes_quarantined} commercial routes quarantined across {len(tiles)} regions."


def repeal_trade_quarantine(target) -> Tuple[bool, str]:
    """Repeal the Trade Quarantine, reopening commercial shipping corridors."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    trace_region, turn, operation_id = _labor_trace_context(
        target, 'repeal_trade_quarantine')
    target_before = bool(getattr(target, 'quarantine_active', False)) if trace_region is not None else None
    snapshots = []
    if trace_region is not None:
        for tile in tiles:
            routes = getattr(tile, 'routes', {})
            factions = getattr(getattr(tile, 'factions', None), 'factions', {})
            snapshots.append({
                'tile': tile,
                'quarantine_before': bool(getattr(tile, 'quarantine_active', False)),
                'routes': [(route, str(getattr(route, 'id',
                                             getattr(route, 'route_id',
                                                     f'{tile.name}:{index}'))),
                             bool(getattr(route, 'is_quarantined', False)))
                            for index, route in enumerate(routes.values())],
                'faction_support': {
                    name: float(faction.support)
                    for name, faction in factions.items()
                    if hasattr(faction, 'support')},
            })
        decision_event_id = _emit_labor_policy_event(
            trace_region, kind='trade_quarantine_repeal_decision',
            record_class='decision',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.trade_quarantine_gate', unit='accepted',
            after=True,
            inputs={'operation_id': operation_id, 'turn': turn,
                    'action_id': 'nat_toggle_quarantine',
                    'quarantine_active_before': target_before,
                    'route_count': sum(len(row['routes']) for row in snapshots),
                    'reason': 'quarantine_repealed'})
    else:
        decision_event_id = None
    for index, tile in enumerate(tiles):
        tile.quarantine_active = False
        routes = getattr(tile, 'routes', {})
        for rt in routes.values():
            rt.is_quarantined = False

        factions = getattr(getattr(tile, 'factions', None), 'factions', {})
        if 'Bourgeoisie' in factions:
            factions['Bourgeoisie'].support = min(1.0, factions['Bourgeoisie'].support + 0.10)

        if trace_region is not None:
            snapshot = snapshots[index]
            tile_event_id = _emit_labor_policy_event(
                trace_region, kind='trade_quarantine_repeal_tile_outcome',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='trade.quarantine_state', unit='active',
                before=snapshot['quarantine_before'], after=False,
                inputs={'operation_id': operation_id, 'turn': turn,
                        'route_count': len(snapshot['routes'])},
                cause_event_ids=([decision_event_id]
                                 if decision_event_id else None))
            for route, route_id, route_before in snapshot['routes']:
                _emit_labor_policy_event(
                    trace_region, kind='trade_route_quarantine_repeal_outcome',
                    subject={'type': 'route', 'id': route_id,
                             'tile': tile.name},
                    metric_id='trade.route_quarantine', unit='active',
                    before=route_before,
                    after=bool(getattr(route, 'is_quarantined', False)),
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'reason': 'commercial_route_reopened'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))
            for name, support_before in snapshot['faction_support'].items():
                faction = factions.get(name)
                if faction is None:
                    continue
                support_after = float(faction.support)
                if support_before == support_after:
                    continue
                _emit_labor_policy_event(
                    trace_region, kind='trade_quarantine_repeal_faction_effect',
                    subject={'type': 'tile/faction', 'id': name,
                             'tile': tile.name},
                    metric_id='politics.faction_support', unit='ratio',
                    before=support_before, after=support_after,
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'support_change': support_after - support_before,
                            'reason': 'trade_quarantine_repeal'},
                    cause_event_ids=([tile_event_id]
                                     if tile_event_id else None))

    setattr(target, 'quarantine_active', False)
    if trace_region is not None:
        _emit_labor_policy_event(
            trace_region, kind='trade_quarantine_repeal_outcome',
            subject={'type': 'nation/action',
                     'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.trade_quarantine_action', unit='policy_result',
            before=target_before, after='repealed',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'target_quarantine_active_after': False,
                    'tile_count': len(tiles),
                    'routes_reopened': sum(len(row['routes']) for row in snapshots)},
            cause_event_ids=([decision_event_id]
                             if decision_event_id else None))
    return True, "Trade Quarantine repealed: Commercial transport corridors reopened."


def emergency_granary_relief(target, food_amount: float = 25.0) -> Tuple[bool, str]:
    """Release municipal/sovereign granary reserves to feed starving citizens and halt pestilence."""
    tiles = getattr(target, 'tiles', [target]) if hasattr(target, 'tiles') else [target]
    total_fed = 0
    trace_region = next((tile for tile in [target, *tiles]
                         if (getattr(tile, '_run_trace', None) is not None
                             and getattr(tile, '_collective_trace_clock', None)
                             is not None)), None)
    trace_clock = (getattr(trace_region, '_collective_trace_clock', {})
                   if trace_region is not None else {})
    turn = int(trace_clock.get('turn', getattr(target, '_last_turn', 0)))
    operation_id = None
    if trace_region is not None:
        operation_id = (
            f"policy:nat_emergency_granary:{getattr(target, 'name', 'unnamed')}:"
            f"{turn}:{int(trace_clock.get('next', 0))}")
    gate_event_ids = []
    stock_event_ids = []
    total_grain_debited = 0.0

    for tile in tiles:
        gov = getattr(tile, 'gov', None)
        food_stock = getattr(gov, 'food_inventory', 0.0) if gov else 0.0
        # Check regional granary buffer stock
        granary_stock = float(getattr(tile, 'granary_stock', 0.0))
        depleted_before = (int(getattr(tile, 'famine_outbreak_turns', 0))
                           if trace_region is not None else None)

        # Distribute available grain to hungry agents
        hungry_agents = [a for a in getattr(tile, 'agents', []) if getattr(a, 'alive', True) and getattr(a, 'hungry_steps', 0) > 0]
        recipients = hungry_agents[:int(food_amount)]
        gate_event_id = None
        if trace_region is not None:
            from run_trace import emit
            gate_event_id = emit(
                trace_region, kind='national_granary_relief_tile_gate',
                record_class='decision', phase='policy_action',
                subject={'type': 'tile/action', 'id': tile.name},
                metric_id='scenario.granary_relief_gate', unit='eligible',
                after=bool(recipients),
                inputs={'operation_id': operation_id, 'turn': turn,
                        'action_id': 'nat_emergency_granary',
                        'tile_id': tile.name,
                        'hungry_alive_count': len(hungry_agents),
                        'recipient_count': len(recipients),
                        'recipient_limit_per_tile': int(food_amount),
                        'recipient_ids': [str(agent.id) for agent in recipients],
                        'treasury_food_inventory_observed': float(food_stock),
                        'treasury_food_inventory_consumed': False,
                        'granary_stock_before': granary_stock,
                        'cumulative_fed_before_tile': total_fed,
                        'reason': ('hungry_households_selected' if recipients
                                   else 'no_living_hungry_households')})
            if gate_event_id is not None:
                gate_event_ids.append(gate_event_id)

        for agent in recipients:
            hunger_before = int(agent.hungry_steps)
            food_inventory_before = (float(agent.inv_get(Goods.food, 0))
                                     if trace_region is not None else None)
            agent.hungry_steps = 0
            total_fed += 1
            if trace_region is not None:
                from run_trace import emit
                emit(
                    trace_region, kind='national_granary_relief_household_outcome',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'agent', 'id': str(agent.id),
                             'tile': tile.name},
                    metric_id='health.hunger_steps',
                    before=hunger_before, after=int(agent.hungry_steps),
                    unit='turns',
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'hungry_steps_before': hunger_before,
                            'hungry_steps_after': int(agent.hungry_steps),
                            'food_inventory_before': food_inventory_before,
                            'food_inventory_after':
                            float(agent.inv_get(Goods.food, 0)),
                            'food_inventory_changed': False,
                            'alive': bool(getattr(agent, 'alive', True)),
                            'granary_gate_event_id': gate_event_id},
                    cause_event_ids=([gate_event_id]
                                     if gate_event_id else None))

        # Preserve cumulative-fed debit semantics: each tile draws half a unit
        # per hungry household fed so far in this nation-wide pass.
        requested_stock_draw = total_fed * 0.5
        tile.granary_stock = max(0.0, granary_stock - requested_stock_draw)
        granary_stock_after = float(tile.granary_stock)
        actual_stock_draw = granary_stock - granary_stock_after
        total_grain_debited += actual_stock_draw
        tile.famine_outbreak_turns = 0  # Resets famine outbreak progression!

        if trace_region is not None:
            from run_trace import emit
            stock_event_id = emit(
                trace_region, kind='national_granary_stock_outcome',
                record_class='outcome', phase='policy_action',
                subject={'type': 'tile', 'id': tile.name},
                metric_id='goods.granary_stock',
                before=granary_stock, after=granary_stock_after,
                unit='grain_units',
                inputs={'operation_id': operation_id, 'turn': turn,
                        'tile_id': tile.name,
                        'cumulative_households_fed': total_fed,
                        'stock_draw_formula': 'cumulative_households_fed * 0.5',
                        'requested_stock_draw': requested_stock_draw,
                        'actual_stock_draw': actual_stock_draw,
                        'granary_stock_shortfall':
                        requested_stock_draw - actual_stock_draw,
                        'granary_gate_event_id': gate_event_id},
                cause_event_ids=([gate_event_id] if gate_event_id else None))
            if stock_event_id is not None:
                stock_event_ids.append(stock_event_id)
            if depleted_before:
                emit(
                    trace_region, kind='national_granary_famine_progression_reset',
                    record_class='outcome', phase='policy_action',
                    subject={'type': 'tile', 'id': tile.name},
                    metric_id='health.famine_outbreak_progression',
                    before=depleted_before, after=0, unit='turns',
                    inputs={'operation_id': operation_id, 'turn': turn,
                            'tile_id': tile.name,
                            'households_fed_on_tile': len(recipients)},
                    cause_event_ids=([stock_event_id]
                                     if stock_event_id else
                                     [gate_event_id] if gate_event_id else None))

    if trace_region is not None:
        from run_trace import emit
        emit(
            trace_region, kind='national_granary_relief_outcome',
            record_class='outcome', phase='policy_action',
            subject={'type': 'nation/action', 'id': getattr(target, 'name', 'unnamed')},
            metric_id='scenario.granary_relief_action',
            after=total_fed, unit='households',
            inputs={'operation_id': operation_id, 'turn': turn,
                    'tile_count': len(tiles), 'households_fed': total_fed,
                    'food_amount_limit_per_tile': int(food_amount),
                    'cumulative_grain_stock_debited': total_grain_debited,
                    'funding_source': 'existing_tile_granary_stock',
                    'government_food_inventory_used': False,
                    'hunger_steps_reset_without_inventory_food_transfer': True,
                    'tile_gate_event_ids': gate_event_ids,
                    'tile_stock_event_ids': stock_event_ids},
            cause_event_ids=stock_event_ids or gate_event_ids or None)

    return True, f"EMERGENCY RELIEF: Distributed grain to {total_fed} starving citizens; halted famine immune collapse."
