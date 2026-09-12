"""
land_rent.py — Cash Rent Collection for Enclosed Plots in REGNUM.

On ENCLOSED (and LEASEHOLD) plots, the feudal in-kind tribute is abolished
and replaced by mandatory cash rent.

Under feudalism, serfs gave a share of what they physically harvested.
Under enclosure, tenants MUST pay fixed cash amounts regardless of harvest,
forcing them into wage labor and market dependency.

Conserved money transfer:
  tenant.cash -= rent_paid
  lord.cash += rent_paid
"""

from goods import Goods
from land_tenure import TenureStatus


def _find_agent(region, agent_id: int):
    for a in region.agents:
        if a.id == agent_id:
            return a
    return None


def collect_rents(region, t: int) -> tuple[float, float, list[dict]]:
    """Lords collect cash rent from tenants residing on ENCLOSED/LEASEHOLD plots.

    Returns:
      (total_collected, total_arrears, events)
    """
    tenure = getattr(region, 'tenure', None)
    if tenure is None or not tenure.plots:
        return 0.0, 0.0, []

    enclosed_plots = [p for p in tenure.plots if p.tenure in (TenureStatus.ENCLOSED, TenureStatus.LEASEHOLD)]
    if not enclosed_plots:
        return 0.0, 0.0, []

    # Non-landlord live agents are candidate tenants
    all_landlords = tenure.lord_ids()
    tenants = [a for a in region.agents
               if a.id not in all_landlords
               and not a.is_trader and not a.is_government
               and a.alive]

    if not tenants:
        return 0.0, 0.0, []

    total_collected = 0.0
    total_arrears = 0.0
    events = []
    tenants_count = len(tenants)
    current_idx = 0

    for plot in enclosed_plots:
        lord = _find_agent(region, plot.lord_id)
        if lord is None or not lord.alive:
            continue

        rent_rate = max(1.0, plot.rent_rate)
        # Proportion of tenants assigned to this plot or bound tenants
        if getattr(plot, 'tenant_ids', None):
            assigned_tenants = [a for a in region.agents if a.id in plot.tenant_ids and a.alive]
        else:
            slice_size = max(1, int(tenants_count * plot.fraction))
            assigned_tenants = tenants[current_idx:current_idx + slice_size]
            current_idx = (current_idx + slice_size) % tenants_count

        # Pastoral conversion ("sheep eat men"): labor drops by 75%
        if getattr(plot, 'production_type', 'arable') == 'pasture' and len(assigned_tenants) > 1:
            keep_count = max(1, int(len(assigned_tenants) * 0.25))
            shepherds = assigned_tenants[:keep_count]
            evicted = assigned_tenants[keep_count:]
            for ex in evicted:
                if hasattr(plot, 'tenant_ids') and ex.id in plot.tenant_ids:
                    plot.tenant_ids.remove(ex.id)
                ex.assigned_plot_id = None
                ex.social_class = 'dispossessed'
                ex.mem_push('mem_eviction', 1.0)
            assigned_tenants = shepherds

        plot_collected = 0.0
        plot_arrears = 0.0

        for tenant in assigned_tenants:
            # Rent payment (conserved cash transfer)
            can_pay = min(tenant.cash, rent_rate)
            if can_pay > 0:
                tenant.cash -= can_pay
                lord.cash += can_pay
                plot_collected += can_pay
            shortfall = rent_rate - can_pay
            if shortfall > 0:
                plot_arrears += shortfall
                # Discontent from debt and rent pressure
                tenant.mem_push('mem_promises', min(1.0, shortfall / rent_rate))

        total_collected += plot_collected
        total_arrears += plot_arrears

        if plot_collected > 0:
            events.append({
                't': t,
                'event': 'RENT_COLLECTED',
                'tile': region.name,
                'plot_id': plot.plot_id,
                'collected': round(plot_collected, 2),
                'arrears': round(plot_arrears, 2),
                'tenants': len(assigned_tenants)
            })

    return round(total_collected, 2), round(total_arrears, 2), events
