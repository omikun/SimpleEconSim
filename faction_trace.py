"""Exact evidence for per-turn faction support and decayed grievance histories."""
from trace_clock import boundary


def faction_state(faction):
    return {'support': float(faction.support),
            'members': set(faction.membership),
            'grievances': dict(faction.grievances),
            'demands': [{'name': demand.name, 'weight': demand.weight,
                         'satisfied': demand.satisfied} for demand in faction.demands]}


def record_faction_histories(region, turn, opening, prepared, eligible, policy_inputs):
    from run_trace import emit

    trace = getattr(region, '_run_trace', None)
    latest = getattr(trace, 'latest_metric_calculation_event_id', None)
    current_boundary = boundary(getattr(region, '_collective_trace_clock', {'turn': turn}))
    if getattr(trace, '_active_turn', current_boundary) != current_boundary:
        latest = None
    source_id = (latest('politics.grievance', {'type': 'tile', 'id': region.name})
                 if callable(latest) else None)
    tax_id = (latest('finance.tax_rate', {'type': 'tile', 'id': region.name})
              if callable(latest) else None)
    for name, faction in region.factions.factions.items():
        prior = opening[name]
        inputs = prepared[name]
        members = inputs['members'] & eligible
        reason = ('retained_no_eligible_agents' if not eligible else
                  'retained_no_eligible_members' if not members else 'support_recomputed')
        emit(region, kind='faction_support_history_calculation',
             record_class='calculation', phase='politics',
             subject={'type': 'tile/faction', 'id': name, 'tile': region.name,
                      'history_field': 'faction_support_log'},
             metric_id='politics.faction_support', unit='ratio',
             before=prior['support'], after=float(faction.support),
             formula_id='factions.support_history.v1',
             inputs={'turn': int(turn), 'faction_kind': faction.kind,
                     'prior_stored_support': prior['support'], 'reason': reason,
                     'eligible_agent_ids': sorted(eligible),
                     'member_ids': sorted(inputs['members']),
                     'eligible_member_ids': sorted(members),
                     'added_member_ids': sorted(inputs['members'] - prior['members']),
                     'removed_member_ids': sorted(prior['members'] - inputs['members']),
                     'demands': inputs['demands'], 'policy_inputs': policy_inputs,
                     'grievances_before_decay': inputs['grievances'],
                     'fresh_source_trace_status': ('linked' if source_id
                                                   else 'no_current_turn_source_record'),
                     'sample_point': 'support uses accumulated grievances before decay',
                     'eligibility_rule': 'all living agents; overlapping factions are independent',
                     'empty_faction_rule': 'early zero return retains stored support'},
             cause_event_ids=[event_id for event_id in (source_id, tax_id)
                              if event_id is not None] or None)
        emit(region, kind='faction_grievance_history_calculation',
             record_class='calculation', phase='politics',
             subject={'type': 'tile/faction', 'id': name, 'tile': region.name,
                      'history_field': 'faction_grievance_log'},
             metric_id='politics.faction_grievance', unit='score',
             before=max(0.0, sum(prior['grievances'].values())),
             after=float(faction.total_grievance()),
             formula_id='factions.grievance_history_decay.v1',
             inputs={'turn': int(turn), 'sources_at_turn_start': prior['grievances'],
                     'sources_before_decay': inputs['grievances'],
                     'source_additions': {
                         key: inputs['grievances'].get(key, 0.0) - prior['grievances'].get(key, 0.0)
                         for key in sorted(set(prior['grievances']) | set(inputs['grievances']))},
                     'decay_factor': 0.95, 'prune_below': 1e-4,
                     'sources_after_decay': dict(faction.grievances),
                     'sample_point': 'after additions and grievance decay'},
             cause_event_ids=([source_id] if source_id else None))


def replay_formula(formula, inputs):
    if formula == 'factions.support_history.v1':
        eligible = set(inputs['eligible_agent_ids'])
        members = set(inputs['member_ids']) & eligible
        if not eligible or not members:
            return inputs['prior_stored_support']
        demands = inputs['demands']
        weight = sum(demand['weight'] for demand in demands) or 1.0
        satisfaction = sum(demand['weight'] * demand['satisfied'] for demand in demands) / weight
        grievance = max(0.0, sum(inputs['grievances_before_decay'].values()))
        drag = min(1.0, 0.03 * grievance)
        return max(0.0, min(1.0, len(members) / len(eligible)
                            * (0.2 + 0.8 * satisfaction) * (1 - drag)))
    if formula == 'factions.grievance_history_decay.v1':
        values = [value * inputs['decay_factor']
                  for value in inputs['sources_before_decay'].values()]
        return max(0.0, sum(value for value in values if value >= inputs['prune_below']))
    raise ValueError(formula)
