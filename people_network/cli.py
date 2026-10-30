"""Headless laboratory, scripted commands, replay and causal exports."""
import argparse
import json
from pathlib import Path
from .scenario import new_session
from .engine import command, step
from .persistence import save, load, replay
from .model import state_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',choices=['governing','displaced'],default='governing')
    parser.add_argument('--seed',type=int,default=4243)
    parser.add_argument('--ruleset',choices=['classic','patronage'],default='classic')
    parser.add_argument('--rounds',type=int,default=24)
    parser.add_argument('--commands',type=Path,help='JSON array of arrays: one list of commands per round')
    parser.add_argument('--load',type=Path)
    parser.add_argument('--save',type=Path)
    parser.add_argument('--export',type=Path)
    parser.add_argument('--no-rival',action='store_true')
    parser.add_argument('--autoplay',action='store_true',help='Use the public heuristic for the player too')
    args = parser.parse_args()
    session = load(args.load) if args.load else new_session(args.start,args.seed,args.ruleset)
    script = json.loads(args.commands.read_text()) if args.commands else []
    for n in range(args.rounds):
        for c in script[n] if n < len(script) else []:
            command(session,c.get('issuer','player'),c['kind'],**c.get('params',{}))
        if args.autoplay:
            from .rival import act
            act(session,'player')
        step(session,rival=not args.no_rival)
    replay(session)
    if args.save:
        save(session,args.save)
    if args.export:
        args.export.parent.mkdir(parents=True,exist_ok=True)
        args.export.write_text(json.dumps(session.payload(),indent=2)+'\n')
    if session.state.get('ruleset')=='patronage':
        from .patronage import result
        print(json.dumps(result(session.state),indent=2))
    print(json.dumps(dict(round=session.state['round'], officeholder=session.state['government']['officeholder'],
                         digest=state_digest(session.state),project=session.state['project'],
                         inflections=len(session.events),replay='passed'),indent=2))


if __name__ == '__main__':
    main()
