"""Reproducible behavioral acceptance, replay, and compact-trace measurements.

These scripted checks do not substitute for human enjoyment testing.
"""
import argparse
import json
import time
from pathlib import Path
from people_network.scenario import new_session
from people_network.engine import command, step, CommandError
from people_network.persistence import replay
from people_network.model import state_digest
from people_network.rival import act


def recovery_actions(session):
    # The public policy now bargains over service allocations and honors group
    # conditions as well as rotating organizers and recruiting councillors.
    act(session,'player')


def run_case(start,policy,rounds=24):
    session=new_session(start)
    elapsed=[]
    fixture=Path(__file__).resolve().parents[1]/'scenarios/people_network/playthroughs/govern_restore.json'
    script=json.loads(fixture.read_text()) if policy=='cycle' else []
    for index in range(rounds):
        if policy=='cycle':
            for c in script[index]:command(session,c['issuer'],c['kind'],**c['params'])
        elif policy=='hold':act(session,'player')
        elif policy=='recover':recovery_actions(session)
        begin=time.perf_counter();step(session);elapsed.append(1000*(time.perf_counter()-begin))
    replay(session)
    transfers=[dict(round=e['round']+1,before=e['before'],after=e['after']) for e in session.events if e['kind']=='office_transfer']
    size=len(json.dumps(session.payload(),separators=(',',':')).encode())
    return session,dict(start=start,policy=policy,rounds=rounds,officeholder=session.state['government']['officeholder'],
                        transfers=transfers,project=session.state['project'],allocations=session.state['government']['allocations'],
                        agreements=[dict(group=a['group'],leader=a['leader'],status=a['status'],breaches=a['breaches']) for a in session.state['agreements']],
                        exhausted=sum(e['kind']=='organizer_exhausted' for e in session.events),version=session.state['version'],mean_step_ms=sum(elapsed)/len(elapsed),
                        max_step_ms=max(elapsed),trace_bytes=size,bytes_per_round=size/rounds,
                        semantic_records=len(session.events),digest=state_digest(session.state),replay='passed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('outputs/people_network/acceptance.json'))
    args=parser.parse_args()
    results=[]
    for start,policy,rounds in [('governing','hold',24),('governing','pass',24),('displaced','recover',24),('displaced','pass',24),('governing','cycle',32)]:
        session,result=run_case(start,policy,rounds)
        results.append(result)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        stem=args.output.parent/f'{start}-{policy}'
        stem.with_suffix('.commands.json').write_text(json.dumps([[c for c in r['commands'] if c['issuer']=='player'] for r in session.journal],indent=2)+'\n')
        stem.with_suffix('.trace.json').write_text(json.dumps(session.payload(),separators=(',',':'))+'\n')
    assert results[0]['officeholder']=='player','A legal hold-office path is required'
    assert any(t['after']=='rival' for t in results[1]['transfers']),'Passive government must be vulnerable'
    assert any(t['after']=='player' for t in results[2]['transfers']),'A legal restoration path is required'
    assert results[3]['officeholder']=='rival','Restoration must not be automatic'
    assert [t['after'] for t in results[4]['transfers'][:2]]==['rival','player'],'Continuous displacement and restoration must work'
    args.output.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
