"""One registered-person death record shared by demographic and violent routes."""


def record_person_death(region, person, turn: int, cause: str, *, inputs=None,
                        phase='demographics') -> bool:
    """Mark and trace a death once; probate remains with the calling subsystem."""
    if getattr(person, 'death_recorded_turn', None) is not None:
        return False
    person.alive = False
    person.death_cause = str(cause)
    person.death_recorded_turn = int(turn)
    person.death_region = getattr(region, 'name', None)
    region.deaths_this_turn = getattr(region, 'deaths_this_turn', 0) + 1
    counts = getattr(region, 'deaths_by_cause_this_turn', None)
    if counts is None:
        counts = {}
        region.deaths_by_cause_this_turn = counts
    counts[cause] = counts.get(cause, 0) + 1
    from run_trace import emit
    emit(region, kind='person_died', record_class='outcome', phase=phase,
         subject={'type': 'tile/agent', 'id': str(person.id)},
         metric_id='people.deaths', unit='people', before=1, after=0,
         formula_id='people.registered_death.v1',
         inputs={'tile': getattr(region, 'name', None),
                 'agent_id': str(person.id),
                 'death_cause': cause, **(inputs or {})})
    return True
