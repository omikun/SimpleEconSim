"""Run a fresh-process causal acceptance/benchmark fixture.

Each child owns one simulation because gameplay registries are process-global.
Timing/RSS are measured before semantic diagnostics and trace inspection. Native
scenario endings are respected; requested and completed turns are both reported.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import sys
import time

import numpy as np

from simulation_semantics import canonical_state,state_digest,normalized_metrics

SCENARIOS=('default','labor_frontier_rivalry','supply_rivalry','egypt_1877')
SEEDS={'default':4242,'labor_frontier_rivalry':612,'supply_rivalry':812,'egypt_1877':1877}


def run(scenario,seed,turns,traced,out,*,audit_trace=True):
    if scenario=='egypt_1877':
        from worldview_engine import build_world_view,step_world
        from world_config import set_map_topology
        set_map_topology('voronoi')
        random.seed(seed);np.random.seed(seed)
        started=time.perf_counter()
        world=build_world_view(seed=seed,terrain_seed=seed,nation_seed=seed,scenario_id=scenario,trace_enabled=traced)
        def step():return step_world(world)
        def context():return world['turn'],world['tiles'],world['nations'],world.get('scenario_state',{}),world.get('run_trace')
        def extra():return {'turn':world['turn'],'pair_orders':world['pair_orders'],'currencies':world['currencies'],
                            'scenario_state':world.get('scenario_state',{}),'currency_totals':world['currency_totals'],
                            'violations':world.get('violations',[]),'player_nation_name':world.get('player_nation_name')}
    else:
        from sim_server.sim_server import SimServer
        random.seed(seed);np.random.seed(seed)
        started=time.perf_counter()
        server=SimServer(seed=seed,terrain_seed=seed,nation_seed=seed,
                         topology='voronoi' if scenario=='default' else 'hex',
                         scenario_id=None if scenario=='default' else scenario,trace_enabled=traced)
        def step():return server.step()
        def context():return server.turn,server.tiles,server.nations,getattr(server,'scenario_state',{}),server.run_trace
        def extra():return {'turn':server.turn,'pair_orders':server.pair_orders,'currencies':server.currencies,
                            'scenario_state':getattr(server,'scenario_state',{}),'currency_totals':server.currency_totals,
                            'violations':server.violations,'player_nation_name':server.player_nation_name,
                            'nation_history':server._nation_history}
    setup_seconds=time.perf_counter()-started
    starting_turn=context()[0]
    durations=[];violations=[]
    for number in range(turns):
        before,*_=context();tick=time.perf_counter();step();durations.append(time.perf_counter()-tick)
        after,tiles,nations,state,trace=context()
        violations.extend(extra()['violations'])
        if after==before:break
        if (number+1)%10==0:print(f'{scenario} seed={seed} trace={traced} turn={after}',flush=True)
        if state.get('ending'):break
    turn,tiles,nations,scenario_state,trace=context()
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
    result={'scenario':scenario,'runner':'worldview_engine' if scenario=='egypt_1877' else 'SimServer',
            'seed':seed,'python_hash_seed':os.environ.get('PYTHONHASHSEED'),
            'requested_turns':turns,'starting_turn':starting_turn,'final_turn':turn,
            'completed_turns':turn-starting_turn,'native_ending':scenario_state.get('ending'),
            'trace_enabled':traced,'setup_seconds':setup_seconds,'step_seconds':sum(durations),
            'median_turn_seconds':statistics.median(durations) if durations else None,'peak_simulation_rss_mb':rss,
            'currency_violations':violations,'python':platform.python_version(),'numpy':np.__version__,
            'platform':platform.platform(),'cpu_count':os.cpu_count(),
            'source_commit':os.environ.get('COC_ACCEPTANCE_SOURCE_COMMIT') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'immutable_source_snapshot':bool(os.environ.get('COC_ACCEPTANCE_SOURCE_COMMIT')),
            'tracked_worktree_dirty':None if os.environ.get('COC_ACCEPTANCE_SOURCE_COMMIT') else bool(subprocess.check_output(['git','diff','--name-only'],text=True).strip())}
    # All native decisions and quantities remain in the economic object graph.
    canonical=canonical_state(tiles,nations,extra=extra())
    result['semantic_sha256']=state_digest(canonical);result['normalization']=canonical['normalization']
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    state_path=out.with_suffix('.state.json.gz')
    with gzip.open(state_path,'wt') as stream:
        json.dump(canonical['graph'],stream,sort_keys=True,separators=(',',':'),allow_nan=False)
    result['semantic_state_file']=str(state_path)
    if trace is not None:
        from trace_index import TraceIndex
        from trace_codec import iter_payloads
        result['trace_path']=str(trace.path);result['trace_bytes']=trace.path.stat().st_size
        result['rows']=trace.count;result['bank_objects_retained']=len(trace.bank_book.banks)
        result['public_accounts_retained']=len(trace.treasury_book.accounts)
        result['known_event_ids_cached']=len(trace._known_event_ids)
        result['shipment_departures_retained']=len(trace._shipment_departure_events)
        payloads=iter_payloads(trace.path)
        try:
            next(payloads);first=json.loads(next(payloads))['event_id']
        finally:payloads.close()
        index=TraceIndex(trace.path);index.index_path.unlink(missing_ok=True)
        begin=time.perf_counter();index.query(event_id=first,limit=1)
        result['index_build_seconds']=time.perf_counter()-begin
        begin=time.perf_counter();TraceIndex(trace.path).query(event_id=first,limit=1)
        result['indexed_application_cold_lookup_seconds']=time.perf_counter()-begin
        timings=[]
        for _ in range(5):
            begin=time.perf_counter();index.query(event_id=first,limit=1);timings.append(time.perf_counter()-begin)
        result['median_warm_lookup_seconds']=statistics.median(timings)
        if audit_trace:
            from trace_audit import audit
            from trace_coverage import coverage
            begin=time.perf_counter();result['audit']=audit(trace.path);result['coverage']=coverage(trace.path)
            result['inspection_seconds']=time.perf_counter()-begin
    out.write_text(json.dumps(result,indent=2,sort_keys=True))
    print(json.dumps({'report':str(out),'completed_turns':turn,'semantic_sha256':result['semantic_sha256']},sort_keys=True),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=SCENARIOS,default='default')
    parser.add_argument('--seed',type=int)
    parser.add_argument('--turns',type=int,default=3)
    parser.add_argument('--trace',choices=('on','off'),default='on')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--skip-audit',action='store_true')
    args=parser.parse_args()
    if args.turns<1:parser.error('--turns must be positive')
    run(args.scenario,args.seed if args.seed is not None else SEEDS[args.scenario],args.turns,args.trace=='on',args.out,audit_trace=not args.skip_audit)


if __name__=='__main__':main()
