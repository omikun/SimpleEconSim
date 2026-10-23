"""Replay effects must use primitive inputs rather than recorded results."""
import copy
import unittest
from price_trace import replay_event


class EconomicReplayTests(unittest.TestCase):
    def test_fractional_charity_stock_uses_native_whole_unit_issue_gate(self):
        row={'formula_id':'charity.food_distribution_transfer.v1','value_after':1,
             'inputs':{'charity_inventory_before':.5,'charity_inventory_after':-.5}}
        self.assertTrue(replay_event(row)['matches'])
        total={'formula_id':'charity.food_aid_allocation.v1','value_after':2,
               'inputs':{'food_inventory_before':1.5,'selected_hungry_ids':['one'],'young_candidates':2}}
        self.assertTrue(replay_event(total)['matches'])

    def test_emergency_foraging_share_is_distinct_from_normal_yield(self):
        row={'formula_id':'commons.forage_activity.v1','value_after':.05,
             'inputs':{'food_units':1,'emergency_fallback':True,'emergency_turn_share':.05}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['emergency_fallback']=False
        self.assertFalse(replay_event(row)['matches'])

    def test_water_uses_capacity_and_weather_instead_of_recorded_availability(self):
        row={'formula_id':'water.capacity_rainfall_maintenance.v1','value_after':3,
             'inputs':{'capacity':10,'rainfall':.5,'canal_condition':.6,'available':900}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['rainfall']=1
        self.assertFalse(replay_event(row)['matches'])

    def test_construction_uses_delivered_materials_and_workers(self):
        row={'formula_id':'construction.material_labor_progress.v1','value_before':0,'value_after':12.5,
             'inputs':{'required_materials':{'wood':10},'delivered_materials':{'wood':5},
                       'navvy_ids':[1,2],'required_workers':2,'total_turns':4,
                       'base_progress':999,'resource_factor':999,'labor_factor':999}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['delivered_materials']['wood']=10
        self.assertFalse(replay_event(row)['matches'])

    def test_wage_pressure_replays_strict_cash_gate_and_cap(self):
        row={'formula_id':'labor.tightness_mrpl_cash_policy.v1','value_before':2,'value_after':2.2,
             'inputs':{'labor_market_tightness':2,'reservation_wage':3,'vacancies':1,
                       'cash':100,'payroll':10,'mrpl_wage_ceiling':4,'wage_cap':None,
                       'worker_count':5,'food_price':1,'decision_reason':'untrusted_label'}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['cash']=11
        self.assertFalse(replay_event(row)['matches'])
        row['value_after']=1.5;row['inputs']['wage_cap']=1.5
        self.assertTrue(replay_event(row)['matches'])

    def test_consumption_replays_draw_without_trusting_claimed_quantity(self):
        row={'formula_id':'demographics.nonfood_consumption.v1','value_before':3,'value_after':2,
             'inputs':{'units_consumed':99,'consumption_components':[{'mechanism':'furniture_stochastic_wear',
                 'quantity':99,'stock_before':3,'random_draw':.01,'consumption_threshold':.066}]}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['consumption_components'][0]['random_draw']=.1
        self.assertFalse(replay_event(row)['matches'])

    def test_matching_sale_quantity_cannot_hide_wrong_good_or_missing_cause(self):
        from causal_contracts import validate
        row={'formula_id':'market.discriminatory_clear.v2','value_after':2,
             'subject':{'type':'tile','id':'A','good':'food'},'cause_event_ids':['sale'],
             'inputs':{'settled_sales':[{'event_id':'sale','quantity':2}]}}
        source={'kind':'paid_market_sale','value_after':2,'subject':dict(row['subject'])}
        self.assertTrue(replay_event(row)['matches'])
        self.assertTrue(validate(row,lambda _:source)['matches'])
        source['subject']['good']='wood'
        self.assertFalse(validate(row,lambda _:source)['matches'])
        source['subject']['good']='food';row['cause_event_ids']=[]
        self.assertFalse(validate(row,lambda _:source)['matches'])

    def test_frozen_withdrawal_uses_cap_and_ignores_claimed_settlement(self):
        row={'formula_id':'bank.deposit_to_cash.v1','value_after':45,
             'inputs':{'deposit_before':50,'requested_amount':40,'bank_frozen':True,
                       'frozen_withdrawal_cap':5,'settled_amount':40}}
        self.assertTrue(replay_event(row)['matches'])
        row['value_after']=10
        self.assertFalse(replay_event(row)['matches'])

    def test_tribute_protects_subsistence_and_does_not_trust_transfer_amount(self):
        row={'formula_id':'feudal_tribute.inventory_share_transfer.v1','value_after':3,
             'inputs':{'tribute_rate':0.5,'protected_food_reserve':4,
                       'transfer_contract':{'amount':100,'payer_account':{'balance_before':10}}}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['protected_food_reserve']=0
        self.assertFalse(replay_event(row)['matches'])

    def test_nutrition_applies_recorded_adapted_need(self):
        row={'formula_id':'nutrition.intake_and_reserve.v1','value_after':300,
             'inputs':{'effective_calorie_need_kcal':1300,'eaten_food_units':2,
                       'calories_per_food_unit':500,'calorie_deficit_after_kcal':999}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['effective_calorie_need_kcal']=2000
        self.assertFalse(replay_event(row)['matches'])

    def test_pollution_uses_opening_emission_and_advection(self):
        row={'formula_id':'ecology.water_emissions_advection.v1',
             'value_before':10,'value_after':10.8,
             'inputs':{'dispersion_fraction':0.12,'raw_emission':4,'downstream_advection':2}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['downstream_advection']=0
        self.assertFalse(replay_event(row)['matches'])

    def test_mortality_replays_plague_threshold(self):
        row={'formula_id':'mortality.age_wealth_crowding_health.v1','value_after':0.65,
             'inputs':{'age_base_probability':0.01,'wealth_discount':0.5,'crowding_factor':1,
                       'health_attrition':0,'active_diseases':['pestilence'],'hungry_steps':4}}
        self.assertTrue(replay_event(row)['matches'])
        row['inputs']['active_diseases']=[]
        self.assertFalse(replay_event(row)['matches'])

    def test_unknown_formula_stays_unsupported(self):
        self.assertIsNone(replay_event({'formula_id':'unimplemented.v1','value_after':7,'inputs':{'result':7}}))


if __name__=='__main__':unittest.main()
