"""Canonical economic state and sampled metrics for continuation acceptance."""
from trace_snapshots import sample


def normalized_metrics(server):
    # Projects created after a checkpoint use UUID4, independently of gameplay
    # RNG. Match by tile and native creation-list position while preserving each
    # identity's references and every measured quantity.
    identities={}
    for tile in server.tiles:
        for index,project in enumerate(getattr(tile,'construction_projects',())):
            identities[project.project_id]=f'project:{tile.name}:{index}'
    def normalize(value):
        if isinstance(value,str):return identities.get(value,value)
        if isinstance(value,tuple):return tuple(normalize(item) for item in value)
        if isinstance(value,list):return [normalize(item) for item in value]
        if isinstance(value,dict):return {normalize(key):normalize(item) for key,item in value.items()}
        return value
    return {normalize(key):normalize(value) for key,value in sample(server.tiles,server.nations).items()}


# Only observational identity/cache fields are omitted. Financial quantities,
# inventories, liabilities, rules, populations, decisions and native ordering
# remain in the graph. Every omission is counted in the acceptance report.
OBSERVATIONAL_FIELDS = frozenset({
    '_run_trace','run_trace','_collective_trace_clock','_public_trace_source','_trace_session',
    '_pending_trader_float_traces','_last_market_novelty_trace','_decision_event_id',
    '_labor_workforce_event_ids','_trade_price_event_ids','_last_execution_times',
    '_last_border_vulnerability_event_id','_last_diplomacy_event_id',
    'trace_event_id','trace_event_ids','cause_event_ids','formula_replay','_cached_wealth',
    'source_link_status',
})


