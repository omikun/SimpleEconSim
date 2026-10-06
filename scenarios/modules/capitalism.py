"""
scenarios/modules/capitalism.py — Sven Beckert Capitalist Propagation Simulation Dynamic Module.

Orchestrates multi-sector transformation graphs, elite capitalist planning,
time-sliced labor mobility with emergency fast-paths, machinery wear-and-tear,
bills of exchange credit cycles, and war capitalism plantation extraction.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from goods import Goods
from scenarios.modules.base import BaseDynamicModule
from economy.transformation_graph import TransformationGraph, apply_machinery_depreciation
from economy.capitalist_planner import EliteCapitalistPlanner
from economy.labor_mobility import LaborMobilityScheduler
from economy.finance_bills import CreditMarketManager, BillOfExchange
from economy.portfolio_optimizer import EstatePortfolioOptimizer


class CapitalismModule(BaseDynamicModule):
    """Dynamic simulation module for capitalist propagation within scenario frameworks."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.planner = EliteCapitalistPlanner()
        self.labor_scheduler = LaborMobilityScheduler(
            target_group_time_sec=float(config.get('target_group_time_sec', 1.0)),
            base_batch_size=int(config.get('base_batch_size', 40))
        )
        self.credit_manager = CreditMarketManager(
            baseline_discount_rate=float(config.get('baseline_discount_rate', 0.05))
        )
        self.portfolio_optimizer = EstatePortfolioOptimizer(
            risk_aversion=float(config.get('risk_aversion', 0.15))
        )
        self.depreciation_interval = int(config.get('machinery_depreciation_interval', 12))

    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        """Seed capitalist tracking state, credit desks, and initial market baselines."""
        state = world.setdefault('scenario_state', {})
        state['capitalism_enabled'] = True
        state['cotton_reserves'] = int(self.config.get('initial_cotton_reserves', 15))
        state['cloth_reserves'] = int(self.config.get('initial_cloth_reserves', 10))
        state['credit_leverage'] = 1.00
        state['active_mills_count'] = 0
        state['proletariat_restiveness'] = float(self.config.get('initial_labor_restiveness', 0.15))
        state['dispossessed_count'] = 0
        state['plantation_gangs_active'] = 0
        state['credit_manager_ref'] = self.credit_manager
        state['labor_scheduler_ref'] = self.labor_scheduler
        state['planner_ref'] = self.planner

        # Give player government or merchants initial cotton/cloth if configured
        player = context.get('player_nation')
        if player:
            tiles = getattr(player, 'tiles', [])
            if tiles:
                capital_tile = tiles[0]
                agents = getattr(capital_tile, 'agents', [])
                if agents:
                    investor = agents[0]
                    investor.inv_add(Goods.cotton, state['cotton_reserves'])
                    investor.inv_add(Goods.cloth, state['cloth_reserves'])

    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        """Execute per-turn capitalist dynamics across all active regions."""
        state = world.setdefault('scenario_state', {})
        player = context.get('player_nation')
        all_tiles = []
        for n in world.get('nations', []):
            all_tiles.extend(getattr(n, 'tiles', []))
        for t in world.get('wilderness_tiles', []):
            all_tiles.append(t)
        # Deduplicate
        seen_names = set()
        tiles = []
        for t in all_tiles:
            if t.name not in seen_names:
                seen_names.add(t.name)
                tiles.append(t)

        total_broken_machinery = 0
        total_mills = 0
        total_cotton = 0
        total_cloth = 0
        total_dispossessed = 0
        all_wages: List[float] = []
        total_consciousness: List[float] = []

        # 1. Machinery Wear-and-Tear Depreciation (Dept I Capital Goods)
        if self.config.get('enable_machinery_depreciation', True):
            for tile in tiles:
                broken = apply_machinery_depreciation(tile, turn)
                total_broken_machinery += broken

        # 2. Rational Expectation Pending Capacity Decay
        for tile in tiles:
            TransformationGraph.step_pending_capacity_decay(tile, turn)

        # 3. Credit Market Matured Bills Settlement
        if self.config.get('enable_credit_market', True):
            for tile in tiles:
                settle_res = self.credit_manager.settle_matured_bills(tile, turn)
                if settle_res.get('defaulted_count', 0) > 0 and ticker_push:
                    ticker_push(world, turn, 'CREDIT_CRUNCH',
                                f"Merchant houses in {tile.name} defaulted on {settle_res['defaulted_count']} commercial bills!",
                                (230, 80, 80))

        # 4. Labor Mobility & Cohort Scheduling (with Emergency Fast-Path)
        for tile in tiles:
            if not getattr(tile, 'wilderness', False) and not getattr(tile, 'is_ocean', False):
                cohort_res = self.labor_scheduler.step_labor_cohort(tile, turn)
                for realloc in cohort_res.get('reallocations', []):
                    if realloc.get('is_emergency_fast_path') and ticker_push:
                        ticker_push(world, turn, 'LABOR_RELIEF',
                                    f"Starving commoner hired on emergency fast-path at ${realloc.get('wage', 0):.2f}/turn.",
                                    (100, 200, 120))

        # 5. Elite Capitalist Planning (every 5 turns or novelty)
        for tile in tiles:
            market_has_new = self.planner.check_new_market_items(tile)
            elites = [a for a in getattr(tile, 'agents', []) if getattr(a, 'alive', True) and self.planner.is_elite(a, tile)]
            for elite in elites:
                if self.planner.should_run_planning(elite, tile, turn, market_has_new):
                    plan_res = self.planner.plan_and_execute_elite(elite, tile, turn)
                    action = plan_res.get('action_taken')
                    if action and ticker_push:
                        if action == 'WAR_CAPITALISM_FRONTIER_CONQUEST':
                            ticker_push(world, turn, 'WAR_CAPITALISM',
                                        f"Chartered expedition under {elite.id} annexed frontier primary commodity enclave!",
                                        (210, 160, 60))
                        elif action == 'MANDATE_PLANTATION_LABOR_GANG':
                            ticker_push(world, turn, 'PLANTATION_EXTRACTION',
                                        f"Plantation gang labor harvested 15 units of export cotton with zero wages.",
                                        (200, 120, 80))
                        elif action == 'INCORPORATE_FIRM':
                            ticker_push(world, turn, 'INDUSTRIAL_EXPANSION',
                                        f"Capitalist investor incorporated new manufacturing corporation offering high wages.",
                                        (80, 180, 220))

        # 6. Aggregate System-Wide Metrics (Domestic Metropole & Empire)
        player_tiles = list(getattr(player, 'tiles', [])) or tiles
        for tile in player_tiles:
            agents = getattr(tile, 'agents', [])
            for a in agents:
                if getattr(a, 'is_corporation', False):
                    total_mills += 1
                    all_wages.append(getattr(a, 'wage', 0.0))
                else:
                    total_cotton += a.inv_get(Goods.cotton, 0)
                    total_cloth += a.inv_get(Goods.cloth, 0)
                    if getattr(a, 'social_class', None) == 'dispossessed':
                        total_dispossessed += 1
                    c = getattr(a, 'class_consciousness', 0.0)
                    if c > 0:
                        total_consciousness.append(c)

        avg_wage = (sum(all_wages) / len(all_wages)) if all_wages else 1.50
        avg_consciousness = (sum(total_consciousness) / len(total_consciousness)) if total_consciousness else 0.15

        # Compute Credit Market Leverage
        credit_stats = self.credit_manager.get_credit_market_stats(player.tiles[0] if player and player.tiles else tiles[0])
        leverage = credit_stats.get('leverage_ratio', 1.0)

        # Update scenario public state
        state['active_mills_count'] = total_mills
        state['cotton_reserves'] = total_cotton
        state['cloth_reserves'] = total_cloth
        state['dispossessed_count'] = total_dispossessed
        state['avg_proletariat_wage'] = round(avg_wage, 2)
        state['proletariat_restiveness'] = round(avg_consciousness, 3)
        state['credit_leverage'] = leverage
        state['is_credit_bubble'] = credit_stats.get('is_credit_bubble', False)
        state['broken_machinery_count'] = total_broken_machinery

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return diagnostic metrics for scenario pressures, triggers, and debrief."""
        state = world.setdefault('scenario_state', {})
        return {
            'cotton_reserves': int(state.get('cotton_reserves', 0)),
            'cloth_reserves': int(state.get('cloth_reserves', 0)),
            'active_mills_count': int(state.get('active_mills_count', 0)),
            'avg_wage': float(state.get('avg_proletariat_wage', 1.50)),
            'proletariat_restiveness': float(state.get('proletariat_restiveness', 0.15)),
            'credit_leverage': float(state.get('credit_leverage', 1.00)),
            'is_credit_bubble': bool(state.get('is_credit_bubble', False)),
            'dispossessed_count': int(state.get('dispossessed_count', 0)),
            'broken_machinery_count': int(state.get('broken_machinery_count', 0)),
        }
