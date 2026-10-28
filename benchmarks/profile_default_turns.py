"""Profile native default turns in isolated sequential timing/profile processes.

Run with PYTHONHASHSEED=0. Map generation and summary collection are outside
step profiling. cProfile times include instrumentation overhead; the separate
ordinary run is the source of gameplay latency measurements.
"""
import argparse
import cProfile
import hashlib
import gzip
import json
import os
from pathlib import Path
import pstats
import random
import subprocess
import sys
import time
from types import SimpleNamespace


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def summarize_profile(path,root):
    stats=pstats.Stats(str(path))
    def location(key):
        filename,line,function=key
        try:filename=str(Path(filename).relative_to(root))
        except ValueError:pass
        return {'file':filename,'line':line,'function':function}
    functions=[];files={}
    for key,(primitive,calls,own,cumulative,callers) in stats.stats.items():
        item={**location(key),'primitive_calls':primitive,'calls':calls,
              'self_seconds':own,'cumulative_seconds':cumulative}
        item['callers']=[{**location(caller),'stats':values} for caller,values in
                         sorted(callers.items(),key=lambda pair:pair[1][3],reverse=True)[:8]]
        functions.append(item)
        filename=item['file'];files[filename]=files.get(filename,0)+own
    return {'total_calls':stats.total_calls,'primitive_calls':stats.prim_calls,
            'total_self_seconds':stats.total_tt,
            'top_self':sorted(functions,key=lambda item:item['self_seconds'],reverse=True)[:80],
            'top_cumulative':sorted(functions,key=lambda item:item['cumulative_seconds'],reverse=True)[:80],
            'self_seconds_by_file':dict(sorted(files.items(),key=lambda pair:pair[1],reverse=True))}


