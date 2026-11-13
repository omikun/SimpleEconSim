"""Shared machinery target selection for prerequisites, execution and evidence."""


def machinery_target(agent, region, *, broken_only=False, minimum_sponsor_cash=None):
    target = agent if getattr(agent, 'is_corporation', False) else getattr(agent, 'company_owned', None)
    if target is not None:
        return target
    if minimum_sponsor_cash is not None and getattr(agent, 'cash', 0.0) < minimum_sponsor_cash:
        return None
    return next((firm for firm in getattr(region, 'agents', [])
                 if getattr(firm, 'is_corporation', False)
                 and (not broken_only or getattr(firm, 'broken_machinery', 0) > 0)), None)
