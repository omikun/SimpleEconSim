"""Derive distribution, medical-access and production evidence from the replay."""
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(name):
    with gzip.open(HERE / name, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def gini(values):
    values = sorted(max(0, v) for v in values)
    n, total = len(values), sum(values)
    return sum((2 * i - n - 1) * v for i, v in enumerate(values, 1)) / (n * total) if n and total else 0


def division(a, b):
    return a / b if b else None


def farmer(a):
    return a['age'] >= 14 and a['output'] == 'food' and a['employer'] is None and not a['is_lord']


validation = json.loads((HERE / 'capture_validation.json').read_text())
assert validation['matches_accepted_untraced_run'] and not validation['trace_write_error']
assert not validation['currency_audit_violations']
births, people_ids, dissolution = [], set(), []
for r in rows('supplementary_trace.jsonl.gz'):
    if r['kind'] == 'birth':
        people_ids.add(r['inputs']['new_agent_id'])
    elif r['kind'] == 'estate_company_dissolved':
        dissolution.append(r)

medical_income = Counter()
journal_by_kind = defaultdict(Counter)
for r in rows('journal.jsonl.gz'):
    if r['kind'] == 'medical_care':
        medical_income[r['recipient_id']] += r['amount']
    journal_by_kind[r['kind']]['amount'] += r['amount']
    journal_by_kind[r['kind']]['quantity'] += r['quantity']
    journal_by_kind[r['kind']]['count'] += 1

daily, samples, patient_groups = [], [], defaultdict(Counter)
pre_care, production_actors = {}, {}
farm_trajectories = defaultdict(list)
for r in rows('boundaries.jsonl.gz'):
    t = r['turn']
    if t == 1 and r['phase'] == 'before_production':
        people_ids.update(a['id'] for a in r['people'])
    # Before-care turn one follows production, so founding IDs are already known.
    people = [a for a in r['people'] if a['id'] in people_ids]
    if r['phase'] == 'before_care':
        pre_care = {a['id']: a for a in people}
    elif r['phase'] == 'after_care':
        for a in people:
            before = pre_care.get(a['id'])
            if before is None or not farmer(before) or not before['diseases']:
                continue
            period = (t - 1) // 20
            affordability = 'cash_below_20' if before['cash'] < 20 else 'cash_at_least_20'
            group = patient_groups[(period, affordability)]
            group['farmer_patient_turns'] += 1
            group['still_sick_after_care'] += bool(a['diseases'])
            group['still_pollution_ill_after_care'] += bool(set(a['diseases']) & {'waterborne', 'respiratory', 'chemical'})
            group['treatment_attempts'] += a['medical_treatments_total'] - before['medical_treatments_total']
            group['private_fees_paid'] += a['medical_paid_total'] - before['medical_paid_total']
    elif r['phase'] == 'before_production':
        adults = [a for a in people if a['age'] >= 14]
        farmers = [a for a in adults if farmer(a)]
        financial = [a['liquid_assets'] for a in adults]
        food = [a['food'] + a['prepared_food'] for a in adults]
        richest = sorted(adults, key=lambda a: a['liquid_assets'], reverse=True)
        top_count = max(1, math.ceil(len(adults) / 10))
        total = sum(financial)
        item = {'turn': t, 'adult_people': len(adults), 'independent_farmers': len(farmers),
                'adult_liquid_assets': total, 'adult_liquid_asset_gini': gini(financial),
                'top_decile_liquid_asset_share': division(sum(a['liquid_assets'] for a in richest[:top_count]), total),
                'adult_food_gini': gini(food),
                'farmers_cash_below_20': sum(a['cash'] < 20 for a in farmers),
                'farmers_pollution_withheld': sum(a['pollution_withheld'] for a in farmers),
                'farmers_inventory_at_cap': sum(a['food'] >= 20 for a in farmers),
                'adult_food_units': sum(food),
                'lord_food_units': sum(a['food'] for a in people if a['is_lord']),
                'water_pollution': r['water_pollution'],
                'richest': [{k: a[k] for k in ('id', 'cash', 'deposits', 'output', 'food', 'is_lord', 'diseases')}
                            for a in richest[:3]]}
        daily.append(item)
        for a in farmers:
            farm_trajectories[a['id']].append((t, a['pollution_withheld'], a['cash']))
        if t in (1, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200):
            samples.append(item)

poor_id = max(farm_trajectories, key=lambda ident: sum(80 <= t <= 140 and blocked and cash < 20
                                                     for t, blocked, cash in farm_trajectories[ident]))
provider_id = medical_income.most_common(1)[0][0]
events = defaultdict(list)
health_totals, zero_reasons, water_sources = Counter(), Counter(), Counter()
zero_by_period = defaultdict(Counter)
farm_output_by_period = Counter()
trace_cases = defaultdict(list)
for r in rows('selected_trace.jsonl.gz'):
    t, kind, i, subject = r['turn'], r['kind'], r.get('inputs', {}), r.get('subject', {})
    ident = subject.get('agent_id', subject.get('id'))
    if kind == 'medical_treatment':
        health_totals['treatment_attempts'] += 1
        health_totals['successful_treatments'] += r['after'] == 0
        health_totals['public_attempts'] += i['payer'] == 'public'
        if 81 <= t <= 140:
            health_totals['attempts_81_140'] += 1
    elif kind == 'medical_treatment_unaffordable':
        health_totals['unaffordable_cases'] += 1
        health_totals['unaffordable_' + subject['disease']] += 1
        if 81 <= t <= 140:
            health_totals['unaffordable_81_140'] += 1
    elif kind == 'pollution_water_update':
        for field in ('urban_emission', 'industrial_emission', 'fertilizer_runoff'):
            water_sources[field] += i[field]
    elif kind == 'independent_production_zero' and subject.get('good') == 'food':
        zero_reasons[i['reason']] += 1
        zero_by_period[(t - 1) // 20][i['reason']] += 1
    elif kind in ('independent_production', 'firm_production') and subject.get('good') == 'food':
        farm_output_by_period[(t - 1) // 20] += r['after']
    if ident in (poor_id, provider_id):
        trace_cases[ident].append(r)

example_unaffordable = next(r for r in trace_cases[poor_id]
                           if r['kind'] == 'medical_treatment_unaffordable'
                           and r['subject']['disease'] == 'waterborne' and r['turn'] >= 60)
example_zero = next(r for r in trace_cases[poor_id]
                    if r['kind'] == 'independent_production_zero'
                    and r['turn'] > example_unaffordable['turn']
                    and r['inputs']['reason'] == 'pollution_illness_revolt')
example_forage = next(r for r in trace_cases[poor_id]
                      if r['kind'] == 'commons_foraging' and r['turn'] == example_zero['turn'])
example_onset = next((r for r in reversed(trace_cases[poor_id])
                     if r['kind'] == 'disease_onset_assessment' and r['turn'] <= example_unaffordable['turn']
                     and r['inputs'].get('risk_checks', {}).get('waterborne', {}).get('contracted')), None)
example_assessment = None
for r in rows('selected_trace.jsonl.gz'):
    if r['kind'] == 'pollution_health_assessment' and r['turn'] == example_zero['turn'] - 1:
        assert poor_id in r['inputs']['revolt_participant_ids']
        example_assessment = {k: r[k] for k in ('event_id', 'turn', 'kind', 'after')}

case_snapshots = []
for r in rows('boundaries.jsonl.gz'):
    if r['phase'] != 'before_production' or r['turn'] not in (40, 60, 80, 100, 120, 140, 160, 180):
        continue
    for a in r['people']:
        if a['id'] in (poor_id, provider_id):
            case_snapshots.append({'turn': r['turn'], **a})

group_rows = []
for (period, affordability), counts in sorted(patient_groups.items()):
    group_rows.append({'turns': [period * 20 + 1, period * 20 + 20],
                       'affordability': affordability, **counts,
                       'still_sick_rate': counts['still_sick_after_care'] / counts['farmer_patient_turns']})
output = {'source_signature': validation['source_signature'],
          'basis': 'Adult human liquid assets = nonnegative cash plus bank deposits; no property/firm valuation or debt subtraction.',
          'human_identity': 'Founding residents plus trace-recorded births; converted corporations excluded.',
          'human_ids': len(people_ids), 'snapshots': samples, 'daily': daily,
          'medical_totals': dict(health_totals),
          'medical_provider_receipts': medical_income.most_common(),
          'recorded_journal_flows': {k: dict(v) for k, v in journal_by_kind.items()},
          'water_emission_sources': dict(water_sources),
          'farm_zero_output_reasons': dict(zero_reasons),
          'farm_zero_output_by_period': [{'turns': [p * 20 + 1, p * 20 + 20], **dict(c)}
                                         for p, c in sorted(zero_by_period.items())],
          'farm_trace_output_by_period': dict(farm_output_by_period),
          'farmer_patient_groups': group_rows, 'poor_farmer_id': poor_id,
          'largest_medical_recipient_id': provider_id,
          'case_snapshots': case_snapshots,
          'case_trace_chain': [example_onset, example_unaffordable, example_assessment,
                               example_forage, example_zero]}
(HERE / 'analysis.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({k: v for k, v in output.items()
                  if k not in ('daily', 'case_trace_chain', 'case_snapshots', 'farmer_patient_groups')}, indent=2))
