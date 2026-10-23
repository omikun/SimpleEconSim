"""Prepare a deterministic inspector browser fixture from an actual .ctr run."""
import argparse
import json
from pathlib import Path
from trace_explanation import ExplanationReader


def build(path,turn=1):
    reader=ExplanationReader(path,Path(path).stat().st_size)
    rows=reader.index.query(turn=turn,kind='treasury_account_closure',limit=1,boundary=reader.boundary)['events']
    if not rows:raise ValueError('no treasury closure in selected turn')
    root=rows[0];events={root['event_id']:root}
    for ident in root.get('cause_event_ids',()):
        event=reader.lookup(ident)
        if event is None:continue
        events[ident]=event
        for cause in event.get('cause_event_ids',()):
            source=reader.lookup(cause)
            if source is not None:events[cause]=source
    return {'root':root['event_id'],'boundary':reader.boundary,'rows':events,
            'explanations':{ident:reader.explain(event) for ident,event in events.items()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--turn',type=int,default=1)
    parser.add_argument('--out',type=Path,default=Path('tmp/trace_inspector_fixture.json'))
    args=parser.parse_args();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(build(args.run,args.turn),sort_keys=True))
    print(args.out)


if __name__=='__main__':main()
