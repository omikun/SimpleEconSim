"""Quantity-linked acquisition records for trader export inventory."""

from __future__ import annotations


def record_trader_acquisition(trader, good, quantity, unit_cost, event, *,
                              source_region, source_seller_id,
                              source_currency, purchase_trace_event_id=None,
                              parent_shipment_id=None,
                              parent_source_shipment_id=None):
    """Link newly purchased export stock to the actual settled purchase event."""
    quantity = int(quantity)
    if quantity <= 0 or event is None:
        return
    lots = getattr(trader, 'trade_acquisition_lots', [])
    lots.append({
        'good': good.name,
        'quantity': quantity,
        'unit_cost': float(unit_cost),
        'acquisition_event': {'tile': event['tile'], 'id': event['id']},
        'purchase_trace_event_id': purchase_trace_event_id,
        'source_region': source_region,
        'source_seller_id': source_seller_id,
        'source_currency': source_currency,
        'parent_shipment_id': parent_shipment_id,
        'parent_source_shipment_id': parent_source_shipment_id,
        'status': 'market_purchase_recorded',
    })
    trader.trade_acquisition_lots = lots


def consume_acquisition_links(lots, quantity):
    """Remove *quantity* from ``lots`` and return matching copied link rows.

    Any amount without a recorded acquisition is explicitly represented as
    unlinked legacy cargo. ``lots`` is modified in place, so callers can use
    the same helper for export inventory, parked imports, and auction fills.
    """
    remaining = max(0, int(quantity))
    consumed = []
    if remaining <= 0:
        return consumed
    for lot in list(lots or []):
        if remaining <= 0:
            break
        available = max(0, int(lot.get('quantity', 0)))
        take = min(available, remaining)
        if take <= 0:
            continue
        row = dict(lot)
        row['quantity'] = take
        consumed.append(row)
        lot['quantity'] = available - take
        remaining -= take
    if remaining > 0:
        consumed.append({'quantity': remaining, 'status': 'unlinked_legacy_cargo'})
    return consumed


def take_trader_acquisition_links(trader, good, quantity):
    """Consume acquisition rows that back a trader's exported stock."""
    rows = getattr(trader, 'trade_acquisition_lots', [])
    matching = [row for row in rows if row.get('good') == good.name]
    consumed = consume_acquisition_links(matching, quantity)
    trader.trade_acquisition_lots = [row for row in rows
                                     if int(row.get('quantity', 0)) > 0]
    return consumed


def restore_trader_acquisition_links(trader, good, links):
    """Restore shipment provenance when queued cargo returns to export stock."""
    rows = getattr(trader, 'trade_acquisition_lots', [])
    for link in links or []:
        quantity = max(0, int(link.get('quantity', 0)))
        if quantity <= 0:
            continue
        restored = dict(link)
        restored['good'] = good.name
        restored['quantity'] = quantity
        rows.append(restored)
    trader.trade_acquisition_lots = rows


def acquisition_cost_summary(links, quantity):
    """Return (known quantity, weighted known cost) for shipment links."""
    known_quantity = 0
    known_value = 0.0
    for link in links or []:
        unit_cost = link.get('unit_cost')
        if unit_cost is None or not link.get('acquisition_event'):
            continue
        linked_quantity = max(0, int(link.get('quantity', 0)))
        known_quantity += linked_quantity
        known_value += linked_quantity * float(unit_cost)
    weighted = known_value / known_quantity if known_quantity else None
    return min(int(quantity), known_quantity), weighted


def source_to_destination_rate(destination, source_region_name, source_currency):
    """Return destination-currency units per source-currency unit.

    Pricing uses the source desk's current buy quote for destination-currency
    proceeds, then inverts it to value source-currency acquisition costs. The
    desk identity and method are returned so downstream records can explain
    this valuation. ``None`` means the currencies cannot be normalized from
    the available bilateral quotes.
    """
    destination_currency = getattr(destination, 'home_currency', None)
    if not source_currency or not destination_currency:
        return None, 'currency_unavailable'
    if source_currency == destination_currency:
        return 1.0, 'same_currency'

    source_region = (getattr(destination, 'neighbors', {}) or {}).get(source_region_name)
    source_desks = getattr(source_region, 'forex_desks', {}) or {}
    source_desk = source_desks.get(getattr(destination, 'name', None))
    if (source_desk is None and source_region is not None
            and getattr(source_region, 'forex', None) is not None
            and getattr(source_region.forex, 'other', None) == destination_currency):
        source_desk = source_region.forex
    if (source_desk is not None
            and getattr(source_desk, 'home', source_currency) == source_currency
            and getattr(source_desk, 'other', destination_currency) == destination_currency):
        source_buy_rate = float(source_desk.buy_rate())
        if source_buy_rate > 0:
            return 1.0 / source_buy_rate, 'source_home_buy_rate_inverse'

    destination_desks = getattr(destination, 'forex_desks', {}) or {}
    destination_desk = destination_desks.get(source_region_name)
    if destination_desk is None:
        destination_desk = next((desk for desk in destination_desks.values()
                                 if getattr(desk, 'other', None) == source_currency), None)
    if (destination_desk is not None
            and getattr(destination_desk, 'home', destination_currency) == destination_currency
            and getattr(destination_desk, 'other', source_currency) == source_currency):
        rate = float(destination_desk.buy_rate())
        if rate > 0:
            return rate, 'destination_home_buy_rate'
    return None, 'bilateral_rate_unavailable'
