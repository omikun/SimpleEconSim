"""Named plot title and seasonal irrigation-right transactions."""
from dataclasses import dataclass


@dataclass
class WaterRight:
    id: int
    plot_id: str
    holder_id: int
    units: float


def transfer_plot_title(region, seller, buyer, plot_id, price, turn=None, lease_turns=0,
                        accepted_proposal_id=None):
    """Voluntary title sale or fixed-term lease; tenants and tenure survive."""
    from supply_proposals import authorized
    kind = 'land_lease' if int(lease_turns) > 0 else 'land_sale'
    if not authorized(region, accepted_proposal_id, buyer.id, seller.id, (kind,)):
        return None
    plot = getattr(region, 'tenure', None)
    plot = plot.find_plot(plot_id) if plot is not None else None
    price = max(0.0, float(price))
    if (plot is None or seller is buyer or plot.lord_id != seller.id or
            not getattr(seller, 'alive', True) or not getattr(buyer, 'alive', True) or
            seller.is_government or buyer.cash < price or
            any(l.get('plot_id') == plot_id and l.get('status') == 'active'
                for l in getattr(region, 'land_leases', []))):
        return None
    seller_id = seller.id
    buyer.cash -= price
    seller.cash += price
    basis = 'lease' if int(lease_turns) > 0 else 'voluntary_sale'
    if basis == 'lease':
        if not hasattr(region, 'land_leases'):
            region.land_leases = []
        lease = {'plot_id': plot_id, 'owner_id': seller_id, 'lessee_id': buyer.id,
                 'start_turn': int(turn or 0), 'end_turn': int(turn or 0) + int(lease_turns),
                 'payment': price, 'status': 'active'}
        region.land_leases.append(lease)
        plot.controlled_by_id = buyer.id
    else:
        plot.lord_id = buyer.id
        if plot_id not in getattr(buyer, 'land_plots', []):
            buyer.land_plots = list(getattr(buyer, 'land_plots', [])) + [plot_id]
        if hasattr(seller, 'land_plots') and plot_id in seller.land_plots:
            seller.land_plots.remove(plot_id)
    event = {'turn': int(turn if turn is not None else getattr(region, '_last_turn', 0)),
             'plot_id': plot_id, 'seller_id': seller_id, 'buyer_id': buyer.id,
             'price': price, 'basis': basis, 'tenants_retained': list(plot.tenant_ids),
             'tenure': getattr(plot.tenure, 'value', str(plot.tenure))}
    region.land_transfer_events = (getattr(region, 'land_transfer_events', []) + [event])[-500:]
    from economy.actor_accounts import record as record_economic_event
    record_economic_event(region, 'land_lease' if basis == 'lease' else 'land_sale',
                          turn=event['turn'], payer_id=buyer.id,
                          recipient_id=seller.id, amount=price, asset_id=plot_id,
                          detail={'basis': basis, 'lease_turns': int(lease_turns),
                                  'tenant_ids': list(plot.tenant_ids)})
    from run_trace import emit
    emit(region, kind='land_title_transfer', record_class='outcome',
         subject={'type': 'plot', 'id': plot_id}, metric_id='land.owner', unit='agent_id',
         before=seller_id, after=buyer.id, formula_id='land.voluntary_transfer.v1', inputs=event)
    return event


def _seed_water_rights(region):
    if getattr(region, 'water_rights_initialized', False):
        return
    plots = list(getattr(getattr(region, 'tenure', None), 'plots', []))
    region.water_rights = [WaterRight(i + 1, p.plot_id, p.lord_id, 1.0)
                           for i, p in enumerate(plots)]
    region._next_water_right_id = len(plots) + 1
    region.water_source_capacity = max(1.0, float(len(plots)))
    region.water_rights_initialized = True


def expire_land_leases(region, turn):
    events = []
    for lease in getattr(region, 'land_leases', []):
        if lease.get('status') != 'active' or int(lease.get('end_turn', 0)) > turn:
            continue
        plot = region.tenure.find_plot(lease['plot_id']) if hasattr(region, 'tenure') else None
        if plot is not None and getattr(plot, 'controlled_by_id', None) == lease['lessee_id']:
            delattr(plot, 'controlled_by_id')
        lease['status'] = 'expired'
        event = {'turn': int(turn), 'plot_id': lease['plot_id'],
                 'owner_id': lease['owner_id'], 'lessee_id': lease['lessee_id'],
                 'status': 'expired'}
        events.append(event)
    region.land_transfer_events = (getattr(region, 'land_transfer_events', []) + events)[-500:]
    from run_trace import emit
    for event in events:
        emit(region, kind='land_lease_expiry', record_class='outcome',
             subject={'type': 'plot', 'id': event['plot_id']},
             metric_id='land.control', unit='status', after='owner_restored',
             formula_id='land.lease_expiry.v1', inputs=event)
    return events


