"""Definitions and provenance for metrics exposed by the simulation.

Unknown legacy histories are inventoried as unexplained rather than assigned
an invented calculation. Chart rounding happens after these definitions.
"""

from __future__ import annotations


METRICS = {
    'goods.price': ('tile/simulation/good', 'local_currency_per_unit', 'displayed recipe reference price; region_market and econsim_trade_money price writers'),
    'goods.national_reference_price': ('nation/good', 'mean_local_currency_per_unit', 'trace_snapshots.sample mean across territories with a recorded reference price; no currency conversion'),
    'goods.national_food_price': ('nation/good', 'mean_local_currency_per_unit', 'sim_server._record_history food_price mean, with explicit territory coverage'),
    'goods.seller_ask': ('tile/good/seller', 'local_currency_per_unit', 'posted offer at evaluation'),
    'goods.delivered_quote': ('tile/good/buyer/seller', 'local_currency_per_unit', 'offer including delivery costs'),
    'goods.transaction_price': ('tile/good/buyer/seller', 'local_currency_per_unit', 'paid settlement price'),
    'goods.transaction_vwap': ('tile/good', 'local_currency_per_unit', 'quantity-weighted mean of paid settlements'),
    'goods.production': ('tile/good', 'units_per_turn', 'region_production.produce'),
    'goods.producer_inventory': ('tile/good', 'units', 'micro.region.stepper.log_metrics'),
    'goods.demand': ('tile/good', 'units_offered', 'region_market.trade'),
    'goods.demand_ratio': ('tile/good', 'ratio', 'region_market.trade order totals'),
    'goods.supply': ('tile/good', 'units_offered', 'region_market.trade'),
    'goods.buyer_bid_quantity': ('tile/good/buyer', 'units', 'region_market.trade submitted orders; positive bids and charter restrictions'),
    'goods.seller_offer_quantity': ('tile/good/seller', 'units', 'region_market.trade submitted local offers; positive offers'),
    'goods.zero_order_count': ('tile/good', 'orders', 'region_market.trade; zero bid and offer reason summary'),
    'goods.sold': ('tile/good', 'units', 'region_market.trade'),
    'goods.food_aid': ('tile/government', 'units', 'government.Government.provide_food_aid'),
    'goods.food_entitlement_transfer': ('tile/giver/recipient', 'food_units', 'scenario_projects.advance_grain_entitlement'),
    'living.cost_of_living': ('tile/nation', 'local_currency_per_basket', 'micro.region.stepper.step_economy and trace_snapshots national aggregation'),
    'people.population': ('tile/nation', 'people', 'sum of profession-coded agent counts and traders in micro.region.stepper.log_metrics'),
    'people.profession_population': ('tile/nation/profession', 'people', 'micro.region.stepper.log_metrics'),
    'people.residents': ('tile/nation', 'people', 'trace_snapshots resident census bridge'),
    'people.deaths': ('tile/agent or nation', 'people_per_turn', 'person_death.record_person_death'),
    'people.births': ('tile', 'people_per_turn', 'demographics_reproduction.handle_reproduction'),
    'people.role': ('tile/agent', 'role', 'construction_politics.find_or_emerge_contractor and region_labor.borrow_or_layoff'),
    'people.hungry': ('tile', 'people', 'micro.region.stepper.log_metrics'),
    'people.food_security': ('tile', 'residents', 'food_security.diagnose_tile'),
    'people.migration_pressure': ('tile', 'score', 'region_logistics.migration_intent_components'),
    'people.migration': ('tile', 'people', 'migration.run_migrations'),
    'people.migration_in': ('tile', 'people', 'migration.run_migrations'),
    'economy.gdp_nominal': ('tile', 'local_currency_per_turn', 'micro.region.stepper.log_gdp'),
    'economy.cash': ('tile', 'local_currency', 'micro.region.stepper.log_metrics'),
    'economy.gini': ('tile/cohort', 'ratio', 'micro.region.stepper.log_metrics'),
    'labor.exploitation_rate': ('tile', 'ratio', 'labor_contract.aggregate_tile_surplus'),
    'labor.strikers': ('tile', 'people', 'labor_resistance.step_workplace_resistance'),
    'labor.available_worker_hours': ('tile/firm', 'hours', 'labor_resistance.record_workforce_availability before production'),
    'labor.hiring_decision': ('tile/firm/worker', 'accepted', 'region_labor.hire_workers'),
    'labor.occupation_change': ('tile/worker', 'occupation', 'labor_choice.apply_career_switch'),
    'labor.status_change': ('tile/worker', 'status', 'labor_choice.record_labor_status'),
    'labor.temporary_activity': ('tile/worker', 'turn_share', 'foraging.forage_tile'),
    'labor.offer_options': ('tile/worker', 'decision', 'economy.labor_mobility.LaborMobilityScheduler'),
    'labor.livelihood_options': ('tile/worker', 'decision', 'economy.labor_mobility.LaborMobilityScheduler'),
    'labor.primary_livelihood': ('tile/livelihood', 'adults', 'trace_snapshots.sample'),
    'labor.employment_status': ('tile/status', 'adults', 'trace_snapshots.sample'),
    'labor.hungry_adults': ('tile', 'adults', 'trace_snapshots.sample'),
    'labor.temporary_work_share': ('tile', 'adult_turn_share', 'trace_snapshots.sample'),
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
    'politics.unrest_level': ('tile', 'ratio', 'scenario_political_economy.apply_action'),
    'politics.unrest_event': ('tile', 'category', 'unrest.step_unrest'),
    'politics.legitimacy': ('nation', 'ratio', 'regime.track_legitimacy'),
    'politics.faction_loyalty': ('tile/faction', 'ratio', 'banking_policy.enact_deposit_bailin_haircut'),
    'fx.bilateral_mid': ('tile/partner', 'home_currency_per_foreign_currency', 'forex.ForexDesk.update'),
    'finance.treasury': ('nation', 'local_currency', 'nation.Nation.treasury'),
    'finance.sovereign_bond': ('nation', 'local_currency', 'sovereign_bonds.SovereignBondMarket'),
    'finance.treasury_flow': ('nation', 'signed_local_currency', 'sovereign_bonds.SovereignBondMarket and treasury operations'),
    'finance.occupation_transfer': ('nation/operation', 'local_currency', 'scenario_occupation.intercept_revenue and occupation settlements'),
    'finance.canal_toll': ('nation_pair/operation', 'payer_currency', 'scenario_geography.move_fleet'),
    'military.fleet_position': ('nation/fleet', 'site', 'scenario_geography.move_fleet'),
    'finance.tribute_value': ('tile', 'local_currency', 'feudal_tribute.record_tribute_value'),
    'finance.cash_transfer': ('tile/operation', 'local_currency', 'finance_trace.emit_cash_transfer'),
    'finance.cash_creation': ('project/contractor', 'local_currency', 'sovereign_bonds.SovereignBondMarket municipal sewer credit; source debit not modelled'),
    'finance.internal_transfer': ('nation/tile', 'local_currency', 'food_security.enact_nation_food_response'),
    'finance.operator_fee': ('tile/agent', 'local_currency', 'economy.capitalist_planner.EliteCapitalistPlanner'),
    'labor.subsistence_exit': ('tile/agent', 'worker', 'economy.labor_mobility.LaborMobilityScheduler'),
    'goods.emergency_levy': ('tile/government', 'units', 'government.Government._levy_emergency_food'),
    'goods.feudal_tribute': ('tile/serf/lord/good', 'units', 'feudal_tribute.collect_tribute'),
    'goods.grain_transfer': ('tile/operation', 'food_units', 'scenario_political_economy grain movement'),
    'goods.provincial_relief': ('province/tile', 'units', 'food_logistics.dispatch_province_food'),
    'land.customary_inheritance': ('tile/agent', 'right', 'livelihood_access.inherit_customary_access'),
    'land.use_right_transfer': ('tile/plot', 'tenant_ids', 'scenario_political_economy._foreclose'),
    'land.tax_foreclosure': ('tile/plot/agent', 'foreclosure_events', 'scenario_political_economy._foreclose'),
    'finance.obligation_balance': ('tile or nation/obligation', 'local_currency', 'livelihood_access.settle_obligations and scenario_debt'),
    'finance.obligation_payment': ('tile/origin', 'local_currency', 'livelihood_access.settle_obligations'),
    'finance.rent_collected': ('tile', 'local_currency', 'micro.region.stepper.settle_obligations'),
    'finance.rent_arrears': ('tile', 'local_currency', 'micro.region.stepper.active_rent_claims'),
    'finance.bank_loan': ('tile/agent', 'local_currency', 'econsim_trade_money.Bank.Borrow'),
    'finance.bank_loan_repayment': ('tile/agent', 'local_currency', 'econsim_trade_money.PayLoans'),
    'finance.bank_capital': ('tile', 'local_currency', 'econsim_trade_money.Bank'),
    'finance.bank_bailin_transfer': ('tile/depositor', 'local_currency', 'econsim_trade_money.Bank.apply_bail_in_haircut'),
    'finance.bank_equity': ('tile', 'local_currency', 'econsim_trade_money.Bank.equity'),
    'finance.bank_deposits': ('tile', 'local_currency', 'econsim_trade_money.Bank.total_deposits'),
    'finance.bank_liabilities': ('tile', 'local_currency', 'econsim_trade_money.Bank.total_liabilities'),
    'finance.bank_bond_writeoff': ('tile/bond', 'local_currency', 'econsim_trade_money.Bank.write_down_bonds'),
    'finance.bank_cumulative_writedowns': ('tile', 'local_currency', 'econsim_trade_money.Bank.cumulative_writedowns'),
    'finance.company_debt_writeoff': ('tile/worker/creditor', 'local_currency', 'labor_politics.enact_anti_truck_act'),
    'finance.tax_arrears_writeoff': ('tile/household/government', 'local_currency', 'scenario_political_economy.apply_action'),
    'finance.tax_arrears_balance': ('tile/agent', 'local_currency', 'scenario_political_economy._assess_arrears and _foreclose'),
    'finance.tax_foreclosure_risk': ('tile/agent', 'probability', 'scenario_political_economy._assess_arrears'),
    'finance.obligation_writeoff': ('tile/debtor/creditor', 'local_currency', 'livelihood_access.cancel_obligation'),
    'finance.bank_debt_inheritance': ('tile/agent', 'local_currency', 'demographics_estate.handle_debt_inheritance'),
    'finance.bank_debt_writeoff': ('tile/agent', 'local_currency', 'demographics_estate.forgive_bad_debt'),
    'finance.bank_debt_bailin': ('tile/depositor', 'local_currency', 'demographics_estate.forgive_bad_debt'),
    'finance.foreign_wallet_debt_payment': ('tile/agent', 'currency', 'demographics_estate.handle_debt_inheritance'),
    'finance.foreign_wallet_inheritance': ('tile/agent', 'currency', 'demographics_estate.handle_wealth_inheritance'),
    'finance.foreign_wallet_escheat': ('tile/agent', 'currency', 'demographics_estate.handle_wealth_inheritance'),
    'finance.bank_recapitalization': ('tile', 'local_currency', 'demographics_estate.recapitalize'),
    'finance.bank_deposit_interest': ('tile', 'local_currency', 'econsim_trade_money.Bank.PayDepositInterest'),
    'finance.bank_deposit': ('tile/bank/agent', 'local_currency', 'econsim_trade_money.Bank.Deposit'),
    'finance.bank_withdrawal': ('tile/bank/agent', 'local_currency', 'econsim_trade_money.Bank.Withdraw'),
    'finance.wage_arrears': ('tile/firm/worker', 'local_currency', 'region_finance.pay_wages'),
    'finance.frontier_expedition': ('frontier/treasury/pioneer', 'currency', 'frontier_policies.launch_frontier_expedition'),
    'finance.owner_transfer': ('tile/firm/owner', 'currency', 'region_finance._record_owner_payment and _record_owner_funding'),
    'finance.election_campaign': ('tile/treasury/candidate', 'currency', 'election.campaign_finance'),
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
    'health.infant_fatalities': ('tile', 'people_per_turn', 'demographics_reproduction.handle_reproduction'),
    'health.trade_contagion': ('tile/route', 'state', 'disease.step_trade_epidemic_transmission'),
    'health.trade_infection': ('tile/agent', 'cases', 'disease.step_trade_epidemic_transmission'),
    'trade.balance': ('tile', 'local_currency_per_turn', 'sim_engine.step_turn'),
    'trade.wilderness_settlement': ('trader/homesteader', 'currency', 'trade_settle.settle_wilderness'),
    'trade.wilderness_goods': ('wilderness/trader/homesteader', 'units', 'trade_settle.settle_wilderness'),
    'trade.market_seller_settlement': ('agent/tile/counterparty', 'currency', 'region_market.clear_discriminatory'),
    'trade.away_trader_food_purchase': ('trader/seller/tile', 'currency', 'world_trade.settle_trade'),
    'trade.fx_order_match': ('tile/fx_desk/trader', 'home_currency', 'forex.ForexDesk.clear_book'),
    'trade.fx_trader_float': ('tile/trader', 'foreign_currency', 'forex.seed_trader_wallet'),
    'finance.cash_wallet_conversion': ('tile/agent', 'currency', 'forex.walletize and forex.decash_wallet'),
    'finance.crop_lien_settlement': ('tile/crop_lien', 'local_currency', 'crop_credit.settle_crop_liens'),
    'land.crop_share': ('tile/tenancy', 'units', 'crop_credit.settle_crop_shares'),
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
    'infant_fatalities_log': 'health.infant_fatalities',
    'rent_collected_log': 'finance.rent_collected',
    'rent_arrears_log': 'finance.rent_arrears',
    'tribute_collected_log': 'finance.tribute_value',
}

