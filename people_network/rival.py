"""Public-state heuristic with the same action budget and command API as the player."""
from copy import deepcopy
from .graph import Graph
from .engine import command, CommandError


def choose(state, issuer):
    gov, people = state['government'], state['people']
    candidates = []
    def offer(score, kind, **params):
        candidates.append((score, kind, params))
    if gov['officeholder'] != issuer and gov['support_streak'][issuer] >= 2 and not gov['challenge'] and state['round'] >= gov['cooldown_until']:
        offer(100,'challenge')
    if gov['officeholder'] == issuer:
        for promise in state['promises']:
            if promise['issuer'] == issuer and promise['status'] == 'pending':
                if promise['term'] == 'liaison':
                    offer(90,'appoint',target=promise['beneficiary'])
                else:
                    offer(85,'adopt',channel=promise['term'])
        if state['project']['package'] is None:
            offer(55,'adopt',channel='market' if issuer == 'rival' else 'upstream')
    if issuer not in state['organizers']:
        offer(60,'organize',target=issuer,channel=issuer)
    graph = Graph(state)
    for pid in graph.contacts(issuer):
        person = people[pid]
        council = pid in gov['council']
        margin = abs(person['pressure']['player']-person['pressure']['rival'])
        priority = (45 if council else 20) + (1-margin)*20
        if person['allegiance'] == issuer and pid not in state['organizers'] and sum(o['issuer'] == issuer for o in state['organizers'].values()) < 4:
            offer(priority+25,'organize',target=pid,channel=issuer)
        elif person['allegiance'] != issuer:
            offer(priority,'approach',target=pid,channel=issuer)
    return sorted(candidates, key=lambda c:(-c[0], c[1], str(sorted(c[2].items()))))


def act(session, issuer='rival'):
    # Plan from the public start-of-round snapshot; never inspect player declarations.
    view = deepcopy(session.decision_start)
    for _ in range(session.state['ap'][issuer]):
        for _, kind, params in choose(view, issuer):
            try:
                command(session,issuer,kind,**params)
                # Update only this leader's known declarations for its second choice.
                if kind == 'organize':
                    view['organizers'][params['target']] = {'issuer':issuer}
                elif kind == 'adopt':
                    view['project']['package'] = params['channel']
                elif kind == 'challenge':
                    view['government']['challenge'] = {'candidate':issuer}
                elif kind == 'appoint':
                    view['government']['liaisons'][params['target']] = issuer
                break
            except CommandError:
                continue
