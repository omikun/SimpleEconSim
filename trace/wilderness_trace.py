"""Sparse frontier state and exact-boundary coverage, without padded economy facts."""
import math
from trace_clock import boundary
from trace_packing import _same

VERSION = 'minimal-wilderness.v1'
MAX_TILES = 512
FIELDS = (('frontier.native_population','wilderness_pop','people'),
          ('ecology.soil_fertility','soil_fertility','ratio'),
          ('ecology.nutrition_density','nutrition_density','ratio'),
          ('ecology.pollution_air','pollution_air','index'),
          ('ecology.pollution_water','pollution_water','index'),
          ('ecology.pollution_soil','pollution_soil','index'))
MESSAGE = ('This wilderness tile has no operating economy or resident agents at this boundary. '
           'Padded market, tax and labor chart values are display defaults, not observed economic statistics. '
           'Background native inhabitants are counted separately. Actual frontier and environmental events remain recorded.')


def policy(tile):
    return getattr(getattr(tile,'_run_trace',None),'wilderness',None)


def quiet(tile):
    recorder = policy(tile)
    return recorder is not None and recorder.quiet(tile)


def validate_record(row):
    """Validate new policy records without synthesizing any per-metric views."""
    kind=row.get('kind')
    if kind not in ('wilderness_initial_state','wilderness_state_observation','wilderness_domain_coverage'):return
    inputs=row['inputs']
    if inputs.get('capture_policy')!=VERSION:raise ValueError('Unsupported wilderness capture policy')
    if kind=='wilderness_domain_coverage':
        names=inputs['tiles'];refs=inputs['state_refs']
        if (not isinstance(names,list) or not 1<=len(names)<=MAX_TILES
                or not all(type(name) is str for name in names) or len(set(names))!=len(names)
                or not isinstance(refs,dict) or not all(type(ident) is str and isinstance(members,list)
                    and all(type(name) is str for name in members) for ident,members in refs.items())):
            raise ValueError('Invalid wilderness coverage')
        covered=[name for members in refs.values() for name in members]
        if (len(covered)!=len(names) or set(covered)!=set(names)
                or set(row.get('cause_event_ids') or [])!=set(refs)
                or inputs.get('fields')!=[field[0] for field in FIELDS]
                or inputs.get('domains')!=['no_operating_economy','no_resident_agents','watched_frontier_state']):
            raise ValueError('Invalid wilderness coverage references')
    else:
        states=inputs['states']
        if not isinstance(states,dict) or not 1<=len(states)<=MAX_TILES:raise ValueError('Invalid wilderness state')
        for name,state in states.items():
            if (type(name) is not str or not isinstance(state,list) or len(state)!=len(FIELDS)
                    or any(type(value) not in (int,float) or not math.isfinite(value) for value in state)):
                raise ValueError('Invalid wilderness state values')
        if kind=='wilderness_state_observation' and list(states)!=[row['subject']['id']]:
            raise ValueError('Invalid wilderness state subject')


