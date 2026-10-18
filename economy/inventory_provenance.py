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
