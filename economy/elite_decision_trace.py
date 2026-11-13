"""Evidence and state snapshots for one elite decision; never selects actions."""
import math
from goods import Goods
from run_trace import emit
from economy.operator_valuation import return_basis
from economy.elite_machinery import machinery_target


def trace_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else str(number)
    except (TypeError, ValueError, OverflowError):
        return str(value)


def trace_payload(value):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return trace_number(value)
    if isinstance(value, dict):
        return {str(key): trace_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [trace_payload(item) for item in value]
    return str(value)


class EliteDecisionTrace:
    def __init__(self, decision):
        self.agent = decision.agent
        self.region = decision.region
        self.turn = decision.turn
        self.shadow_cash = decision.shadow_cash
        self.result = decision.result
        self.enabled = decision.trace_enabled

    def stage_snapshot(self, operator, *, execution=False):
        if not self.enabled:
            return None
        return self.operator_state_snapshot(operator, include_recipients=execution)

    def record_luxury_decision(self, candidate_rows, selected_good, reason):
        if not self.enabled:
            return None
        trace_recorder = getattr(self.region, '_run_trace', None)
        cause_ids = [row['price_trace_event_id'] for row in candidate_rows
                     if row.get('price_trace_event_id') is not None]
        event_id = emit(
            self.region, kind='elite_luxury_purchase_evaluation',
            record_class='decision', phase='local',
            subject={'type': 'agent', 'id': self.agent.id,
                     'tile': getattr(self.region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='luxury_purchase',
            after=(selected_good if selected_good is not None else reason),
            formula_id='elite.luxury_purchase_priority.v1',
            cause_event_ids=cause_ids or None,
            inputs=trace_payload({
                'turn': int(self.turn), 'cash_before': float(self.agent.cash),
                'minimum_cash_gate': 25.0,
                'cash_gate_passed': bool(self.agent.cash >= 25.0),
                'candidate_evaluations': candidate_rows,
                'selection_order': 'descending prestige / max(1, price)',
                'selection_rule': 'first affordable good with another live stocked seller',
                'selected_good': selected_good,
                'selection_reason': reason}))
        return event_id


    def operator_return_basis(self, operator):
        return return_basis(operator, self.agent, self.region, self.shadow_cash)


    def operator_prerequisite_basis(self, operator):
        operator_id = str(operator.id)
        if operator_id == 'maintain_repair_machinery':
            target = machinery_target(self.agent, self.region, broken_only=True, minimum_sponsor_cash=20.0)
            return {'target_firm_id': (str(target.id) if target is not None else None),
                    'broken_machinery': (int(getattr(target, 'broken_machinery', 0))
                                         if target is not None else 0),
                    'required_broken_machinery_minimum': 1}
        if operator_id == 'construct_machinery':
            target = machinery_target(self.agent, self.region, minimum_sponsor_cash=60.0)
            iron_price = float(getattr(self.region, 'recipes', {}).get(
                Goods.iron, {}).get('price', 5.0))
            coal_price = float(getattr(self.region, 'recipes', {}).get(
                Goods.coal, {}).get('price', 3.0))
            required_cash = 25.0 + (2.0 * iron_price) + coal_price
            return {
                'target_firm_id': (str(target.id) if target is not None else None),
                'owner_cash': float(self.agent.cash),
                'target_firm_cash': (float(target.cash)
                                     if target is not None and target is not self.agent else 0.0),
                'combined_cash': (float(self.agent.cash)
                                  + (float(target.cash)
                                     if target is not None and target is not self.agent else 0.0)),
                'required_cash_before_inventory_credit': required_cash,
                'required_materials': {'iron': 2.0, 'coal': 1.0},
                'material_prices': {'iron': iron_price, 'coal': coal_price}}
        return None


    def record_operator_gate(self, operator, *, stage, can_execute, reason,
                             net_return=None, threshold=None,
                             selected_for_execution=False,
                             execution_result=None, state_before=None,
                             selected_action=None,
                             planner_cash_gate_threshold=None,
                             planner_cash_gate_passed=None):
        if not self.enabled:
            return None
        trace_return = None
        if net_return is not None:
            try:
                candidate_return = float(net_return)
                if math.isfinite(candidate_return):
                    trace_return = candidate_return
            except (TypeError, ValueError, OverflowError):
                pass
        event_id = emit(
            self.region, kind='elite_operator_evaluation', record_class='decision',
            phase='local', subject={'type': 'agent', 'id': self.agent.id,
                                    'tile': getattr(self.region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='operator_gate',
            after=(selected_action if selected_action else
                   'selected_for_execution' if selected_for_execution else
                   'not_selected'),
            formula_id='elite.transformation_operator_gate.v1',
            inputs={'stage': stage, 'operator_id': str(operator.id),
                    'operator_name': str(operator.name),
                    'operator_category': str(operator.category),
                    'can_execute': bool(can_execute),
                    'feasibility_reason': str(reason),
                    'cash_before': float(self.agent.cash if state_before is None
                                         else state_before.get('cash', self.agent.cash)),
                    'cash_cost': float(operator.cash_cost),
                    'shadow_price_cash': float(self.shadow_cash),
                    'estimated_net_return': trace_return,
                    'return_basis': (self.operator_return_basis(operator)
                                     if net_return is not None else None),
                    'prerequisite_basis': self.operator_prerequisite_basis(operator),
                    'strict_return_threshold': threshold,
                    'planner_cash_gate_threshold': planner_cash_gate_threshold,
                    'planner_cash_gate_passed': planner_cash_gate_passed,
                    'selection_reason': (
                        'return_gate_passed' if selected_for_execution and threshold is not None else
                        'feasible_action' if selected_for_execution else
                        'operator_ineligible' if not can_execute else
                        'estimated_return_not_above_strict_threshold'),
                    'return_gate_passed': (bool(selected_for_execution)
                                           if threshold is not None else None),
                    'selected_for_execution': bool(selected_for_execution),
                    'execution_result': execution_result,
                    'state_before': state_before})
        if event_id is not None:
            self.result['evaluation_event_ids'].append(event_id)
        return event_id


    def record_operator_execution(self, operator, *, stage, evaluation_event_id,
                                  execution_result, cash_before, state_before):
        crop = {'corvee_cotton_plantation': Goods.cotton,
                'corvee_sugar_plantation': Goods.sugar}.get(operator.id)
        if crop is not None and execution_result and execution_result.get('success'):
            quantity = max(0.0, float(execution_result.get(
                'yield', execution_result.get('yield_received', 0.0)) or 0.0))
            if getattr(self.region, 'emission_production_turn', None) != self.turn:
                self.region.emission_production_turn = self.turn
                self.region.emission_production = {}
            self.region.emission_production[crop] = self.region.emission_production.get(crop, 0) + quantity
        if not self.enabled:
            return None
        cash_after = float(self.agent.cash)
        event_id = emit(
            self.region, kind='elite_operator_execution', record_class='outcome',
            phase='local', subject={'type': 'agent', 'id': self.agent.id,
                                    'tile': getattr(self.region, 'name', 'default')},
            metric_id='ai.elite_economic_decision', unit='operator_action',
            before=cash_before, after=cash_after,
            cause_event_ids=([evaluation_event_id]
                             if evaluation_event_id is not None else None),
            inputs={'stage': stage, 'operator_id': str(operator.id),
                    'execution_result': execution_result,
                    'state_before': state_before,
                    'state_after': self.operator_state_snapshot(
                        operator, include_tenure=(stage == 'lord_transformation'),
                        include_recipients=True)})
        if event_id is not None:
            self.result['execution_event_ids'].append(event_id)
        return event_id


    def operator_state_snapshot(self, operator=None, *, include_tenure=False, include_recipients=False):
        commoners = [
            person for person in getattr(self.region, 'agents', [])
            if getattr(person, 'alive', True)
            and not getattr(person, 'is_lord', False)
            and not getattr(person, 'is_corporation', False)
            and not getattr(person, 'is_government', False)
            and not getattr(person, 'is_trader', False)]
        gov_agent = getattr(getattr(self.region, 'gov', None), 'agent', None)
        tracked_goods = [Goods.rum, Goods.cloth, Goods.cotton,
                         Goods.tobacco, Goods.iron_ore, Goods.iron,
                         Goods.coal, Goods.wood, Goods.sugar, Goods.wool]
        if operator is not None:
            for good in (*getattr(operator, 'input_goods', {}).keys(),
                         *getattr(operator, 'output_goods', {}).keys()):
                if good not in tracked_goods:
                    tracked_goods.append(good)
        firms = [person for person in getattr(self.region, 'agents', [])
                 if getattr(person, 'is_corporation', False)]
        owner_company = getattr(self.agent, 'company_owned', None)
        if owner_company is not None and all(owner_company is not firm for firm in firms):
            firms.append(owner_company)
        if getattr(self.agent, 'is_corporation', False) and all(self.agent is not firm for firm in firms):
            firms.append(self.agent)
        state = {
            'cash': float(self.agent.cash),
            'tracked_inventory': {
                getattr(good, 'name', str(good)): float(self.agent.inv_get(good, 0))
                for good in tracked_goods},
            'frontier_estates': [
                {'target_region': str(estate.get('target_region', '')),
                 'primary_commodity': str(estate.get('primary_commodity', '')),
                 'captive_labor': int(estate.get('captive_labor', 0))}
                for estate in getattr(self.agent, 'frontier_estates', [])],
            'firm_state': [
                {'agent_id': str(getattr(firm, 'id', 'unknown')),
                 'cash': float(getattr(firm, 'cash', 0.0)),
                 'machinery_level': int(getattr(firm, 'machinery_level', 0)),
                 'broken_machinery': int(getattr(firm, 'broken_machinery', 0)),
                 'machinery_wear': float(getattr(firm, 'machinery_wear', 0.0)),
                 'max_employees': int(getattr(firm, 'max_employees', 0)),
                 'iron_inventory': float(firm.inv_get(Goods.iron, 0)),
                 'coal_inventory': float(firm.inv_get(Goods.coal, 0))}
                for firm in firms],
            'lord_tenure_plots': ([
                {'plot_id': str(getattr(plot, 'plot_id', '')),
                 'lord_id': str(getattr(plot, 'lord_id', '')),
                 'tenure': str(getattr(getattr(plot, 'tenure', None), 'value',
                                       getattr(plot, 'tenure', ''))),
                 'production_type': str(getattr(plot, 'production_type', ''))}
                for plot in getattr(getattr(self.region, 'tenure', None), 'plots', [])
                if getattr(plot, 'lord_id', None) == self.agent.id]
                if include_tenure or (operator is not None
                   and str(getattr(operator, 'id', '')) == 'enclose_plot_for_pasture')
                else []),
            'commoner_cash_summary': {
                'recipient_count': len(commoners),
                'aggregate_cash': sum(float(getattr(person, 'cash', 0.0))
                                      for person in commoners)},
            'government_cash': (float(gov_agent.cash)
                                if gov_agent is not None else None)}
        if include_recipients:
            state['commoner_cash'] = [
                {'agent_id': str(getattr(person, 'id', 'unknown')),
                 'cash': float(getattr(person, 'cash', 0.0))} for person in commoners]
        return state




def record_decision_outcome(agent, region, t, result, cash_before, cash_after):
    """Publish the action decision and observed outcome without fabricating cash."""
    reported_details = result.get('details', {})
    scalar_details = {str(key): value for key, value in reported_details.items()
                      if value is None or isinstance(value, (str, int, float, bool))}
    subject = {'type': 'agent', 'id': agent.id, 'tile': region.name}
    decision_id = emit(region, kind='corporation_ai_decision', record_class='decision',
                       phase='local', subject=subject,
                       metric_id='ai.elite_economic_decision', unit='candidate_plan',
                       after=result.get('action_taken') or 'do_nothing',
                       cause_event_ids=(result.get('evaluation_event_ids') or None),
                       inputs={'opening_cash': cash_before,
                               'preflight_snapshot_status': (
                                   'omitted; live planner records its actual '
                                   'evaluations once'),
                               'actual_consideration_order': [
                                   'local_luxury_purchase', 'triangular_trade_voyage',
                                   'spatial_trade', 'class_legislation',
                                   *(['lord_transformation']
                                     if getattr(agent, 'is_lord', False) else []),
                                   'repair_machinery', 'construct_machinery',
                                   'supply_control', 'plantation_labor_gang',
                                   'procure_captive_labor', 'frontier_conquest',
                                   'capital_expansion_or_incorporation',
                                   'inventory_liquidation', 'do_nothing'],
                               'selected': result.get('action_taken') or 'do_nothing',
                               'shadow_cash_price': result.get('shadow_price_cash'),
                               'operator_execution_event_ids': (
                                   result.get('execution_event_ids') or []),
                               'neighbors': sorted(getattr(region, 'neighbors', {}).keys())})
    emit(region, kind='corporation_ai_outcome', record_class='outcome',
         phase='local', subject=subject, metric_id='economy.cash',
         unit=getattr(region, 'home_currency', 'local_currency'),
         before=cash_before, after=cash_after,
         decision_id=decision_id,
         cause_event_ids=(result.get('evaluation_event_ids', [])
                          + result.get('execution_event_ids', [])) or None,
         inputs={'action': result.get('action_taken') or 'do_nothing',
                 'details': scalar_details,
                 'omitted_detail_keys': sorted(str(key) for key, value in reported_details.items()
                                               if value is not None and not isinstance(value, (str, int, float, bool)))})
