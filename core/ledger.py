"""ledger.py — explicit destruction ledger (v3_wilderness).

Money/goods may legitimately be DESTROYED: an heirless homesteader dying on a
state-less wilderness tile leaves cash that no government/charity can receive;
a future "cargo lost at sea" milestone will destroy goods in transit.

Transfers must ALWAYS conserve (a transfer is a move between countable
holders).  Destruction must be RECORDED so the per-currency audit in
sim_world can EXEMPT it from the "SUPPLY SHIFT" alarm — an alarm that should
only fire on an UNEXPLAINED transfer loss, not on sanctioned destruction.
"""
# Entries: {'t': turn, 'currency': str|None, 'amount': float, 'reason': str}
_destruction = []


def record(t, currency, amount, reason):
    """Record *amount* (>0) of *currency* destroyed at turn *t*."""
    if amount and amount > 0:
        _destruction.append({
            't': t, 'currency': currency, 'amount': float(amount),
            'reason': reason,
        })


def cleared(t, currency):
    """Total recorded destruction of *currency* at turn *t* (>=0)."""
    return sum(e['amount'] for e in _destruction
               if e['t'] == t and e['currency'] == currency)


def all_events():
    """All destruction events in chronological order."""
    return list(_destruction)


def reset():
    """Clear the ledger (fresh run)."""
    _destruction.clear()