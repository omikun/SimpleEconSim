"""Production, trade, wages, profit, and named claim settlement."""
import region_production as _prod
import region_market as _market
import region_finance as _fin
import region_logistics as _logistics
import foraging as _forage
import feudal_tribute as _tribute
from micro.region import disabled_phases


def run(region, t, flags):
    from micro.region.stepper import audit_cash
    from livelihood_access import settle_obligations
    # Workplace participation must be decided before food allocation and output.
    # Existing strike records are stored by firm ID and survive save/load.
    from labor_resistance import step_workplace_resistance
    res_info = (step_workplace_resistance(region, t) if flags.workplace_resistance
                else disabled_phases.workplace_resistance(region))
    region.strikers_log.append(res_info['strikers'])
    region.broken_machinery_log.append(res_info['broken_machinery'])
    region.sabotage_log.append(res_info['smashed_this_turn'])
    audit_cash(region, t, "resistance_done")

    # Inputs and real working-capital advances settle before work is committed.
    from production_policy import prepare_programs
    prepare_programs(region, t)
    if flags.local_market:
        _market.trade(region, t, defer_food_price=True)
    audit_cash(region, t, "inputs_and_business_sales_done")

    # Workers share one turn between production and local subsistence.
    from food_economy import prepare_work
    prepare_work(region, t, production_enabled=flags.production)
    region.food_foraged_this_turn = _forage.forage_tile(region, t) if flags.foraging else 0
    from work_allocation import finish as finish_work_plan
    finish_work_plan(region, t, production_enabled=flags.production)

    # Capital goods machinery depreciation (operational wear-and-tear)
    if flags.production:
        from economy import apply_machinery_depreciation
        apply_machinery_depreciation(region, t)

    # Production
    from collective_action import record_production
    from supply_rights import allocate_seasonal_water
    if getattr(region, 'water_allocation_turn', None) != t:
        allocate_seasonal_water(region, t)
    firm_inventory_before = {a.id: a.inv_get(a.output, 0) for a in region.agents
                             if a.alive and a.is_corporation}
    _prod.produce(region, t, enabled=flags.production)
    record_production(region, t, firm_inventory_before)
    audit_cash(region, t, "produce_done")

    # Feudal tribute: lords collect in-kind share of harvest from serfs
    if flags.feudal_tribute:
        tribute_data, tribute_event_ids = _tribute.collect_tribute(
            region, t, return_trace=True)
        tribute_val, _valuation_event_id = _tribute.record_tribute_value(
            region, t, tribute_data, cause_event_ids=tribute_event_ids)
    else:
        tribute_val = 0.0
    region.tribute_collected_log.append(tribute_val)

    # Crop liens and share tenancy claim only this turn's independently produced harvest.
    from crop_credit import settle_crop_liens, settle_crop_shares, settle_offtake_contracts
    if flags.crop_credit:
        settle_offtake_contracts(region, t)
        settle_crop_liens(region, t)
    if flags.crop_share_tenancy:
        settle_crop_shares(region, t)

    # Dispatch goods actually acquired in the input/business market.
    if flags.regional_trade:
        _logistics.post_exports_to_route(region)
    audit_cash(region, t, "trade_done")

    # Wages & Profits
    if flags.wages:
        from collective_action import record_payroll_and_review
        _fin.pay_wages(region, t)
        _fin.settle_wage_arrears(region, t)
        record_payroll_and_review(region, t, {})
        _fin.redeem_company_scrip(region, t)
    else:
        from micro.region.disabled_phases import defer_payroll_reviews
        defer_payroll_reviews(region, t)
    audit_cash(region, t, "wages_done")

    if flags.profits:
        _fin.distribute_profits(region, t)
    audit_cash(region, t, "profits_done")

    # Settle named claims after wages; receipts move debtor cash to the named creditor.
    obligation_settlement_trace_ids = {}
    obligation_payment_trace_ids = {}
    claim_events = settle_obligations(
        region, t,
        settlement_trace_event_ids_by_origin=obligation_settlement_trace_ids,
        payment_trace_event_ids_by_origin=obligation_payment_trace_ids)
    if flags.local_market:
        _market.food_after_payroll(region, t)
    from production_policy import settle_programs
    settle_programs(region, t)
    _prod.release_emergency_food(region, t)
    rent_coll = sum(e['paid'] for e in claim_events if e['origin'] == 'rent')
    rent_arr = sum(c.balance for c in getattr(region, 'cash_obligations', [])
                   if c.origin == 'rent' and c.status == 'active')
    region.rent_collected_log.append(rent_coll)
    region.rent_arrears_log.append(rent_arr)
    from run_trace import emit
    rent_settlements = [event for event in claim_events if event['origin'] == 'rent']
    emit(region, kind='rent_collection_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.rent_collected', unit='local_currency',
         after=rent_coll, formula_id='rent.obligation_settlement.v1',
         inputs={'paid_claims': rent_settlements,
                 'active_rent_arrears': rent_arr,
                 'active_rent_claim_count': sum(
                     1 for claim in getattr(region, 'cash_obligations', [])
                     if claim.origin == 'rent' and claim.status == 'active')},
         cause_event_ids=obligation_payment_trace_ids.get('rent'))
    emit(region, kind='rent_arrears_summary', record_class='calculation',
         subject={'type': 'tile', 'id': region.name},
         metric_id='finance.rent_arrears', unit='local_currency',
         after=rent_arr, formula_id='rent.active_obligations.v1',
         inputs={'active_rent_claims': [
             {'obligation_id': claim.id, 'debtor_id': claim.debtor_id,
              'creditor_id': claim.creditor_id, 'balance': claim.balance,
              'due_turn': claim.due_turn}
             for claim in getattr(region, 'cash_obligations', [])
             if claim.origin == 'rent' and claim.status == 'active']},
         cause_event_ids=obligation_settlement_trace_ids.get('rent'))
    tenure = getattr(region, 'tenure', None)
    pasture_plots = [
        {'plot_id': str(plot.plot_id), 'fraction': float(plot.fraction),
         'production_type': str(getattr(plot, 'production_type', 'arable'))}
        for plot in getattr(tenure, 'plots', ())]
    pasture_f = tenure.pasture_fraction if tenure else 0.0
    region.pasture_fraction_log.append(pasture_f)
    from run_trace import emit
    emit(region, kind='pasture_fraction_calculation',
         record_class='calculation', phase='local',
         subject={'type': 'tile', 'id': region.name},
         metric_id='land.pasture_fraction', unit='fraction_of_tile',
         before=(region.pasture_fraction_log[-2]
                 if len(region.pasture_fraction_log) > 1 else None),
         after=pasture_f, formula_id='land.pasture_fraction_from_plots.v1',
         inputs={'turn': int(t), 'plots': pasture_plots,
                 'included_plot_ids': [plot['plot_id'] for plot in pasture_plots
                                       if plot['production_type'] == 'pasture'],
                 'formula': 'sum plot fractions whose production type is pasture'})
    audit_cash(region, t, "rent_done")

    # Unpaid claims become named cases and cannot resolve until a later turn.
    from labor_cases import process_default_cases
    process_default_cases(region, t)

    # Migrate legacy survey claims; new claims are handled by the obligation ledger.
    from enclosure import step_enclosure_survey_debts
    survey_evs = step_enclosure_survey_debts(region, t)
    audit_cash(region, t, "survey_debts_done")
