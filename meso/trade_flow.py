"""Bilateral settlement and source-valued export rows for one world turn."""

from goods import Goods
from world_trade import desk_for, settle_trade


def settle_pairs(turn, tiles, pair_orders, *, enabled=True):
    """Settle active pairs and return export evidence by source tile.

    Disabled trade leaves every tile with an empty row set. Callers can still
    append a zero-valued turn sample without inventing partner transactions.
    """
    exports = {region.name: [] for region in tiles}
    for source, destination in (pair_orders if enabled else ()):
        settle_trade(turn, destination, source)
        if source.name not in exports:
            continue
        partner_currency = getattr(destination, 'home_currency', None)
        home_currency = getattr(source, 'home_currency', None)
        source_sales = getattr(destination, '_auction_import_sales_by_source', {})
        quantity_total = 0
        partner_value = 0.0
        sale_event_ids = []
        good_rows = []
        for good in (Goods.food, Goods.wood, Goods.furniture):
            rows = source_sales.get(good)
            if rows is None:
                quantity, value = getattr(destination, '_auction_import_sales', {}).get(
                    good, (0, 0.0))
                event_ids = []
            else:
                row = rows.get(source.name, {})
                quantity = int(row.get('quantity', 0))
                value = float(row.get('value', 0.0))
                event_ids = list(row.get('event_ids', ()))
            quantity_total += int(quantity)
            partner_value += float(value)
            sale_event_ids.extend(event_ids)
            good_rows.append({'good': good.name, 'quantity': int(quantity),
                              'value': float(value), 'sale_event_ids': event_ids})
        if home_currency == partner_currency:
            rate, basis = 1.0, 'same_currency'
        elif home_currency is None or partner_currency is None:
            rate, basis = 1.0, 'parity_assumed_missing_currency'
        else:
            desk = desk_for(source, destination)
            if desk is None:
                rate, basis = 1.0, 'parity_assumed_no_source_desk'
            else:
                rate, basis = float(desk.buy_rate()), 'source_desk_current_buy_rate'
        exports[source.name].append({
            'partner_tile': destination.name,
            'partner_currency': partner_currency,
            'home_currency': home_currency,
            'quantity': quantity_total,
            'value_in_partner_currency': partner_value,
            'conversion_rate_to_home': rate,
            'conversion_basis': basis,
            'value_in_home_currency': partner_value * rate,
            'goods': good_rows,
            'source_sale_event_ids': sale_event_ids,
        })
    return exports
