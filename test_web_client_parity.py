import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_server.sim_server import SimServer
from sim_server.protocol import CommandMessage, CommandType


class TestWebClientParity(unittest.TestCase):
    def setUp(self):
        import random
        random.seed(4242)
        import diplomacy
        from diplomacy import DiplomacySystem
        diplomacy.diplomacy_instance = DiplomacySystem()
        import innovation
        from innovation import InnovationSystem
        innovation._INNOVATION_SYSTEM = InnovationSystem()
        self.sim = SimServer(seed=4242, terrain_seed=4242, nation_seed=4242)

    def test_macro_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('macro', w)
        macro = w['macro']
        self.assertIn('treasury_cash', macro)
        self.assertIn('population', macro)
        self.assertIn('gdp', macro)
        self.assertIn('unrest_energy', macro)
        self.assertIn('unrest_stage', macro)
        self.assertIn('gini', macro)
        self.assertIn('cost_of_living', macro)
        self.assertIn('trade_balance', macro)
        self.assertIn('tax_rate', macro)
        self.assertIn('tariff_rate', macro)
        self.assertIn('credit_rating', macro)

    def test_initial_trader_float_is_written_to_turn_zero_trace(self):
        seeded = [event for tile in self.sim.tiles
                  for event in getattr(tile, 'economic_events', [])
                  if event['kind'] == 'wallet_transfer_in'
                  and event.get('detail', {}).get('payment_kind')
                  == 'initial_trader_working_capital']
        self.assertGreater(len(seeded), 0)
        traces = [row for row in self.sim.run_trace.recent
                  if row.get('kind') == 'fx_trader_float_seeded']
        self.assertEqual(len(traces), len(seeded))
        wallet_event_ids = {event['id'] for event in seeded}
        self.assertEqual(
            {row['inputs']['wallet_event']['event_id'] for row in traces},
            wallet_event_ids)
        self.assertTrue(all(row['turn'] == 0 for row in traces))

    def test_history_series(self):
        # Step a few turns
        for _ in range(3):
            self.sim.step()
        w = self.sim.serialize_world()
        self.assertIn('history', w)
        hist = w['history']
        self.assertGreaterEqual(len(hist['turns']), 3)
        self.assertEqual(len(hist['turns']), len(hist['treasury']))
        self.assertEqual(len(hist['turns']), len(hist['gdp']))

    def test_tile_deep_inspection(self):
        inhabited = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) is not None][0]
        accounts = list(getattr(inhabited, 'actor_turn_accounts', []))
        accounts.append({
            'actor_id': -999, 'actor_name': 'Company debt relief test worker',
            'type': 'other', 'event_ids': [1], 'sales_cash': 0.0, 'crop_value': 0.0,
            'company_debt_written_off': 25.0, 'company_receivable_written_off': 0.0,
            'tax_arrears_written_off': 10.0, 'tax_receivable_written_off': 0.0,
            'bank_cash_deposited': 12.0, 'bank_cash_withdrawn': 5.0,
            'opening_wage_arrears_payable': 3.0,
            'closing_wage_arrears_payable': 4.0,
            'wage_arrears_accrued': 1.0,
            'wage_arrears_payable_written_off': 2.0,
            'wage_arrears_claim_inherited': 4.0,
            'opening_owner_loan': 8.0, 'closing_owner_loan': 5.0,
            'owner_loan_repaid': 3.0,
            'wallet_transfer_in_by_currency': {'USD': 12.0},
            'wallet_transfer_out_by_currency': {'GBP': 7.0},
        })
        inhabited.actor_turn_accounts = accounts
        data = self.sim.serialize_tile(inhabited, turn=self.sim.turn)
        self.assertIn('market_prices', data)
        self.assertIn('stockpiles', data)
        self.assertIn('buildings', data)
        self.assertIn('construction_projects', data)
        self.assertIn('ecology', data)
        self.assertIn('citizens', data)
        self.assertGreater(len(data['citizens']), 0)
        c0 = data['citizens'][0]
        self.assertIn('id', c0)
        self.assertIn('career', c0)
        self.assertIn('primary_livelihood', c0)
        self.assertIn('employment_status', c0)
        self.assertIn('cash', c0)
        counts = data['labor_institutions']['counts']
        self.assertIn('adult_residents', counts)
        self.assertIn('hungry_adults', counts)
        self.assertIn('livelihoods', data['labor_institutions'])
        self.assertIn('market_activity', data)
        self.assertIn('economic_actors', data)
        self.assertTrue(any(row['actor_id'] == -999 for row in data['actor_accounts']))
        account = next(row for row in data['actor_accounts'] if row['actor_id'] == -999)
        self.assertEqual(account['bank_cash_deposited'], 12.0)
        self.assertEqual(account['bank_cash_withdrawn'], 5.0)
        self.assertEqual(account['closing_wage_arrears_payable'], 4.0)
        self.assertEqual(account['wage_arrears_payable_written_off'], 2.0)
        self.assertEqual(account['wage_arrears_claim_inherited'], 4.0)
        self.assertEqual(account['closing_owner_loan'], 5.0)
        self.assertEqual(account['wallet_transfer_in_by_currency'], {'USD': 12.0})
        self.assertEqual(data['financial_institution']['type'], 'commercial_bank')
        self.assertIn('cumulative_bond_writeoffs', data['financial_institution'])
        self.assertIn('sovereign_bonds_held', data['financial_institution'])
        self.assertIn('water_rights', data['tenure'])
        self.assertIn('market_charters', data['tenure'])

    def test_player_can_review_market_charter_and_inspect_supply_controls(self):
        tile = next(t for t in self.sim.tiles
                    if getattr(t, 'owner_nation', None)
                    and t.owner_nation.name == self.sim.player_nation_name)
        sponsor = tile.agents[0]
        sponsor.cash = 100.0
        tile.recipes.setdefault(__import__('goods').Goods.cotton, {'price': 5.0})
        petition_result = self.sim.execute_command(CommandMessage(CommandType.PETITION_MARKET_CHARTER, {
            'tile': tile.name, 'sponsor_id': sponsor.id, 'good': 'cotton',
            'charter_type': 'exclusive_buying', 'fee': 10, 'term_turns': 5,
        }))
        self.assertTrue(petition_result['success'], petition_result)
        petition = petition_result['petition']
        self.assertTrue(petition['player_review'])
        resolution = self.sim.execute_command(CommandMessage(CommandType.RESOLVE_MARKET_CHARTER, {
            'tile': tile.name, 'petition_id': petition['id'], 'decision': 'approve',
        }))
        self.assertTrue(resolution['success'], resolution)
        self.assertTrue(any(c['status'] == 'active' for c in tile.market_charters))
        data = self.sim.serialize_tile(tile, turn=self.sim.turn)
        self.assertTrue(data['tenure']['market_charters'])

    def test_build_command(self):
        p_nat = self.sim.player_nation_name
        tile = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) and t.owner_nation.name == p_nat][0]
        res = self.sim.execute_command(CommandMessage(CommandType.BUILD_PROJECT, {
            'tile': tile.name, 'building': 'granary'
        }))
        self.assertTrue(res['success'], res)

    def test_policy_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.SET_POLICY, {
            'key': 'tax_rate', 'val': 0.25
        }))
        self.assertTrue(res['success'], res)
        p_nat = self.sim.player_nation_name
        nation = next(n for n in self.sim.nations if n.name == p_nat)
        self.assertEqual(nation.tax_rate, 0.25)

    def test_diplomacy_command(self):
        p_nat = self.sim.player_nation_name
        other = next(n.name for n in self.sim.nations if n.name != p_nat)
        res = self.sim.execute_command(CommandMessage(CommandType.DIPLOMATIC_ACTION, {
            'action': 'propose_trade', 'target': other
        }))
        self.assertTrue(res['success'], res)

    def test_bond_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.SOVEREIGN_BOND, {
            'action': 'issue_bond', 'amount': 1000, 'duration': 50
        }))
        self.assertTrue(res['success'], res)

    def test_science_command(self):
        res = self.sim.execute_command(CommandMessage(CommandType.RESEARCH_TECH, {
            'action': 'pledge_prize', 'tech_id': 'crop_rotation', 'amount': 300
        }))
        self.assertTrue(res['success'], res)

    def test_recruit_command(self):
        p_nat = self.sim.player_nation_name
        tile = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) and t.owner_nation.name == p_nat][0]
        res = self.sim.execute_command(CommandMessage(CommandType.RECRUIT_UNIT, {
            'tile': tile.name, 'soldiers': 10
        }))
        self.assertTrue(res['success'], res)

    def test_select_nation_command(self):
        target = self.sim.nations[1].name
        res = self.sim.execute_command(CommandMessage(CommandType.SELECT_NATION, {
            'nation': target
        }))
        self.assertTrue(res['success'], res)
        self.assertEqual(self.sim.player_nation_name, target)


    def test_charts_and_comparison_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('comparison_suite', w)
        cs = w['comparison_suite']
        self.assertIn('tab1_macro', cs)
        self.assertIn('tab2_goods', cs)
        self.assertIn('tab3_forex', cs)
        self.assertIn('tab4_extraction', cs)
        self.assertIn('tab5_protest', cs)
        self.assertIn('tab6_ecology', cs)

        # Verify tile chart series
        inhabited = [t for t in self.sim.tiles if getattr(t, 'owner_nation', None) is not None][0]
        data = self.sim.serialize_tile(inhabited, turn=self.sim.turn)
        self.assertIn('charts', data)
        charts = data['charts']
        self.assertIn('economic', charts)
        self.assertIn('ecological', charts)
        self.assertIn('labor', charts)
        self.assertIn('citizens', charts)

    def test_cadastre_actions(self):
        tile = [t for t in self.sim.tiles if getattr(t, 'tenure', None) and t.tenure.plots][0]
        plot = tile.tenure.plots[0]

        # Toggle land use
        res = self.sim.execute_command(CommandMessage(CommandType.CADASTRE_TOGGLE_LAND_USE, {
            'tile': tile.name, 'plot_id': plot.plot_id, 'production_type': 'pasture'
        }))
        self.assertTrue(res['success'], res)

        # Restore commons
        res = self.sim.execute_command(CommandMessage(CommandType.RESTORE_COMMONS, {
            'tile': tile.name, 'plot_id': plot.plot_id
        }))
        self.assertTrue(res['success'], res)

    def test_province_decree_command(self):
        prov = self.sim.nations[0].provinces[0]
        prov.gov.agent.cash = 500.0
        res = self.sim.execute_command(CommandMessage(CommandType.PROVINCE_DECREE, {
            'province': prov.name, 'decree': 'standardize_routes'
        }))
        self.assertTrue(res['success'], res)

    def test_labor_and_border_policies(self):
        res1 = self.sim.execute_command(CommandMessage(CommandType.SET_BORDER_POLICY, {
            'open_borders': False
        }))
        self.assertTrue(res1['success'], res1)

        res2 = self.sim.execute_command(CommandMessage(CommandType.SET_FACTORY_SAFETY, {
            'enabled': True
        }))
        self.assertTrue(res2['success'], res2)

        res3 = self.sim.execute_command(CommandMessage(CommandType.SET_TRUCK_ACT, {
            'enabled': True
        }))
        self.assertTrue(res3['success'], res3)


    def test_comparison_suite_drilldowns(self):
        w = self.sim.serialize_world()
        self.assertIn('comparison_suite', w)
        cs = w['comparison_suite']
        self.assertIn('tab1_macro', cs)
        self.assertIn('tab2_goods', cs)
        self.assertIn('tab3_forex', cs)
        self.assertIn('tab4_extraction', cs)
        self.assertIn('tab5_protest', cs)
        self.assertIn('tab6_ecology', cs)

        for tab_key in ['tab1_macro', 'tab2_goods', 'tab4_extraction', 'tab5_protest', 'tab6_ecology']:
            self.assertIn('by_country', cs[tab_key])
            self.assertIn('by_province', cs[tab_key])
            self.assertIn('by_tile', cs[tab_key])
            self.assertGreater(len(cs[tab_key]['by_country']), 0)
            self.assertGreater(len(cs[tab_key]['by_province']), 0)
            self.assertGreater(len(cs[tab_key]['by_tile']), 0)

        # Tab 3 FX Matrix & Banking
        self.assertIn('banking', cs['tab3_forex'])
        self.assertIn('fx_matrix', cs['tab3_forex'])
        self.assertGreater(len(cs['tab3_forex']['banking']), 0)
        self.assertGreater(len(cs['tab3_forex']['fx_matrix']), 0)
        for home_nation in self.sim.nations:
            for foreign_nation in self.sim.nations:
                home, foreign = home_nation.currency, foreign_nation.currency
                displayed = cs['tab3_forex']['fx_matrix'][home][foreign]
                if home == foreign:
                    self.assertEqual(displayed, 1.0)
                    continue
                quotes = [desk.mid for tile in home_nation.tiles
                          for desk in getattr(tile, 'forex_desks', {}).values()
                          if desk.home == home and desk.other == foreign]
                self.assertEqual(displayed, sum(quotes) / len(quotes) if quotes else None)

    def test_progress_suite_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('progress_suite', w)
        ps = w['progress_suite']
        self.assertIn('active_nation', ps)
        self.assertIn('all_nations', ps)
        self.assertIn('stalled_count', ps)

    def test_emergency_subsidy_command(self):
        p_nat = self.sim.player_nation_name
        nation = next(n for n in self.sim.nations if n.name == p_nat)
        tile = nation.tiles[0]

        # Build a project
        res_build = self.sim.execute_command(CommandMessage(CommandType.BUILD_PROJECT, {
            'tile': tile.name, 'building': 'barge_canal'
        }))
        self.assertTrue(res_build['success'])

        # Stall project and verify subsidy
        projs = getattr(tile, 'construction_projects', []) + getattr(nation, 'construction_projects', [])
        self.assertGreater(len(projs), 0)
        proj = projs[0]
        proj.status = 'stalled'
        proj.stall_reason = 'missing_materials'

        # Ensure nation government has cash
        if getattr(nation, 'government', None) and getattr(nation.government, 'agent', None):
            nation.government.agent.cash = 500.0

        res_sub = self.sim.execute_command(CommandMessage(CommandType.EMERGENCY_OVERRUN_SUBSIDY, {
            'project_id': proj.project_id, 'amount': 100.0
        }))
        self.assertTrue(res_sub['success'], res_sub)

    def test_seasonal_clock_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('seasonal_info', w)
        si = w['seasonal_info']
        self.assertIn('year', si)
        self.assertIn('turn_in_year', si)
        self.assertIn('name', si)
        self.assertIn('icon', si)
        self.assertIn('color', si)
        self.assertIn('phase_desc', si)
        self.assertIn('mult', si)
        self.assertIn('pct_delta', si)
        self.assertIn('granary_food', si)
        self.assertIn('buffer_turns', si)

    def test_trade_network_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('trade_network', w)
        tn = w['trade_network']
        self.assertIn('edges', tn)
        self.assertIn('flows', tn)
        self.assertGreater(len(tn['edges']), 0)
        e0 = tn['edges'][0]
        self.assertIn('from', e0)
        self.assertIn('to', e0)

    def test_scenario_pressures_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('scenario_info', w)
        si = w['scenario_info']
        self.assertIn('pressures', si)
        pressures = si['pressures']
        self.assertGreater(len(pressures), 0)
        p0 = pressures[0]
        self.assertIn('title', p0)
        self.assertIn('value', p0)
        self.assertIn('tone', p0)

    def test_tile_color_serialization(self):
        w = self.sim.serialize_world()
        self.assertIn('tiles', w)
        self.assertGreater(len(w['tiles']), 0)
        for tile_summary in w['tiles'][:20]:
            self.assertIn('color', tile_summary)
            color = tile_summary['color']
            self.assertIsNotNone(color)
            self.assertTrue(color.startswith('#'), f"Expected hex color, got {color}")
            self.assertEqual(len(color), 7)
            # Ensure not black or dark void
            self.assertNotEqual(color.lower(), '#000000')

        # Test deep tile serialization
        t0 = self.sim.tiles[0]
        deep = self.sim.serialize_tile(t0, turn=self.sim.turn)
        self.assertIn('color', deep)
        self.assertIsNotNone(deep['color'])
        self.assertTrue(deep['color'].startswith('#'))

    def test_web_static_directory_unification(self):
        root = os.path.dirname(os.path.abspath(__file__))
        web_client = os.path.join(root, 'web_client')
        client_static = os.path.join(root, 'client', 'web', 'static')
        self.assertTrue(os.path.isdir(web_client))
        self.assertTrue(os.path.isdir(client_static))
        self.assertEqual(os.path.realpath(web_client), os.path.realpath(client_static))


if __name__ == '__main__':
    unittest.main()
