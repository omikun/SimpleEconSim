"""
Structural inter-region transport routes.

A Route is a FIFO cargo queue owned by a source region.  Traders post
export goods to it; the route advances them turn by turn and delivers
them to the trader's foreign inventory (destination import pool) when
they mature.

Conservation invariant: goods strictly move
    trader.inventory_export -> route (pending -> in_transit) -> trader.inventory_foreign
at every step.  The route never creates or destroys goods.
"""

from collections import defaultdict


class Route:
    """A directional cargo route from *src* region to *dst* region.

    ``base_delay`` is the number of turns a shipment takes in transit with
    an empty queue.  Congestion scales the delay: each ``capacity_per_unit``
    shipments queued behind adds one extra turn, so the route — not the
    individual trader — governs delivery time.
    """

    def __init__(self, name, src, dst, base_delay=1, capacity_per_unit=10):
        self.name = name
        self.src = src          # source Region
        self.dst = dst          # destination Region
        self.base_delay = base_delay
        self.capacity_per_unit = capacity_per_unit
        self.pending = []       # posted this turn, followed by optional cost/provenance
        self.in_transit = []    # en route:        [trader, good, qty, turns_left, location]
        self.delivered_this_turn = []   # (trader, good, qty) matured this turn
        self.parked_this_turn = []      # (trader, good, qty) matured into parked_foreign
        self._next_shipment_id = 1

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------

    @property
    def is_frozen(self) -> bool:
        """True if route is paralyzed by a General Strike, Naval Blockade, or Quarantine."""
        return bool(getattr(self, 'is_blocked_by_strike', False)
                    or getattr(self, 'is_blockaded', False)
                    or getattr(self, 'is_quarantined', False))

    def post(self, trader, good, qty, *, unit_cost=None, freight_per_unit=0.0,
             source_currency=None):
        """Move ``qty`` from ``trader.inventory_export`` into this route.

        Returns the quantity actually moved (never more than available).
        """
        if self.is_frozen:
            return 0
        qty = int(min(qty, trader.inventory_export[good.value]))
        if qty <= 0:
            return 0
        trader.inventory_export[good.value] -= qty
        # M0.3: every shipment carries its current tile location; starts at
        # the source tile, ready for multi-hop paths on a future map.
        shipment_id = f'{self.name}:{self._next_shipment_id}'
        self._next_shipment_id += 1
        if unit_cost is None:
            unit_cost = float(trader.cost_get(good, 0.0))
        unit_cost = float(unit_cost)
        source_currency = source_currency or getattr(self.src, 'home_currency', None)
        cost_status = 'trader_cost_basis' if unit_cost > 0 else 'unknown_cost_basis'
        self.pending.append([trader, good, qty, self.src.name, shipment_id,
                             unit_cost, float(freight_per_unit), source_currency,
                             shipment_id, self.src.name, cost_status, [self.name]])
        return qty

    def post_parked(self, trader, good, qty):
        """T1: post cargo from a trader's PARKED pool at this route's source.

        Used when goods matured at an old destination the trader left, and it
        is now worth re-shipping them toward this route's dst.  Goods move:
        trader.parked_foreign[src.name] -> this route's pending queue.
        """
        if self.is_frozen:
            return 0
        src_name = self.src.name
        qty = int(min(qty, trader.parked_get(src_name, good, 0)))
        if qty <= 0:
            return 0
        trader.parked_sub(src_name, good, qty)
        remaining = qty
        lots = getattr(trader, 'import_lots', [])
        for lot in lots:
            if (remaining <= 0 or lot.get('destination') != src_name
                    or lot.get('good') != good.name or not lot.get('parked', False)):
                continue
            available = max(0, int(lot.get('quantity', 0)))
            moved = min(available, remaining)
            if moved <= 0:
                continue
            lot['quantity'] = available - moved
            shipment_id = f'{self.name}:{self._next_shipment_id}'
            self._next_shipment_id += 1
            history = list(lot.get('route_history') or [])
            history.append(self.name)
            self.pending.append([
                trader, good, moved, src_name, shipment_id,
                lot.get('unit_cost'), float(lot.get('freight_per_unit') or 0.0),
                lot.get('source_currency'),
                lot.get('source_shipment_id') or lot.get('shipment_id'),
                lot.get('source_region') or src_name,
                lot.get('source_cost_status') or 'unlinked_legacy_cargo', history])
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(self.src, 'shipment_departure', payer_id=trader.id,
                                  good=good, quantity=moved, asset_id=shipment_id,
                                  currency=lot.get('source_currency'),
                                  detail={'destination': self.dst.name,
                                          'shipment_id': shipment_id,
                                          'source_shipment_id':
                                              lot.get('source_shipment_id') or lot.get('shipment_id'),
                                          'source_region': lot.get('source_region') or src_name,
                                          'source_unit_cost': lot.get('unit_cost'),
                                          'freight_per_unit': lot.get('freight_per_unit'),
                                          'source_cost_status': lot.get('source_cost_status') or
                                              'unlinked_legacy_cargo',
                                          'route_history': history})
            from run_trace import emit
            emit(self.src, kind='route_shipment_departure', record_class='observation',
                 subject={'type': 'shipment', 'id': shipment_id},
                 inputs={'trader_id': trader.id, 'good': good.name,
                         'quantity': moved, 'source_shipment_id':
                             lot.get('source_shipment_id') or lot.get('shipment_id'),
                         'source_region': lot.get('source_region') or src_name,
                         'source_unit_cost': lot.get('unit_cost'),
                         'freight_per_unit': lot.get('freight_per_unit'),
                         'source_currency': lot.get('source_currency'),
                         'source_cost_status': lot.get('source_cost_status') or
                             'unlinked_legacy_cargo',
                         'route_history': history})
            remaining -= moved
        if remaining > 0:
            shipment_id = f'{self.name}:{self._next_shipment_id}'
            self._next_shipment_id += 1
            self.pending.append([trader, good, remaining, src_name, shipment_id,
                                 None, 0.0, getattr(self.src, 'home_currency', None),
                                 None, src_name, 'unlinked_legacy_cargo', [self.name]])
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(self.src, 'shipment_departure', payer_id=trader.id,
                                  good=good, quantity=remaining, asset_id=shipment_id,
                                  detail={'destination': self.dst.name,
                                          'shipment_id': shipment_id,
                                          'source_shipment_id': None,
                                          'source_region': src_name,
                                          'source_unit_cost': None,
                                          'freight_per_unit': 0.0,
                                          'source_cost_status': 'unlinked_legacy_cargo',
                                          'route_history': [self.name]})
            from run_trace import emit
            emit(self.src, kind='route_shipment_departure', record_class='observation',
                 subject={'type': 'shipment', 'id': shipment_id},
                 inputs={'trader_id': trader.id, 'good': good.name,
                         'quantity': remaining, 'source_shipment_id': None,
                         'source_region': src_name, 'source_unit_cost': None,
                         'freight_per_unit': 0.0,
                         'source_currency': getattr(self.src, 'home_currency', None),
                         'source_cost_status': 'unlinked_legacy_cargo',
                         'route_history': [self.name]})
        return qty

    # ------------------------------------------------------------------
    # Advance / delivery
    # ------------------------------------------------------------------

    def advance(self):
        """Advance all in-transit cargo one turn.

        Shipments whose ``turns_left`` reaches 0 land in the owning
        trader's ``inventory_foreign`` (the destination import pool).
        """
        self.delivered_this_turn = []
        self.parked_this_turn = []
        if self.is_frozen:
            return
        remaining = []
        for entry in self.in_transit:
            entry[3] -= 1
            if entry[3] <= 0:
                trader, good, qty = entry[0], entry[1], entry[2]
                shipment_id = entry[5] if len(entry) > 5 else None
                unit_cost = entry[6] if len(entry) > 6 else None
                freight_per_unit = entry[7] if len(entry) > 7 else 0.0
                source_currency = entry[8] if len(entry) > 8 else None
                source_shipment_id = entry[9] if len(entry) > 9 else shipment_id
                source_region = entry[10] if len(entry) > 10 else self.src.name
                source_cost_status = (entry[11] if len(entry) > 11 else
                                      ('trader_cost_basis' if unit_cost else 'unknown_cost_basis'))
                route_history = list(entry[12] if len(entry) > 12 and entry[12] else [self.name])
                # T1: the cargo matures HERE (this route's dst) no matter what.
                # If the trader re-pointed away, park it instead of letting it
                # ride the trader's new destination.
                if getattr(trader, 'destination_region', None) is not self.dst:
                    trader.parked_add(self.dst.name, good, qty)
                    self.parked_this_turn.append((trader, good, qty))
                    parked = True
                else:
                    trader.inventory_foreign[good.value] += qty
                    self.delivered_this_turn.append((trader, good, qty))
                    parked = False
                if shipment_id is not None:
                    lots = getattr(trader, 'import_lots', [])
                    lots.append({'shipment_id': shipment_id,
                                 'source_shipment_id': source_shipment_id,
                                 'good': good.name, 'destination': self.dst.name,
                                 'quantity': qty, 'unit_cost': unit_cost,
                                 'freight_per_unit': freight_per_unit,
                                 'source_currency': source_currency,
                                 'source_region': source_region,
                                 'source_cost_status': source_cost_status,
                                 'route_history': route_history, 'parked': parked})
                    trader.import_lots = lots[-500:]
                    from economy.actor_accounts import record as record_economic_event
                    record_economic_event(self.src, 'shipment_arrival',
                                          payer_id=trader.id, good=good,
                                          quantity=qty, asset_id=shipment_id,
                                          currency=source_currency,
                                          detail={'destination': self.dst.name,
                                                  'source_unit_cost': unit_cost,
                                                  'freight_per_unit': freight_per_unit,
                                                  'shipment_id': shipment_id,
                                                  'source_shipment_id': source_shipment_id,
                                                  'source_region': source_region,
                                                  'source_cost_status': source_cost_status,
                                                  'route_history': route_history,
                                                  'parked': parked})
                    from run_trace import emit
                    emit(self.src, kind='route_shipment_arrival',
                         record_class='observation',
                         subject={'type': 'shipment', 'id': shipment_id},
                         inputs={'trader_id': trader.id, 'good': good.name,
                                 'quantity': qty, 'destination': self.dst.name,
                                 'source_shipment_id': source_shipment_id,
                                 'source_region': source_region,
                                 'source_unit_cost': unit_cost,
                                 'freight_per_unit': freight_per_unit,
                                 'source_currency': source_currency,
                                 'source_cost_status': source_cost_status,
                                 'route_history': route_history,
                                 'parked': parked})
            else:
                remaining.append(entry)
        self.in_transit = remaining

    def deliver_pending(self):
        """Loaded posted cargo into the queue with congestion-scaled delay."""
        depth = len(self.in_transit)
        for entry in self.pending:
            trader, good, qty = entry[0], entry[1], entry[2]
            location = entry[3] if len(entry) > 3 else self.src.name
            delay = self.base_delay + depth // max(1, self.capacity_per_unit)
            self.in_transit.append([trader, good, qty, delay, location, *entry[4:]])
            depth += 1
        self.pending = []

    # ------------------------------------------------------------------
    # Queries / liquidation
    # ------------------------------------------------------------------

    def holdings_of(self, trader):
        """In-transit quantity per good for *trader* (as a dict good->qty)."""
        result = defaultdict(int)
        for entry in self.in_transit:
            if entry[0] is trader:
                result[entry[1]] += entry[2]
        return result

    def in_transit_depth(self):
        """Total number of queued shipments (for congestion)."""
        return len(self.in_transit)

    def in_transit_total(self, good):
        """Total in-transit units of *good* across all traders."""
        return sum(e[2] for e in self.in_transit if e[1] == good)

    def reclaim(self, trader):
        """Return all of *trader*'s in-transit cargo to its export inventory.

        Used when a trader exits the profession so no goods are stranded
        or destroyed on the route.
        """
        kept = []
        for entry in self.in_transit:
            if entry[0] is trader:
                trader.inventory_export[entry[1].value] += entry[2]
            else:
                kept.append(entry)
        self.in_transit = kept
        # Return anything posted but not yet loaded, too.
        pending = []
        for entry in self.pending:
            if entry[0] is trader:
                trader.inventory_export[entry[1].value] += entry[2]
            else:
                pending.append(entry)
        self.pending = pending
