"""Named tenancy access agreements and current-harvest crop-share rent."""

from labor_institutions import TenancyAgreement


def create_tenancy_agreement(region, tenant, landlord, plot_id, kind='cash_rent',
                             cash_rent=0.0, crop_share=0.0):
    from world_config import gameplay_flags_for
    if kind == 'crop_share' and not gameplay_flags_for(region).crop_share_tenancy:
        return None
    plot = getattr(region, 'tenure', None)
    plot = plot.find_plot(plot_id) if plot is not None else None
    if plot is None or tenant.id == landlord.id or plot.lord_id != landlord.id:
        return None
    if kind not in ('cash_rent', 'crop_share'):
        return None
    for agreement in getattr(region, 'tenancy_agreements', []):
        if agreement.active and agreement.tenant_id == tenant.id and agreement.plot_id == plot_id:
            return None
    agreement = TenancyAgreement(tenant.id, landlord.id, plot_id, kind,
                                 max(0.0, float(cash_rent)),
                                 max(0.0, min(1.0, float(crop_share))))
    if not hasattr(region, 'tenancy_agreements'):
        region.tenancy_agreements = []
    region.tenancy_agreements.append(agreement)
    if tenant.id not in plot.tenant_ids:
        plot.tenant_ids.append(tenant.id)
    tenant.assigned_plot_id = plot_id
    from livelihood_access import grant_access
    grant_access(region, tenant.id, plot_id, 'field', source='tenancy')
    grant_access(region, tenant.id, plot_id, 'commons_food', source='tenancy')
    return agreement


def settle_crop_shares(region, turn):
    from world_config import gameplay_flags_for
    if not gameplay_flags_for(region).crop_share_tenancy:
        return []
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    events = []
    for agreement in sorted(getattr(region, 'tenancy_agreements', []),
                            key=lambda a: (a.plot_id, a.tenant_id)):
        if not agreement.active or agreement.type != 'crop_share' or agreement.crop_share <= 0:
            continue
        tenant, landlord = agents.get(agreement.tenant_id), agents.get(agreement.landlord_id)
        if tenant is None or landlord is None or not tenant.alive or not landlord.alive:
            continue
        good = getattr(tenant, 'output', None)
        from harvest_claims import available as claimable_harvest
        quantity = claimable_harvest(region, tenant, good, turn)
        take = min(quantity, int(quantity * agreement.crop_share))
        if take <= 0 or good is None:
            continue
        tenant.inv_add(good, -take)
        landlord.inv_add(good, take)
        unit_price = float(region.recipes.get(good, {}).get('price', 1.0))
        reference_value = take * unit_price
        events.append({'turn': turn, 'tenant_id': tenant.id, 'landlord_id': landlord.id,
                       'plot_id': agreement.plot_id, 'good': getattr(good, 'value', str(good)),
                       'quantity': take, 'unit_price': unit_price,
                       'reference_value': reference_value})
        transfer_id = f'crop-share:{turn}:{agreement.plot_id}:{tenant.id}:{landlord.id}'
        from economy.actor_accounts import record as record_economic_event
        event = record_economic_event(
            region, 'crop_share_rent', turn=turn, payer_id=tenant.id,
            recipient_id=landlord.id, good=good, quantity=take,
            amount=reference_value, asset_id=agreement.plot_id,
            source_id=transfer_id,
            currency=getattr(region, 'home_currency', None),
            detail={'transfer_id': transfer_id, 'plot_id': agreement.plot_id,
                    'crop_share': float(agreement.crop_share),
                    'unit_price': unit_price,
                    'reference_value': reference_value,
                    'valuation_basis': 'displayed_recipe_reference_price'})
        from run_trace import emit
        emit(region, kind='crop_share_rent_settlement', record_class='transfer',
             phase='settlement',
             subject={'type': 'tenancy', 'id': transfer_id,
                      'tile': region.name},
             metric_id='land.crop_share', unit=getattr(good, 'name', str(good)),
             after=take, formula_id='tenancy.crop_share.harvest.v1',
             inputs={'tenant_id': tenant.id, 'landlord_id': landlord.id,
                     'plot_id': agreement.plot_id, 'crop': getattr(good, 'name', str(good)),
                     'available_harvest': int(quantity), 'quantity_transferred': take,
                     'crop_share': float(agreement.crop_share),
                     'reference_price': unit_price,
                     'reference_value': reference_value,
                     'valuation_basis': 'displayed_recipe_reference_price',
                     'economic_event_id': event['id']})
    region.crop_share_events = (getattr(region, 'crop_share_events', []) + events)[-500:]
    return events
