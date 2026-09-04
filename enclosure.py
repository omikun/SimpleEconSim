"""
enclosure.py — Feudal Enclosure & Dispossession Engine for REGNUM.

Under the Enclosure Act, a lord petitions the crown to strip customary
usufruct rights from their feudal estate. The crown grants an enclosure
charter in exchange for a charter fee (conserved transfer: lord -> crown).

Consequences of enclosure:
  1. Plot tenure changes from FEUDAL to ENCLOSED.
  2. The plot ceases paying in-kind tribute and will charge cash rent.
  3. Serfs lose access to the enclosed commons (commons_access decreases).
  4. Dispossessed serfs receive persistent 'mem_eviction' trauma.
  5. Grievances spike on identity and class factions, raising protest energy.
  6. Dispossessed serfs become dependent on the wage-labor market.
"""

from goods import Goods
from land_tenure import TenureStatus, LandPlot

# Charter fee per 10% (0.10) fraction of tile enclosed
CHARTER_FEE_PER_TENTH = 100.0
DEFAULT_CASH_RENT = 3.0


def calculate_charter_fee(plot: LandPlot) -> float:
    """Calculate the crown charter fee required to enclose this plot."""
    return round((plot.fraction / 0.10) * CHARTER_FEE_PER_TENTH, 2)


def dispossess_commoners(tile, plot: LandPlot, t: int) -> list[dict]:
    """Apply dispossession trauma and grievance to serfs on the enclosed tile.

    - Pushes 'mem_eviction' memory to serfs on the tile.
    - Increases grievance and protest energy.
    - Returns event records for logging / UI ticker.
    """
    events = []
    serfs = [a for a in tile.agents
             if not a.is_trader and not a.is_government
             and not getattr(a, 'is_lord', False)
             and a.alive]

    if not serfs:
        return events

    # Number of serfs directly dispossessed by this plot's enclosure
    dispossessed_count = max(1, int(len(serfs) * plot.fraction))
    for serf in serfs[:dispossessed_count]:
        serf.mem_push('mem_eviction', 1.0)

    # Spike protest energy on tile
    protest_bump = round(plot.fraction * 5.0, 2)
    current_energy = getattr(tile, 'protest_energy_log', [])
    if current_energy:
        current_energy[-1] = min(10.0, current_energy[-1] + protest_bump)

    events.append({
        't': t,
        'event': 'ENCLOSURE_DISPOSSESSION',
        'tile': tile.name,
        'plot_id': plot.plot_id,
        'dispossessed_count': dispossessed_count,
        'message': (f"Enclosure of plot {plot.plot_id} on {tile.name}: "
                    f"{dispossessed_count} serfs dispossessed of customary rights.")
    })
    return events


def execute_enclosure(tile, plot_id: str, t: int, rent_rate: float = DEFAULT_CASH_RENT) -> tuple[bool, str, list[dict]]:
    """Execute legal enclosure of a FEUDAL plot on *tile*.

    Conserved transfer:
      lord.cash -= fee
      gov.agent.cash += fee

    State transition:
      plot.tenure: FEUDAL -> ENCLOSED
    """
    tenure = getattr(tile, 'tenure', None)
    if tenure is None:
        return False, f"Tile '{tile.name}' has no land tenure system.", []

    plot = tenure.find_plot(plot_id)
    if plot is None:
        return False, f"Plot '{plot_id}' not found on tile '{tile.name}'.", []

    if plot.tenure != TenureStatus.FEUDAL:
        return False, f"Plot '{plot_id}' is already {plot.tenure.value}.", []

    # Find the lord owning this plot
    lord = None
    for a in tile.agents:
        if a.id == plot.lord_id:
            lord = a
            break

    if lord is None or not lord.alive:
        return False, f"Lord for plot '{plot_id}' is deceased or absent.", []

    fee = calculate_charter_fee(plot)
    if lord.cash < fee:
        return False, f"Lord cash (${lord.cash:.1f}) insufficient for charter fee (${fee:.1f}).", []

    gov = tile.gov
    if gov is None or gov.agent is None:
        return False, f"No government authority seated to issue enclosure charter on '{tile.name}'.", []

    # Conserved financial transfer: lord pays the crown
    lord.cash -= fee
    gov.agent.cash += fee

    # Enclose the plot
    tenure.enclose_plot(plot_id, turn=t, rent_rate=rent_rate)

    # Dispossess serfs and log events
    events = dispossess_commoners(tile, plot, t)
    msg = (f"Enclosure Charter granted on {tile.name}: Plot {plot_id} enclosed. "
           f"Charter fee ${fee:.1f} paid to crown. Commons access reduced to {tenure.commons_access:.1%}.")

    events.append({
        't': t,
        'event': 'ENCLOSURE_COMPLETED',
        'tile': tile.name,
        'plot_id': plot_id,
        'fee': fee,
        'message': msg
    })
    return True, msg, events
