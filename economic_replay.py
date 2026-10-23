"""Independent arithmetic replay for recorded economic and social transitions.

These functions validate the transition conditional on its captured inputs.
Input provenance is checked separately; an arithmetic match is not proof that
an unlinked input was itself measured correctly.
"""
import math


def clamp(value, low, high):
    return max(low, min(high, value))


def replay(row):
    formula=row.get('formula_id');i=row.get('inputs') or {};before=row.get('value_before')
    if formula=='bank.cash_to_deposit.v1':
        return i['deposit_before']+max(0.0,i['requested_amount'])
    if formula=='bank.deposit_to_cash.v1':
        ceiling=i['deposit_before']
        if i['bank_frozen']:ceiling=min(ceiling,i['frozen_withdrawal_cap'])
        return i['deposit_before']-clamp(i['requested_amount'],0.0,ceiling)
    if formula=='fx.trader_float.funded.v1':
        return i['trader_wallet_before']+i['home_amount']/i['rate_home_per_foreign']
    if formula=='forex.bank_conversion.v1':
        rate=i['rate_home_per_foreign']
        if i['direction']=='sell_foreign':
            settled=min(i['requested_foreign'],i['trader_fx_before'])
            if settled*rate>max(0.0,i['bank_fx_pool_before']):
                settled=max(0.0,i['bank_fx_pool_before'])/rate if rate>0 else 0
            return i['trader_fx_before']-max(0,settled)
        settled=min(i['requested_foreign'],i['bank_foreign_reserves_before'])
        if i['trader_cash_before']<settled*rate:
            settled=i['trader_cash_before']/rate if rate>0 else 0
        return i['trader_fx_before']+max(0,settled)
    if formula=='forex.reserve_ppp.v1':
        if i['regime']=='fixed':return 1.0
        ratio=i['partner_reserves']/i['target_reserves'] if i['target_reserves']>0 else 1.0
        pressure=clamp(i['adjustment_speed']*(1/max(0.05,ratio)-1),-0.02,0.02)
        result=before*math.exp(pressure)
        if i['ppp_target']>0:result*=math.exp(0.005*math.log(i['ppp_target']/max(0.01,before)))
        return clamp(result,*row['constraints']['band'])
    if formula=='military.border_vulnerability.v1':
        return min(1.0,i['hostile_adjacent_strength']/max(i['denominator_floor'],i['local_strength']+i['local_strength_buffer']))
    if formula=='commons.forage_activity.v1':return min(0.25,i['food_units']/16.0)
    if formula=='production.independent.v1':
        return int(round(i['base_production']*i['terrain_multiplier']*i['tenure_multiplier'])) if i['draw']<i['success_probability'] else 0
    if formula=='feudal_tribute.inventory_share_transfer.v1':
        payer=i['transfer_contract']['payer_account']
        return int(max(0,payer['balance_before']-i['protected_food_reserve'])*i['tribute_rate'])
    if formula=='feudal_tribute.reference_valuation.v1':return sum(v['quantity']*v['reference_price'] for v in i['valuations'])
    if formula=='market.clear_plus_public_buyers.v1':return i['private_units']+i['charity_units']+i['government_units']
    if formula=='gdp.sum_output_times_reference_price.v1':return sum(v['units']*v['reference_price'] for v in i['goods'].values())
    if formula=='inventory.sum_producer_holdings.v1':return sum(v['units'] for v in i['holdings'])
    if formula=='population.sum_hungry_output_groups.v1':return sum(i['group_counts'][g] for g in i['included_groups'])
    if formula=='population.sum_professions.v1':return sum(i['by_profession'].values())
    if formula=='social_class.group_population.v1':return sum(i['member_class_counts'][g] for g in i['member_classes'])
    if formula=='food.source_total.v1':return sum(v['food_units'] for v in i['agent_food_units'])
    if formula=='population.resident_census_bridge.v1':
        counts={name:len(entries) for name,entries in i['flows'].items()}
        return before+sum(counts.get(k,0) for k in ('arrivals','births','external_entries','role_conversions_in'))-sum(counts.get(k,0) for k in ('departures','deaths','role_conversions_out','unknown_exits'))
    if formula=='production.sum_receipts.v1':return sum(v['units'] for v in i['producer_receipts'])+i['granary_release_units']+i['wool_from_pasture']
    if formula=='production.independent_zero.v1':
        reason=i['reason']
        if ((reason=='production_random_draw_failed' and i['draw']>=i['success_probability'])
                or (reason=='input_material_unavailable' and not i['inputs_available'])
                or (reason=='nonpositive_recipe_output' and i['recipe_production']<=0)):
            return 0
        return NotImplemented
    if formula=='mortality.age_wealth_crowding_health.v1':
        result=i['age_base_probability']*i['wealth_discount']*i['crowding_factor']
        if i['health_attrition']>0:result*=1+min(3.0,i['health_attrition']*1.5)
        diseases=i['active_diseases']
        if 'pestilence' in diseases:result=max(result,min(0.65,0.35*(1+0.35*i['hungry_steps'])))
        elif diseases:result*=1+min(4.0,0.45*len(diseases))
        return result
    if formula=='medicine.regional_spending.v1':return i['private_spending']+i['public_spending']
    if formula=='disease.count_active_cases.v1':return len(i['case_agent_ids'])
    if formula=='government.income_components.v1':return sum(i['components'].values())
    if formula=='trade.sum_partner_values_in_home_currency.v1':return sum(sum(g['value'] for g in v['goods'])*v['conversion_rate_to_home'] for v in i['partner_settlements'])
    if formula=='trade.sum_market_import_values_in_home_currency.v1':return sum(v['value'] for v in i['goods'])
    if formula=='trade.export_minus_import_value.v1':return i['export_value_home_currency']-i['import_value_home_currency']
    if formula=='labor.weighted_average_shift_hours.v1':
        workers=sum(v['worker_count'] for v in i['firms'])
        return sum(v['weight']*v['shift_hours'] for v in i['firms'])/workers if workers else i['empty_value']
    if formula=='labor.count_active_strikers.v1':return len(i['striking_agent_ids'])
    if formula=='labor.workforce_availability.v1':return sum(v['effective_hours'] for v in i['worker_hours'])
    if formula=='labor.round_robin_emergency_cohort.v1':return len(set(i['active_cohort_agent_ids'])|{v['agent_id'] for v in i['emergency_agent_reasons']})
    if formula=='tenure.commons_access_from_plots.v1':
        if not i['plots']:return i['no_plot_default']
        return min(i['upper_bound'],sum(p['fraction']*i[p['tenure']+'_weight'] for p in i['plots']))
    if formula=='regime.legitimacy_target_drift.v1':return clamp(before+(i['target']-before)*i['drift_rate'],0.0,1.0)
    if formula=='diplomacy.ideology_trade_treaty_memory.v1':
        return clamp(before+i['ideology_drift']+i['trade_drift']+i['active_treaty_drift']+i['betrayal_drift'],-1.0,1.0)
    if formula=='migration.pressure_gate.v1':return 0.5*i['wage_distress_term']+i['food_price_differential']*(0.5+i['risk_tolerance_average'])
    if formula=='factions.grievance_sources.v1':return sum(i['raw_sources'].values())
    if formula=='factions.protest_energy.v1':
        additions=list(i['faction_additions'].values())
        return max(0.0,min(10.0,(sum(additions)/len(additions) if additions else 0.0)*2.0))
    if formula=='nutrition.intake_and_reserve.v1':return max(0.0,i['effective_calorie_need_kcal']-i['eaten_food_units']*i['calories_per_food_unit'])
    if formula=='disease.compound_wear.v1':return min(i['wear_cap'],before+0.025*len(i['active_diseases'])+(0.08 if 'pestilence' in i['active_diseases'] else 0.0))
    if formula=='medicine.cure_chance.v1':return 0 if i['cure_draw']<i['effective_cure_chance'] else 1
    if formula=='disease.exposure_risk.v1':return before+sum(1 for check in i['risk_checks'].values() if check['draw']<check['capped_risk'])
    if formula=='health.untreated_case_rollup.v1':return len(i['untreated_patients'])
    if formula=='ecology.downstream_advection.v1':return min(100.0,before+(i['source_pollution_before_emission']+i['source_emission'])*i['advection_fraction']/i['downstream_tile_count'])
    if formula=='ecology.soil_balance.v1':return clamp(before+i['regeneration_rate']-i['extraction_rate'],row['constraints']['lower_bound'],row['constraints']['upper_bound'])
    if formula=='ecology.nutrition_transition.v1':return before+(i['target_density']-before)*i['blend_fraction']
    if formula=='ecology.air_emissions_dispersion.v1':return clamp(before*(1-i['dispersion_fraction'])+i['raw_emission_after_controls'],0.0,100.0)
    if formula=='ecology.water_emissions_advection.v1':return clamp(before*(1-i['dispersion_fraction'])+i['raw_emission']-i['downstream_advection'],0.0,100.0)
    if formula=='ecology.soil_toxins_biodegradation.v1':return clamp(before*(1-i['biodegradation_fraction'])+i['raw_soil_emission'],0.0,100.0)
    if formula=='government.food_aid_recipient_transfer.v1':return i['recipient_food_before']+i['units']
    if formula=='charity.food_distribution_transfer.v1':return min(1,i['charity_inventory_before'])
    if formula=='charity.food_aid_allocation.v1':return min(i['food_inventory_before'],len(i['selected_hungry_ids'])+i['young_candidates'])
    if formula=='gini.retain_previous_value.v1':return i['previous_gini']
    return NotImplemented