def canonical_state(tiles,nations,*,extra=None):
    """Canonical economic object graph, gameplay globals and RNG for acceptance.

    UUID domain identities are renamed consistently; amounts and references are
    retained. Unknown native objects fail serialization rather than being hidden
    behind repr(), which can embed process addresses.
    """
    from collections import Counter,defaultdict,deque
    from enum import Enum
    import hashlib,json,math,random,re,types
    import numpy as np
    from simulation_checkpoint import capture_globals
    globals_state,_=capture_globals()
    identities={};seen={};omitted=Counter()
    # Only registered native UUID fields are normalized. Numeric strings,
    # economic codes and arbitrary eight-character values remain untouched.
    identities={}
    def register(value):
        if not isinstance(value,str):return
        value=value.removeprefix('proj_').removeprefix('bill_')
        if re.fullmatch(r'[0-9a-f]{8}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',value):
            identities.setdefault(value,'uuid:'+str(len(identities)+1))
    for tile in tiles:
        for project in getattr(tile,'construction_projects',()):register(project.project_id)
    def fields_of(value):
        fields=dict(getattr(value,'__dict__',{}))
        for cls in type(value).__mro__:
            slots=vars(cls).get('__slots__',())
            if isinstance(slots,str):slots=(slots,)
            for name in slots:
                if name in {'__dict__','__weakref__'}:continue
                try:fields[name]=getattr(value,name)
                except AttributeError:pass
        return fields
    pattern=None
    def text(value):
        return pattern.sub(lambda match:identities[match.group(0)],value) if pattern is not None else value
    def skip(name,event=False,trace_derived=False,chart_point=False):
        if (isinstance(name,str) and (name in OBSERVATIONAL_FIELDS or name.startswith('_trace_')
                or name.endswith(('_trace_event_id','_trace_event_ids','_trace_id','_trace_ids'))
                or (event and name=='sequence') or (trace_derived and name=='source_event_id') or (chart_point and name=='event_id'))):
            omitted[name]+=1;return True
        return False
    def key(value):
        if isinstance(value,Enum):return f'enum:{type(value).__module__}.{type(value).__qualname__}:{value.name}'
        if isinstance(value,(str,int,float,bool,type(None))):return str(type(value))+':'+text(str(value))
        for field in ('id','project_id','name','index'):
            name=getattr(value,field,None)
            if isinstance(name,(str,int)):return type(value).__qualname__+':'+text(str(name))
        return type(value).__module__+'.'+type(value).__qualname__
    objects=[]
    pending=deque()
    def encode(value):
        if isinstance(value,Enum):return {'enum':type(value).__module__+'.'+type(value).__qualname__,'name':value.name}
        if value is None or isinstance(value,(bool,int)):return value
        if isinstance(value,float):return value if math.isfinite(value) else {'float':str(value)}
        if isinstance(value,str):return text(value)
        if isinstance(value,np.generic):return encode(value.item())
        if isinstance(value,bytes):return {'bytes_sha256':hashlib.sha256(value).hexdigest(),'length':len(value)}
        if isinstance(value,(type,types.BuiltinFunctionType,types.ModuleType)):
            return {'symbol':getattr(value,'__module__','')+'.'+getattr(value,'__qualname__',getattr(value,'__name__',type(value).__qualname__))}
        if isinstance(value,types.MethodType):return {'method':encode(value.__func__),'self':encode(value.__self__)}
        if isinstance(value,tuple):return {'tuple':[encode(item) for item in value]}
        if isinstance(value,frozenset):return {'frozenset':[encode(item) for item in sorted(value,key=key)]}
        if isinstance(value,re.Pattern):return {'regex':value.pattern,'flags':value.flags}
        address=id(value)
        if address not in seen:
            number=len(objects);seen[address]=number
            objects.append(None);pending.append((number,value))
        return {'ref':seen[address]}

    def fill(number,value):
        result={'id':number,'type':type(value).__module__+'.'+type(value).__qualname__}
        if isinstance(value,types.FunctionType):
            from python_code_signature import code_signature
            result.update(symbol=value.__module__+'.'+value.__qualname__,
                          code_sha256=code_signature(value.__code__),
                          defaults=encode(value.__defaults__),keyword_defaults=encode(value.__kwdefaults__),
                          closure=[encode(cell.cell_contents) for cell in value.__closure__ or ()],
                          attributes=encode(value.__dict__))
        elif isinstance(value,random.Random):result['random_state']=encode(value.getstate())
        elif isinstance(value,np.random.Generator):
            result.update(bit_generator=type(value.bit_generator).__name__,random_state=encode(value.bit_generator.state))
        elif isinstance(value,np.random.RandomState):result['random_state']=encode(value.get_state())
        elif isinstance(value,np.ndarray):result.update(dtype=str(value.dtype),shape=list(value.shape),values=value.tolist())
        elif isinstance(value,dict):
            event='kind' in value or 'record_class' in value
            entries=[]
            for k,v in value.items():
                if skip(k,event,'source_link_status' in value,set(value)=={'turn','value','event_id'}):continue
                if k=='source_id' and 'kind' in value and 'amount' in value and (v is None or
                        isinstance(v,str) and re.match(r'^(?:desktop-)?[0-9a-f]{32}(?:-[0-9]+)?:',v)):
                    omitted[k]+=1;continue
                entries.append((k,v))
            result['items']=[[encode(k),encode(v)] for k,v in sorted(entries,key=lambda pair:key(pair[0]))]
            result['insertion_keys']=[encode(k) for k,v in entries]
            if isinstance(value,defaultdict):result['factory']=encode(value.default_factory)
        elif isinstance(value,(list,deque,set)):
            items=sorted(value,key=key) if isinstance(value,set) else value
            result['items']=[encode(item) for item in items]
            if isinstance(value,deque):result['maxlen']=value.maxlen
        else:
            fields=fields_of(value)
            extras=fields.get('_extra_attrs')
            if isinstance(extras,dict) and not any(
                    name not in OBSERVATIONAL_FIELDS and not name.startswith('_trace_')
                    and not name.endswith(('_trace_event_id','_trace_event_ids','_trace_id','_trace_ids'))
                    for name in extras):
                omitted.update(extras.keys());fields['_extra_attrs']=None
            if not fields and not hasattr(value,'__dict__'):raise TypeError('unsupported semantic state object: '+result['type'])
            result['fields']={name:encode(item) for name,item in sorted(fields.items()) if not skip(name)}
        objects[number]=result
    discovered=set()
    to_discover=[{'tiles':tiles,'nations':nations,'globals':globals_state,'extra':extra}]
    while to_discover:
        value=to_discover.pop()
        if isinstance(value,types.FunctionType):
            if id(value) not in discovered:
                discovered.add(id(value))
                to_discover.extend((value.__defaults__,value.__kwdefaults__,value.__dict__))
                to_discover.extend(cell.cell_contents for cell in value.__closure__ or ())
            continue
        if isinstance(value,(str,bytes,int,float,bool,type(None),Enum,np.ndarray,np.generic,
                             type,types.BuiltinFunctionType,types.ModuleType,re.Pattern)):
            continue
        if id(value) in discovered:continue
        discovered.add(id(value))
        if isinstance(value,dict):items=list(value.items())
        elif isinstance(value,(list,tuple,deque,set,frozenset)):
            to_discover.extend(reversed(list(value)));continue
        else:items=list(fields_of(value).items())
        for name,item in items:
            if isinstance(name,str) and (name in OBSERVATIONAL_FIELDS or name.startswith('_trace_') or name.endswith(('_trace_event_id','_trace_event_ids','_trace_id','_trace_ids'))):continue
            if name in {'intent_id','project_id','bill_id','contract_id','petition_id'} or (name=='id' and isinstance(item,str) and item.startswith('bill_')):register(item)
        to_discover.extend(item for name,item in reversed(items) if not (isinstance(name,str) and (name in OBSERVATIONAL_FIELDS or name.startswith('_trace_') or name.endswith(('_trace_event_id','_trace_event_ids','_trace_id','_trace_ids')))))
    if identities:
        pattern=re.compile(r'(?<![0-9a-f])(?:'+'|'.join(re.escape(value) for value in sorted(identities,key=len,reverse=True))+r')(?![0-9a-f])')
    root=encode({'tiles':tiles,'nations':nations,'globals':globals_state,'extra':extra,
                 'python_rng':random.getstate(),'numpy_rng':np.random.get_state()})
    while pending:
        number,value=pending.popleft();fill(number,value)
    return {'graph':{'root':root,'objects':objects},'normalization':{'domain_uuid_count':len(identities),'omitted_observation_fields':dict(omitted)}}


def state_digest(state):
    """Hash canonical graph chunks without constructing a second giant string."""
    import hashlib,json
    digest=hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(state['graph']):
        digest.update(chunk.encode())
    return digest.hexdigest()


def graph_differences(left,right,limit=20):
    """Small iterative diagnostic; flat graph IDs preserve shared references."""
    differences=[];stack=[('',left,right)]
    while stack and len(differences)<limit:
        path,a,b=stack.pop()
        if type(a)!=type(b):
            differences.append({'path':path,'left':str(a)[:200],'right':str(b)[:200]});continue
        if isinstance(a,dict):
            for name in sorted(a.keys()|b.keys(),reverse=True):
                if name not in a or name not in b:differences.append({'path':path+'/'+name,'left_present':name in a,'right_present':name in b})
                else:stack.append((path+'/'+name,a[name],b[name]))
        elif isinstance(a,list):
            if len(a)!=len(b):differences.append({'path':path,'left_length':len(a),'right_length':len(b)})
            stack.extend((path+'/'+str(index),a[index],b[index]) for index in range(min(len(a),len(b))-1,-1,-1))
        elif a!=b:differences.append({'path':path,'left':a,'right':b})
    return differences[:limit]
