"""Evidence-based political consequences of corporate labor conflicts.

Constitutional preferences exist only where a scenario names a colonial
authority on the region. A private contract never changes them by itself.
"""

from __future__ import annotations

from collective_action import _clamp, _event, _records


def _residents(region):
    return {person.id: person for person in region.agents
            if person.alive and not person.is_corporation
            and not person.is_government and not person.is_trader}


def _colonial_authority(region):
    authority = getattr(region, 'colonial_authority', None)
    return getattr(authority, 'name', authority) if authority else None


def _preferences(region):
    if not hasattr(region, 'constitutional_preferences'):
        region.constitutional_preferences = {}
    if not hasattr(region, 'applied_political_incidents'):
        region.applied_political_incidents = set()
    if _colonial_authority(region):
        for pid in _residents(region):
            region.constitutional_preferences.setdefault(pid, {
                'reform': .35, 'federation': .25, 'independence': .40})
    return region.constitutional_preferences


def record_authority_incident(region, t, incident_id, authority, affected_ids,
                              *, breach=0.0, repression=0.0, reform=0.0,
                              attribution=1.0, accepted_commitment_id=None):
    """Apply one verified incident once to named residents; return affected count.

    A breach requires an accepted commitment ID. Callers must document what
    was due and what was delivered in their own authoritative event record.
    """
    if not incident_id or not authority:
        return 0
    if breach and not accepted_commitment_id:
        raise ValueError('A broken promise requires an accepted commitment ID')
    _records(region)
    preferences = _preferences(region)
    if incident_id in region.applied_political_incidents:
        return 0
    region.applied_political_incidents.add(incident_id)
    authority_name = getattr(authority, 'name', authority)
    colonial = _colonial_authority(region) == authority_name
    residents = _residents(region)
    affected = sorted(set(affected_ids) & residents.keys())
    breach, repression, reform, attribution = map(
        _clamp, (breach, repression, reform, attribution))
    changes = []
    if colonial:
        for pid in affected:
            before = dict(preferences[pid])
            old = before['independence']
            new = _clamp(old + .25 * breach * attribution * (1 - old)
                         + .20 * repression * attribution * (1 - old)
                         - .20 * reform * old)
            rest = max(0.0, 1 - old)
            if rest > 0:
                reform_fraction = before['reform'] / rest
            else:
                reform_fraction = .6
            preferences[pid] = {'reform': (1 - new) * reform_fraction,
                                'federation': (1 - new) * (1 - reform_fraction),
                                'independence': new}
            changes.append({'person_id': pid, 'before': round(old, 4),
                            'after': round(new, 4)})
    _event(region, t, 'authority_incident', 0,
           message=(f'{authority_name} action affects {len(affected)} residents: '
                    f'broken commitment {breach:.2f}, repression {repression:.2f}, '
                    f'delivered reform {reform:.2f}.'),
           incident_id=incident_id, authority=authority_name,
           colonial_responsibility=colonial,
           affected_ids=affected, accepted_commitment_id=accepted_commitment_id,
           breach=breach, repression=repression, reform=reform,
           attribution=attribution, independence_changes=changes)
    return len(affected)


def political_summary(region):
    """Unique-person coverage; index is agenda strength, never a probability."""
    authority = _colonial_authority(region)
    residents = _residents(region)
    if not authority:
        return {'colonial_authority': None, 'covered_residents': 0,
                'eligible_residents': len(residents), 'mobilization_index': None}
    preferences = _preferences(region)
    strength = {}
    for org in _records(region).values():
        capacity = .60 * org.organization + .40 * org.confidence
        for pid in org.member_ids & residents.keys():
            strength[pid] = max(strength.get(pid, 0.0), capacity)
    eligible = len(residents)
    index = (100 * sum(capacity * preferences[pid]['independence']
                       for pid, capacity in strength.items()) / eligible
             if eligible else 0.0)
    return {'colonial_authority': authority,
            'covered_residents': len(strength), 'eligible_residents': eligible,
            'mobilization_index': round(index, 4),
            'support_for_independence_among_covered':
                round(sum(preferences[pid]['independence'] for pid in strength)
                      / len(strength), 4) if strength else None}
