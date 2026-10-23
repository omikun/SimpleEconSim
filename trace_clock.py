"""Trace boundaries are finer than gameplay turns; commands do not age agents."""
from functools import wraps


def boundary(clock):
    return clock.get('turn',0),clock.get('epoch',0)


def trace_command_boundary(function):
    @wraps(function)
    def wrapped(server,command):
        kind=getattr(command.cmd_type,'value',str(command.cmd_type))
        if kind in {'STEP','PLAY','PAUSE','SET_SPEED','SELECT_NATION','SELECT_REGION'}:
            return function(server,command)
        trace=getattr(server,'run_trace',None)
        tiles=getattr(server,'tiles',())
        if trace is None or not tiles:return function(server,command)
        with server._lock:
            supplied_id=getattr(command,'command_id',None)
            request=command.to_dict()
            if supplied_id is not None:
                stable_id=f'client:{command.client_id}:{supplied_id}'
                existing=trace.query(subject={'type':'command','id':stable_id},kind='player_command_result',limit=1)['events']
                if existing:
                    inputs=existing[0]['inputs']
                    if inputs['request']!=request:
                        return {'success':False,'error':'Command ID was already used for a different request.'}
                    return inputs['response']
            clock=tiles[0]._collective_trace_clock
            clock['epoch']=clock.get('epoch',0)+1
            clock['phase']='player_command'
            operation_id=stable_id if supplied_id is not None else f'{trace.run_id}:command:{clock["next"]}'
            started=trace.emit(clock,kind='player_command_started',record_class='decision',
                               subject={'type':'command','id':operation_id},
                               inputs={'command':kind,'payload':command.payload,'operation_id':operation_id})
            clock['command_event_id']=started
            clock['command_id']=operation_id
            try:
                result=function(server,command)
                trace.emit(clock,kind='player_command_result',record_class='outcome',
                           subject={'type':'command','id':operation_id},
                           inputs={'command':kind,'success':bool(result.get('success',False)),
                                   'message':result.get('message',result.get('error')),
                                   'request':request,'response':result},
                           cause_event_ids=[started])
                return result
            finally:
                from trace_snapshots import record
                record(server)
                trace.checkpoint(clock)
                clock.pop('command_event_id',None);clock.pop('command_id',None)
    return wrapped
