"""Definitions and provenance for metrics exposed by the simulation.

Unknown legacy histories are inventoried as unexplained rather than assigned
an invented calculation. Chart rounding happens after these definitions.
"""

from __future__ import annotations


METRICS = {
    'goods.price': ('tile/good', 'local_currency_per_unit', 'region_market.update_price_ref/price_decay/set_price'),
    'goods.production': ('tile/good', 'units_per_turn', 'region_production.produce'),
    'goods.producer_inventory': ('tile/good', 'units', 'micro.region.stepper.log_metrics'),
    'goods.demand': ('tile/good', 'units_offered', 'region_market.trade'),
    'goods.supply': ('tile/good', 'units_offered', 'region_market.trade'),
    'goods.sold': ('tile/good', 'units', 'region_market.trade'),
    'living.cost_of_living': ('tile', 'local_currency_per_basket', 'micro.region.stepper.step_economy'),
    'people.population': ('tile', 'people', 'micro.region.stepper.log_metrics'),
    'people.hungry': ('tile', 'people', 'micro.region.stepper.log_metrics'),
    'people.migration_pressure': ('tile', 'score', 'region_logistics.migration_intent_components'),
    'people.migration': ('tile', 'people', 'migration.run_migrations'),
    'people.migration_in': ('tile', 'people', 'migration.run_migrations'),
    'economy.gdp_nominal': ('tile', 'local_currency_per_turn', 'micro.region.stepper.log_gdp'),
    'economy.cash': ('tile', 'local_currency', 'micro.region.stepper.log_metrics'),
    'economy.gini': ('tile/cohort', 'ratio', 'micro.region.stepper.log_metrics'),
    'labor.exploitation_rate': ('tile', 'ratio', 'labor_contract.aggregate_tile_surplus'),
    'labor.strikers': ('tile', 'people', 'labor_resistance.step_workplace_resistance'),
    'labor.hiring_decision': ('tile/firm/worker', 'accepted', 'region_labor.hire_workers'),
    'labor.payroll_funding': ('tile/firm', 'workers', 'region_labor.borrow_or_layoff'),
    'labor.firm_incorporation': ('tile/firm', 'local_currency', 'region_labor.incorporate'),
    'labor.corporate_wage': ('tile/firm', 'local_currency_per_turn', 'region_labor.adjust_wages'),
    'construction.progress': ('tile/project', 'percent', 'buildings.ConstructionProject.step'),
    'war.battle': ('tile/attacker/defender', 'soldiers', 'army.resolve_battle'),
    'war.territory_control': ('tile', 'nation_name', 'intents.MoveArmyIntent.execute'),
    'war.cohesion': ('nation/opponent', 'ratio', 'war_logic.update_wars'),
    'war.posture': ('nation/opponent', 'category', 'war_logic.classify_posture'),
    'diplomacy.relation': ('nation_pair', 'ratio', 'diplomacy.DiplomacySystem.update_relations'),
    'politics.grievance': ('tile/faction', 'score', 'region_factions.accumulate_grievances'),
    'politics.protest_energy': ('tile', 'score', 'region_factions.protest_energy'),
    'politics.unrest_event': ('tile', 'category', 'unrest.step_unrest'),
    'politics.legitimacy': ('nation', 'ratio', 'regime.track_legitimacy'),
    'fx.bilateral_mid': ('tile/partner', 'home_currency_per_foreign_currency', 'forex.ForexDesk.update'),
    'finance.treasury': ('nation', 'local_currency', 'nation.Nation.treasury'),
    'finance.obligation_balance': ('tile/obligation', 'local_currency', 'livelihood_access.settle_obligations'),
    'finance.obligation_payment': ('tile/origin', 'local_currency', 'livelihood_access.settle_obligations'),
    'finance.rent_collected': ('tile', 'local_currency', 'micro.region.stepper.settle_obligations'),
    'finance.rent_arrears': ('tile', 'local_currency', 'micro.region.stepper.active_rent_claims'),
    'finance.bank_loan': ('tile/agent', 'local_currency', 'econsim_trade_money.Bank.Borrow'),
    'finance.bank_loan_repayment': ('tile/agent', 'local_currency', 'econsim_trade_money.PayLoans'),
    'finance.bank_capital': ('tile', 'local_currency', 'econsim_trade_money.Bank'),
    'finance.bank_deposit_interest': ('tile', 'local_currency', 'econsim_trade_money.Bank.PayDepositInterest'),
    'ecology.soil_fertility': ('tile', 'ratio', 'externalities.step_tile_externalities'),
    'ecology.nutrition_density': ('tile', 'ratio', 'externalities.step_tile_externalities'),
    'ecology.pollution_air': ('tile', 'index', 'externalities.step_tile_externalities'),
    'ecology.pollution_water': ('tile', 'index', 'externalities.step_tile_externalities'),
    'ecology.pollution_soil': ('tile', 'index', 'externalities.step_tile_externalities'),
    'health.disease_cases': ('tile/disease', 'people', 'disease.step_medical_care'),
    'health.disease_incidence': ('tile/agent', 'cases', 'disease.step_agent_disease_onset'),
    'health.attrition': ('tile/agent', 'attrition_points', 'disease.step_agent_disease_onset'),
    'health.mortality_risk': ('tile/agent', 'probability', 'demographics_estate.handle_death'),
    'health.starvation_hazard': ('tile/agent', 'probability', 'demographics_estate.handle_death'),
    'health.medical_treatment': ('tile/agent/disease', 'treatment', 'disease.step_medical_care'),
    'health.medical_spending': ('tile', 'local_currency', 'disease.step_medical_care'),
    'health.untreated_cases': ('tile', 'cases', 'disease.step_medical_care'),
    'health.fatalities': ('tile', 'people', 'disease.step_medical_care'),
    'trade.balance': ('tile', 'local_currency_per_turn', 'sim_engine.step_turn'),
}

