"""
social_class.py — Dynamic Social Class Engine for REGNUM.

Classes are not static labels assigned at birth; they emerge dynamically
from each agent's real, objective relation to property, land, and capital:
  - Do you hold feudal land with customary tribute? -> LORD
  - Do you hold enclosed land and collect cash rent? -> LANDLORD
  - Do you own a multi-employee corporation? -> INDUSTRIALIST
  - Do you work for wages under an employer? -> PROLETARIAN
  - Do you work independently with your own tools? -> PETTY_BOURGEOIS
  - Do you live on customary land with commons access? -> SERF
  - Do you live on enclosed land paying cash rent? -> TENANT
  - Are you unemployed, landless, with no commons? -> DISPOSSESSED
"""

from enum import Enum
from land_tenure import TenureStatus


class SocialClass(Enum):
    LORD = 'lord'                     # Feudal title, customary tribute
    LANDLORD = 'landlord'             # Enclosed estate, cash rent
    INDUSTRIALIST = 'industrialist'   # Owns corporation with employees
    PETTY_BOURGEOIS = 'petty_bourgeois' # Independent master / craftsman
    PROLETARIAN = 'proletarian'       # Sells labor power for wages
    SERF = 'serf'                     # Un-enclosed commons subsistence
    TENANT = 'tenant'                 # Enclosed land, pays cash rent
    DISPOSSESSED = 'dispossessed'     # Landless, jobless, desperate


def compute_class(agent, region) -> SocialClass:
    """Determine an agent's social class from current economic relations."""
    if agent.is_government:
        return SocialClass.LORD if getattr(agent, 'is_lord', False) else SocialClass.PETTY_BOURGEOIS

    # Check land ownership
    tenure = getattr(region, 'tenure', None)
    if tenure is not None and getattr(agent, 'is_lord', False):
        plots = tenure.plots_by_lord(agent.id)
        if any(p.tenure == TenureStatus.ENCLOSED for p in plots):
            return SocialClass.LANDLORD
        if any(p.tenure == TenureStatus.FEUDAL for p in plots):
            return SocialClass.LORD

    # Check corporate capital ownership
    if getattr(agent, 'is_corporation', False):
        if len(getattr(agent, 'employees', [])) > 0:
            return SocialClass.INDUSTRIALIST
        return SocialClass.PETTY_BOURGEOIS

    if getattr(agent, 'company_owned', None) is not None:
        return SocialClass.INDUSTRIALIST

    # Check wage labor relation
    if getattr(agent, 'employer', None) is not None:
        return SocialClass.PROLETARIAN

    # Check independent artisan / trader status
    if getattr(agent, 'is_trader', False):
        return SocialClass.PETTY_BOURGEOIS

    commons = tenure.commons_access if tenure is not None else 1.0

    # If commons access is open (> 0.5), agent is an agrarian serf/commoner
    if commons > 0.5:
        return SocialClass.SERF

    # If land is enclosed and agent has cash/housing to pay rent
    if commons <= 0.5:
        if agent.cash >= 5.0:
            return SocialClass.TENANT
        # Destitute, jobless, landless
        return SocialClass.DISPOSSESSED

    return SocialClass.PETTY_BOURGEOIS


def update_tile_social_classes(region) -> dict[str, int]:
    """Compute and update social_class on all agents in *region*.

    Returns distribution dict: {class_name: count}.
    """
    counts = {}
    for a in region.agents:
        if not a.alive:
            continue
        sclass = compute_class(a, region)
        a.social_class = sclass.value
        counts[sclass.value] = counts.get(sclass.value, 0) + 1
    return counts
