"""Source-owned withholding behind the existing is_striking production flag.

Tracking is explicitly enrolled by the governing experiment. Other worlds keep
the exact legacy Boolean behavior, including absence of any new actor state.
"""


def tracked(person):
    return isinstance(getattr(person, '_strike_sources', None), dict)


def enable(person):
    if not tracked(person):
        person._strike_sources = ({'legacy': True} if getattr(person, 'is_striking', False) else {})


def source(kind, region, owner=None):
    return f'{kind}:{region.name}' + (f':{getattr(owner, "id", owner)}' if owner is not None else '')


def set_striking(person, origin, active, *, region=None):
    if region is not None and getattr(region, '_governing_strike_sources', False) is True:
        enable(person)
    if not tracked(person):
        person.is_striking = bool(active)
        return
    if active:
        person._strike_sources[origin] = True
    else:
        person._strike_sources.pop(origin, None)
    person.is_striking = bool(person._strike_sources)


def has_source(person, origin):
    if not tracked(person):
        return bool(getattr(person, 'is_striking', False))
    return origin in person._strike_sources


def clear_all(person, *, region=None):
    """Explicit whole-person repression/death, rather than a local settlement."""
    if region is not None and getattr(region, '_governing_strike_sources', False) is True:
        enable(person)
    ended = sorted(person._strike_sources) if tracked(person) else []
    if tracked(person):
        person._strike_sources.clear()
    person.is_striking = False
    return ended


def has_non_network_source(person):
    """Generic route-freeze escalation must not duplicate a network walkout."""
    if not tracked(person):
        return bool(getattr(person, 'is_striking', False))
    return any(not key.startswith('network:') for key in person._strike_sources)
