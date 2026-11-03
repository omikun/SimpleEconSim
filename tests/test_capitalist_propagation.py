"""
test_capitalist_propagation.py — Unit & Integration Tests for Sven Beckert Capitalist Propagation Engine.

Tests:
1. Universal Sectors, Recipes & Professions Verification.
2. Feudal Luxury Shock & Multi-Step Conversion (Enclosure/Corvée -> Cash -> Luxury).
3. Capitalist Investment & Wage-Driven Labor Reallocation.
4. Cadence & Sub-Second Non-Elite Cohort Time-Slicing.
5. Zero-Hardcoding Extensibility: Dynamic Runtime Injection of Novel Commodities & Operators.
"""

import unittest
import time
from goods import Goods, profession
from region import Region
from nation import Nation
from land_tenure import LandPlot, TenureStatus
from agent import Agent, initialize_agent, seed_traits
from economy import (
    TransformationGraph,
    CommoditySpec,
    TransformationOperator,
    EliteCapitalistPlanner,
    LaborMobilityScheduler,
    apply_machinery_depreciation,
)


class TestCapitalistPropagation(unittest.TestCase):

    def setUp(self):
        self.nation = Nation("Kingdom", initial_cash=1000.0)
        self.tile = Region("Wessex", 0, 110)
        self.nation.add_tile(self.tile)

    def test_01_sectors_recipes_and_professions(self):
        """Verify all new sectors and luxury commodities are registered in goods, recipes, and professions."""
        new_goods = [
            Goods.cotton, Goods.iron_ore, Goods.iron, Goods.coal,
            Goods.tobacco, Goods.sugar, Goods.tea,
            Goods.fine_textiles, Goods.porcelain, Goods.rum, Goods.foreign_luxuries
        ]
        for g in new_goods:
            # 1. Goods enum
            self.assertIn(g, Goods)
            # 2. Profession character
            self.assertIn(g, profession)
            self.assertNotEqual(profession[g], '-')
            # 3. Recipe dictionary
            self.assertIn(g, self.tile.recipes)
            recipe = self.tile.recipes[g]
            self.assertGreater(recipe['production'], 0)
            self.assertGreater(recipe['price'], 0)

        # Verify luxury flags and prestige ratings
        self.assertTrue(self.tile.recipes[Goods.fine_textiles].get('is_luxury', False))
        self.assertTrue(self.tile.recipes[Goods.foreign_luxuries].get('is_luxury', False))
        self.assertGreater(self.tile.recipes[Goods.foreign_luxuries].get('prestige_rating', 0), 10.0)

    def test_02_feudal_luxury_shock_and_multistep_conversion(self):
        """Verify feudal lords convert customary holdings when luxury goods appear on market."""
        planner = EliteCapitalistPlanner()

        # 1. Setup Feudal Lord with customary plot
        lord = self.tile.agents[0]
        initialize_agent(lord, Goods.food, 0, 10, 50.0)
        lord.is_lord = True
        plot = LandPlot(
            plot_id='p_feudal_commons',
            tile_name=self.tile.name,
            lord_id=lord.id,
            fraction=0.4,
            tenure=TenureStatus.FEUDAL,
            rent_rate=0.0,
            tribute_rate=0.5,
            name='Common Fields'
        )
        self.tile.tenure.plots = [plot]
        plot.tenant_ids = [a.id for a in self.tile.agents if not a.is_lord and not a.is_government]
        for tenant in self.tile.agents:
            if tenant.id in plot.tenant_ids:
                tenant.assigned_plot_id = plot.plot_id

        # Initially without luxuries on the market, shadow price of cash is baseline
        lambda_initial = planner.calculate_shadow_price_cash(lord, self.tile)
        self.assertAlmostEqual(lambda_initial, 1.0, places=1)

        # 2. Introduce foreign luxury on the market (held by a traveling merchant)
        merchant = self.tile.agents[1]
        merchant.is_lord = False
        initialize_agent(merchant, Goods.foreign_luxuries, 0, 5, 20.0)
        merchant.inv_set(Goods.foreign_luxuries, 2)

        # Shadow price of cash spikes because luxury is reachable!
        lambda_shock = planner.calculate_shadow_price_cash(lord, self.tile)
        self.assertGreater(lambda_shock, lambda_initial)

        # 3. Lord plans: discovers that enclosing plot for pasture or mandating corvée yields cash
        self.tile.demand_log[Goods.wool] = [12.0]  # buyers must fund the expected proceeds
        plan_res = planner.plan_and_execute_elite(lord, self.tile, t=5)
        self.assertIsNotNone(plan_res['action_taken'])
        # Verify an enclosure or corvée operator was executed
        self.assertTrue(
            'ENCLOSE' in plan_res['action_taken'] or 'CORVEE' in plan_res['action_taken'],
            f"Expected enclosure or corvée action, got: {plan_res['action_taken']}"
        )

        # If enclosed, plot tenure transitioned
        if 'ENCLOSE' in plan_res['action_taken']:
            self.assertEqual(plot.tenure, TenureStatus.ENCLOSED)
            # Peasants on tile were dispossessed
            dispossessed = [a for a in self.tile.agents if getattr(a, 'social_class', None) == 'dispossessed'
                            or getattr(a, 'mem_avg', lambda *_: 0.0)('mem_eviction', 0.0) > 0]
            self.assertGreater(len(dispossessed), 0)

    def test_03_capitalist_investment_and_labor_attraction(self):
        """Verify capital investment creates wage jobs and pulls commoners into new professions."""
        planner = EliteCapitalistPlanner()
        scheduler = LaborMobilityScheduler()

        # 1. Enriched Capitalist with $300 cash
        capitalist = self.tile.agents[0]
        initialize_agent(capitalist, Goods.furniture, 0, 10, 300.0)
        capitalist.is_lord = False
        self.tile.demand_log[Goods.cloth] = [20.0]

        # Run capitalist planning: incorporates or expands firm in profitable sector (e.g. cloth, iron, fine_textiles)
        res = planner.plan_and_execute_elite(capitalist, self.tile, t=5)
        self.assertEqual(res['action_taken'], 'INCORPORATE_FIRM')
        firm_id = res['details']['company_id']
        firm = next(a for a in self.tile.agents if a.id == firm_id)
        self.assertTrue(firm.is_corporation)
        self.assertGreater(firm.wage, 1.5)

        # 2. Commoner / Dispossessed Workers evaluate labor mobility
        # Make agent 5 a dispossessed worker
        worker = self.tile.agents[5]
        initialize_agent(worker, Goods.food, 0, 1, 0.0)
        worker.social_class = 'dispossessed'
        worker.assigned_plot_id = None
        worker.employer = None
        worker.calorie_deficit_kcal = 500

        # A funded offer must exceed the usable independent livelihood.
        firm.wage = 100
        firm.cash = 10000

        # Execute the common career phase.
        non_elites = scheduler.get_non_elites(self.tile)
        worker_idx = non_elites.index(worker)
        n_groups = scheduler.calculate_n_groups(len(non_elites))
        cohort_res = scheduler.step_labor_cohort(self.tile, t=worker_idx)
        # Vacancies can fill before this particular worker is considered.
        # Verify that funded jobs actually attracted members of the cohort.
        self.assertGreater(len(firm.employees), 0)
        self.assertTrue(any(employee in non_elites for employee in firm.employees))
        self.assertTrue(all(employee.employer is firm for employee in firm.employees))
        self.assertTrue(all(employee.output == firm.output for employee in firm.employees))
        self.assertTrue(all(employee.wage == firm.wage for employee in firm.employees))

    def test_04_cadence_and_subsecond_cohort_timing(self):
        """Verify elite cadence (5 turns / novelty) and that non-elite cohorts execute in < 1 second."""
        planner = EliteCapitalistPlanner()
        scheduler = LaborMobilityScheduler()

        lord = self.tile.agents[0]
        lord.is_lord = True
        lord.cash = 100.0

        # Turn 1: Not turn % 5 and no new items -> should NOT run
        should_run_1 = planner.should_run_planning(lord, self.tile, t=1, market_has_new_items=False)
        self.assertFalse(should_run_1)

        # Turn 5: Turn % 5 == 0 -> should run!
        should_run_5 = planner.should_run_planning(lord, self.tile, t=5, market_has_new_items=False)
        self.assertTrue(should_run_5)

        # Turn 7: New item entered market -> should run immediately!
        should_run_novelty = planner.should_run_planning(lord, self.tile, t=7, market_has_new_items=True)
        self.assertTrue(should_run_novelty)

        # Test Cohort Timing on full population: must take < 1.0 second
        start = time.perf_counter()
        step_result = scheduler.step_labor_cohort(self.tile, t=0)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"Cohort execution took {elapsed:.4f}s, exceeding 1s requirement!")
        self.assertEqual(step_result['n_groups'], 1)
        self.assertEqual(step_result['deferred'], 0)

    def test_05_zero_hardcoding_extensibility(self):
        """Verify dynamic injection of a completely novel commodity and operator at runtime.
        
        Zero lines of agent AI code are modified; the agent discovers the conversion path automatically!
        """
        # Register a totally new, unseen commodity
        custom_luxury = CommoditySpec(
            good='astral_silk',
            name='Astral Silk',
            category='luxury',
            base_price=80.0,
            prestige_rating=35.0, # Astronomical luxury status
            tradeable=True
        )
        TransformationGraph.register_commodity(custom_luxury)

        # Register a transformation operator converting wood into astral silk
        custom_op = TransformationOperator(
            id='spin_astral_silk',
            name='Weave Astral Silk from Sacred Timber',
            category='artisan',
            input_goods={Goods.wood: 3.0},
            output_goods={'astral_silk': 1.0},
            requires_lord=False,
            cash_cost=10.0,
            description='Enchants harvested lumber into astral silk fabric.'
        )
        TransformationGraph.register_operator(custom_op)

        # Setup an agent holding wood and cash
        agent = self.tile.agents[2]
        initialize_agent(agent, Goods.wood, 0, 5, 50.0)
        agent.inv_set(Goods.wood, 5)

        # Query transformation graph: can the agent execute this new operator?
        can_exec, msg = custom_op.can_agent_execute(agent, self.tile)
        self.assertTrue(can_exec, f"Agent should be able to execute novel operator: {msg}")

        # Commercial production needs buyers; prestige is earned by consumption.
        net_ret = custom_op.estimate_net_return(agent, self.tile, shadow_price_cash=2.0)
        self.assertLess(net_ret, 0.0)
        self.tile.demand_log['astral_silk'] = [1.0]
        net_ret = custom_op.estimate_net_return(agent, self.tile, shadow_price_cash=2.0)
        self.assertGreater(net_ret, 0.0)
        self.assertAlmostEqual(net_ret, 80.0 * 2.0 - (10.0 * 2.0 + 3.0 * 1.0 * 2.0), delta=5.0)

    def test_06_ecological_and_biome_gating(self):
        """Verify that agricultural and mining operators respect ecological and climate constraints."""
        cotton_op = TransformationGraph.get_operator('corvee_cotton_plantation')
        self.assertIsNotNone(cotton_op)

        lord = self.tile.agents[0]
        lord.is_lord = True
        lord.cash = 50.0

        # In cold / arctic climate, cotton cultivation is ecologically prohibited
        self.tile.climate = 'cold'
        can_exec_cold, reason_cold = cotton_op.can_agent_execute(lord, self.tile)
        self.assertFalse(can_exec_cold)
        self.assertIn("cold", reason_cold)

        # In temperate / subtropical climate, cotton cultivation is allowed
        self.tile.climate = 'temperate'
        can_exec_warm, reason_warm = cotton_op.can_agent_execute(lord, self.tile)
        self.assertTrue(can_exec_warm, f"Cotton should be allowed in temperate climate, got: {reason_warm}")

        # Ocean biome prohibits mining
        iron_op = TransformationGraph.get_operator('mine_iron_ore')
        self.tile.biome = 'ocean'
        can_mine, mine_reason = iron_op.can_agent_execute(lord, self.tile)
        self.assertFalse(can_mine)
        self.assertIn("ocean", mine_reason)

    def test_07_class_legislation_wage_suppression(self):
        """Verify elites weaponize the state via the Statute of Laborers to suppress high wages."""
        planner = EliteCapitalistPlanner()

        capitalist = self.tile.agents[0]
        initialize_agent(capitalist, Goods.furniture, 0, 10, 300.0)
        capitalist.is_lord = False

        # Set up a high-wage firm on the tile
        firm = self.tile.agents[1]
        initialize_agent(firm, Goods.cloth, 0, 10, 1000.0)
        firm.is_corporation = True
        firm.wage = 2.50 # Squeezing employer profit margins

        # Tile currently does not have statute
        self.tile.statute_of_laborers = False

        # Capitalist evaluates class legislation to protect profit margins
        res = planner.evaluate_class_legislation(capitalist, self.tile, t=5)
        self.assertIsNotNone(res)
        self.assertEqual(res['action_taken'], 'PETITION_STATUTE_OF_LABORERS')

        # A capitalist petition is pending; law only binds after the government decision window.
        self.assertFalse(getattr(self.tile, 'statute_of_laborers', False))
        self.assertEqual(firm.wage, 2.50)
        from labor_laws import decide_labor_laws
        decide_labor_laws(self.tile, 6)
        self.assertTrue(getattr(self.tile, 'statute_of_laborers', False))
        self.assertLessEqual(firm.wage, 1.50)

    def test_08_elite_planner_does_not_bypass_route_auctions(self):
        """Cross-region inventory only moves through trader routes and auctions."""
        planner = EliteCapitalistPlanner()
        from region_logistics import add_neighbor

        # Setup neighboring tile with foreign luxury supplies
        neighbor = Region("Dorset", 0, 110)
        self.nation.add_tile(neighbor)
        add_neighbor(self.tile, neighbor)

        # Local tile has NO luxury on market
        # Neighbor has foreign luxury held by a trader
        seller = neighbor.agents[1]
        seller.is_lord = False
        initialize_agent(seller, Goods.foreign_luxuries, 0, 5, 20.0)
        seller.inv_set(Goods.foreign_luxuries, 3)

        # Local lord with $150 cash has no local luxury to buy
        lord = self.tile.agents[0]
        lord.is_lord = True
        initialize_agent(lord, Goods.food, 0, 10, 150.0)
        lord.inv_set(Goods.foreign_luxuries, 0)

        lord_cash_before = lord.cash
        res = planner.evaluate_spatial_trade(lord, self.tile, t=5)
        self.assertIsNone(res)
        self.assertEqual(lord.cash, lord_cash_before)
        self.assertEqual(lord.inv_get(Goods.foreign_luxuries, 0), 0)
        self.assertEqual(seller.inv_get(Goods.foreign_luxuries, 0), 3)

    def test_09_rational_expectations_cobweb_damping(self):
        """Verify rational expected prices damp cobweb overproduction cycles.
        
        When Lord 1 commits land to wool pasture, pending capacity increases,
        lowering expected price for subsequent planners and directing them to other sectors.
        """
        planner = EliteCapitalistPlanner()
        self.tile.climate = 'temperate'

        # Set market conditions: high wool spot price, but moderate recent sales
        self.tile.recipes[Goods.wool]['price'] = 20.0
        self.tile.price_log[Goods.wool] = [20.0] * 5
        self.tile.sold_log[Goods.wool] = [2.0] * 5
        self.tile.pending_capacity = {}

        # 1. Initial expected price equals baseline trend
        initial_expected_wool = TransformationGraph.compute_expected_price(self.tile, Goods.wool)
        self.assertAlmostEqual(initial_expected_wool, 20.0, places=1)

        # 2. Lord 1 encloses land for wool pasture
        lord1 = self.tile.agents[0]
        lord1.is_lord = True
        initialize_agent(lord1, Goods.food, 0, 10, 50.0)
        self.tile.tenure.plots[0].lord_id = lord1.id
        self.tile.tenure.plots[0].tenure = TenureStatus.FEUDAL

        # Also provide a luxury so shadow price of cash is high
        merchant = self.tile.agents[2]
        merchant.is_lord = False
        merchant.inv_set(Goods.foreign_luxuries, 2)

        res1 = planner.plan_and_execute_elite(lord1, self.tile, t=5)
        self.assertEqual(res1['action_taken'], 'OPERATOR_EXECUTED_ENCLOSE_PLOT_FOR_PASTURE')
        self.assertGreater(self.tile.pending_capacity.get(Goods.wool, 0), 0)

        # 3. Rational expected price for wool is now damped by pending capacity
        damped_expected_wool = TransformationGraph.compute_expected_price(self.tile, Goods.wool)
        self.assertLess(damped_expected_wool, initial_expected_wool * 0.5)

        # 4. Without a funded alternative market, Lord 2 waits rather than
        # replacing an unprofitable wool investment with another unsold crop.
        lord2 = self.tile.agents[1]
        lord2.is_lord = True
        initialize_agent(lord2, Goods.food, 0, 10, 50.0)
        self.tile.tenure.plots[1].lord_id = lord2.id
        self.tile.tenure.plots[1].tenure = TenureStatus.FEUDAL

        res2 = planner.plan_and_execute_elite(lord2, self.tile, t=5)
        self.assertIsNone(res2['action_taken'])
        # Lord 2 does NOT enclose for pasture again due to cobweb damping!
        self.assertNotEqual(res2['action_taken'], 'OPERATOR_EXECUTED_ENCLOSE_PLOT_FOR_PASTURE')

    def test_10_capital_goods_and_machinery_depreciation(self):
        """Verify capital goods operators (Department I) and machinery wear-and-tear depreciation."""
        planner = EliteCapitalistPlanner()

        # Set up a manufacturing firm with 1 machinery unit
        firm = self.tile.agents[0]
        firm.is_corporation = True
        firm.is_lord = False
        initialize_agent(firm, Goods.cloth, 0, 10, 200.0)
        firm.machinery_level = 1
        firm.broken_machinery = 0
        firm.max_employees = 10

        # Capitalist investor owning firm
        capitalist = self.tile.agents[1]
        capitalist.is_lord = False
        initialize_agent(capitalist, Goods.furniture, 0, 10, 150.0)
        capitalist.company_owned = firm

        # 1. Operational depreciation: machinery suffers wear and tear
        apply_machinery_depreciation(self.tile, t=12) # t=12 triggers interval
        self.assertEqual(firm.machinery_level, 0)
        self.assertEqual(firm.broken_machinery, 1)

        # 2. Repair machinery using bar iron and cash (Dept I maintenance)
        # Give firm iron or cash to buy iron
        firm.inv_set(Goods.iron, 2)
        repair_res = planner.plan_and_execute_elite(firm, self.tile, t=13)
        self.assertEqual(repair_res['action_taken'], 'REPAIR_MACHINERY')
        self.assertEqual(firm.broken_machinery, 0)
        self.assertEqual(firm.machinery_level, 1)

        # 3. Construct new machinery (Dept I expansion): consumes iron + coal + cash
        firm.inv_set(Goods.iron, 3)
        firm.inv_set(Goods.coal, 2)
        construct_res = planner.plan_and_execute_elite(firm, self.tile, t=15)
        self.assertEqual(construct_res['action_taken'], 'CONSTRUCT_MACHINERY')
        self.assertEqual(firm.machinery_level, 2)
        self.assertGreaterEqual(firm.max_employees, 15)

    def test_11_war_capitalism_frontier_expropriation(self):
        """Verify War Capitalism: armed conquest of wilderness frontier with mercenary pay and Crown charter."""
        from region_logistics import add_neighbor

        # Wessex borders an uncolonized wilderness region
        frontier = Region("Frontier_Territory", 0, wilderness=True, wilderness_pop=30)
        self.nation.add_tile(frontier)
        add_neighbor(self.tile, frontier)

        investor = self.tile.agents[0]
        investor.is_lord = False
        investor.is_trader = True
        initialize_agent(investor, Goods.none, 0, 10, 100.0)

        # Record total initial cash across tile (gov.agent is included in agents)
        init_total_cash = sum(a.cash for a in self.tile.agents)

        # Execute War Capitalism frontier conquest
        war_op = TransformationGraph.get_operator('chartered_frontier_conquest')
        can_exec, msg = war_op.can_agent_execute(investor, self.tile)
        self.assertTrue(can_exec, f"Should be executable, got: {msg}")

        exec_res = war_op.on_execute(investor, self.tile, t=5)
        self.assertTrue(exec_res['success'])
        self.assertEqual(exec_res['target_region'], 'Frontier_Territory')

        # Frontier native population dispossessed
        self.assertLess(frontier.wilderness_pop, 30)

        # Investor receives primary commodity enclave shipment
        comm = getattr(Goods, exec_res['commodity'])
        self.assertEqual(investor.inv_get(comm, 0), 10)

        # Investor records frontier estate
        self.assertTrue(hasattr(investor, 'frontier_estates'))
        self.assertEqual(len(investor.frontier_estates), 1)

        # Strict monetary conservation check:
        # $50 cost = $35 mercenary wages distributed to commoners + $15 charter fee to gov.agent
        final_total_cash = sum(a.cash for a in self.tile.agents)
        self.assertAlmostEqual(init_total_cash, final_total_cash, places=5)

    def test_12_hungry_and_wealthy_commoners_share_one_career_phase(self):
        """All adults are considered; savings and cohort timing cannot exclude hunger."""
        labor_engine = LaborMobilityScheduler(base_batch_size=5)
        workers = labor_engine.get_non_elites(self.tile, 0)
        self.assertGreaterEqual(len(workers), 6)
        starving_worker = workers[1]
        starving_worker.employer = None
        starving_worker.hungry_steps = 3
        starving_worker.cash = 500
        result = labor_engine.step_labor_cohort(self.tile, 0)
        self.assertEqual(result['n_groups'], 1)
        self.assertEqual(result['deferred'], 0)
        self.assertTrue(any(row['person_id'] == starving_worker.id
                            for row in self.tile.career_choice_log))
        self.assertTrue(labor_engine.step_labor_cohort(self.tile, 0)['already_processed'])

    def test_13_coerced_plantation_labor_regime(self):
        """Verify Issue-08: War Capitalism coerced labor, human commodification, zero-wage extraction & attrition."""
        investor = self.tile.agents[0]
        investor.is_lord = False
        investor.is_trader = True
        initialize_agent(investor, Goods.none, 0, 10, 80.0)
        investor.frontier_estates = [{
            'target_region': 'Overseas_Colony',
            'primary_commodity': 'cotton',
            'turn_acquired': 0,
            'displaced_population': 20,
            'captive_labor': 0,
        }]

        # Ensure cotton price is set
        self.tile.recipes[Goods.cotton] = {'price': 4.0, 'production': 10, 'numInput': 0}

        init_total_cash = sum(a.cash for a in self.tile.agents)

        # 1. Procure Captive Labor ($25 cash cost conserved to commoners)
        procure_op = TransformationGraph.get_operator('procure_captive_labor')
        can_procure, msg = procure_op.can_agent_execute(investor, self.tile)
        self.assertTrue(can_procure, f"Should be able to procure captive labor, got: {msg}")

        proc_res = procure_op.on_execute(investor, self.tile, t=1)
        self.assertTrue(proc_res['success'])
        self.assertEqual(proc_res['captive_labor_added'], 5)
        self.assertEqual(investor.frontier_estates[0]['captive_labor'], 5)

        # Currency strictly conserved
        self.assertAlmostEqual(sum(a.cash for a in self.tile.agents), init_total_cash, places=5)

        # 2. Mandate Plantation Labor Gang
        gang_op = TransformationGraph.get_operator('mandate_plantation_labor_gang')
        can_gang, msg = gang_op.can_agent_execute(investor, self.tile)
        self.assertTrue(can_gang, f"Should be able to mandate gang labor, got: {msg}")

        init_cotton = investor.inv_get(Goods.cotton, 0)
        gang_res = gang_op.on_execute(investor, self.tile, t=2)
        self.assertTrue(gang_res['success'])
        self.assertEqual(gang_res['commodity'], 'cotton')
        self.assertEqual(gang_res['yield_received'], 15)
        self.assertEqual(gang_res['wage_cost_to_laborers'], 0.0) # Zero wage coerced labor
        self.assertEqual(gang_res['overseer_wages_paid'], 10.0)
        self.assertEqual(investor.inv_get(Goods.cotton, 0), init_cotton + 15)
        # Attrition: 1 captive laborer lost to exhaustion
        self.assertEqual(investor.frontier_estates[0]['captive_labor'], 4)
        self.assertEqual(gang_res['captive_labor_remaining'], 4)

        # Currency strictly conserved ($10 overseer pay distributed to commoners)
        self.assertAlmostEqual(sum(a.cash for a in self.tile.agents), init_total_cash, places=5)

        # 3. Autonomous Execution via Capitalist Planner
        planner = EliteCapitalistPlanner()
        plan_res = planner.plan_and_execute_elite(investor, self.tile, t=5)
        self.assertEqual(plan_res['action_taken'], 'MANDATE_PLANTATION_LABOR_GANG')
        self.assertEqual(investor.frontier_estates[0]['captive_labor'], 3)
        self.assertEqual(investor.inv_get(Goods.cotton, 0), init_cotton + 30)

    def test_14_continuous_portfolio_optimization(self):
        """Verify Issue-05: Continuous multi-asset portfolio optimization across land plots."""
        from economy.portfolio_optimizer import EstatePortfolioOptimizer

        optimizer = EstatePortfolioOptimizer()
        lord = self.tile.agents[0]
        lord.is_lord = True

        # Lord with 8 plots and 10 serfs in temperate climate
        self.tile.climate = 'temperate'
        res = optimizer.compute_optimal_allocation(
            agent=lord,
            region=self.tile,
            total_plots=8,
            serf_count=10,
            shadow_cash=1.0,
        )

        allocs = res['allocations']
        # Food security constraint enforced:
        self.assertGreaterEqual(allocs['food_subsistence'], 1)
        # Customary stability floor enforced:
        self.assertGreaterEqual(allocs['customary_tenure'], 1)
        # Total plots equals 8:
        total_allocated = sum(allocs.values())
        self.assertEqual(total_allocated, 8)
        # Expected profit is positive:
        self.assertGreater(res['expected_profit'], 0.0)

        # Apply allocation to physical plots:
        changes = optimizer.apply_allocation_to_tenure(lord, self.tile, res, t=0)
        self.assertIsInstance(changes, list)

    def test_15_bills_of_exchange_and_credit_cycle(self):
        """Verify Issue-09: Negotiable bills of exchange, discounting, and credit cycles."""
        from economy.finance_bills import CreditMarketManager

        credit_mgr = CreditMarketManager(baseline_discount_rate=0.05)

        # Setup agents: Drawer A, Drawee B, Payee C, Buyer D
        drawer = Agent(0)
        drawer.cash = 20.0
        drawee = Agent(0)
        drawee.cash = 150.0
        payee = Agent(0)
        payee.cash = 10.0
        buyer = Agent(0)
        buyer.cash = 100.0

        self.tile.agents.extend([drawer, drawee, payee, buyer])
        init_total_cash = sum(a.cash for a in self.tile.agents)

        # 1. Issue Bill: Face value $80.0, matures at t=5 (tenor 4 turns from t=1)
        bill = credit_mgr.issue_bill(
            drawer=drawer,
            drawee=drawee,
            payee=payee,
            face_value=80.0,
            current_turn=1,
            tenor_turns=4,
        )
        self.assertEqual(bill.face_value, 80.0)
        self.assertEqual(bill.maturity_turn, 5)

        # 2. Negotiable Discounting at t=2:
        # Payee C discounts bill to Buyer D for immediate cash
        disc_res = credit_mgr.discount_bill(
            holder=payee,
            buyer=buyer,
            bill=bill,
            current_turn=2,
        )
        self.assertTrue(disc_res['success'])
        self.assertEqual(bill.payee_id, buyer.id)
        # Verify present value discount haircut
        self.assertLess(disc_res['cash_transferred'], 80.0)
        self.assertGreater(disc_res['haircut'], 0.0)
        # Currency strictly conserved
        self.assertAlmostEqual(sum(a.cash for a in self.tile.agents), init_total_cash, places=5)

        # 3. Settlement at Maturity (t=5):
        settle_res = credit_mgr.settle_matured_bills(self.tile, current_turn=5)
        self.assertEqual(settle_res['settled_count'], 1)
        self.assertEqual(settle_res['defaulted_count'], 0)
        self.assertTrue(bill.is_settled)
        # Buyer D received full $80 face value from Drawee B
        self.assertAlmostEqual(sum(a.cash for a in self.tile.agents), init_total_cash, places=5)

        # 4. Insolvent Default Case
        broke_drawee = Agent(0)
        broke_drawee.cash = 15.0
        broke_drawee.credit_rating = 1.0
        self.tile.agents.append(broke_drawee)

        bad_bill = credit_mgr.issue_bill(
            drawer=drawer,
            drawee=broke_drawee,
            payee=payee,
            face_value=100.0,
            current_turn=5,
            tenor_turns=1,
        )
        bad_settle = credit_mgr.settle_matured_bills(self.tile, current_turn=6)
        self.assertEqual(bad_settle['defaulted_count'], 1)
        self.assertTrue(bad_bill.is_defaulted)
        self.assertLess(broke_drawee.credit_rating, 1.0) # Credit rating penalized

    def test_16_dynamic_commodity_visuals_and_slot_acceleration(self):
        """Verify Issue-11: Pre-allocated commodity slot lookups and UI symbol/texture mappings."""
        from economy.commodity_visuals import get_commodity_visual, get_fast_commodity_slot

        # Core goods have valid visual metadata
        cotton_vis = get_commodity_visual(Goods.cotton)
        self.assertEqual(cotton_vis['symbol'], '☁️')
        self.assertEqual(cotton_vis['profession_char'], 'O')
        self.assertEqual(cotton_vis['category'], 'cash_crop')

        iron_vis = get_commodity_visual(Goods.iron_ore)
        self.assertEqual(iron_vis['symbol'], '⛏️')
        self.assertEqual(iron_vis['profession_char'], 'I')

        # Fast contiguous integer slot lookups
        slot_food = get_fast_commodity_slot(Goods.food)
        slot_cotton = get_fast_commodity_slot(Goods.cotton)
        self.assertIsInstance(slot_food, int)
        self.assertIsInstance(slot_cotton, int)
        self.assertNotEqual(slot_food, slot_cotton)

        # Dynamic runtime novel commodity
        slot_silk = get_fast_commodity_slot('astral_silk')
        self.assertIsInstance(slot_silk, int)
        # Consistent cache hit
        self.assertEqual(get_fast_commodity_slot('astral_silk'), slot_silk)

        silk_vis = get_commodity_visual('astral_silk')
        self.assertIn('color_rgb', silk_vis)
        self.assertEqual(silk_vis['symbol'], '📦')

    def test_17_geological_deposit_gating_and_game_balance(self):
        """Verify geological deposit gating and rarity tuning for game balance."""
        iron_op = TransformationGraph.get_operator('mine_iron_ore')
        coal_op = TransformationGraph.get_operator('mine_coal')

        worker = self.tile.agents[1]

        # Tile 1: Ordinary agrarian plain without deposits
        plain_tile = Region("Plain_Farm", 0)
        plain_tile.biome = 'plains'
        plain_tile.elevation = 0.20
        plain_tile.has_iron_deposit = False
        plain_tile.has_coal_vein = False

        # Attempt to mine iron on non-deposit tile -> Rejected!
        can_mine_iron, msg = iron_op.can_agent_execute(worker, plain_tile)
        self.assertFalse(can_mine_iron)
        self.assertIn('iron_deposit', msg)

        # Attempt to mine coal on non-deposit tile -> Rejected!
        can_mine_coal, msg = coal_op.can_agent_execute(worker, plain_tile)
        self.assertFalse(can_mine_coal)
        self.assertIn('coal_vein', msg)

        # Tile 2: Mountain highland with verified iron deposit
        mountain_tile = Region("Iron_Peak", 0)
        mountain_tile.biome = 'mountains'
        mountain_tile.elevation = 0.65
        mountain_tile.has_iron_deposit = True
        mountain_tile.mineral_richness = 0.85

        can_mine_iron_mtn, _ = iron_op.can_agent_execute(worker, mountain_tile)
        self.assertTrue(can_mine_iron_mtn)

        # Tile 3: Foothill forest with verified coal vein
        foothill_tile = Region("Coal_Forest", 0)
        foothill_tile.biome = 'hills'
        foothill_tile.elevation = 0.40
        foothill_tile.has_coal_vein = True

        can_mine_coal_ft, _ = coal_op.can_agent_execute(worker, foothill_tile)
        self.assertTrue(can_mine_coal_ft)

    def test_18_map_generation_and_regeneration_consistency(self):
        """Verify comprehensive procedural map generation, balanced deposits, and regeneration consistency."""
        from economy.map_generator import generate_capitalism_map

        # 1. Generate new capitalism map
        tiles1, nations1, grid1 = generate_capitalism_map(seed=42)

        land_tiles1 = [t for t in tiles1 if not getattr(t, 'is_ocean', False)]
        self.assertGreater(len(land_tiles1), 20)

        # Ore deposit rarity tuning:
        iron_tiles1 = [t for t in land_tiles1 if getattr(t, 'has_iron_deposit', False)]
        coal_tiles1 = [t for t in land_tiles1 if getattr(t, 'has_coal_vein', False)]
        self.assertGreaterEqual(len(iron_tiles1), 2)
        self.assertGreaterEqual(len(coal_tiles1), 2)
        # Controlled rarity: iron ore deposits capped under 25% of land tiles for balance
        self.assertLessEqual(len(iron_tiles1) / len(land_tiles1), 0.25)

        # Climate zoning exists:
        climates1 = {getattr(t, 'climate', '') for t in land_tiles1}
        self.assertIn('temperate', climates1)
        self.assertIn('subtropical', climates1)

        # Peripheral wilderness frontier exists for war capitalism:
        wilderness_tiles1 = [t for t in tiles1 if getattr(t, 'wilderness', False) and getattr(t, 'wilderness_pop', 0) > 0]
        self.assertGreaterEqual(len(wilderness_tiles1), 5)

        # 2. Regeneration Consistency: Identical seed produces identical map & deposits
        tiles2, nations2, grid2 = generate_capitalism_map(seed=42)
        for t1, t2 in zip(tiles1, tiles2):
            self.assertEqual(t1.name, t2.name)
            self.assertEqual(getattr(t1, 'has_iron_deposit', False), getattr(t2, 'has_iron_deposit', False))
            self.assertEqual(getattr(t1, 'has_coal_vein', False), getattr(t2, 'has_coal_vein', False))
            self.assertEqual(getattr(t1, 'climate', ''), getattr(t2, 'climate', ''))

        # 3. New Seed Produces Procedurally Distinct Balanced Map:
        tiles3, nations3, grid3 = generate_capitalism_map(seed=999)
        land_tiles3 = [t for t in tiles3 if not getattr(t, 'is_ocean', False)]
        iron_tiles3 = [t for t in land_tiles3 if getattr(t, 'has_iron_deposit', False)]
        coal_tiles3 = [t for t in land_tiles3 if getattr(t, 'has_coal_vein', False)]
        self.assertGreaterEqual(len(iron_tiles3), 2)
        self.assertGreaterEqual(len(coal_tiles3), 2)


if __name__ == '__main__':
    unittest.main()

