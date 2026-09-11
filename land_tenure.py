"""
Land tenure — the legal relationship between people and land.

At game start, all claimed tiles are FEUDAL: a lord holds title,
serfs hold customary usufruct rights (grazing, gleaning, firewood).
Enclosure converts FEUDAL to ENCLOSED by stripping those rights.
LEASEHOLD is a transitional state where customary rents are being
replaced by cash rents but some commons access remains.

This module is a LEAF — zero simulation imports.  Safe to import
from agent.py, region.py, or any other module without cycles.

Invariants:
  - sum(plot.fraction for plot in tenure.plots) <= 1.0
  - commons_access = feudal_fraction * 1.0 + leasehold_fraction * 0.5
  - Enclosing a plot NEVER creates or destroys money or goods.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class TenureStatus(Enum):
    """Legal status of a land parcel."""
    FEUDAL = 'feudal'          # Lord holds title, serfs have usufruct
    LEASEHOLD = 'leasehold'    # Transitional: cash rents, partial rights
    ENCLOSED = 'enclosed'      # Fully privatized, no customary rights
    COMMONS = 'commons'        # Reverted or revolutionary commons: full usufruct, zero rent


@dataclass
class LandPlot:
    """A single parcel of land on a tile with a specific tenure status.

    Under feudalism, the lord collects in-kind tribute.
    Under enclosure, the lord collects cash rent.
    Under commons, community holds usufruct with zero tribute or rent.
    """
    plot_id: str                        # unique identifier
    tile_name: str                      # which Region this plot sits on
    lord_id: int                        # Agent.id of the feudal lord / landlord
    fraction: float                     # fraction of the tile (0.0-1.0)
    tenure: TenureStatus                # current tenure status
    enclosed_turn: int = -1             # turn when customary rights stripped (-1 = never)
    rent_rate: float = 0.0              # cash rent per tenant per turn (0 under feudal/commons)
    tribute_rate: float = 0.5           # in-kind tribute fraction (feudal only)
    production_type: str = 'mixed'      # 'mixed', 'cash_crop', 'pasture', 'forest'


@dataclass
class TileTenure:
    """Aggregate land tenure state for one tile/Region.

    At game start, a claimed tile has 1-3 FEUDAL plots (one per lord),
    each covering a fraction of the tile, summing to 1.0.
    Wilderness tiles have an empty plots list (fully wild, no lord).
    """
    plots: list[LandPlot] = field(default_factory=list)

    # ---- Derived properties ----

    @property
    def feudal_fraction(self) -> float:
        """Land still under feudal customary tenure."""
        return sum(p.fraction for p in self.plots
                   if p.tenure == TenureStatus.FEUDAL)

    @property
    def enclosed_fraction(self) -> float:
        """Land fully enclosed (no customary rights)."""
        return sum(p.fraction for p in self.plots
                   if p.tenure == TenureStatus.ENCLOSED)

    @property
    def leasehold_fraction(self) -> float:
        """Land under transitional leasehold."""
        return sum(p.fraction for p in self.plots
                   if p.tenure == TenureStatus.LEASEHOLD)

    @property
    def commons_fraction(self) -> float:
        """Land restored to customary or revolutionary commons."""
        return sum(p.fraction for p in self.plots
                   if p.tenure == TenureStatus.COMMONS)

    @property
    def commons_access(self) -> float:
        """Effective fraction of tile where serfs can still forage.

        FEUDAL plots grant full access (serfs have usufruct rights).
        LEASEHOLD plots grant half access (partial rights remain).
        COMMONS plots grant full access (restored usufruct rights).
        ENCLOSED plots grant zero access (trespassing criminalized).

        Wilderness tiles (no plots) return 1.0 — fully wild.
        """
        if not self.plots:
            return 1.0  # wilderness: fully accessible
        return min(1.0, (self.feudal_fraction * 1.0
                + self.leasehold_fraction * 0.5
                + self.commons_fraction * 1.0))

    @property
    def total_plotted(self) -> float:
        """Total fraction of tile covered by plots."""
        return sum(p.fraction for p in self.plots)

    # ---- Query helpers ----

    def lord_ids(self) -> set[int]:
        """Set of all lord Agent.ids holding plots on this tile."""
        return {p.lord_id for p in self.plots}

    def plots_by_lord(self, lord_id: int) -> list[LandPlot]:
        """All plots belonging to a specific lord."""
        return [p for p in self.plots if p.lord_id == lord_id]

    def total_by_lord(self, lord_id: int) -> float:
        """Total fraction of tile held by a specific lord."""
        return sum(p.fraction for p in self.plots_by_lord(lord_id))

    def feudal_plots(self) -> list[LandPlot]:
        """All plots still under feudal tenure (enclosable)."""
        return [p for p in self.plots
                if p.tenure == TenureStatus.FEUDAL]

    def enclosed_plots(self) -> list[LandPlot]:
        """All fully enclosed plots."""
        return [p for p in self.plots
                if p.tenure == TenureStatus.ENCLOSED]

    def find_plot(self, plot_id: str) -> Optional[LandPlot]:
        """Find a plot by ID, or None."""
        for p in self.plots:
            if p.plot_id == plot_id:
                return p
        return None

    # ---- Mutation helpers ----

    def add_plot(self, plot: LandPlot):
        """Add a plot, enforcing the fraction invariant."""
        new_total = self.total_plotted + plot.fraction
        if new_total > 1.0 + 1e-9:
            raise ValueError(
                f"Cannot add plot {plot.plot_id}: total would be "
                f"{new_total:.4f} > 1.0"
            )
        self.plots.append(plot)

    def enclose_plot(self, plot_id: str, turn: int,
                     rent_rate: float = 5.0) -> Optional[LandPlot]:
        """Convert a FEUDAL plot to ENCLOSED.

        Sets enclosed_turn, zeroes tribute_rate, sets cash rent_rate.
        Returns the modified plot, or None if not found / already enclosed.
        """
        plot = self.find_plot(plot_id)
        if plot is None or plot.tenure != TenureStatus.FEUDAL:
            return None
        plot.tenure = TenureStatus.ENCLOSED
        plot.enclosed_turn = turn
        plot.tribute_rate = 0.0
        plot.rent_rate = rent_rate
        return plot

    def revert_plot_to_commons(self, plot_id: str, turn: int = -1) -> Optional[LandPlot]:
        """Convert an ENCLOSED or LEASEHOLD plot back to COMMONS.

        Used in anti-enclosure revolts or popular commune decrees.
        Zeroes rent_rate and tribute_rate, restoring full customary foraging access.
        """
        plot = self.find_plot(plot_id)
        if plot is None:
            return None
        plot.tenure = TenureStatus.COMMONS
        plot.rent_rate = 0.0
        plot.tribute_rate = 0.0
        return plot

    def revert_all_to_commons(self, turn: int = -1) -> int:
        """Convert all plots on the tile to COMMONS (revolutionary commune decree).

        Returns count of converted plots.
        """
        count = 0
        for plot in self.plots:
            if plot.tenure != TenureStatus.COMMONS:
                plot.tenure = TenureStatus.COMMONS
                plot.rent_rate = 0.0
                plot.tribute_rate = 0.0
                count += 1
        return count

