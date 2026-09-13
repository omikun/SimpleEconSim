"""
construction_politics.py — Emergent Construction Companies, Labor Politics & Dynamic Infrastructure for REGNUM.

Implements:
1. Zero Companies at Game Start: No construction contractors exist initially.
2. Organic Agent Transition: When a project is funded, the contract money incentivizes
   an eligible living agent (artisan, merchant, ambitious petty-bourgeois) to incorporate
   into a Construction Company (is_construction_company = True).
3. Labor & Scaling: Contractor recruits living agents as navvies/builders, paying wages.
   More projects / capital = more hiring or competing contractor syndicates.
4. Contractor Political Power:
   Power = (cash * 0.01) + (workers * 2.0) + (projects_completed * 3.0).
   Boosts Bourgeoisie faction influence and generates infrastructure petitions.
5. Emergency Overrun Subsidies: Option to inject treasury grants to keep contractors
   solvent and finish jobs before layoffs occur.
6. Project Droughts, Layoffs & Navvy Riots:
   If idle for >= 2 turns without contracts, contractor discharges navvies into
   dispossessed vagrancy, spiking protest energy and triggering destructive Navvy Riots.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from goods import Goods

if TYPE_CHECKING:
    from region import Region
    from agent import Agent
    from nation import Nation
    from buildings import ConstructionProject


def find_or_emerge_contractor(region: Region, budget: float, t: int) -> Agent:
    """Find an existing construction company with capacity, or transition an eligible living agent."""
    # 1. Look for existing construction companies in the region
    existing_contractors = [
        a for a in getattr(region, 'agents', [])
        if getattr(a, 'is_construction_company', False) and getattr(a, 'alive', True)
    ]

    # Check if any existing contractor has spare capacity (< 2 active projects)
    projects = getattr(region, 'construction_projects', [])
    for c in existing_contractors:
        active_cnt = sum(1 for p in projects if p.contractor == c and p.status in ('in_progress', 'stalled'))
        if active_cnt < 2:
            c.idle_turns = 0
            return c

    # 2. No contractor or all existing are busy: An eligible living agent transitions!
    eligible_candidates = [
        a for a in getattr(region, 'agents', [])
        if getattr(a, 'alive', True)
        and not getattr(a, 'is_corporation', False)
        and not getattr(a, 'is_government', False)
    ]

    if eligible_candidates:
        # Score candidates by savings, class, and enterprise suitability
        def _score(cand):
            s = cand.cash
            sclass = getattr(cand, 'social_class', '')
            if sclass in ('industrialist', 'petty_bourgeois', 'artisan', 'landlord', 'merchant'):
                s += 40.0
            elif sclass == 'proletarian':
                s += 10.0
            return s

        eligible_candidates.sort(key=_score, reverse=True)
        founder = eligible_candidates[0]
        founder.is_construction_company = True
        founder.is_corporation = True
        founder.social_class = 'contractor'
        founder_name = getattr(founder, 'name', f"Citizen #{founder.id}")
        founder.company_name = f"{founder_name}'s Contracting Syndicate"
        founder.projects_completed = getattr(founder, 'projects_completed', 0)
        founder.idle_turns = 0
        if not hasattr(founder, 'employees'):
            founder.employees = []
        return founder

    # 3. Fallback: create fresh contractor agent if population is zero or completely unavailable
    from agent import Agent, initialize_agent, seed_traits
    contractor = Agent(t)
    contractor.is_corporation = True
    contractor.is_construction_company = True
    contractor.social_class = 'contractor'
    contractor.output = Goods.transport
    contractor._bank_ref = getattr(region, 'bank', None)
    contractor.home_currency = getattr(region, 'home_currency', 'gold')
    contractor.region = region.name
    contractor.company_name = f"{region.name} Public Works Syndicate"
    contractor.projects_completed = 0
    contractor.idle_turns = 0
    seed_traits(contractor)
    initialize_agent(contractor, Goods.transport, 0, 0, 0.0)
    region.agents.append(contractor)
    return contractor


def calculate_contractor_political_power(contractor: Agent) -> float:
    """Calculates political power derived from capital, navvy headcount, and completed works."""
    if not contractor or not getattr(contractor, 'alive', True):
        return 0.0
    cash = getattr(contractor, 'cash', 0.0)
    workers = len(getattr(contractor, 'employees', []))
    completed = getattr(contractor, 'projects_completed', 0)
    return (cash * 0.01) + (workers * 2.0) + (completed * 3.0)


def subsidize_contractor(project: ConstructionProject, amount: float, nation: Nation, world: dict = None) -> tuple[bool, str]:
    """Transfers emergency overrun grant from Treasury to contractor to avert bankruptcy and layoffs."""
    contractor = project.contractor
    if contractor is None:
        return False, "Project has no contractor to subsidize."

    gov = getattr(nation, 'government', None)
    if gov is None or gov.agent.cash < amount:
        return False, f"Insufficient treasury cash (${getattr(gov.agent, 'cash', 0.0):.2f} < ${amount:.2f})."

    # Conserved transfer: Treasury -> Contractor
    gov.agent.cash -= amount
    contractor.cash += amount
    project.emergency_subsidies_received = getattr(project, 'emergency_subsidies_received', 0.0) + amount

    # Resume project if stalled
    if project.status == 'stalled':
        project.status = 'in_progress'
        project.stall_reason = ""

    comp_name = getattr(contractor, 'company_name', f"Contractor #{contractor.id}")
    msg = (f"[SUBSIDY GRANTED] Injected ${amount:.0f} overrun grant into {comp_name} "
           f"for {project.recipe.display_name}. Navvy layoffs averted; construction resumed.")
    project.events.append({'t': getattr(world, 'get', lambda k, d=0: 0)('turn', 0), 'event': 'SUBSIDY', 'message': msg})

    if world is not None:
        try:
            from worldview_engine import ticker_push
            t = world.get('turn', 0)
            ticker_push(world, t, 'CONSTRUCT', msg, (100, 220, 140))
        except Exception:
            pass

    return True, msg


def step_construction_politics(region: Region, t: int, world: dict = None):
    """Advance turn lifecycle of construction contractors, political lobbying, drought layoffs, and riots."""
    contractors = [
        a for a in getattr(region, 'agents', [])
        if getattr(a, 'is_construction_company', False) and getattr(a, 'alive', True)
    ]
    if not contractors:
        return

    projects = getattr(region, 'construction_projects', [])
    try:
        from worldview_engine import ticker_push
    except ImportError:
        ticker_push = lambda w, turn, cat, txt, col: None

    for contractor in contractors:
        comp_name = getattr(contractor, 'company_name', f"Contractor #{contractor.id}")
        active_projects = [
            p for p in projects
            if p.contractor == contractor and p.status in ('in_progress', 'stalled')
        ]

        if active_projects:
            contractor.idle_turns = 0
            # Check for financial distress warning
            worker_count = len(getattr(contractor, 'employees', []))
            payroll_needed = worker_count * 1.50
            if contractor.cash < max(5.0, payroll_needed * 1.5):
                proj = active_projects[0]
                warning_msg = (f"[CONTRACTOR DISTRESS] {comp_name} running out of capital on "
                               f"{proj.recipe.display_name} in {region.name}! Subsidize to avert layoffs.")
                if world is not None:
                    ticker_push(world, t, 'CONSTRUCT', warning_msg, (245, 120, 80))
        else:
            # No active projects: Idle turn accumulates
            contractor.idle_turns = getattr(contractor, 'idle_turns', 0) + 1

            # 1. Corporate Lobbying (Turn 1 idle)
            if contractor.idle_turns == 1:
                power = calculate_contractor_political_power(contractor)
                lobby_msg = (f"[LOBBYING] {comp_name} (Power: {power:.1f}) petitions Parliament for "
                             f"new public works contracts in {region.name}.")
                if world is not None:
                    ticker_push(world, t, 'POLITICS', lobby_msg, (240, 200, 80))

            # 2. Project Drought & Mass Layoffs (Turn >= 2 idle)
            elif contractor.idle_turns >= 2 and getattr(contractor, 'employees', []):
                workers = list(contractor.employees)
                num_laid_off = len(workers)
                for w in workers:
                    w.employer = None
                    w.social_class = 'dispossessed'
                    w.mem_push('mem_layoff', 2.5)
                    w.mem_push('mem_unemployment', 2.0)
                contractor.employees.clear()

                # Spike tile protest energy
                if hasattr(region, 'protest_energy_log') and region.protest_energy_log:
                    pe_boost = min(4.5, num_laid_off * 0.9)
                    region.protest_energy_log[-1] = min(10.0, region.protest_energy_log[-1] + pe_boost)

                layoff_msg = (f"[NAVVY LAYOFFS] Project drought forced {comp_name} to lay off "
                              f"{num_laid_off} navvies in {region.name} into dispossessed vagrancy!")
                if world is not None:
                    ticker_push(world, t, 'CONSTRUCT', layoff_msg, (240, 140, 60))

                # 3. Navvy Riots if local protest energy boils over
                cur_pe = region.protest_energy_log[-1] if region.protest_energy_log else 0.0
                if cur_pe >= 5.5:
                    riot_msg = (f"[NAVVY RIOT] Disgruntled discharged navvies in {region.name} "
                                f"staged a riot, clashing with municipal constabulary!")
                    if world is not None:
                        ticker_push(world, t, 'UNREST', riot_msg, (235, 70, 70))

            # 4. Long Drought: Bankruptcy & Dissolution (Turn >= 5 idle, low cash)
            elif contractor.idle_turns >= 5 and contractor.cash < 15.0:
                contractor.is_construction_company = False
                contractor.is_corporation = False
                contractor.social_class = 'proletarian'
                dissolve_msg = f"[BANKRUPTCY] {comp_name} liquidated and dissolved following prolonged project drought."
                if world is not None:
                    ticker_push(world, t, 'CONSTRUCT', dissolve_msg, (180, 160, 160))
