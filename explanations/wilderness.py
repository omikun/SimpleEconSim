"""Deterministic historical answers for explicitly covered frontier domains."""
from explanations.packet import digest, input_summary
from wilderness_trace import FIELDS, MESSAGE, VERSION


def packet(captured,index,status):
    selection=captured['selection'];metric=selection['metric_id'];subject=selection['subject']
    epoch=selection.get('epoch');turn=selection['turn']
    previous=index.wilderness_status(turn=turn if epoch and epoch>0 else turn-1,
        epoch=epoch-1 if epoch and epoch>0 else None,subject=subject,boundary=captured['boundary'])
    before=after=None;unit='';message=MESSAGE
    lookup={name:(position,unit) for position,(name,_,unit) in enumerate(FIELDS)}
    if metric in lookup:
        position,unit=lookup[metric];after=status['state'][position]
        before=previous['state'][position] if previous else None
        message=('This frontier field is checked at the selected boundary. Its recorded state is shown above; '
                 'no current-turn change event was required. Background native population is separate from resident agents.')
    elif metric=='people.residents':
        after=0;before=0 if previous else None;unit='people'
        message=('The checked wilderness boundary has no resident agents. Background native inhabitants '
                 'are a separate population used by frontier claims and resistance.')
    rows=[status['coverage'],status['source']]
    if previous:rows += [previous['coverage'],previous['source']]
    evidence=[];seen=set()
    for row in rows:
        if row['event_id'] in seen:continue
        seen.add(row['event_id'])
        evidence.append({'event_id':row['event_id'],'turn':row.get('turn'),'kind':row['kind'],
            'metric_id':row.get('metric_id'),'subject':row.get('subject'),'before':row.get('value_before'),
            'after':row.get('value_after'),'unit':row.get('unit'),'status':'observation','issues':[],
            'issue_count':0,'notes':[MESSAGE],'formula_id':None,'inputs':input_summary(row.get('inputs') or {}),
            'cause_event_ids':(row.get('cause_event_ids') or [])[:24],
            'omitted_cause_count':max(0,len(row.get('cause_event_ids') or [])-24)})
    # Keep the selected tile's state even when the baseline is a large cohort.
    evidence[0]['inputs']={'capture_policy':VERSION,'selected_tile':subject['id'],
                          'state':dict(zip((field[0] for field in FIELDS),status['state']))}
    result={'version':'2','selection':selection,'scenario':captured.get('scenario'),
        'nation':captured.get('nation'),'era':captured.get('era'),
        'definition':('tile',unit,'Explicit quiet-wilderness capture policy'),
        'values':{'before':before,'after':after,'delta':after-before if before is not None else None,
                  'percent':100*(after-before)/abs(before) if before else None,'unit':unit,
                  'epoch':status['coverage'].get('epoch',0)},
        'root_event_ids':[status['coverage']['event_id']],'evidence':evidence,
        'limitations':['Explicit domain coverage, not a reconstructed operating economy.',
                       'Display defaults and recipe references do not establish economic deltas.'],
        'actions':[],'catalog_coverage':captured['catalog_coverage'],'national_contributions':[],
        'historical_candidates':[],'action_context_turn':captured.get('action_context_turn'),
        'local_explanation':message,'capture_policy':VERSION}
    result['selection_id']=digest(result)
    return result