TRACE_INSTRUMENTED = set(LEGACY_HISTORY_TO_METRIC.values()) | {
    'fx.bilateral_mid', 'politics.legitimacy', 'people.births', 'people.residents',
    'people.profession_population',
    'finance.sovereign_bond', 'finance.treasury_flow', 'finance.cash_creation',
    'finance.cash_transfer', 'goods.grain_transfer',
    'finance.occupation_transfer', 'finance.canal_toll', 'military.fleet_position',
    'finance.tribute_value', 'goods.feudal_tribute',
    'finance.tax_arrears_balance', 'finance.tax_foreclosure_risk',
    'land.use_right_transfer', 'land.tax_foreclosure',
    'finance.bank_bailin_transfer', 'finance.bank_debt_bailin',
    'finance.bank_debt_writeoff', 'finance.bank_recapitalization',
    'politics.faction_loyalty',
    'people.deaths',
    'people.role',
    'politics.unrest_level',
    'health.trade_contagion', 'health.trade_infection',
    'goods.food_aid', 'goods.food_entitlement_transfer', 'people.food_security',
    'labor.occupation_change',
    'labor.status_change', 'labor.temporary_activity',
    'labor.offer_options', 'labor.livelihood_options',
    'labor.primary_livelihood', 'labor.employment_status',
    'labor.hungry_adults', 'labor.temporary_work_share',
    'finance.internal_transfer', 'finance.operator_fee', 'labor.subsistence_exit',
    'goods.emergency_levy', 'goods.provincial_relief', 'land.customary_inheritance',
    'goods.demand_ratio', 'goods.buyer_bid_quantity', 'goods.seller_offer_quantity',
    'goods.zero_order_count',
    'goods.national_reference_price',
    'goods.national_food_price',
    'labor.strikers', 'labor.available_worker_hours',
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
        'state': raw.get('tax', 0.0) + raw.get('grain_levy', 0.0)
                 + raw.get('repression', 0.0),
        'inequality': raw.get('inequality', 0.0) + raw.get('unemployment', 0.0),
    }
    total = sum(grouped.values())
    return {key: (100.0 * value / total if total else 0.0)
            for key, value in grouped.items()}