class WildernessTrace:
    def __init__(self,trace,enabled):
        self.trace=trace;self.enabled=enabled;self.regions={};self.members=set()
        self.states={};self.sources={};self.modes={};self.observed_modes={};self.quotes={};self.last_boundary=None

    def register(self,tiles,nations):
        self.regions={str(tile.name):tile for tile in tiles}
        self.members={str(tile.name) for nation in nations for tile in nation.tiles}

    def quiet(self,tile):
        mode=self._eligible(tile);name=str(tile.name)
        if self.observed_modes.get(name) is True and not mode:self.clear_quotes(name)
        self.observed_modes[name]=mode
        return mode

    def clear_quotes(self,name):
        for key in [key for key in self.quotes if key[0]==name]:
            ident=self.quotes.pop(key)[1]
            if self.trace._latest_reference_price_events.get(key)==ident:
                self.trace._latest_reference_price_events.pop(key)

    def _eligible(self,tile):
        if (not self.enabled or str(tile.name) not in self.regions or not getattr(tile,'wilderness',False)
                or str(tile.name) in self.members or getattr(tile,'owner_nation',None) is not None
                or getattr(tile,'agents',()) or getattr(tile,'trader_agents',())
                or any(getattr(tile,key,None) is not None for key in ('bank','gov','charity','home_currency'))
                or getattr(tile,'military_units',()) or getattr(tile,'births_this_turn',0)
                or getattr(tile,'deaths_this_turn',0)):
            return False
        factions=getattr(getattr(tile,'factions',None),'factions',{}) or {}
        if any(getattr(group,'membership',()) for group in factions.values()):return False
        if any(getattr(project,'status','') not in ('completed','cancelled')
               for project in getattr(tile,'construction_projects',())):return False
        routes=getattr(tile,'_all_routes',lambda:())()
        return not any(getattr(route,field,()) for route in routes
                       for field in ('pending','in_transit','delivered_this_turn','parked_this_turn'))

    def state(self,tile):
        result=tuple(getattr(tile,field,0) for _,field,_ in FIELDS)
        if any(type(value) not in (int,float) or not math.isfinite(value) for value in result):
            raise ValueError('Invalid wilderness state value')
        return result

    def reference(self,tile,good):
        """Observe the current recipe value at the consumption point, never at F12 read time."""
        recipe=next((recipe for item,recipe in tile.recipes.items()
                     if getattr(item,'name',str(item))==good),None)
        if not recipe or 'price' not in recipe:return None
        value=float(recipe['price']);key=(str(tile.name),good)
        if not math.isfinite(value):raise ValueError('Invalid wilderness reference price')
        previous=self.quotes.get(key)
        signature=(value,getattr(tile,'home_currency',None),bool(getattr(tile,'wilderness',False)))
        if previous and all(_same(left,right) for left,right in zip(previous[0],signature)):
            self.trace._known_event_ids.add(previous[1])
            return previous[1]
        clock=tile._collective_trace_clock
        ident=self.trace.emit(clock,kind='wilderness_reference_price_observation',
            subject={'type':'tile','id':str(tile.name),'good':good},metric_id='goods.price',
            unit='local_currency_per_unit',after=value,
            inputs={'basis':'recipe_reference_without_operating_market','market_active':False,
                    'observation_point':'consuming_calculation','currency':getattr(tile,'home_currency',None)},
            explanation_status='observed_reference_only')
        if self.trace.write_error:raise OSError(self.trace.write_error)
        self.quotes[key]=(signature,ident)
        return ident

    def record(self,tiles,clock):
        if not self.enabled:return
        current_boundary=boundary(clock)
        if self.last_boundary is not None:
            turn,epoch=self.last_boundary;new_turn,new_epoch=current_boundary
            if not ((new_turn==turn and epoch<=new_epoch<=epoch+1) or new_turn==turn+1):
                self.states.clear();self.sources.clear()
        eligible=[];initial=[]
        for tile in tiles:
            name=str(tile.name);mode=self.quiet(tile);old_mode=self.modes.get(name)
            if old_mode is not None and mode!=old_mode:
                self.trace.emit(clock,kind='wilderness_capture_transition',subject={'type':'tile','id':name},
                    inputs={'capture_policy':VERSION,'from':'minimal' if old_mode else 'full',
                            'to':'minimal' if mode else 'full'})
                self.clear_quotes(name)
            self.modes[name]=mode
            if not mode:continue
            state=self.state(tile);previous=self.states.get(name) if old_mode is not False else None
            if previous is None:initial.append((name,state))
            elif any(not _same(left,right) for left,right in zip(state,previous)):
                causes=[]
                for index,(metric,_,unit) in enumerate(FIELDS):
                    if not _same(previous[index],state[index]):
                        causes.append(self.trace.snapshot(clock,subject={'type':'tile','id':name},
                            metric_id=metric,unit=unit,before=previous[index],after=state[index]))
                ident=self.trace.emit(clock,kind='wilderness_state_observation',
                    subject={'type':'tile','id':name},metric_id='world.wilderness_state',
                    inputs={'capture_policy':VERSION,'states':{name:list(state)}},
                    cause_event_ids=[self.sources[name],*causes])
                self.sources[name]=ident
            self.states[name]=state;eligible.append(name)
        for start in range(0,len(initial),MAX_TILES):
            batch=initial[start:start+MAX_TILES]
            ident=self.trace.emit(clock,kind='wilderness_initial_state',subject={'type':'world','id':'wilderness'},
                inputs={'capture_policy':VERSION,'states':dict((name,list(state)) for name,state in batch),
                        'fields':[metric for metric,_,_ in FIELDS]})
            for name,_ in batch:self.sources[name]=ident
        for start in range(0,len(eligible),MAX_TILES):
            names=eligible[start:start+MAX_TILES];refs={}
            for name in names:refs.setdefault(self.sources[name],[]).append(name)
            self.trace.emit(clock,kind='wilderness_domain_coverage',subject={'type':'world','id':'wilderness'},
                inputs={'capture_policy':VERSION,'tiles':names,'state_refs':refs,
                        'domains':['no_operating_economy','no_resident_agents','watched_frontier_state'],
                        'fields':[metric for metric,_,_ in FIELDS]},cause_event_ids=list(refs))
        if self.trace.write_error:raise OSError(self.trace.write_error)
        self.last_boundary=current_boundary
