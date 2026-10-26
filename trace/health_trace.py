"""Preserve mortality contributors until the native medical-history sample.

Medical care reads and resets the fatality counter before the later mortality
phase. Contributors can therefore belong to the preceding gameplay turn.
"""


def remember_fatality(region, agent, turn, event_id, draw, baseline, risk, diseases):
    pending = getattr(region, '_trace_pending_disease_fatalities', [])
    pending.append({'event_id': event_id, 'agent_id': agent.id,
                    'mortality_turn': turn, 'death_draw': draw,
                    'probability_without_disease': baseline,
                    'adjusted_probability': risk,
                    'active_diseases': list(diseases)})
    region._trace_pending_disease_fatalities = pending


def record_fatalities(region, turn, count):
    if getattr(region, '_run_trace', None) is None:
        return
    from run_trace import emit
    contributors = getattr(region, '_trace_pending_disease_fatalities', [])
    region._trace_pending_disease_fatalities = []
    emit(region, kind='disease_fatalities_observed', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='health.fatalities', unit='people', after=count,
         formula_id='disease.threshold_crossing_fatalities.v1',
         inputs={'fatalities': contributors, 'sample_turn': turn,
                 'sample_point': 'medical_care_counter_read_before_mortality',
                 'attribution_rule': 'baseline < death_draw <= adjusted risk with active disease'},
         cause_event_ids=[person['event_id'] for person in contributors])
