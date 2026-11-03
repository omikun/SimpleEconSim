"""Replay the frozen 200-turn parish with causal trace and wealth boundaries.

The observed result must equal every daily row of the accepted untraced run.
No food, cash, medical treatment, production or random draws are altered.
"""
from collections import Counter
from contextlib import redirect_stdout
import gzip
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ['ABUNDANCE_SOURCE_ROOT'])
sys.path.insert(0, str(SOURCE))
import sitecustomize
from scripts import audit_natural_abundance as campaign
from run_trace import RunTrace
from goods import Goods
from labor_choice import career_lifecycle_age
from economy import actor_accounts
import disease
import region_production

KINDS = {
    'disease_onset_assessment', 'medical_treatment', 'medical_treatment_unaffordable',
    'medical_care_summary', 'medical_care_payment', 'disease_untreated_cases_observed',
    'pollution_health_assessment', 'pollution_water_update', 'pollution_air_update',
    'independent_production', 'independent_production_zero', 'firm_production',
    'firm_production_zero', 'commons_foraging', 'food_intake',
}
original_step = campaign.step_turn
original_care = disease.step_medical_care
original_production = region_production.produce
original_record = actor_accounts.record
event_counts = Counter()


def write(stream, row):
    stream.write(json.dumps(row, separators=(',', ':'), default=lambda x: getattr(x, 'name', str(x))) + '\n')


class EvidenceTrace(RunTrace):
    def emit(self, clock, **kwargs):
        ident = super().emit(clock, **kwargs)
        kind = kwargs.get('kind')
        event_counts[kind] += 1
        if kind in KINDS:
            write(selected, {'event_id': ident, 'turn': clock['turn'], **kwargs})
        return ident


def snapshot(region, turn, phase):
    people = []
    for a in region.agents:
        if not a.alive or a.is_government or a.is_corporation:
            continue
        deposit = region.bank.deposits.get(a, 0)
        people.append({
            'id': a.id, 'age': career_lifecycle_age(a, turn),
            'output': a.output.name, 'employer': getattr(a.employer, 'id', None),
            'is_lord': a.is_lord, 'social_class': getattr(a, 'social_class', None),
            'cash': a.cash, 'deposits': deposit, 'liquid_assets': max(0, a.cash) + max(0, deposit),
            'food': a.inv_get(Goods.food, 0), 'prepared_food': a.inv_get(Goods.prepared_food, 0),
            'diseases': list(a.diseases or ()), 'hungry_steps': a.hungry_steps,
            'calorie_deficit': a.calorie_deficit_kcal, 'reserve_kcal': a.energy_reserve_kcal,
            'medical_paid_total': a.medical_expenses_paid,
            'medical_treatments_total': a.medical_treatments_count,
            'pollution_withheld': a.id in getattr(region, 'pollution_revolt_ids', ()),
            'striking': a.is_striking, 'revolt': a.in_revolt,
            'temporary_work_share': a.temporary_work_share,
            'plot': a.assigned_plot_id,
        })
    write(boundaries, {'turn': turn, 'phase': phase, 'people': people,
                      'water_pollution': region.pollution_water,
                      'health_state': getattr(region, 'pollution_health_state', {}),
                      'buildings': [b.name for b in region.buildings],
                      'public_healthcare': getattr(region, 'public_healthcare_decree', False)})


def care(region, turn, *args, **kwargs):
    snapshot(region, turn, 'before_care')
    result = original_care(region, turn, *args, **kwargs)
    snapshot(region, turn, 'after_care')
    return result


def production(region, turn):
    snapshot(region, turn, 'before_production')
    return original_production(region, turn)


def record(region, kind, **kwargs):
    result = original_record(region, kind, **kwargs)
    if kind in ('medical_care', 'feudal_tribute', 'estate_food_relief', 'tax',
                'cash_tax', 'birth_endowment', 'inheritance', 'wage', 'rent'):
        write(journal, dict(result))
    return result


def step(turn, tiles, *args, **kwargs):
    for r in tiles:
        r._run_trace = recorder
    result = original_step(turn, tiles, *args, **kwargs)
    for r in tiles:
        snapshot(r, turn, 'after_turn')
    if turn % 10 == 0:
        (HERE / 'progress.json').write_text(json.dumps({'turn': turn, 'trace_events': recorder.count}) + '\n')
    return result


if __name__ == '__main__':
    expected = json.loads((HERE.parent / 'natural_abundance_200turn_20261031/frozen/seed_4243.json').read_text())
    if (HERE / 'seed_4243.ctr').exists():
        raise FileExistsError('Move the generated trace aside before replaying; existing evidence is retained.')
    with gzip.open(HERE / 'selected_trace.jsonl.gz', 'wt') as selected, \
            gzip.open(HERE / 'boundaries.jsonl.gz', 'wt') as boundaries, \
            gzip.open(HERE / 'journal.jsonl.gz', 'wt') as journal:
        recorder = EvidenceTrace(HERE / 'seed_4243.ctr', 'foraging-inequality-4243', seed=4243)
        try:
            with patch.object(campaign, 'step_turn', step), \
                    patch.object(disease, 'step_medical_care', care), \
                    patch.object(region_production, 'produce', production), \
                    patch.object(actor_accounts, 'record', record), redirect_stdout(campaign.DiscardOutput()):
                actual = campaign.run(4243, 200)
            for key in ('source_signature', 'opening', 'observations', 'periods',
                        'events', 'innovation_log', 'currency_audit_violations'):
                assert actual[key] == expected[key], f'Tracing altered {key}'
            assert actual['source_unchanged']
            result = {'matches_accepted_untraced_run': True,
                      'source_signature': actual['source_signature'],
                      'trace_events': recorder.count, 'selected_kinds': dict(event_counts),
                      'currency_audit_violations': actual['currency_audit_violations'],
                      'trace_write_error': recorder.write_error}
            (HERE / 'capture_validation.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps({k: v for k, v in result.items() if k != 'selected_kinds'}))
        finally:
            recorder._compact_writer.close()
