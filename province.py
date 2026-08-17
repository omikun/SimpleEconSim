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