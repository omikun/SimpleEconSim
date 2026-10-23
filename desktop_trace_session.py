"""Attach the same causal recorder to both native desktop world entry points."""
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
import uuid


def attach(world):
    if world.get('_trace_session') is not None:
        return world['_trace_session']
    from run_trace import RunTrace
    from trace_snapshots import sample, resident_census, entity_role_census
    from labor_census_trace import capture_labor_censuses
    import forex
    identity='desktop-'+uuid.uuid4().hex
    trace=RunTrace(Path(__file__).resolve().parent/'tmp'/'traces'/(identity+'.ctr'),identity,
                   seed=world.get('seed'),scenario=world.get('scenario_id'))
    tiles,nations=world['tiles'],world['nations']
    clock={'turn':world.get('turn',0),'epoch':0,'next':1,'phase':'setup'}
    for source in [*tiles,*nations]:
        source._run_trace=trace;source._collective_trace_clock=clock
    trace.bank_book.register_tiles(tiles,clock)
    trace.treasury_book.register_nations(nations,clock)
    for tile in tiles:forex.flush_pending_trader_float_traces(tile)
    session=SimpleNamespace(tiles=tiles,nations=nations,run_trace=trace,_nation_history={})
    session._trace_previous_labor_censuses=capture_labor_censuses(tiles)
    session._trace_previous=sample(tiles,nations,labor_censuses=session._trace_previous_labor_censuses)
    session._trace_previous_people=resident_census(tiles)
    session._trace_previous_roles=entity_role_census(tiles)
    session._trace_previous_nation_membership={nation.name:[tile.name for tile in nation.tiles] for nation in nations}
    session._trace_previous_tile_currencies={tile.name:getattr(tile,'home_currency',None) for tile in tiles}
    session._trace_previous_nation_currencies={nation.name:getattr(nation,'currency',None) for nation in nations}
    session.pending_start=trace.count
    world['_trace_session']=session
    world['run_trace']=trace
    return session


def traced_world_builder(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        world=function(*args,**kwargs)
        attach(world)
        return world
    return wrapped


def traced_world_step(function):
    @wraps(function)
    def wrapped(world,*args,**kwargs):
        from trace_snapshots import record, sample
        session=attach(world);trace=session.run_trace
        clock=session.tiles[0]._collective_trace_clock if session.tiles else None
        if clock is None:return function(world,*args,**kwargs)
        # Native player actions occur between ticks. Close their pending stock
        # boundary before step_turn starts a fresh gameplay turn.
        if trace.count!=session.pending_start or sample(session.tiles,session.nations)!=session._trace_previous:
            record(session);trace.checkpoint(clock)
        turn_before=world.get('turn',0)
        result=function(world,*args,**kwargs)
        session.tiles=world['tiles'];session.nations=world['nations']
        if world.get('turn',0)!=turn_before:
            record(session);trace.checkpoint(clock)
        clock['epoch']=clock.get('epoch',0)+1
        clock['phase']='between_turns'
        trace.emit(clock,kind='native_command_boundary',record_class='audit')
        session.pending_start=trace.count
        return result
    return wrapped
