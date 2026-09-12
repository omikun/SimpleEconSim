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
STATUTORY_SURVEY_FEE = 15.0


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

    # Phase 1: Assess statutory surveying and hedging fees on customary tenants
    if not hasattr(tile, 'enclosure_survey_debts'):
        tile.enclosure_survey_debts = []

    # Identify tenants on this plot
    plot_tenants = [a for a in tile.agents if a.id in getattr(plot, 'tenant_ids', []) and a.alive]
    if not plot_tenants:
        plot_tenants = [a for a in tile.agents if not a.is_trader and not a.is_government and not getattr(a, 'is_lord', False) and a.alive][:max(1, int(len(tile.agents) * plot.fraction))]

    for tenant in plot_tenants:
        tile.enclosure_survey_debts.append({
            'tenant_id': tenant.id,
            'plot_id': plot_id,
            'fee': STATUTORY_SURVEY_FEE,
            'deadline': t + 3,
            'enclosed_turn': t,
        })

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


def step_enclosure_survey_debts(tile, t: int) -> list[dict]:
    """Process statutory surveying and hedging fee debts for enclosed plots.

    Tenants have 3 turns to pay the statutory fee ($15.0).
    - If tenant has cash >= fee: fee paid to municipal government (conserved transfer).
    - If t < deadline: tenant suffers debt anxiety (mem_promises).
    - If t >= deadline and unpaid: customary claim is legally foreclosed!
      An auction is held on the tile: the wealthiest bidder pays the auction price
      to the municipal treasury, and the defaulting tenant is evicted into
      SocialClass.DISPOSSESSED with mem_debt_trap and mem_eviction.
    """
    if not hasattr(tile, 'enclosure_survey_debts') or not tile.enclosure_survey_debts:
        return []

    events = []
    gov = getattr(tile, 'gov', None)
    gov_agent = gov.agent if gov else None
    remaining_debts = []

    for debt in tile.enclosure_survey_debts:
        tenant_id = debt['tenant_id']
        fee = debt['fee']
        deadline = debt['deadline']
        plot_id = debt['plot_id']

        tenant = None
        for a in tile.agents:
            if a.id == tenant_id:
                tenant = a
                break

        if tenant is None or not tenant.alive:
            continue

        if tenant.cash >= fee:
            # Solvent tenant pays survey fee (conserved transfer)
            tenant.cash -= fee
            if gov_agent:
                gov_agent.cash += fee
            events.append({
                't': t,
                'event': 'SURVEY_FEE_PAID',
                'tile': tile.name,
                'tenant_id': tenant_id,
                'plot_id': plot_id,
                'fee': fee,
                'message': f"Tenant {tenant_id} paid statutory surveying fee ${fee:.1f} on {tile.name}."
            })
        elif t < deadline:
            # Under legal debt pressure
            tenant.mem_push('mem_promises', 0.5)
            remaining_debts.append(debt)
        else:
            # Insolvent at deadline -> Foreclosure & Auction
            plot = tile.tenure.find_plot(plot_id) if hasattr(tile, 'tenure') else None

            # Find wealthy bidders on tile
            bidders = [a for a in tile.agents if a.id != tenant_id and a.alive and a.cash >= 10.0 and not a.is_government]
            bidders.sort(key=lambda a: a.cash, reverse=True)

            clearing_bid = 0.0
            winner_id = None
            if bidders and gov_agent:
                winner = bidders[0]
                winner_id = winner.id
                clearing_bid = min(winner.cash, 25.0)
                winner.cash -= clearing_bid
                gov_agent.cash += clearing_bid

            # Evict the tenant from customary holding
            if plot and hasattr(plot, 'tenant_ids') and tenant.id in plot.tenant_ids:
                plot.tenant_ids.remove(tenant.id)
            tenant.assigned_plot_id = None
            tenant.social_class = 'dispossessed'
            tenant.mem_push('mem_debt_trap', 1.0)
            tenant.mem_push('mem_eviction', 1.0)

            # Raise tile protest energy
            if hasattr(tile, 'protest_energy_log') and tile.protest_energy_log:
                tile.protest_energy_log[-1] = min(10.0, tile.protest_energy_log[-1] + 1.0)

            msg = (f"Legal Foreclosure on {tile.name}: Tenant {tenant_id} unable to pay "
                   f"statutory surveying fee (${fee:.1f}). Holding auctioned"
                   f"{f' to agent {winner_id} for ${clearing_bid:.1f}' if winner_id else ' off'}."
                   f" Tenant dispossessed.")
            events.append({
                't': t,
                'event': 'SURVEY_DEBT_FORECLOSURE',
                'tile': tile.name,
                'tenant_id': tenant_id,
                'plot_id': plot_id,
                'winner_id': winner_id,
                'clearing_bid': clearing_bid,
                'message': msg
            })

    tile.enclosure_survey_debts = remaining_debts
    return events
