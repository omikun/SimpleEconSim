"""A shared monotonic clock for observed economic and collective events."""


def attach_clock(regions):
    """Reuse a saved clock, then attach it to every region in this world."""
    regions = list(regions)
    if not regions:
        return None
    clock = next((getattr(region, '_collective_trace_clock', None)
                  for region in regions
                  if getattr(region, '_collective_trace_clock', None)), None)
    if clock is None:
        clock = {'next': 1}
    for region in regions:
        region._collective_trace_clock = clock
    return clock


def stamp(region, row):
    """Mark a ledger row at its append point, including after an engine tick."""
    clock = getattr(region, '_collective_trace_clock', None)
    if clock is None:
        clock = attach_clock([region])
    if 'sequence' not in row:
        row['sequence'] = clock['next']
        clock['next'] += 1
    return row
