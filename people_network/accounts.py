"""Conserved integer credits for the isolated Patronage fixture only."""


def account(person):
    return 'person:' + person


def balance(state, owner):
    return state['patronage']['accounts'][owner]


def transfer(session, source, target, amount, reason, parents=(), audience=None):
    accounts = session.state['patronage']['accounts']
    if type(amount) is not int or amount < 0 or source == target:
        raise ValueError('Transfers need distinct accounts and nonnegative integer credits')
    if source not in accounts or target not in accounts or accounts[source] < amount:
        raise ValueError('An actual funded account is required')
    accounts[source] -= amount
    accounts[target] += amount
    eid = session.emit('payment', target, None, amount, parents,
                       source=source, destination=target, reason=reason,
                       audience=sorted(audience if audience is not None else session.state['people']))
    session.state['last_change']['account:' + target] = eid
    return eid


def validate(state):
    p = state['patronage']
    expected = {'bridge_fund', 'escrow:bridge'} | {account(pid) for pid in state['people']}
    accounts = p['accounts']
    if set(accounts) != expected or any(type(v) is not int or v < 0 for v in accounts.values()):
        raise ValueError('Invalid laboratory credit accounts')
    if sum(accounts.values()) != p['initial_total'] or p['initial_total'] != 164:
        raise ValueError('Laboratory credits must conserve the initial 164 credits')
