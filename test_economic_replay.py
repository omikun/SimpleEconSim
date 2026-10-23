"""Replay effects must use primitive inputs rather than recorded results."""
import copy
import unittest
from price_trace import replay_event


class EconomicReplayTests(unittest.TestCase):
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
