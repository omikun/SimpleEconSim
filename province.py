"""
province.py — shared institutions for the v3 province model.

A Province owns ONE bundle of institutions (bank / government / charity) that
is shared by all its tiles.  Each Region keeps its own per-tile economy
(production, prices, local auction) but forwards ``region.bank / .gov /
.charity`` to the owning province's bundle — preserving the ~40 existing
read sites across region.py, world_trade.py, forex.py, econsim_live.py and
the viewers.

Millstone D keeps behavior byte-identical: every Region still gets its own
bundle (one tile : one bundle) and ``Region.step()`` runs the institutional
helpers in the exact same order as today.  Milestone E then lets several
Regions point at ONE shared bundle and moves the institutional steps to run
once per province per turn.
"""

from __future__ import annotations

import government as govmod
import econsim_trade_money as _tm
from charity import Charity


class InstitutionBundle:
    """Holder for one tile's (later: one province's) bank / gov / charity.

    During construction the tile creates the bundle, then Region's
    ``bank`` / ``gov`` / ``charity`` properties forward to it.  A Province
    owns exactly one bundle and shares it across its tiles.
    """

    def __init__(self, name: str, recipes, t: int = 0,
                 initial_cash: float = 200.0, wilderness: bool = False):
        # Government (None on unclaimed wilderness — no institutions).
        if wilderness:
            self.gov = None
            self.bank = None
            self.charity = None
        else:
            self.gov = govmod.Government(name, t, initial_cash=initial_cash)
            self.gov.agent.is_government = True
            self.bank = _tm.Bank(gov=self.gov)
            self.charity = Charity(name, recipes)


# Backwards-compatible factory: one bundle per Region (legacy 1:1).
def make_bundle(name, recipes, t=0, initial_cash=200.0, wilderness=False):
    return InstitutionBundle(name, recipes, t=t,
                             initial_cash=initial_cash,
                             wilderness=wilderness)


class Province:
    """A sub-national territory sharing ONE institution bundle.

    Tiles keep their own economy (production, prices, local auction); the
    province's tiles all point at the SAME ``InstitutionBundle`` so bank /
    government / charity are shared.  ``Province.step`` runs the once-per-
    province institutional flows (charity donations, deposit interest) across
    all member tiles; per-tile economy runs via ``Region.step_economy``.
    """

    def __init__(self, name, nation, t=0, recipes=None):
        self.name = name
        self.nation = nation
        self.tiles: list = []
        if recipes is None:
            import econsim_states
            recipes = econsim_states.recipes
        # Own the shared bundle.  Tiles are CONSTRUCTED with this bundle
        # (Region.__init__ institutions=...), so no per-tile bank/government/
        # charity with countable capital is ever abandoned — a tile that
        # re-points to a new bundle would leave its old bank's $2000 capital
        # and $200 gov cash un-counted (a guaranteed SUPPLY SHIFT).
        self.institutions = make_bundle(name, recipes, t=t, initial_cash=200.0)
        self.currency = getattr(nation, 'currency', None)

    @property
    def bank(self):
        return self.institutions.bank

    @property
    def gov(self):
        return self.institutions.gov

    @property
    def charity(self):
        return self.institutions.charity

    def add_tile(self, region):
        """Adopt *region*, repointing it at this province's shared bundle.

        Only call this BEFORE the region has countable money in any old
        bundle (i.e. immediately after construction with ``institutions=``
        or for a freshly-claimed wilderness tile whose bundle is all-None).
        """
        region._institutions = self.institutions
        region.province = self
        if region not in self.tiles:
            self.tiles.append(region)

    def all_agents(self):
        out = []
        for r in self.tiles:
            out.extend(r.agents)
        return out

    def step(self, t):
        """Run one province turn.

        Order mirrors the legacy per-tile cadence but runs the SHARED
        institutionals once across all member agents:
          1. charity collects donations (before trade, so it has cash),
          2. each tile's per-tile economy (labour/produce/trade/tax/live) —
             the province guards in Region.step_economy skip the shared
             institutionals that would otherwise double-run per tile,
          3. bank pays deposit interest once,
          4. charity distributes food once,
          5. government seals its income once.
        """
        all_agents = self.all_agents()
        bank = self.bank
        charity = self.charity
        gov = self.gov
        if charity is not None and bank is not None:
            charity.collect_donations(t, all_agents, bank)
        for r in self.tiles:
            r.step_economy(t)
        if bank is not None:
            bank.PayDepositInterest(all_agents)
        if charity is not None:
            charity.distribute_food(t, all_agents)
        if gov is not None:
            gov.seal_income(t)


def partition_contiguous(cells, layout, nparts, rng=None):
    """Split a contiguous set of even-r offset (row, col) cells into
    *nparts* contiguous subclusters (BFS growth from separable seeds).

    *cells*: list of (row, col).  *layout*: {name: (q, r)} axial map (hexmap).
    Returns a list of lists of (row, col).  When *nparts* == 1 (or the cluster
    is too small to split), returns the whole cluster as one part.
    """
    import random as _random
    rng = rng if rng is not None else _random
    cells = list(cells)
    if nparts <= 1 or len(cells) < nparts:
        return [cells]
    from hexmap import offset_to_axial, hex_distance, axial_to_offset  # noqa
    # Build adjacency via the same odd-r axial layout used everywhere.
    by_rc = {c: c for c in cells}
    # Fallback: just seed greedily by distance from previous seeds.
    # (Full BFS component splitting is overkill for 3-5 cell clusters.)
    seeds = [cells[0]]
    while len(seeds) < nparts and len(seeds) < len(cells):
        best = None
        best_d = -1
        for c in cells:
            if c in seeds:
                continue
            d = min(_offset_dist(c, s) for s in seeds)
            if d > best_d:
                best_d = d
                best = c
        if best is not None:
            seeds.append(best)
        else:
            break
    # Grow each part from its seed (greedy nearest-cell assignment keeps
    # every part connected in practice for tiny clusters).
    parts = [[s] for s in seeds]
    remaining = [c for c in cells if c not in seeds]
    while remaining:
        best_part, best_cell, best_d = None, None, 1e18
        for pi, part in enumerate(parts):
            for c in remaining:
                d = min(_offset_dist(c, m) for m in part)
                if d < best_d:
                    best_part, best_cell, best_d = pi, c, d
        if best_cell is None:
            break
        parts[best_part].append(best_cell)
        remaining.remove(best_cell)
    return parts


def _offset_dist(a, b):
    """Even-r offset (row,col) distance approximated by axial hex distance."""
    from hexmap import offset_to_axial, hex_distance
    qa, ra = offset_to_axial(a[1], a[0])
    qb, rb = offset_to_axial(b[1], b[0])
    return hex_distance((qa, ra), (qb, rb))
