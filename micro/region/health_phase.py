"""Regional workhouse, health, and externality phases."""
from micro.region import disabled_phases


def run(region, t, flags):
    from micro.region.stepper import audit_cash
    # Parish Workhouse & Vagrancy Enforcement (Phase 1)
    from workhouse import step_workhouse, get_workhouse_inmates
    if flags.workhouse:
        step_workhouse(region, t)
        region.workhouse_inmates_log.append(len(get_workhouse_inmates(region)))
    else:
        disabled_phases.workhouse(region)
    audit_cash(region, t, "workhouse_done")

    # Alienation, Health Attrition & Despair (P2.2)
    from alienation import step_tile_alienation
    if flags.alienation:
        step_tile_alienation(region, t)
    else:
        disabled_phases.alienation(region)

    # Metabolic Rift & Externalities Engine (P3)
    from externalities import step_tile_externalities
    if flags.pollution:
        step_tile_externalities(region, t)
    else:
        disabled_phases.pollution(region)

    # Epidemics & Medical Economics (P3)
    from disease import step_tile_diseases
    if flags.disease:
        step_tile_diseases(region, t)
    else:
        disabled_phases.disease(region)
    audit_cash(region, t, "disease_done")

    # True Cost & Externalities Ledger Finalization
    try:
        from economy.true_cost_ledger import get_true_cost_ledger
        scen_id = getattr(getattr(region, 'gov', None), 'scenario_id', None)
        get_true_cost_ledger().seal_turn(t, scenario_id=scen_id)
    except Exception:
        pass

    # Charity distributes through Live before meals and mortality in all modes.
