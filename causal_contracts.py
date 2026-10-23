"""Required source links for supported stock and production closures.

Contracts are explicit and independent of whether the arithmetic happens to
match. Other records remain outside this provenance coverage contract.
"""
import math


SUPPORTED = {'bank.opening_plus_transitions.v1', 'treasury.account_chain.v1',
             'treasury.closed_accounts.v1', 'production.sum_receipts.v1','market.discriminatory_clear.v2',
             'disease.threshold_crossing_fatalities.v1', 'gini.recorded_sample.v1'}


def requirements(row):
    formula=row.get('formula_id');i=row.get('inputs') or {}
    if row.get('kind')=='metric_snapshot':
        if row.get('explanation_status')!='calculation_recorded':return None
        return [('source_event_id',i.get('source_event_id'),
                 {'value_after':row['value_after'],'metric_id':row['metric_id'],'subject':row['subject']})]
    if row.get('kind')=='price_bridge':
        return [(f'steps[{index}].event_id',step.get('event_id'),
                 {'value_before':step['before'],'value_after':step['after'],'subject':row['subject']})
                for index,step in enumerate(i['steps'])]
    if formula not in SUPPORTED:return None
    result=[]
    if formula in {'bank.opening_plus_transitions.v1','treasury.account_chain.v1'}:
        result.append(('opening_source_event_id',i.get('opening_source_event_id'),{'@opening_balance':i['opening_balance'],'@field':i.get('field')}))
        field=i.get('field')
        for index,operation in enumerate(i['operations']):
            expected={'value_before':operation['before'],'value_after':operation['after']}
            if field is not None:expected={key:{field:value} for key,value in expected.items()}
            expected['subject']=row.get('subject',{})
            result.append((f'operations[{index}].event_id',operation.get('event_id'),expected))
    elif formula=='treasury.closed_accounts.v1':
        for index,account in enumerate(i['accounts']):
            result.append((f'accounts[{index}].source_event_id',account.get('source_event_id'),
                           {'value_after':account['closing'],
                            'subject':{'type':'public_account','id':account['account_id']}}))
    elif formula=='production.sum_receipts.v1':
        for index,receipt in enumerate(i['producer_receipts']):
            result.append((f'producer_receipts[{index}].event_id',receipt.get('event_id'),
                           {'value_after':receipt['units']}))
    elif formula=='market.discriminatory_clear.v2':
        for index,sale in enumerate(i['settled_sales']):
            result.append((f'settled_sales[{index}].event_id',sale.get('event_id'),
                           {'kind':'paid_market_sale','value_after':sale['quantity'],'subject':row['subject']}))
    elif formula=='disease.threshold_crossing_fatalities.v1':
        for index, person in enumerate(i['fatalities']):
            result.append((f'fatalities[{index}].event_id', person.get('event_id'),
                           {'kind': 'mortality_assessment',
                            'turn': person['mortality_turn'],
                            'subject': {**row['subject'], 'agent_id': person['agent_id']},
                            'value_after': person['adjusted_probability'],
                            'inputs': {'death_draw': person['death_draw'],
                                       'probability_without_disease': person['probability_without_disease'],
                                       'active_diseases': person['active_diseases'],
                                       'died': True, 'disease_attributed_by_threshold_crossing': True}}))
    elif formula=='gini.recorded_sample.v1':
        result.append(('source_event_id', i.get('source_event_id'),
                       {'metric_id':'economy.gini', 'subject':row['subject'],
                        'value_after':i['sampled_gini']}))
    return result


def _contains(actual, expected):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and _contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        return isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-8)
    return actual==expected


def validate(row, lookup):
    required=requirements(row)
    if required is None:return None
    declared=set(row.get('cause_event_ids') or ());issues=[]
    for path,ident,expected in required:
        if ident is None:
            issues.append({'path':path,'problem':'required_source_not_recorded'})
            continue
        if ident not in declared:
            issues.append({'path':path,'source_event_id':ident,'problem':'required_cause_not_declared'})
        source=lookup(ident)
        if source is None:
            issues.append({'path':path,'source_event_id':ident,'problem':'required_source_missing'})
        elif expected is not None and '@opening_balance' in expected:
            field=expected['@field']
            actual=source.get('value_after')
            if source.get('kind')=='bank_registered':actual=source.get('inputs',{}).get('starting_balances',{}).get(field)
            if not _contains(actual,expected['@opening_balance']) or not _contains(source.get('subject',{}),row.get('subject',{})):
                issues.append({'path':path,'source_event_id':ident,'problem':'opening_value_or_identity_mismatch'})
        elif expected is not None and not _contains(source,expected):
            issues.append({'path':path,'source_event_id':ident,'problem':'source_value_or_identity_mismatch'})
    return {'supported':True,'matches':not issues,'issues':issues}