def worker(args):
    os.environ.update(COC_TRACE_STORAGE='packed',COC_TRACE_COVERAGE='1',COC_TRACE_SPARSE='1',
                      COC_TRACE_TEMPLATES='1',COC_TRACE_SHARED_INPUTS='1',COC_TRACE_NATIONAL_SUMMARIES='1')
    import numpy as np
    from client.worldview.worldview_engine import build_world_view,step_world
    from simulation_semantics import normalized_metrics
    np.random.seed(args.seed)
    started=time.perf_counter()
    world=build_world_view(seed=args.seed,terrain_seed=args.seed,nation_seed=args.seed,
                          **({'scenario_id':args.scenario} if args.scenario else {}))
    build_seconds=time.perf_counter()-started
    trace=world['run_trace'];turns=[];profile_paths=[]
    previous_count=trace.event_count;previous_expanded=trace.count
    try:
        for _ in range(args.turns):
            profiler=cProfile.Profile() if args.worker=='profile' else None
            started=time.perf_counter()
            if profiler:profiler.enable()
            try:step_world(world)
            finally:
                if profiler:profiler.disable()
            seconds=time.perf_counter()-started
            row={'turn':world['turn'],'seconds':seconds,'event_records':trace.event_count-previous_count,
                 'expanded_records':trace.count-previous_expanded}
            previous_count=trace.event_count;previous_expanded=trace.count
            if profiler:
                path=args.output/f'turn-{world["turn"]:02}.prof'
                profiler.dump_stats(str(path));profile_paths.append(path)
            turns.append(row)
            print(json.dumps({'mode':args.worker,**row}),flush=True)
        trace.publish()
        metrics=normalized_metrics(SimpleNamespace(tiles=world['tiles'],nations=world['nations']))
        result={'mode':args.worker,'seed':args.seed,'tiles':len(world['tiles']),
                'build_seconds':build_seconds,'turns':turns,'total_step_seconds':sum(row['seconds'] for row in turns),
                'trace':str(trace.path),'trace_bytes':trace.path.stat().st_size,
                'event_records':trace.event_count,'expanded_records':trace.count,
                'metrics_digest':digest(sorted(metrics.items())),
                'python_rng_digest':hashlib.sha256(repr(random.getstate()).encode()).hexdigest(),
                'numpy_rng_digest':hashlib.sha256(repr(np.random.get_state()).encode()).hexdigest()}
        if args.capture_state:
            from simulation_semantics import canonical_state,state_digest
            state=canonical_state(world['tiles'],world['nations'],extra={
                'turn':world['turn'],'pair_orders':world['pair_orders'],'currencies':world['currencies'],
                'currency_totals':world['currency_totals'],'violations':world['violations']})
            result['economic_state_digest']=state_digest(state)
            result['state_normalization']=state['normalization']
            with gzip.open(args.output/(args.worker+'-state.json.gz'),'wt') as output:
                json.dump(state['graph'],output,separators=(',',':'))
        from trace_index import TraceIndex
        index=TraceIndex(trace.path)
        subject={'type':'tile','id':world['tiles'][0].name}
        started=time.perf_counter();options=index.available_metrics(turn=world['turn'],subject=subject)
        result['catalog_cold_seconds']=time.perf_counter()-started
        started=time.perf_counter();again=index.available_metrics(turn=world['turn'],subject=subject)
        result['catalog_warm_seconds']=time.perf_counter()-started
        assert options==again
        result['catalog_options']=len(options)
        if profile_paths:
            combined=pstats.Stats(str(profile_paths[0]))
            for path in profile_paths[1:]:combined.add(str(path))
            combined_path=args.output/'combined.prof';combined.dump_stats(str(combined_path))
            root=Path(__file__).resolve().parents[1]
            result['profile']=summarize_profile(combined_path,root)
            result['per_turn_hotspots']=[{'turn':row['turn'],
                'top_cumulative':summarize_profile(path,root)['top_cumulative'][:12],
                'top_self':summarize_profile(path,root)['top_self'][:12]}
                for row,path in zip(turns,profile_paths)]
        (args.output/(args.worker+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    finally:trace._compact_writer.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=777)
    parser.add_argument('--turns',type=int,default=10)
    parser.add_argument('--output',type=Path,default=Path('tmp/default-ten-turn-profile'))
    parser.add_argument('--worker',choices=('timing','profile'))
    parser.add_argument('--scenario',choices=('egypt_1877',))
    parser.add_argument('--capture-state',action='store_true',help='compare the full canonical economy outside measured steps')
    args=parser.parse_args()
    if args.turns<1:parser.error('--turns must be positive')
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    if args.worker:return worker(args)
    root=Path(__file__).resolve().parents[1]
    for mode in ('timing','profile'):
        print('Starting isolated',mode,'run',flush=True)
        subprocess.run([sys.executable,'-m','benchmarks.profile_default_turns',
                        '--seed',str(args.seed),'--turns',str(args.turns),
                        '--output',str(args.output),'--worker',mode,
                        *(['--scenario',args.scenario] if args.scenario else []),
                        *(['--capture-state'] if args.capture_state else [])],check=True,cwd=root,
                       env={**os.environ,'PYTHONHASHSEED':'0'})
    reports={mode:json.loads((args.output/(mode+'.json')).read_text()) for mode in ('timing','profile')}
    for key in ('metrics_digest','python_rng_digest','numpy_rng_digest','event_records','expanded_records'):
        if reports['timing'][key]!=reports['profile'][key]:raise AssertionError('Profile changed '+key)
    if ([row['event_records'] for row in reports['timing']['turns']]
            !=[row['event_records'] for row in reports['profile']['turns']]):
        raise AssertionError('Profile changed per-turn event counts')
    report={'seed':args.seed,'turns':args.turns,'hash_seed':0,
            'notes':['Separate sequential timing/profile processes, V5 tracing enabled.',
                     'Map construction, summary generation and profile serialization excluded from step timing.',
                     'cProfile distorts timings and heavily called Python loops; use ordinary run for latency.',
                     'Cumulative times overlap: do not sum parent and child rows.',
                     'No UI rendering, F12 query, provider call or full trace audit in measured steps.'],
            'profile_and_timing_metrics_rng_and_counts_match':True,'reports':reports}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Completed:',args.output/'report.json',flush=True)


if __name__=='__main__':main()
