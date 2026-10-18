"""Shared currency and trade-cost conventions for imported goods."""


def import_tariff_terms(destination, seller_currency):
    """Return (statutory, drawback, effective) import tariff rates.

    Settlement applies import tariffs to foreign-currency seller proceeds.
    Domestic-currency sales therefore carry no import tariff under the current
    rules, even when the goods arrived on an inter-region route.
    """
    destination_currency = getattr(destination, 'home_currency', None)
    if (not seller_currency or not destination_currency
            or seller_currency == destination_currency):
        return 0.0, 0.0, 0.0
    government = getattr(destination, 'gov', None)
    tariff = (max(0.0, float(getattr(government, 'import_tariff_rate', 0.0)))
              if getattr(government, 'import_tariff_enabled', False) else 0.0)
    drawback = (max(0.0, min(1.0, float(getattr(government, 'import_drawback_rate', 0.0))))
                if getattr(government, 'import_drawback_enabled', False) else 0.0)
    return tariff, drawback, tariff * (1.0 - drawback)
