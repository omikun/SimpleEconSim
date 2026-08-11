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
        self.pending = []       # posted this turn: [trader, good, qty, location]
        self.in_transit = []    # en route:        [trader, good, qty, turns_left, location]
        self.delivered_this_turn = []   # (trader, good, qty) matured this turn

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------

    def post(self, trader, good, qty):
        """Move ``qty`` from ``trader.inventory_export`` into this route.

        Returns the quantity actually moved (never more than available).
        """
        qty = int(min(qty, trader.inventory_export[good.value]))
        if qty <= 0:
            return 0
        trader.inventory_export[good.value] -= qty
        # M0.3: every shipment carries its current tile location; starts at
        # the source tile, ready for multi-hop paths on a future map.
        self.pending.append([trader, good, qty, self.src.name])
        return qty

    # ------------------------------------------------------------------
    # Advance / delivery
    # ------------------------------------------------------------------

    def advance(self):
        """Advance all in-transit cargo one turn.

        Shipments whose ``turns_left`` reaches 0 land in the owning
        trader's ``inventory_foreign`` (the destination import pool).
        """
        remaining = []
        self.delivered_this_turn = []
        for entry in self.in_transit:
            entry[3] -= 1
            if entry[3] <= 0:
                trader, good, qty = entry[0], entry[1], entry[2]
                trader.inventory_foreign[good.value] += qty
                self.delivered_this_turn.append((trader, good, qty))
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
            self.in_transit.append([trader, good, qty, delay, location])
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
        # Also drop anything this trader posted but never loaded
        self.pending = [e for e in self.pending if e[0] is not trader]