"""Per-run gameplay gates and their disabled turn contracts."""

import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import ExitStack

from sim_server.protocol import CommandMessage, CommandType
from sim_server.sim_server import SimServer
from world_config import (
    FULL_GAMEPLAY_FLAGS, GAMEPLAY_FLAG_NAMES, GAMEPLAY_FLAGS_VERSION,
    describe_gameplay_flags, resolve_gameplay_flags,
)


class GameplayFlagsTests(unittest.TestCase):
    def test_profiles_resolve_dependency_closed_sets(self):
        full = resolve_gameplay_flags(profile='full')
        core = resolve_gameplay_flags(profile='core')
        forage = resolve_gameplay_flags(profile='isolate:foraging')
        epidemic = resolve_gameplay_flags(profile='isolate:trade_epidemic_spread')
        self.assertEqual(full, FULL_GAMEPLAY_FLAGS)
        self.assertFalse(any(core.as_dict().values()))
        self.assertEqual([name for name, on in forage.as_dict().items() if on], ['foraging'])
        self.assertEqual({name for name, on in epidemic.as_dict().items() if on},
                         {'trade_epidemic_spread', 'disease'})
        with self.assertRaisesRegex(ValueError, 'required'):
            resolve_gameplay_flags(profile='isolate:trade_epidemic_spread',
                                   disabled=('disease',))
        with self.assertRaises(ValueError):
            resolve_gameplay_flags(profile='isolate:missing')
        with self.assertRaises(ValueError):
            resolve_gameplay_flags(profile='full', base=core)
        self.assertIn('enabled: foraging', describe_gameplay_flags('isolate:foraging', forage))

    def test_scenario_defaults_are_central_and_isolates_can_override_them(self):
        full_scenario = resolve_gameplay_flags(
            scenario_id='labor_frontier_rivalry')
        isolated = resolve_gameplay_flags(
            profile='isolate:private_technology_adoption',
            scenario_id='labor_frontier_rivalry')
        for name in ('elite_planning', 'career_mobility', 'abundance',
                     'private_technology_adoption', 'wage_quotes'):
            self.assertFalse(getattr(full_scenario, name))
        self.assertTrue(isolated.private_technology_adoption)
        self.assertEqual(sum(isolated.as_dict().values()), 1)

    def test_core_profile_advances_with_all_optional_mechanisms_off(self):
        flags = resolve_gameplay_flags(profile='core')
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False, gameplay_flags=flags,
                           gameplay_profile='core')
        with patch('scenario_labor_frontier_rivalry.advance_after_engine') as scenario:
            with patch('terrain.wilderness.wilderness.forage',
                       side_effect=AssertionError('disabled wilderness foraging ran')) as forage:
                self.assertEqual(server.step(), 1)
        scenario.assert_not_called()
        forage.assert_not_called()
        self.assertFalse(server.violations)
        world = server.serialize_world(compact=True)
        self.assertEqual(world['gameplay_profile'], 'core')
        self.assertEqual(world['gameplay_flags'], flags.as_dict())
        self.assertEqual(world['gameplay_flags_version'], GAMEPLAY_FLAGS_VERSION)

    def test_isolated_wilderness_enables_its_declared_dependencies(self):
        flags = resolve_gameplay_flags(profile='isolate:wilderness')
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', trace_enabled=False,
                           gameplay_flags=flags, gameplay_profile='isolate:wilderness')
        with patch('terrain.wilderness.wilderness.forage', return_value=0) as forage:
            server.step()
        self.assertEqual(forage.call_count,
                         sum(bool(tile.wilderness) for tile in server.tiles))
        self.assertFalse(server.violations)

    def test_registry_preserves_full_defaults_and_rejects_typos(self):
        self.assertEqual(GAMEPLAY_FLAG_NAMES, set(FULL_GAMEPLAY_FLAGS.as_dict()))
        self.assertTrue(all(FULL_GAMEPLAY_FLAGS.as_dict().values()))
        flags = resolve_gameplay_flags(disabled=('disease',))
        self.assertFalse(flags.disease)
        self.assertFalse(flags.trade_epidemic_spread)
        self.assertTrue(flags.pollution)
        self.assertTrue(FULL_GAMEPLAY_FLAGS.disease)
        with self.assertRaises(ValueError):
            resolve_gameplay_flags(disabled=('unknown_mechanism',))
        with self.assertRaises(TypeError):
            type(FULL_GAMEPLAY_FLAGS)(nation_ai=1)

    def test_disabled_local_mechanisms_keep_turn_histories_aligned(self):
        disabled = ('pollution', 'disease', 'factions', 'unrest',
                    'innovation', 'imperialism', 'sovereign_bonds')
        flags = resolve_gameplay_flags(disabled=disabled)
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False, gameplay_flags=flags)
        self.assertEqual(server.step(), 1)
        self.assertFalse(server.violations)
        for tile in server.tiles:
            self.assertEqual(len(tile.pollution_air_log), 1)
            self.assertEqual(len(tile.disease_cases_log), 1)
            self.assertEqual(len(tile.protest_energy_log), 1)
            self.assertEqual(len(tile.unrest_log), 1)
            self.assertEqual(tile.protest_energy_log[-1], 0.0)
            self.assertEqual(tile.unrest_log[-1]['stage'], 'calm')
        state = server.serialize_world(compact=True)
        self.assertEqual(state['gameplay_flags_version'], GAMEPLAY_FLAGS_VERSION)
        self.assertEqual(state['gameplay_flags'], flags.as_dict())

    def test_disabled_bonds_reject_player_commands(self):
        server = SimServer(seed=4243, terrain_seed=4243, nation_seed=4243,
                           topology='hex', trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('sovereign_bonds',)))
        result = server.execute_command(CommandMessage(
            CommandType.SOVEREIGN_BOND, {'action': 'issue_bond'}))
        self.assertFalse(result['success'])
        self.assertIn('disabled', result['error'])

    def test_local_gates_skip_one_mechanism_at_a_time(self):
        targets = {
            'workplace_resistance': 'labor_resistance.step_workplace_resistance',
            'foraging': 'foraging.forage_tile',
            'feudal_tribute': 'feudal_tribute.collect_tribute',
            'workhouse': 'workhouse.step_workhouse',
            'alienation': 'alienation.step_tile_alienation',
            'pollution': 'externalities.step_tile_externalities',
            'disease': 'disease.step_tile_diseases',
            'factions': 'region_factions.step_factions',
            'unrest': 'unrest.step_unrest',
        }
        for name, target in targets.items():
            with self.subTest(mechanism=name):
                server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                                   topology='hex', scenario_id='labor_frontier_rivalry',
                                   trace_enabled=False,
                                   gameplay_flags=resolve_gameplay_flags(disabled=(name,)))
                with patch(target, side_effect=AssertionError(f'{name} ran')) as step:
                    server.step()
                    step.assert_not_called()
                self.assertFalse(server.violations)

    def test_world_gates_skip_one_mechanism_at_a_time(self):
        targets = {
            'construction_projects': 'construction_politics.step_construction_politics',
            'private_technology_adoption': 'technology_adoption.step_private_adoption',
            'national_food_logistics': 'food_logistics.prepare_food_relief',
            'trade_epidemic_spread': 'disease.step_trade_epidemic_transmission',
            'migration': 'sim_engine.run_migrations',
            'frontier_claims': 'sim_engine.check_and_apply_claims',
            'regime': 'sim_engine.step_regime',
            'military': 'sim_engine.step_armies',
            'wars': 'sim_engine.update_wars',
            'innovation': 'innovation.step_innovation',
        }
        for name, target in targets.items():
            with self.subTest(mechanism=name):
                server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                                   topology='hex', scenario_id='labor_frontier_rivalry',
                                   trace_enabled=False,
                                   gameplay_flags=resolve_gameplay_flags(disabled=(name,)))
                with patch(target, side_effect=AssertionError(f'{name} ran')) as step:
                    server.step()
                    step.assert_not_called()
                self.assertFalse(server.violations)

    def test_construction_gate_keeps_private_adoption_active(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_profile='full',
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('construction_projects',)))
        with patch('technology_adoption.step_private_adoption', return_value=[]) as adoption:
            server.step()
        adoption.assert_called_once()

    def test_existing_region_switches_obey_central_gates(self):
        from abundance import enabled as abundance_enabled
        from career_transitions import step_careers
        region = SimpleNamespace(abundance_enabled=True,
                                 scenario_owner_policy=False, wilderness=False,
                                 _gameplay_flags=resolve_gameplay_flags(
                                     disabled=('abundance', 'career_mobility')))
        self.assertFalse(abundance_enabled(region))
        result = step_careers(region, 1)
        self.assertTrue(result['disabled'])
        self.assertEqual(region.labor_scheduler_last_turn, 1)

    def test_elite_planning_gate_overrides_region_default(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('elite_planning',)))
        for tile in server.tiles:
            tile.owner_planning_enabled = True
        target = 'economy.capitalist_planner.EliteCapitalistPlanner.check_new_market_items'
        with patch(target, side_effect=AssertionError('planner ran')) as planning:
            server.step()
            planning.assert_not_called()

    def test_forex_gate_freezes_quotes_and_keeps_history_aligned(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(disabled=('forex',)))
        desks = {(region.name, name): desk for region in server.tiles
                 for name, desk in region.forex_desks.items()}
        before = {key: (desk.mid, len(desk.log)) for key, desk in desks.items()}
        with patch('sim_engine.fx.cycle_all_markets', side_effect=AssertionError('FX cycle ran')):
            with patch('forex.ForexDesk.update', side_effect=AssertionError('FX quote changed')):
                server.step()
        self.assertFalse(server.violations)
        for key, desk in desks.items():
            self.assertEqual(desk.mid, before[key][0])
            self.assertEqual(len(desk.log), before[key][1] + 1)

    def test_regional_trade_gate_freezes_cargo_and_records_zero_flow(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('regional_trade',)))
        targets = ('transporter.Route.advance', 'sim_engine.pending_imports',
                   'sim_engine.resolve_parked', 'trade_flow.settle_trade',
                   'region_logistics.repoint_traders',
                   'region_logistics.post_exports_to_route',
                   'sim_engine.settle_wilderness')
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError(
                    f'{target} ran while trade was disabled')))
            server.step()
        self.assertFalse(server.violations)
        for tile in server.tiles:
            self.assertEqual(tile.pending_imports, {})
            self.assertEqual(tile.export_value_log[-1], 0.0)
            self.assertEqual(tile.import_value_log[-1], 0.0)

    def test_land_rent_gate_freezes_existing_claims(self):
        from livelihood_access import assess_obligation, due_cash_for
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('land_rent',)))
        region = server.tiles[0]
        debtor, creditor = region.agents[:2]
        region._gameplay_flags = FULL_GAMEPLAY_FLAGS
        claim = assess_obligation(region, debtor.id, creditor.id,
                                  'rent', 5.0, 1, interest_rate=0.1)
        region._gameplay_flags = server.gameplay_flags
        self.assertEqual(due_cash_for(debtor.id, region, 1), 0.0)
        self.assertIsNone(assess_obligation(region, debtor.id, creditor.id,
                                            'rent', 2.0, 1))
        with patch('land_rent.assess_rents', side_effect=AssertionError('rent assessed')):
            server.step()
        self.assertEqual(claim.balance, 5.0)
        self.assertEqual(claim.status, 'active')
        self.assertEqual(region.rent_collected_log[-1], 0.0)

    def test_crop_credit_gate_keeps_share_tenancy_active(self):
        from livelihood_access import assess_obligation, due_cash_for
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('crop_credit',)))
        region = server.tiles[0]
        debtor, creditor = region.agents[:2]
        region._gameplay_flags = FULL_GAMEPLAY_FLAGS
        claim = assess_obligation(region, debtor.id, creditor.id,
                                  'advance', 5.0, 1, interest_rate=0.1)
        region._gameplay_flags = server.gameplay_flags
        self.assertEqual(due_cash_for(debtor.id, region, 1), 0.0)
        self.assertIsNone(assess_obligation(region, debtor.id, creditor.id,
                                            'advance', 2.0, 1))
        with patch('crop_credit.settle_crop_liens',
                   side_effect=AssertionError('lien settled')):
            with patch('crop_credit.settle_offtake_contracts',
                       side_effect=AssertionError('offtake settled')):
                with patch('crop_credit.settle_crop_shares', return_value=[]) as shares:
                    server.step()
        self.assertEqual(shares.call_count, len(server.tiles))
        shares.assert_any_call(region, 1)
        self.assertEqual(claim.balance, 5.0)
        self.assertEqual(claim.status, 'active')

    def test_crop_share_tenancy_gate_leaves_credit_available(self):
        from crop_credit import create_tenancy_agreement
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('crop_share_tenancy',)))
        region = server.tiles[0]
        plot = region.tenure.plots[0]
        lord = next(agent for agent in region.agents if agent.id == plot.lord_id)
        tenant = next(agent for agent in region.agents if agent.id != lord.id)
        self.assertIsNone(create_tenancy_agreement(
            region, tenant, lord, plot.plot_id, kind='crop_share', crop_share=0.2))
        with patch('crop_credit.settle_crop_shares',
                   side_effect=AssertionError('crop share settled')):
            server.step()
        self.assertFalse(server.violations)

    def test_food_spoilage_gate_preserves_stocks_and_loss_remainders(self):
        def run(flags):
            server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                               topology='hex', scenario_id='labor_frontier_rivalry',
                               trace_enabled=False, gameplay_flags=flags)
            from food_economy import prepare_region
            for tile in server.tiles:
                tile.food_spoilage_enabled = True
                prepare_region(tile, 1)
                for farm in tile.farms.values():
                    farm['loss_remainder'] = 0.0004
            server.step()
            natural_loss = sum(
                event['units'] for tile in server.tiles
                for event in tile.food_accounts['events']
                if event['turn'] == 1 and event['kind'] == 'storage_loss'
                and 'reason' not in event)
            self.assertFalse(server.violations)
            return natural_loss, server

        full_loss, _ = run(FULL_GAMEPLAY_FLAGS)
        disabled_loss, disabled = run(resolve_gameplay_flags(
            disabled=('food_spoilage',)))
        self.assertGreater(full_loss, 0)
        self.assertEqual(disabled_loss, 0)
        for tile in disabled.tiles:
            self.assertTrue(all(farm['loss_remainder'] == 0.0004
                                for farm in tile.farms.values()))

    def test_food_relief_gate_freezes_shipments_and_skips_relief(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('food_relief',)))
        provinces = [p for n in server.nations for p in n.provinces]
        for province in provinces:
            province.food_shipments.append({
                'shipment_id': f'{province.name}:held', 'units': 10,
                'arrival_turn': 1, 'destination': province.tiles[0].name,
                'dispatched_turn': 0, 'source': province.tiles[0].name})
        before = {p.name: list(p.food_shipments) for p in provinces}
        with patch('food_logistics.deliver_province_food',
                   side_effect=AssertionError('relief shipment delivered')):
            with patch('food_logistics.dispatch_province_food',
                       side_effect=AssertionError('relief shipment dispatched')):
                server.step()
        self.assertFalse(server.violations)
        for province in provinces:
            self.assertEqual(province.food_shipments, before[province.name])

    def test_household_food_gate_skips_food_sharing(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('household_food',)))
        with patch('households.allocate',
                   side_effect=AssertionError('household food was allocated')) as allocate:
            server.step()
        allocate.assert_not_called()
        self.assertFalse(server.violations)

    def test_taxation_gate_skips_tax_without_skipping_fiscal_settlement(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('taxation',)))
        region = server.tiles[0]
        region.cash_tax_per_person = 10.0
        with patch('livelihood_access.assess_obligation',
                   side_effect=AssertionError('fixed tax assessed')):
            server.step()
        self.assertFalse(server.violations)
        self.assertTrue(region.tax_distribution_log)
        self.assertEqual(region.tax_distribution_log[-1]['total'], 0.0)

    def test_profits_gate_skips_owner_income_and_financing(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('profits',)))
        with patch('region_finance.distribute_profits',
                   side_effect=AssertionError('owner income was settled')) as settle:
            server.step()
        settle.assert_not_called()
        self.assertFalse(server.violations)

    def test_household_lifecycle_gate_skips_births_and_mortality(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('household_lifecycle',)))
        with patch('econsim_live.handle_reproduction',
                   side_effect=AssertionError('births ran')) as reproduce:
            with patch('econsim_live.handle_death',
                       side_effect=AssertionError('mortality ran')) as mortality:
                server.step()
        reproduce.assert_not_called()
        mortality.assert_not_called()
        self.assertFalse(server.violations)
        for tile in server.tiles:
            self.assertEqual(tile.dead_pop[-1], 0)

    def test_local_market_gate_skips_both_market_clearing_passes(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('local_market',)))
        with patch('region_market.trade',
                   side_effect=AssertionError('local market trade ran')):
            with patch('region_market.food_after_payroll',
                       side_effect=AssertionError('post-payroll market ran')):
                server.step()
        self.assertFalse(server.violations)

    def test_wages_gate_freezes_payments_and_defers_strike_review(self):
        from types import SimpleNamespace
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('wages',)))
        strike = SimpleNamespace(status='review', settlement_applied=False,
                                 ended_turn=0, review_turn=1)
        with patch('region_finance.pay_wages',
                   side_effect=AssertionError('wages paid')) as pay:
            with patch('region_finance.settle_wage_arrears',
                       side_effect=AssertionError('wage arrears settled')) as arrears:
                with patch('region_finance.redeem_company_scrip',
                           side_effect=AssertionError('scrip redeemed')) as scrip:
                    with patch('labor_resistance.step_workplace_resistance',
                               return_value={'strikers': 0, 'broken_machinery': 0,
                                             'smashed_this_turn': 0}):
                        server.step()
        pay.assert_not_called()
        arrears.assert_not_called()
        scrip.assert_not_called()
        from micro.region.disabled_phases import defer_payroll_reviews
        defer_payroll_reviews(SimpleNamespace(
            collective_organizations={'test': SimpleNamespace(strikes=[strike])}), 1)
        self.assertEqual(strike.review_turn, 2)
        self.assertFalse(server.violations)

    def test_production_gate_skips_crop_inputs_and_records_zero_output(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('production',)))
        with patch('agriculture.commit_crop_inputs',
                   side_effect=AssertionError('crop inputs committed')) as inputs:
            with patch('agriculture.produce',
                       side_effect=AssertionError('crops produced')) as crops:
                with patch('economy.apply_machinery_depreciation',
                           side_effect=AssertionError('machinery depreciated')) as wear:
                    server.step()
        inputs.assert_not_called()
        crops.assert_not_called()
        wear.assert_not_called()
        self.assertFalse(server.violations)
        for tile in server.tiles:
            self.assertTrue(all(tile.production_log[good][-1] == 0
                                for good in tile.goods if good.name != 'gov'))
            self.assertEqual(tile.production_receipts, [])
            self.assertEqual(tile.emission_production_turn, 1)
            self.assertFalse(any(tile.emission_production.values()))

    def test_labor_market_gate_freezes_firm_creation_and_wage_quotes(self):
        server = SimServer(seed=612, terrain_seed=612, nation_seed=612,
                           topology='hex', scenario_id='labor_frontier_rivalry',
                           trace_enabled=False,
                           gameplay_flags=resolve_gameplay_flags(
                               disabled=('labor_market',)))
        with patch('region_labor.incorporate',
                   side_effect=AssertionError('firm incorporated')) as incorporate:
            with patch('region_labor.adjust_wages',
                       side_effect=AssertionError('wage quote adjusted')) as adjust:
                server.step()
        incorporate.assert_not_called()
        adjust.assert_not_called()
        self.assertFalse(server.violations)


if __name__ == '__main__':
    unittest.main()
