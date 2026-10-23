"""Sequential acceptance pairs against an immutable committed source archive.

Example: venv/bin/python causal_acceptance_matrix.py --profile smoke --out tmp/acceptance-smoke
The release profile uses two seeds, 30/100 sandbox turns and full authored
scenario horizons. Terminal scenarios stop naturally and report actual turns.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from causal_acceptance import SCENARIOS, SEEDS
from simulation_semantics import graph_differences

ROOT=Path(__file__).resolve().parent


def cases(profile):
    if profile=='smoke':return [(scenario,SEEDS[scenario],3) for scenario in SCENARIOS]
    return ([('default',seed,turns) for seed in (4242,4243) for turns in (30,100)]
            +[(scenario,SEEDS[scenario]+offset,20) for scenario in SCENARIOS[1:] for offset in (0,1)])


def summarize(left,right):
    same=left['semantic_sha256']==right['semantic_sha256']
    checks={
        'semantic_state_rng_actions_equal':same,
        'completed_turns_equal':left['completed_turns']==right['completed_turns'],
        'currency_violations_absent':not left['currency_violations'] and not right['currency_violations'],
        'structural_and_supported_checks_pass':left['audit']['structural_and_supported_formula_checks_pass'],
        'changed_snapshots_explained':not any(row.get('unexplained',0) for row in left['coverage'].values()),
        'public_account_closure_pass':not left['coverage']['_treasury_account_closure']['gaps'],
    }
    result={'scenario':left['scenario'],'seed':left['seed'],'requested_turns':left['requested_turns'],
            'completed_turns':left['completed_turns'],'checks':checks,'pass':all(checks.values()),
            'on_report':left['report_file'],'off_report':right['report_file'],
            'step_runtime_ratio_on_over_off':left['step_seconds']/right['step_seconds'],
            'trace_bytes_per_completed_turn':left['trace_bytes']/max(1,left['completed_turns'])}
    if left.get('step_cpu_seconds') is not None and right.get('step_cpu_seconds'):
        result['step_cpu_ratio_on_over_off']=left['step_cpu_seconds']/right['step_cpu_seconds']
    if left.get('decoded_trace_bytes') is not None:
        result['decoded_trace_bytes_per_completed_turn']=left['decoded_trace_bytes']/max(1,left['completed_turns'])
    if not same:
        with gzip.open(left['semantic_state_file'],'rt') as file:a=json.load(file)
        with gzip.open(right['semantic_state_file'],'rt') as file:b=json.load(file)
        result['state_differences']=graph_differences(a,b)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('smoke','release'),default='smoke')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--source-commit',default='HEAD')
    parser.add_argument('--case', action='append', default=[], metavar='SCENARIO:SEED:TURNS',
                        help='run selected native on/off pairs instead of the full profile')
    args=parser.parse_args()
    selected=[]
    for value in args.case:
        try:
            scenario, seed, turns = value.split(':')
            seed, turns = int(seed), int(turns)
            if scenario not in SCENARIOS or turns < 1:
                raise ValueError
        except ValueError:
            parser.error('--case must be SCENARIO:SEED:TURNS with a known scenario and positive turns')
        selected.append((scenario,seed,turns))
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(['git','rev-parse',args.source_commit],cwd=ROOT,text=True).strip()
    source=out/'source'
    if source.exists():parser.error('output source directory already exists; use a fresh output directory')
    source.mkdir()
    archive=out/'source.tar'
    with archive.open('wb') as file:subprocess.run(['git','archive',commit],cwd=ROOT,stdout=file,check=True)
    with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
    archive.unlink()
    env=dict(os.environ,PYTHONHASHSEED='0',MPLCONFIGDIR='/private/tmp/plunder-mpl',
             SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',COC_ACCEPTANCE_SOURCE_COMMIT=commit)
    result={'source_commit':commit,'profile':args.profile,'cases':[],'failures':[],'complete':False}
    if selected:result['selected_cases']=[list(case) for case in selected]
    def publish():
        temporary=out/'matrix.json.pending';temporary.write_text(json.dumps(result,indent=2,sort_keys=True))
        temporary.replace(out/'matrix.json')
    publish()
    for scenario,seed,turns in selected or cases(args.profile):
        reports={}
        for mode in ('on','off'):
            stem=f'{scenario}-{seed}-{turns}-{mode}';report=out/(stem+'.json')
            command=[sys.executable,str(source/'causal_acceptance.py'),'--scenario',scenario,
                     '--seed',str(seed),'--turns',str(turns),'--trace',mode,'--out',str(report)]
            print('START '+stem,flush=True)
            with (out/(stem+'.log')).open('w') as log:
                completed=subprocess.run(command,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
            if completed.returncode:
                result['failures'].append({'case':stem,'returncode':completed.returncode,'log':str(log.name)})
                publish();continue
            data=json.loads(report.read_text());data['report_file']=str(report);reports[mode]=data
        if set(reports)=={'on','off'}:
            pair=summarize(reports['on'],reports['off']);result['cases'].append(pair)
            print(('PASS ' if pair['pass'] else 'FAIL ')+f'{scenario}-{seed}-{turns}',flush=True)
            publish()
    result['complete']=True
    result['pass']=not result['failures'] and all(row['pass'] for row in result['cases'])
    publish()
    return 0 if result['pass'] else 1


if __name__=='__main__':raise SystemExit(main())
