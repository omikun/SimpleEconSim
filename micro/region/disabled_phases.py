"""Turn-aligned observations when an optional local mechanism is disabled."""


def workhouse(region):
    from workhouse import get_workhouse_inmates
    region.workhouse_inmates_log.append(len(get_workhouse_inmates(region)))


def workplace_resistance(region):
    """Keep stock readings aligned while producing no new strike or damage."""
    return {
        'strikers': region.strikers_log[-1] if region.strikers_log else 0,
        'broken_machinery': (region.broken_machinery_log[-1]
                             if region.broken_machinery_log else 0),
        'smashed_this_turn': 0,
    }


def alienation(region):
    for name in ('avg_alienation_log', 'avg_health_attrition_log',
                 'avg_consciousness_log'):
        history = getattr(region, name)
        history.append(history[-1] if history else 0.0)
    region.workplace_accidents_log.append(0)
    region.entertainment_log.append(region.entertainment_level)


def pollution(region):
    for history, value in (
        ('soil_fertility_log', 'soil_fertility'),
        ('nutrition_density_log', 'nutrition_density'),
        ('pollution_air_log', 'pollution_air'),
        ('pollution_water_log', 'pollution_water'),
        ('pollution_soil_log', 'pollution_soil'),
    ):
        getattr(region, history).append(getattr(region, value))
    region.fertilizer_consumed_last_turn = 0.0
    region.fertilizer_inflow_last_turn = 0.0


def disease(region):
    from collections import Counter
    counts = Counter(disease for agent in region.agents
                     if getattr(agent, 'alive', True)
                     for disease in getattr(agent, 'diseases', ()))
    region.disease_cases_log.append(dict(counts))
    region.medical_spending_private_log.append(0.0)
    region.medical_spending_public_log.append(0.0)
    region.untreated_cases_log.append(0)
    region.disease_fatalities_log.append(region.disease_fatalities_this_turn)
    region.active_pestilence_count = counts.get('pestilence', 0)


def factions(region):
    region.faction_support_log.append({name: faction.support
                                       for name, faction in region.factions.factions.items()})
    region.faction_grievance_log.append({name: faction.total_grievance()
                                         for name, faction in region.factions.factions.items()})
    region.protest_energy_log.append(0.0)


def unrest(region):
    region.unrest_flag = False
    region.unrest_log.append({'stage': 'calm', 'looted': 0, 'takeover': False})


def defer_payroll_reviews(region, turn):
    """Keep pending strike reviews open while wage settlement is paused."""
    for organization in getattr(region, 'collective_organizations', {}).values():
        for strike in organization.strikes:
            if (strike.status == 'review' and not strike.settlement_applied
                    and strike.review_turn is not None
                    and strike.ended_turn is not None
                    and turn > strike.ended_turn
                    and turn <= strike.review_turn):
                strike.review_turn += 1