LEGACY_HISTORY_TO_METRIC = {
    'price_log': 'goods.price',
    'production_log': 'goods.production',
    'inventory_log': 'goods.producer_inventory',
    'demand_log': 'goods.demand',
    'supply_log': 'goods.supply',
    'sold_log': 'goods.sold',
    'gdp_log': 'economy.gdp_nominal',
    'cost_of_living_log': 'living.cost_of_living',
    'total_population': 'people.population',
    'protest_energy_log': 'politics.protest_energy',
    'unrest_log': 'politics.unrest_event',
    'grievance_sources_log': 'politics.grievance',
    'soil_fertility_log': 'ecology.soil_fertility',
    'nutrition_density_log': 'ecology.nutrition_density',
    'pollution_air_log': 'ecology.pollution_air',
    'pollution_water_log': 'ecology.pollution_water',
    'pollution_soil_log': 'ecology.pollution_soil',
    'migration_intent_log': 'people.migration_pressure',
    'disease_cases_log': 'health.disease_cases',
    'medical_spending_private_log': 'health.medical_spending',
    'medical_spending_public_log': 'health.medical_spending',
    'untreated_cases_log': 'health.untreated_cases',
    'disease_fatalities_log': 'health.fatalities',
    'rent_collected_log': 'finance.rent_collected',
    'rent_arrears_log': 'finance.rent_arrears',
}

TRACE_INSTRUMENTED = set(LEGACY_HISTORY_TO_METRIC.values()) | {
    'fx.bilateral_mid', 'politics.legitimacy',
}


def inventory_region_histories(region):
    """List all live legacy history fields, including those not yet explained."""
    rows = []
    for field in sorted(vars(region)):
        if field.endswith('_log') or field.endswith('_history') or field in LEGACY_HISTORY_TO_METRIC:
            metric_id = LEGACY_HISTORY_TO_METRIC.get(field)
            rows.append({'field': field, 'metric_id': metric_id,
                         'coverage': 'instrumented' if metric_id in TRACE_INSTRUMENTED
                         else 'untraced'})
    return rows


def protest_band(energy):
    value = float(energy)
    if value >= 9.5:
        return 'Takeover'
    if value >= 8:
        return 'Compromise'
    if value >= 6.5:
        return 'Mob/Riot'
    if value >= 4:
        return 'Protest'
    if value >= 2:
        return 'Unrest'
    return 'Calm'


def grievance_breakdown(tiles):
    """Sum observed raw source scores, then derive six display shares."""
    raw = {}
    for tile in tiles:
        history = getattr(tile, 'grievance_sources_log', ())
        if not history:
            continue
        for key, value in history[-1].get('raw', {}).items():
            raw[key] = raw.get(key, 0.0) + float(value)
    grouped = {
        'overwork': raw.get('overworked', 0.0),
        'enclosure': raw.get('rent_enclosure', 0.0),
        'hunger': raw.get('hunger', 0.0),
        'strikes': (raw.get('labor_resistance', 0.0)
                    + raw.get('wage_inflation', 0.0)
                    + raw.get('wage_suppression', 0.0)),
        'state': raw.get('tax', 0.0) + raw.get('repression', 0.0),
        'inequality': raw.get('inequality', 0.0) + raw.get('unemployment', 0.0),
    }
    total = sum(grouped.values())
    return {key: (100.0 * value / total if total else 0.0)
            for key, value in grouped.items()}
