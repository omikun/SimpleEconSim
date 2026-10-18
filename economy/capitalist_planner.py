"""
economy/capitalist_planner.py — Goal-Oriented Action Planner & Investment Engine for Elites.

Theoretical Grounding (Sven Beckert / Werner Sombart):
1. Luxury Catalyst: Traditional elites are stimulated by the presence of prestige goods on the
   market to convert their endowments (feudal land tenure, serf labor, natural resources)
   into liquid money.
2. Capitalist Investment: Capitalists allocate liquid wealth into production sectors yielding
   the highest Return on Capital (ROC), bidding up wages and creating labor vacancies.
3. Cadence Requirement: Elites run planning every 5 turns or immediately when a new item enters
   the market.
"""

from __future__ import annotations
import math
from typing import List, Dict, Any, Optional, Tuple
from goods import Goods
from economy.transformation_graph import TransformationGraph, CommoditySpec, TransformationOperator


class EliteCapitalistPlanner:
    """Decision engine for landed nobility, merchants, and capitalists."""

    def __init__(self):
        self._known_market_goods: Dict[str, set] = {}
        self._last_plan_turn: Dict[int, int] = {}
        self._active_plans: Dict[int, Dict[str, Any]] = {}

    def get_market_luxuries(self, region: Any) -> List[Tuple[Any, float, float, int]]:
        """Identify available luxury goods in region or trade pipelines.
        
        Returns: list of (good, price, prestige_rating, available_qty)
        """
        luxuries = []
        recipes = getattr(region, 'recipes', {})
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating > 0:
                price = float(recipes.get(g, {}).get('price', spec.base_price))
                # Check supply on market or in region agent inventories
                market_qty = sum(a.inv_get(g, 0) for a in getattr(region, 'agents', [])
                                 if getattr(a, 'alive', True) and not getattr(a, 'is_lord', False))
                if market_qty > 0:
                    luxuries.append((g, price, spec.prestige_rating, market_qty))
        return luxuries

    def check_new_market_items(self, region: Any) -> bool:
        """Check if any previously unobserved goods have appeared on the region market."""
        reg_name = getattr(region, 'name', 'default')
        known = self._known_market_goods.get(reg_name, set())
        current = set()
        for a in getattr(region, 'agents', []):
            if getattr(a, 'alive', True):
                for g in getattr(region, 'goods', []):
                    if a.inv_get(g, 0) > 0:
                        current.add(g)

        new_items = current - known
        if new_items:
            self._known_market_goods[reg_name] = current
            return True
        self._known_market_goods[reg_name] = current
        return False

    def calculate_shadow_price_cash(self, agent: Any, region: Any) -> float:
        """Calculate dynamic shadow price of cash (lambda_cash) based on luxury desires."""
        base_lambda = 1.0
        luxuries = self.get_market_luxuries(region)
        if not luxuries:
            return base_lambda

        # Check agent's existing luxury satisfaction
        held_luxury_prestige = 0.0
        for g, _, prestige, _ in luxuries:
            held_luxury_prestige += agent.inv_get(g, 0) * prestige

        # Marginal utility of cash spikes when high-prestige luxuries are available
        best_luxury_ratio = max(prestige / max(1.0, price) for _, price, prestige, _ in luxuries)
        saturation_discount = 1.0 / (1.0 + 0.1 * held_luxury_prestige)
        shadow_price = base_lambda + (best_luxury_ratio * 2.0 * saturation_discount)
        return round(shadow_price, 3)

    def is_elite(self, agent: Any, region: Any) -> bool:
        """Check if agent qualifies as an elite (lord, capitalist, large merchant)."""
        if getattr(agent, 'is_lord', False):
            return True
        if getattr(agent, 'is_corporation', False) or getattr(agent, 'company_owned', None) is not None:
            return True
        if getattr(agent, 'cash', 0.0) >= 150.0:
            return True
        if getattr(agent, 'is_trader', False) and getattr(agent, 'cash', 0.0) >= 50.0:
            return True
        return False

    def should_run_planning(self, agent: Any, region: Any, t: int, market_has_new_items: bool) -> bool:
        """Check user cadence constraint: every 5 turns or when a new item enters market."""
        if not self.is_elite(agent, region):
            return False
        if market_has_new_items:
            return True
        return (t % 5 == 0)

    def evaluate_spatial_trade(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Spatial sales clear through trader routes and the destination auction.

        Kept as a no-op compatibility seam for the elite planner. Direct
        neighbor-to-neighbor inventory edits bypass freight, FX, and market
        prices; route traders now respond to profitable destinations and
        input shortages instead.
        """
        return None

    def evaluate_class_legislation(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Evaluate institutional state power operators (Statute of Laborers, Vagrancy Enforcement)."""
        statute_op = TransformationGraph.get_operator('petition_statute_of_laborers')
        if statute_op:
            can_run, _ = statute_op.can_agent_execute(agent, region)
            if can_run:
                exec_res = statute_op.on_execute(agent, region, t)
                return {
                    'action_taken': 'PETITION_STATUTE_OF_LABORERS',
                    'details': exec_res
                }

        vagrancy_op = TransformationGraph.get_operator('enforce_vagrancy_decree')
        if vagrancy_op:
            can_run, _ = vagrancy_op.can_agent_execute(agent, region)
            if can_run:
                exec_res = vagrancy_op.on_execute(agent, region, t)
                return {
                    'action_taken': 'PETITION_VAGRANCY_DECREE',
                    'details': exec_res
                }

        return None

    def _input_control_options(self, agent: Any, region: Any) -> List[Dict[str, Any]]:
        """Score practical supply-security moves for a short-input corporation."""
        if not getattr(agent, 'is_corporation', False) or agent.output not in region.recipes:
            return []
        recipe = region.recipes[agent.output]
        if recipe.get('numInput', 0) <= 0 or recipe.get('input') is None:
            return []
        good = recipe['input']
        price = float(region.recipes.get(good, {}).get('price', 1.0))
        needed = max(1, int(recipe['numInput'] * max(1, len(getattr(agent, 'employees', [])))))
        stock = int(agent.inv_get(good, 0))
        shortage = max(0, needed - stock)
        if shortage <= 0:
            return []
        margin = (float(recipe.get('production', 1.0))
                  * float(recipe.get('price', 1.0)) - price * float(recipe.get('numInput', 0))
                  - float(getattr(agent, 'wage', 0.0)) * max(1, len(getattr(agent, 'employees', []))))
        if margin <= 0:
            return [{'candidate': 'reduce_or_pause_output', 'feasible': True,
                     'good': good.name, 'shortage': shortage, 'estimated_margin': margin,
                     'score': 0.0, 'reason': 'input cost and payroll exceed expected output receipts'}]
        urgency = min(1.0, shortage / needed)
        options = []
        active_contract = any(c.get('status') == 'active' and c.get('lender_id') == agent.id
                              for c in getattr(region, 'offtake_contracts', []))
        growers = [a for a in region.agents if a.id != agent.id and getattr(a, 'alive', True)
                   and not getattr(a, 'is_corporation', False) and a.output == good
                   and getattr(a, 'assigned_plot_id', None)]
        grower = min(growers, key=lambda a: (a.cash, a.id), default=None)
        advance = min(15.0, max(3.0, price * 2.0))
        options.append({'candidate': 'advance_offtake', 'feasible': bool(grower and not active_contract
                          and agent.cash >= advance + 5.0), 'good': good.name,
                        'grower_id': grower.id if grower else None,
                        'plot_id': getattr(grower, 'assigned_plot_id', None) if grower else None,
                        'advance': advance, 'quantity': min(3, shortage),
                        'unit_price': price, 'shortage': shortage,
                        'estimated_margin': margin,
                        'score': urgency * min(1.0, margin / max(1.0, price * needed)) * 1.2,
                        'reason': 'fund a named grower and reserve part of the next harvest'})

        if grower is not None:
            from supply_rights import _seed_water_rights
            _seed_water_rights(region)
            target_plot = grower.assigned_plot_id
            rights = getattr(region, 'water_rights', [])
            target_units = sum(r.units for r in rights if r.plot_id == target_plot)
            water_units = min(.25, max(0.0, 1.25 - target_units))
            water_source = next((r for r in rights if r.plot_id != target_plot and r.units >= water_units
                                 and any(a.id == r.holder_id and a.id != agent.id
                                         for a in region.agents)), None)
            if water_source is not None and water_units > 0:
                water_seller = next((a for a in region.agents if a.id == water_source.holder_id), None)
                options.append({'candidate': 'acquire_water_right',
                                'feasible': bool(water_seller and agent.cash >= 5.0),
                                'good': good.name, 'grower_id': grower.id,
                                'from_plot_id': water_source.plot_id, 'to_plot_id': target_plot,
                                'seller_id': water_seller.id, 'units': water_units, 'price': 5.0,
                                'shortage': shortage,
                                'score': urgency * min(.65, margin / max(1.0, price * needed)) * .7,
                                'reason': 'redirect a measured seasonal allocation to a named input grower'})

        controlled = [p for p in getattr(getattr(region, 'tenure', None), 'plots', [])
                      if getattr(p, 'controlled_by_id', p.lord_id) == agent.id]
        for plot in getattr(getattr(region, 'tenure', None), 'plots', []):
            seller = next((a for a in region.agents if a.id == plot.lord_id), None)
            if (plot in controlled or seller is None or seller is agent or not getattr(seller, 'alive', True)
                    or any(l.get('plot_id') == plot.plot_id and l.get('status') == 'active'
                           for l in getattr(region, 'land_leases', []))):
                continue
            lease_cost = max(5.0, price * max(.25, float(plot.fraction)) * 4.0)
            options.append({'candidate': 'lease_input_land', 'feasible': agent.cash >= lease_cost + 5,
                            'good': good.name, 'plot_id': plot.plot_id, 'seller_id': seller.id,
                            'price': lease_cost, 'shortage': shortage,
                            'score': urgency * min(.8, margin / max(1.0, price * needed)) * .6,
                            'reason': 'lease titled land while retaining named tenants and customary tenure'})

        existing = [c for c in getattr(region, 'market_charters', [])
                    if c.get('status') == 'active' and c.get('sponsor_id') == agent.id]
        pending = [c for c in getattr(region, 'concession_petitions', [])
                   if c.get('status') == 'proposed' and c.get('sponsor_id') == agent.id]
        options.append({'candidate': 'exclusive_processing_charter',
                        'feasible': (shortage >= 2 and agent.cash >= 20 and not existing and not pending
                                     and getattr(region, 'gov', None) is not None),
                        'good': good.name, 'fee': 10.0, 'term_turns': 10,
                        'shortage': shortage,
                        'score': urgency * min(.75, margin / max(1.0, price * needed)) * .5,
                        'reason': 'ask the government to restrict competing processors; approval is uncertain'})
        return options

    def _execute_input_control(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        options = self._input_control_options(agent, region)
        viable = [row for row in options if row.get('feasible') and row.get('score', 0) > .08]
        if not viable:
            return None
        # Contracts are reversible and deliver material next harvest; leases and
        # charters have longer consequences and need materially higher pressure.
        viable.sort(key=lambda row: (-row['score'],
                                    {'advance_offtake': 0, 'lease_input_land': 1,
                                     'exclusive_processing_charter': 2}.get(row['candidate'], 9)))
        best = viable[0]
        good = next(g for g in region.recipes if g.name == best['good'])
        if best['candidate'] == 'advance_offtake':
            grower = next(a for a in region.agents if a.id == best['grower_id'])
            from supply_proposals import propose
            proposal = propose(region, 'advance_offtake', agent, grower,
                               turn=t, price=best['advance'], due_turn=t + 2,
                               plot_id=best['plot_id'], good=best['good'],
                               quantity=best['quantity'], unit_price=best['unit_price'],
                               max_price=best['advance'])
            if proposal is None:
                return None
            details = proposal
        elif best['candidate'] == 'acquire_water_right':
            seller = next(a for a in region.agents if a.id == best['seller_id'])
            from supply_proposals import propose
            proposal = propose(region, 'water_right', agent, seller, turn=t,
                               price=best['price'], units=best['units'],
                               from_plot_id=best['from_plot_id'],
                               to_plot_id=best['to_plot_id'], max_price=best['price'] * 1.25)
            if proposal is None:
                return None
            details = proposal
        elif best['candidate'] == 'lease_input_land':
            seller = next(a for a in region.agents if a.id == best['seller_id'])
            from supply_proposals import propose
            proposal = propose(region, 'land_lease', agent, seller, turn=t,
                               price=best['price'], plot_id=best['plot_id'],
                               lease_turns=10, max_price=best['price'] * 1.25)
            if proposal is None:
                return None
            details = proposal
        else:
            from market_concessions import submit_concession_petition
            petition = submit_concession_petition(agent, region, good, 'exclusive_processing',
                                                   best['fee'], best['term_turns'], t)
            if petition is None:
                return None
            details = petition
        return {'action_taken': best['candidate'].upper(), 'details': details,
                'selected_score': best['score'], 'candidate_options': options}

    def _elite_candidate_snapshot(self, agent: Any, region: Any, shadow_cash: float) -> List[Dict[str, Any]]:
        """Capture the actionable alternatives and gates used by elite planning."""
        candidates = [{'candidate': 'do_nothing', 'feasible': True,
                       'priority': 'fallback'}]
        candidates.extend(self._input_control_options(agent, region))
        cash = float(getattr(agent, 'cash', 0.0))
        for good, price, prestige, quantity in self.get_market_luxuries(region):
            seller = next((person for person in getattr(region, 'agents', [])
                           if person.id != agent.id and getattr(person, 'alive', True)
                           and person.inv_get(good, 0) > 0), None)
            candidates.append({
                'candidate': 'luxury_purchase', 'good': getattr(good, 'name', str(good)),
                'feasible': bool(cash >= 25.0 and cash >= price and seller),
                'reason': ('ready seller and cash available' if seller and cash >= price
                           else 'requires a live seller and enough cash'),
                'seller_id': str(seller.id) if seller else None,
                'price': float(price), 'prestige': float(prestige),
                'available_quantity': int(quantity),
                'prestige_per_cash': float(prestige) / max(1.0, float(price))})

        recipes = getattr(region, 'recipes', {})
        sectors = []
        for good, recipe in recipes.items():
            if good in (Goods.gov, Goods.none, Goods.foreign_luxuries):
                continue
            if recipe.get('is_luxury') and recipe.get('numInput', 0) == 0:
                continue
            output_price = float(recipe.get('price', 1.0))
            input_good = recipe.get('input')
            input_price = float(recipes.get(input_good, {}).get('price', 0.0)) \
                if recipe.get('numInput', 0) > 0 else 0.0
            margin = (output_price * recipe.get('production', 1.0)
                      - input_price * recipe.get('numInput', 0))
            if not math.isfinite(float(margin)):
                continue
            sectors.append({'good': getattr(good, 'name', str(good)),
                             'estimated_margin': float(margin),
                             'output_price': output_price, 'input_price': input_price})
        sectors.sort(key=lambda row: row['estimated_margin'], reverse=True)
        for sector in sectors[:8]:
            candidates.append({'candidate': 'capital_investment',
                               'feasible': cash >= 150.0 and not getattr(agent, 'is_lord', False),
                               'reason': 'cash threshold 150 and non-lord', **sector})

        trade_manager = getattr(region, 'trade_manager', None)
        if trade_manager is not None:
            for circuit in getattr(trade_manager, 'circuits', {}).values():
                try:
                    arbitrage = trade_manager.evaluate_dynamic_arbitrage(circuit, region)
                    can_charter, charter_reason = trade_manager.can_charter_voyage(
                        agent, region, circuit)
                except (AttributeError, KeyError, TypeError, ValueError):
                    continue
                roi = float(arbitrage.get('roi', 0.0))
                if not math.isfinite(roi):
                    continue
                pioneer = getattr(circuit, 'status', '') == 'DORMANT_UNEXPLORED'
                score = roi + (0.2 if pioneer else 0.0)
                candidates.append({'candidate': 'triangular_trade_voyage',
                                   'circuit_id': str(getattr(circuit, 'circuit_id', 'unknown')),
                                   'feasible': bool(arbitrage.get('viable') and can_charter),
                                   'reason': str(charter_reason), 'roi': roi,
                                   'pioneer_bonus': 0.2 if pioneer else 0.0,
                                   'effective_score': score, 'selection_threshold': 0.20})

        for neighbor_name, neighbor in getattr(region, 'neighbors', {}).items():
            for good, price, prestige, quantity in self.get_market_luxuries(neighbor):
                if agent.inv_get(good, 0) > 0:
                    continue
                total_cost = float(price) + 2.0
                seller = next((person for person in getattr(neighbor, 'agents', [])
                               if getattr(person, 'alive', True) and person.inv_get(good, 0) > 0), None)
                candidates.append({'candidate': 'spatial_luxury_import',
                                   'neighbor': str(neighbor_name),
                                   'good': getattr(good, 'name', str(good)),
                                   'feasible': bool(seller and cash >= 30.0 and cash >= total_cost),
                                   'reason': 'requires cash threshold and neighbor seller',
                                   'price': float(price), 'haulage_fee': 2.0,
                                   'available_quantity': int(quantity)})

        for operator_id in ('petition_statute_of_laborers', 'enforce_vagrancy_decree',
                            'maintain_repair_machinery', 'construct_machinery',
                            'mandate_plantation_labor_gang', 'procure_captive_labor',
                            'chartered_frontier_conquest'):
            operator = TransformationGraph.get_operator(operator_id)
            if operator is None:
                continue
            try:
                feasible, reason = operator.can_agent_execute(agent, region)
                net_return = (operator.estimate_net_return(agent, region, shadow_cash)
                              if feasible else None)
                if net_return is not None and not math.isfinite(float(net_return)):
                    net_return = None
            except (AttributeError, KeyError, TypeError, ValueError):
                feasible, reason, net_return = False, 'candidate evaluation unavailable', None
            candidates.append({'candidate': operator_id, 'feasible': bool(feasible),
                               'reason': str(reason), 'estimated_net_return': net_return,
                               'cash': cash, 'shadow_cash_price': float(shadow_cash)})

        if getattr(agent, 'is_lord', False):
            for operator in TransformationGraph.all_operators():
                if operator.category not in ('enclosure', 'corvee', 'artisan', 'war_capitalism'):
                    continue
                try:
                    feasible, reason = operator.can_agent_execute(agent, region)
                    net_return = (operator.estimate_net_return(agent, region, shadow_cash)
                                  if feasible else None)
                    if net_return is not None and not math.isfinite(float(net_return)):
                        net_return = None
                except (AttributeError, KeyError, TypeError, ValueError):
                    feasible, reason, net_return = False, 'candidate evaluation unavailable', None
                candidates.append({'candidate': operator.id, 'category': operator.category,
                                   'feasible': bool(feasible), 'reason': str(reason),
                                   'estimated_net_return': net_return,
                                   'selection_threshold': 5.0})
        return candidates

    def evaluate_triangular_trade_voyage(self, agent: Any, region: Any, t: int) -> Optional[Dict[str, Any]]:
        """Evaluate chartering an oceanic merchant voyage on discovered trade circuits."""
        trade_mgr = getattr(region, 'trade_manager', None)
        if not trade_mgr:
            return None

        best_circuit = None
        best_roi = -999.0
        best_is_pioneer = False

        for c in trade_mgr.circuits.values():
            arb = trade_mgr.evaluate_dynamic_arbitrage(c, region)
            if arb.get('viable'):
                can_run, _ = trade_mgr.can_charter_voyage(agent, region, c)
                if can_run:
                    roi = arb.get('roi', 0.0)
                    is_pioneer = (getattr(c, 'status', '') == 'DORMANT_UNEXPLORED')
                    effective_score = roi + (0.2 if is_pioneer else 0.0)
                    if effective_score > best_roi:
                        best_roi = effective_score
                        best_circuit = c
                        best_is_pioneer = is_pioneer

        if best_circuit and best_roi >= 0.20:
            res = trade_mgr.charter_voyage(agent, region, best_circuit.circuit_id, is_pioneer=best_is_pioneer)
            if res.get('success'):
                return {
                    'action_taken': 'CHARTER_MERCHANT_VOYAGE',
                    'details': res
                }
        return None

    def plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Trace the evaluated plan and its observed execution without a second AI pass."""
        from run_trace import emit
        cash_before = float(agent.cash)
        TransformationGraph.step_pending_capacity_decay(region, t)
        shadow_cash = self.calculate_shadow_price_cash(agent, region)
        candidates = self._elite_candidate_snapshot(agent, region, shadow_cash)
        result = self._plan_and_execute_elite(agent, region, t)
        reported_details = result.get('details', {})
        scalar_details = {str(key): value for key, value in reported_details.items()
                          if value is None or isinstance(value, (str, int, float, bool))}
        subject = {'type': 'agent', 'id': agent.id, 'tile': region.name}
        decision_id = emit(region, kind='corporation_ai_decision', record_class='decision',
                           phase='local', subject=subject,
                           inputs={'opening_cash': cash_before, 'candidates': candidates,
                                   'consideration_order': [
                                       'luxury_purchase', 'triangular_trade', 'spatial_trade',
                                       'class_legislation', 'lord_transformation', 'machinery',
                                       'supply_security', 'captured_labor', 'capital_investment',
                                       'inventory_liquidation', 'do_nothing'],
                                   'selected': result.get('action_taken') or 'do_nothing',
                                   'shadow_cash_price': shadow_cash,
                                   'neighbors': sorted(getattr(region, 'neighbors', {}).keys())})
        emit(region, kind='corporation_ai_outcome', record_class='outcome',
             phase='local', subject=subject, metric_id='economy.cash',
             unit=getattr(region, 'home_currency', 'local_currency'),
             before=cash_before, after=float(agent.cash),
             decision_id=decision_id,
             inputs={'action': result.get('action_taken') or 'do_nothing',
                     'details': scalar_details,
                     'omitted_detail_keys': sorted(str(key) for key, value in reported_details.items()
                                                   if value is not None and not isinstance(value, (str, int, float, bool)))})
        return result

    def _plan_and_execute_elite(self, agent: Any, region: Any, t: int) -> Dict[str, Any]:
        """Formulate and execute a multi-step conversion or investment plan for an elite agent."""
        self._last_plan_turn[agent.id] = t
        shadow_cash = self.calculate_shadow_price_cash(agent, region)
        luxuries = self.get_market_luxuries(region)
        result = {
            'agent_id': agent.id,
            'is_lord': getattr(agent, 'is_lord', False),
            'shadow_price_cash': shadow_cash,
            'action_taken': None,
            'details': {}
        }

        # ---------------------------------------------------------------------
        # 1. Luxury Purchase Check: If elite has enough cash, buy luxury!
        # ---------------------------------------------------------------------
        if luxuries and agent.cash >= 25.0:
            luxuries.sort(key=lambda item: item[2] / max(1.0, item[1]), reverse=True)
            for good, price, prestige, qty in luxuries:
                if agent.cash >= price:
                    seller = next((a for a in region.agents if a.id != agent.id and a.alive
                                   and a.inv_get(good, 0) > 0), None)
                    if seller:
                        agent.cash -= price
                        seller.cash += price
                        seller.inv_add(good, -1)
                        agent.inv_add(good, 1)
                        result['action_taken'] = 'PURCHASE_LUXURY'
                        result['details'] = {'good': good.name if hasattr(good, 'name') else str(good),
                                             'price': price, 'seller_id': seller.id}
                        return result

        # ---------------------------------------------------------------------
        # 2. Oceanic Triangular Trade Check (Venture Capital & Merchant Voyages)
        # ---------------------------------------------------------------------
        voyage_res = self.evaluate_triangular_trade_voyage(agent, region, t)
        if voyage_res:
            result['action_taken'] = voyage_res['action_taken']
            result['details'] = voyage_res['details']
            return result

        # ---------------------------------------------------------------------
        # 3. Macro & Spatial Trade Check (Inter-Regional Luxury & Input Import)
        # ---------------------------------------------------------------------
        spatial_res = self.evaluate_spatial_trade(agent, region, t)
        if spatial_res:
            result['action_taken'] = spatial_res['action_taken']
            result['details'] = spatial_res['details']
            return result

        # ---------------------------------------------------------------------
        # 4. Class Legislation Check (Statute of Laborers / Vagrancy Decrees)
        # ---------------------------------------------------------------------
        leg_res = self.evaluate_class_legislation(agent, region, t)
        if leg_res:
            result['action_taken'] = leg_res['action_taken']
            result['details'] = leg_res['details']
            return result

        # ---------------------------------------------------------------------
        # 4. Feudal Lord Conversion: Convert Customary Tenures to Liquid Cash Flows
        # ---------------------------------------------------------------------
        if getattr(agent, 'is_lord', False):
            # Lord evaluates conversion paths to generate cash for luxuries:
            # - Enclosure of customary plot to sheep pasture
            # - Corvée cash crops (cotton, sugar, tobacco)
            # - War Capitalism frontier conquest
            all_ops = TransformationGraph.all_operators()
            best_op = None
            best_roc = -999.0

            for op in all_ops:
                can_run, _ = op.can_agent_execute(agent, region)
                if can_run and op.category in ('enclosure', 'corvee', 'artisan', 'war_capitalism'):
                    net_return = op.estimate_net_return(agent, region, shadow_cash)
                    if net_return > best_roc:
                        best_roc = net_return
                        best_op = op

            # If an enclosure, corvée, or war capitalism operator yields positive net return, execute it!
            if best_op and best_roc > 5.0:
                if best_op.on_execute:
                    exec_res = best_op.on_execute(agent, region, t)
                    result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
                    result['details'] = {'operator': best_op.name, 'execution_result': exec_res}
                    return result
                else:
                    # Generic operator inventory transformation
                    if best_op.cash_cost > 0:
                        # Generic cash costs are local permit and service
                        # fees. Keep the payment in the monetary system.
                        if getattr(region, 'gov', None) is None:
                            return result
                        agent.cash -= best_op.cash_cost
                        region.gov.agent.cash += best_op.cash_cost
                        from run_trace import emit
                        emit(region, kind='elite_operator_fee',
                             record_class='transfer', phase='labor',
                             subject={'type': 'agent', 'id': agent.id},
                             metric_id='finance.operator_fee',
                             unit=region.home_currency,
                             after=best_op.cash_cost,
                             inputs={'operator': best_op.id,
                                     'recipient_id': region.gov.agent.id})
                    for g, q in best_op.output_goods.items():
                        agent.inv_add(g, int(q))
                    result['action_taken'] = f'OPERATOR_EXECUTED_{best_op.id.upper()}'
                    result['details'] = {'operator': best_op.name, 'yield': best_op.output_goods}
                    return result

        # ---------------------------------------------------------------------
        # 5. Capital Goods Maintenance & Machinery Construction (Issue-06)
        # ---------------------------------------------------------------------
        repair_op = TransformationGraph.get_operator('maintain_repair_machinery')
        if repair_op:
            can_repair, _ = repair_op.can_agent_execute(agent, region)
            if can_repair:
                exec_res = repair_op.on_execute(agent, region, t)
                if exec_res.get('success'):
                    result['action_taken'] = 'REPAIR_MACHINERY'
                    result['details'] = exec_res
                    return result

        construct_op = TransformationGraph.get_operator('construct_machinery')
        if construct_op and agent.cash >= 60.0:
            can_construct, _ = construct_op.can_agent_execute(agent, region)
            if can_construct:
                construct_ret = construct_op.estimate_net_return(agent, region, shadow_cash)
                if construct_ret > 15.0:
                    exec_res = construct_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'CONSTRUCT_MACHINERY'
                        result['details'] = exec_res
                        return result

        # First maintain the productive plant; supply-control investment follows
        # only after a damaged firm has restored its existing capacity.
        supply_res = self._execute_input_control(agent, region, t)
        if supply_res:
            result['action_taken'] = supply_res['action_taken']
            result['details'] = supply_res['details']
            return result

        # ---------------------------------------------------------------------
        # 6. Non-Lord War Capitalism: Chartered Colonial Concessions & Plantation Regimes
        # ---------------------------------------------------------------------
        # A. Plantation gang labor extraction if captive labor available
        gang_op = TransformationGraph.get_operator('mandate_plantation_labor_gang')
        if gang_op:
            can_gang, _ = gang_op.can_agent_execute(agent, region)
            if can_gang:
                gang_ret = gang_op.estimate_net_return(agent, region, shadow_cash)
                if gang_ret > 10.0:
                    exec_res = gang_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'MANDATE_PLANTATION_LABOR_GANG'
                        result['details'] = exec_res
                        return result

        # B. Procure captive labor for existing estates
        procure_op = TransformationGraph.get_operator('procure_captive_labor')
        if procure_op:
            can_procure, _ = procure_op.can_agent_execute(agent, region)
            if can_procure:
                procure_ret = procure_op.estimate_net_return(agent, region, shadow_cash)
                if procure_ret > 15.0:
                    exec_res = procure_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'PROCURE_CAPTIVE_LABOR'
                        result['details'] = exec_res
                        return result

        # C. Chartered frontier conquest
        war_cap_op = TransformationGraph.get_operator('chartered_frontier_conquest')
        if war_cap_op and agent.cash >= 50.0:
            can_conquer, _ = war_cap_op.can_agent_execute(agent, region)
            if can_conquer:
                conquer_ret = war_cap_op.estimate_net_return(agent, region, shadow_cash)
                if conquer_ret > 20.0:
                    exec_res = war_cap_op.on_execute(agent, region, t)
                    if exec_res.get('success'):
                        result['action_taken'] = 'WAR_CAPITALISM_FRONTIER_CONQUEST'
                        result['details'] = exec_res
                        return result

        # ---------------------------------------------------------------------
        # 3. Capitalist Investment & Wage Bidding
        # ---------------------------------------------------------------------
        if agent.cash >= 150.0 and not getattr(agent, 'is_lord', False):
            # Find the most profitable sector to invest or incorporate
            recipes = getattr(region, 'recipes', {})
            best_sector = None
            best_profit_margin = 0.0

            for g, r in recipes.items():
                if g in (Goods.gov, Goods.none, Goods.foreign_luxuries):
                    continue
                if r.get('is_luxury') and r.get('numInput', 0) == 0:
                    continue
                if r.get('import_only'):
                    continue
                p_out = float(r.get('price', 1.0))
                req_qty = float(r.get('numInput', 0))
                in_good = r.get('input')
                p_in = float(recipes.get(in_good, {}).get('price', 0.0)) if req_qty > 0 else 0.0
                margin = (p_out * r.get('production', 1.0)) - (p_in * req_qty)
                if req_qty > 0 and in_good is not None:
                    local_supply = (
                        sum(p.inv_get(in_good, 0) for p in getattr(region, 'agents', []) if getattr(p, 'alive', True))
                        + sum(1 for p in getattr(region, 'agents', []) if getattr(p, 'alive', True) and getattr(p, 'output', None) == in_good)
                    )
                    if local_supply < req_qty:
                        margin *= 0.05
                if margin > best_profit_margin:
                    best_profit_margin = margin
                    best_sector = g

            # Invest in existing firm or found new corporation
            company = getattr(agent, 'company_owned', None)
            if (company and getattr(company, 'is_corporation', False) and company.alive
                    and company in region.agents
                    and company.home_currency == region.home_currency):
                # Capital injection to expand workforce & machinery
                injection = min(agent.cash * 0.4, 50.0)
                agent.cash -= injection
                company.cash += injection
                # Raise offered wage to attract more workers
                company.wage = round(max(company.wage * 1.10, company.wage + 0.5), 2)
                company.max_employees = min(50, company.max_employees + 5)
                result['action_taken'] = 'CAPITAL_EXPANSION'
                result['details'] = {'company_id': company.id, 'injection': injection, 'new_wage': company.wage}
                return result
            elif (company is None and agent.cash >= 300.0
                  and not getattr(agent, 'employer', None) and best_sector):
                # Incorporate firm in highest-margin sector
                from agent import Agent, seed_traits
                comp = Agent(t)
                comp.is_corporation = True
                seed_traits(comp)
                comp.output = best_sector
                comp.owner = agent
                comp._bank_ref = getattr(region, 'bank', None)
                comp.home_currency = getattr(region, 'home_currency', None)
                comp.region = getattr(region, 'name', '')
                agent.company_owned = comp
                equity = min(agent.cash * 0.5, agent.cash - 60.0)
                agent.cash -= equity
                comp.cash = equity
                # Attractive wage to stimulate profession adoption
                food_p = float(region.recipes.get(Goods.food, {}).get('price', 1.0))
                comp.wage = round(max(2.0, food_p * 2.0), 2)
                comp.max_employees = 15
                region.agents.append(comp)
                result['action_taken'] = 'INCORPORATE_FIRM'
                result['details'] = {'company_id': comp.id, 'sector': best_sector.name, 'wage': comp.wage}
                return result

        # ---------------------------------------------------------------------
        # 4. Market Liquidation: Sell excess non-luxury inventory for cash
        # ---------------------------------------------------------------------
        for g in getattr(region, 'goods', []):
            spec = TransformationGraph.get_commodity_spec(g)
            if spec and spec.prestige_rating == 0.0 and g != Goods.food:
                held = agent.inv_get(g, 0)
                if held > 0:
                    p = float(region.recipes.get(g, {}).get('price', 1.0))
                    buyer = next((a for a in region.agents if a.id != agent.id and a.alive
                                  and a.cash >= p), None)
                    if buyer:
                        sale_qty = min(held, max(1, int(buyer.cash // p)))
                        trade_cash = sale_qty * p
                        buyer.cash -= trade_cash
                        agent.cash += trade_cash
                        agent.inv_add(g, -sale_qty)
                        buyer.inv_add(g, sale_qty)
                        result['action_taken'] = f'LIQUIDATE_{g.name.upper()}'
                        result['details'] = {'good': g.name, 'quantity': sale_qty, 'cash_received': trade_cash}
                        return result

        return result
