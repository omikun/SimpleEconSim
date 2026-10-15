"""Locate treasury movement by turn phase without assigning an invented cause."""

from run_trace import emit


def treasury_boundary(tiles, nations, phase):
    if not tiles or getattr(tiles[0], '_run_trace', None) is None:
        return
    clock = getattr(tiles[0], '_collective_trace_clock', None)
    if clock is None:
        return
    previous = clock.setdefault('treasury_phase_values', {})
    for nation in nations:
        current = nation.treasury()['total']
        old = previous.get(nation.name)
        if old is not None and old != current and nation.tiles:
            emit(nation.tiles[0], kind='treasury_phase_delta',
                 record_class='observation', phase=phase,
                 subject={'type': 'nation', 'id': nation.name},
                 metric_id='finance.treasury', unit=nation.currency,
                 before=old, after=current,
                 inputs={'boundary': phase,
                         'interpretation': 'movement occurred since prior boundary; specific transfer may be unrecorded'})
        previous[nation.name] = current
