"""Read-only final labor census and evidence for its derived rollups."""
from trace_clock import boundary


def tile_labor_census(tile):
    adults, excluded = [], []
    age_turn = getattr(tile, '_last_turn', 0)
    for person in tile.agents:
        ident = str(getattr(person, 'id', 'unknown'))
        reason = ('dead' if not person.alive else
                  'corporation' if person.is_corporation else
                  'government' if person.is_government else None)
        age = None
        native_child = bool(getattr(person, 'is_native_child', False))
        if reason is None and native_child:
            age = person.age(age_turn)
            if age < 14:
                reason = 'native_child_under_14'
        if reason is not None:
            excluded.append({'person_id': ident, 'reason': reason, 'age': age})
            continue
        livelihood = getattr(getattr(person, 'primary_livelihood', None), 'name', 'none')
        status = ('military' if getattr(person, 'military_unit_id', None) else
                  'trader' if getattr(person, 'is_trader', False) else
                  'constable' if getattr(person, 'social_class', None) == 'constable' else
                  'workhouse' if getattr(person, 'in_workhouse', False) else
                  'employed' if getattr(person, 'employer', None) is not None else 'independent')
        adults.append({'person_id': ident, 'livelihood': livelihood, 'status': status,
                       'hungry_steps': getattr(person, 'hungry_steps', 0),
                       'temporary_work_share': float(getattr(person, 'temporary_work_share', 0.0)),
                       'native_child': native_child, 'age': age,
                       'military_unit_id': getattr(person, 'military_unit_id', None),
                       'is_trader': bool(getattr(person, 'is_trader', False)),
                       'social_class': getattr(person, 'social_class', None),
                       'in_workhouse': bool(getattr(person, 'in_workhouse', False)),
                       'employer_id': getattr(getattr(person, 'employer', None), 'id', None)})
    return {'adults': adults, 'excluded': excluded, 'age_evaluation_turn': age_turn}


def capture_labor_censuses(tiles):
    return {tile.name: tile_labor_census(tile) for tile in tiles}


def census_groups(census, field):
    result = {}
    for person in census['adults']:
        result.setdefault(person[field], []).append(person['person_id'])
    return result


def record_labor_censuses(trace, clock, current_censuses, prior_censuses, previous_values):
    sources_current = getattr(trace, '_active_turn', None) == boundary(clock)
    for tile_name, census in current_censuses.items():
        prior = prior_censuses.get(tile_name)
        current_people = {row['person_id']: row for row in census['adults']}
        previous_people = {row['person_id']: row for row in prior['adults']} if prior else {}
        all_ids = set(current_people) | set(previous_people)
        links = {}
        for ident in sorted(all_ids):
            if sources_current:
                grouped = {category: trace.person_event_ids(ident, categories=(category,))
                           for category in ('resident', 'occupation', 'status')}
                grouped['food_intake'] = [trace.food_intake_event_id(ident)]
                grouped['temporary_activity'] = [trace.temporary_activity_event_id(ident)]
                grouped = {category: [event_id for event_id in events if event_id is not None]
                           for category, events in grouped.items()}
                if any(grouped.values()):
                    links[ident] = grouped
        evidence = {'turn': int(clock.get('turn', 0)),
                    'adult_records': census['adults'],
                    'excluded_records': census['excluded'],
                    'previous_adult_records': prior['adults'] if prior is not None else None,
                    'previous_excluded_records': prior['excluded'] if prior is not None else None,
                    'age_evaluation_turn': census['age_evaluation_turn'],
                    'eligibility_rule': 'living non-corporate non-government agents, excluding native children younger than 14',
                    'status_priority': ['military', 'trader', 'constable', 'workhouse', 'employed', 'independent'],
                    'sample_point': 'end of world turn, after migration and scenario operations',
                    'person_event_links': links}
        for metric_id, dimension, unit in (
                ('labor.primary_livelihood', 'livelihood', 'adults'),
                ('labor.employment_status', 'status', 'adults'),
                ('labor.hungry_adults', None, 'adults')):
            if dimension:
                groups = census_groups(census, dimension)
                old_groups = census_groups(prior, dimension) if prior else {}
                categories = set(groups) | set(old_groups)
                categories.update(key[2] for key in previous_values
                                  if key[0] == metric_id and key[1] == tile_name)
            else:
                groups = {'hungry': [row['person_id'] for row in census['adults'] if row['hungry_steps'] > 0]}
                old_groups = ({'hungry': [row['person_id'] for row in prior['adults']
                                          if row['hungry_steps'] > 0]} if prior else {})
                categories = {'hungry'}
            for category in sorted(categories):
                members = groups.get(category, [])
                previous_members = old_groups.get(category) if prior is not None else None
                if prior is not None and previous_members is None:
                    previous_members = []
                subject = {'type': 'tile', 'id': tile_name,
                           **({dimension: category} if dimension else {})}
                key = (metric_id, tile_name, category) if dimension else (metric_id, tile_name)
                before = (previous_values[key][2] if key in previous_values else
                          len(previous_members) if previous_members is not None else None)
                relevant_ids = set(members) | set(previous_members or ())
                cause_categories = ('resident', 'occupation' if dimension == 'livelihood' else
                                     'status' if dimension == 'status' else 'food_intake')
                causes = [event_id for ident in sorted(relevant_ids) for category in cause_categories
                          for event_id in links.get(ident, {}).get(category, ())]
                trace.emit(
                    clock, kind='final_labor_member_count', record_class='calculation',
                    phase='snapshot', subject=subject, metric_id=metric_id, unit=unit,
                    before=before, after=len(members), formula_id='labor.final_member_count.v1',
                    inputs={**evidence, 'category': category,
                            'dimension': dimension or 'hungry_steps', 'member_ids': members,
                            'previous_member_ids': previous_members,
                            'added_member_ids': sorted(set(members) - set(previous_members))
                            if previous_members is not None else None,
                            'removed_member_ids': sorted(set(previous_members) - set(members))
                            if previous_members is not None else None},
                    cause_event_ids=list(dict.fromkeys(causes)) or None)
        shares = [{'person_id': person['person_id'], 'share': person['temporary_work_share']}
                  for person in census['adults']]
        denominator = max(1, len(shares))
        key = ('labor.temporary_work_share', tile_name)
        trace.emit(
            clock, kind='final_temporary_work_share_mean', record_class='calculation',
            phase='snapshot', subject={'type': 'tile', 'id': tile_name},
            metric_id='labor.temporary_work_share', unit='adult_turn_share',
            before=previous_values[key][2] if key in previous_values else None,
            after=sum(row['share'] for row in shares) / denominator,
            formula_id='labor.final_temporary_share_mean.v1',
            inputs={**evidence, 'shares': shares, 'denominator': denominator},
            cause_event_ids=list(dict.fromkeys(
                event_id for grouped in links.values() for category in ('resident', 'temporary_activity')
                for event_id in grouped.get(category, ()))) or None)