def acquire_water_right(region, seller, buyer, from_plot_id, to_plot_id,
                        units=0.25, price=0.0, turn=None, accepted_proposal_id=None):
    """Buy a quantified seasonal allocation and redirect it between named plots."""
    from supply_proposals import authorized
    if not authorized(region, accepted_proposal_id, buyer.id, seller.id, ('water_right',)):
        return None
    _seed_water_rights(region)
    units, price = max(0.0, float(units)), max(0.0, float(price))
    source = next((r for r in region.water_rights if r.plot_id == from_plot_id
                   and r.holder_id == seller.id and r.units >= units), None)
    target = region.tenure.find_plot(to_plot_id) if hasattr(region, 'tenure') else None
    if (source is None or target is None or units <= 0 or seller is buyer or
            not getattr(seller, 'alive', True) or not getattr(buyer, 'alive', True) or
            buyer.cash < price):
        return None
    buyer.cash -= price
    seller.cash += price
    source.units -= units
    target_right = next((r for r in region.water_rights
                         if r.plot_id == to_plot_id and r.holder_id == buyer.id), None)
    if target_right is None:
        target_right = WaterRight(region._next_water_right_id, to_plot_id, buyer.id, 0.0)
        region._next_water_right_id += 1
        region.water_rights.append(target_right)
    target_right.units += units
    event = {'turn': int(turn if turn is not None else getattr(region, '_last_turn', 0)),
             'right_id': target_right.id, 'from_plot_id': from_plot_id,
             'to_plot_id': to_plot_id, 'seller_id': seller.id, 'buyer_id': buyer.id,
             'units': units, 'price': price}
    region.water_right_events = (getattr(region, 'water_right_events', []) + [event])[-500:]
    from economy.actor_accounts import record as record_economic_event
    record_economic_event(region, 'water_sale', turn=event['turn'], payer_id=buyer.id,
                          recipient_id=seller.id, quantity=units, amount=price,
                          asset_id=target_right.id,
                          detail={'from_plot_id': from_plot_id, 'to_plot_id': to_plot_id})
    from run_trace import emit
    emit(region, kind='water_right_transfer', record_class='outcome',
         subject={'type': 'water_right', 'id': target_right.id},
         metric_id='water.allocation_right', unit='seasonal_units', after=units,
         formula_id='water.right_transfer.v1', inputs=event)
    return event


def allocate_seasonal_water(region, turn):
    """Allocate this season's finite source across plot-specific entitlements."""
    _seed_water_rights(region)
    rights = getattr(region, 'water_rights', [])
    capacity = max(0.0, float(getattr(region, 'water_source_capacity', 0.0)))
    # Low rainfall and damaged channels reduce physical supply, never create it.
    rainfall_source = getattr(region, 'seasonal_rainfall',
                              getattr(region, 'scenario_food_yield_modifier', 1.0))
    rainfall = max(0.0, min(1.5, float(rainfall_source)))
    maintenance = max(0.0, min(1.0, float(getattr(region, 'canal_condition', 1.0))))
    available = capacity * rainfall * maintenance
    total_rights = sum(max(0.0, r.units) for r in rights)
    scale = min(1.0, available / total_rights) if total_rights else 0.0
    region.water_allocations = {}
    for right in sorted(rights, key=lambda r: (r.id, r.plot_id)):
        region.water_allocations[right.plot_id] = region.water_allocations.get(right.plot_id, 0.0) + right.units * scale
    region.water_allocation_turn = int(turn)
    event = {'turn': int(turn), 'capacity': capacity, 'rainfall': rainfall,
             'canal_condition': maintenance, 'available': available,
             'allocated': sum(region.water_allocations.values()), 'rights_total': total_rights,
             'plot_allocations': dict(region.water_allocations)}
    region.water_allocation_events = (getattr(region, 'water_allocation_events', []) + [event])[-500:]
    from run_trace import emit
    emit(region, kind='seasonal_water_allocation', record_class='calculation',
         subject={'type': 'tile', 'id': region.name}, metric_id='water.seasonal_supply',
         unit='water_units', before=capacity, after=available,
         formula_id='water.capacity_rainfall_maintenance.v1', inputs=event)
    return region.water_allocations


def water_yield_factor(region, producer=None):
    plot_id = getattr(producer, 'assigned_plot_id', None)
    if plot_id is None and getattr(producer, 'is_corporation', False):
        plot_id = next((p.plot_id for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                        if getattr(p, 'controlled_by_id', p.lord_id) == producer.id), None)
    if plot_id is None:
        return 1.0
    plots = getattr(getattr(region, 'tenure', None), 'plots', [])
    if not any(p.plot_id == plot_id for p in plots):
        return 1.0
    allocation = getattr(region, 'water_allocations', {}).get(plot_id, 0.0)
    return max(0.25, min(1.25, float(allocation)))
