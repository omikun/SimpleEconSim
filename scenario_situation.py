"""Data-driven creditor reactions and foreign reports for authored situations."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path


EFFECT_FIELDS = frozenset({
    'confidence_delta', 'autonomy_delta', 'legitimacy_delta', 'treasury_cost',
    'payment_amount_multiplier', 'payment_due_in', 'payment_status',
    'export_fraction', 'levy_per_turn',
})


def _validate_template(data: dict) -> None:
    if data.get('format') != 'regnum.situation.v1' or not isinstance(data.get('branches'), dict):
        raise ValueError('Unsupported situation scenario format.')
    naval_rules = data.get('naval_crisis', {})
    for key in ('british_squadron_strength', 'alexandria_battery_strength',
                'battery_reinforcement_strength', 'battery_reinforcement_cost',
                'mobilization_cost', 'upkeep_per_turn', 'max_british_protest_energy',
                'max_french_protest_energy', 'minimum_force_ratio', 'settlement_fraction'):
        if not isinstance(naval_rules.get(key), (int, float)) or naval_rules[key] <= 0:
            raise ValueError(f'naval_crisis: {key} must be positive.')
    response_ids = set()
    for action_id, branch in data['branches'].items():
        reaction = branch.get('reaction')
        if not isinstance(branch.get('delay_turns'), int) or branch['delay_turns'] < 1:
            raise ValueError(f'{action_id}: delay_turns must be at least one.')
        if not isinstance(reaction, dict) or not reaction.get('headline') or not reaction.get('body'):
            raise ValueError(f'{action_id}: reaction needs a headline and body.')
        for node in [reaction] + list(reaction.get('responses', [])):
            effects = node.get('effects', {})
            if not isinstance(effects, dict) or set(effects) - EFFECT_FIELDS:
                raise ValueError(f'{action_id}: unsupported situation effect.')
        for response in reaction.get('responses', []):
            response_id = response.get('id')
            if not response_id or response_id in response_ids or not response.get('label') or not response.get('tooltip'):
                raise ValueError(f'{action_id}: response needs a unique id, label, and tooltip.')
            if float(response.get('requires_cash', 0.0)) < float(response.get('effects', {}).get('treasury_cost', 0.0)):
                raise ValueError(f'{action_id}: response cash requirement is below its cost.')
            response_ids.add(response_id)


@lru_cache(maxsize=1)
def situation_template() -> dict:
    path = Path(__file__).with_name('situation_scenario_template.json')
    with path.open(encoding='utf-8') as source:
        data = json.load(source)
    _validate_template(data)
    return data


def _egypt(world: dict):
    return next((nation for nation in world.get('nations', [])
                 if nation.name == world.get('player_nation_name')), None)


def queue_creditor_reaction(world: dict, action_id: str) -> None:
    branch = situation_template()['branches'].get(action_id)
    if branch is None:
        return
    state = world.get('scenario_state', {})
    state.setdefault('creditor_reactions', []).append({
        'action_id': action_id,
        'due_turn': int(world.get('turn', 0)) + int(branch['delay_turns']),
        'status': 'pending',
    })


def _pay_creditors(world: dict, amount: float) -> None:
    creditors = [n for n in world.get('nations', []) if n.name in ('Britain', 'France')]
    if creditors:
        for creditor in creditors:
            creditor.government.agent.cash += amount / len(creditors)


def apply_effects(world: dict, effects: dict) -> tuple[bool, str]:
    """Apply only the bounded effects supported by situation template v1."""
    nation = _egypt(world)
    if nation is None:
        return False, 'The Egyptian administration is unavailable.'
    state = world.get('scenario_state', {})
    cost = float(effects.get('treasury_cost', 0.0))
    if cost > nation.government.agent.cash:
        return False, f'The treasury needs {cost:,.0f} units for this response.'
    if cost:
        nation.government.agent.cash -= cost
        _pay_creditors(world, cost)
    for field, delta in (('creditor_confidence', effects.get('confidence_delta', 0.0)),
                         ('fiscal_autonomy', effects.get('autonomy_delta', 0.0))):
        state[field] = max(0.0, min(1.0, float(state.get(field, 0.0)) + float(delta)))
    if 'legitimacy_delta' in effects:
        nation.legitimacy = max(0.0, min(1.0, float(nation.legitimacy) + float(effects['legitimacy_delta'])))
    if 'payment_amount_multiplier' in effects:
        state['scheduled_remittance'] = round(float(state['scheduled_remittance'])
                                              * float(effects['payment_amount_multiplier']), 2)
    if 'payment_due_in' in effects:
        state['payment_window_turn'] = int(world.get('turn', 0)) + int(effects['payment_due_in'])
    if 'payment_status' in effects:
        state['payment_status'] = effects['payment_status']
        if state['payment_status'] == 'deferred':
            state['deferral_count'] = max(1, int(state.get('deferral_count', 0)))
    if 'export_fraction' in effects:
        fraction = max(0.0, min(1.0, float(effects['export_fraction'])))
        for tile in nation.tiles:
            tile.food_export_fraction = fraction
        state['domestic_grain_priority'] = fraction < 1.0
    if 'levy_per_turn' in effects:
        state['creditor_levy_per_turn'] = max(0.0, float(effects['levy_per_turn']))
        state['creditor_levy_remaining'] = (float(state.get('scheduled_remittance', 0.0))
                                             if state['creditor_levy_per_turn'] > 0 else 0.0)
    return True, ''


def advance_creditor_reactions(world: dict, turn: int, ticker_push) -> None:
    """Resolve informational replies and pause for the next demanding reply."""
    if world.get('scenario_warning_modal'):
        return
    state = world.get('scenario_state', {})
    for pending in state.get('creditor_reactions', []):
        if pending.get('status') != 'pending' or int(pending['due_turn']) > turn:
            continue
        reaction = situation_template()['branches'][pending['action_id']]['reaction']
        ok, message = apply_effects(world, reaction.get('effects', {}))
        if not ok:
            state['creditor_feedback'] = message
            continue
        headline = reaction['headline']
        state['creditor_feedback'] = f'{headline}. {reaction["body"]}'
        world['scenario_feedback'] = state['creditor_feedback']
        state.setdefault('creditor_news', []).append({'turn': turn, 'headline': headline,
                                                      'body': reaction['body']})
        ticker_push(world, turn, 'CREDITOR', state['creditor_feedback'], (225, 178, 87))
        if reaction.get('responses'):
            pending['status'] = 'awaiting_response'
            world['scenario_warning_modal'] = {
                'kind': 'creditor_reaction', 'action_id': pending['action_id'],
            }
            world['playing'] = False
            return
        pending['status'] = 'resolved'


def creditor_response_options(world: dict, action_id: str) -> list[dict]:
    reaction = situation_template()['branches'].get(action_id, {}).get('reaction', {})
    cash = float(getattr(getattr(getattr(_egypt(world), 'government', None), 'agent', None), 'cash', 0.0))
    used_plan = bool(world.get('scenario_state', {}).get('arrears_plan_used'))
    horizon = int(world.get('scenario', {}).get('horizon_turns', 20))
    arrears_response = next((response for response in reaction.get('responses', [])
                             if response['id'] == 'offer_arrears_plan'), None)
    arrears_delay = int(arrears_response.get('effects', {}).get('payment_due_in', 0)) if arrears_response else 0
    beyond_horizon = int(world.get('turn', 0)) + arrears_delay > horizon
    return [{**response, 'enabled': cash >= float(response.get('requires_cash', 0.0))
             and not (response['id'] == 'offer_arrears_plan' and (used_plan or beyond_horizon))}
            for response in reaction.get('responses', [])]


def response_label(response_id: str) -> str | None:
    for branch in situation_template()['branches'].values():
        for response in branch['reaction'].get('responses', []):
            if response['id'] == response_id:
                return response['label']
    return None


def resolve_creditor_response(world: dict, response_id: str) -> tuple[bool, str]:
    state = world.get('scenario_state', {})
    pending = next((item for item in state.get('creditor_reactions', [])
                    if item.get('status') == 'awaiting_response'), None)
    if pending is None:
        return False, 'There is no creditor demand awaiting a response.'
    options = creditor_response_options(world, pending['action_id'])
    response = next((item for item in options if item['id'] == response_id), None)
    if response is None:
        return False, 'That response is unavailable.'
    if not response['enabled']:
        if response_id == 'offer_arrears_plan' and state.get('arrears_plan_used'):
            return False, 'The Caisse will not accept another arrears plan.'
        due_delay = int(response.get('effects', {}).get('payment_due_in', 0))
        if (response_id == 'offer_arrears_plan'
                and int(world.get('turn', 0)) + due_delay > int(world.get('scenario', {}).get('horizon_turns', 20))):
            return False, 'The proposed arrears date falls after the campaign ends.'
        return False, f'The treasury needs {float(response.get("requires_cash", 0.0)):,.0f} units for this response.'
    from scenario_status import snapshot, record_change
    before = snapshot(world)
    ok, message = apply_effects(world, response.get('effects', {}))
    if not ok:
        return False, message
    record_change(world, response_id, before, snapshot(world))
    if response_id == 'offer_arrears_plan':
        state['arrears_plan_used'] = True
    pending['status'] = 'resolved'
    if response_id in ('contest_customs_claim', 'reject_revised_terms'):
        from scenario_gunboat import begin_escalation
        begin_escalation(world, response_id)
    elif response_id in ('accept_customs_control', 'offer_arrears_plan'):
        if state.get('naval_crisis', {}).get('stage') in ('mobilizing', 'ultimatum', 'blockaded'):
            from scenario_gunboat import withdraw
            withdraw(world, 'Cairo and the creditors reach terms; the naval claim is withdrawn.')
    text = f'Creditor reply: {response["label"]}.'
    state.setdefault('actions_taken', []).append({'turn': int(world.get('turn', 0)),
                                                   'action': response_id,
                                                   'message': f'{text} {response["tooltip"]}'})
    state['creditor_feedback'] = text
    world['scenario_feedback'] = text
    from client.desktop.engine import ticker_push
    ticker_push(world, int(world.get('turn', 0)), 'SCENARIO', text, (120, 220, 170))
    return True, text


def collect_creditor_levy(world: dict) -> float:
    state = world.get('scenario_state', {})
    remaining = float(state.get('creditor_levy_remaining', 0.0))
    requested = min(float(state.get('creditor_levy_per_turn', 0.0)), remaining)
    nation = _egypt(world)
    if not requested or nation is None:
        return 0.0
    paid = min(requested, max(0.0, float(nation.government.agent.cash)))
    nation.government.agent.cash -= paid
    _pay_creditors(world, paid)
    state['creditor_levy_remaining'] = round(max(0.0, remaining - paid), 2)
    if state['creditor_levy_remaining'] <= 0.01:
        state['creditor_levy_per_turn'] = 0.0
        state['payment_status'] = 'paid'
    return paid


def _foreign_snapshot(world: dict) -> dict:
    reports = {}
    for nation in world.get('nations', []):
        if nation.name not in ('Britain', 'France'):
            continue
        tiles = list(getattr(nation, 'tiles', []))
        if not tiles:
            continue
        highest = max(tiles, key=lambda tile: tile.protest_energy_log[-1]
                      if getattr(tile, 'protest_energy_log', None) else 0.0)
        energy = float(highest.protest_energy_log[-1]) if getattr(highest, 'protest_energy_log', None) else 0.0
        sources = getattr(highest, 'grievance_sources_log', [])
        raw = sources[-1].get('raw', {}) if sources else {}
        driver = max(raw, key=raw.get) if raw else 'mixed pressures'
        people = [agent for tile in tiles for agent in getattr(tile, 'agents', [])
                  if getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False)
                  and not getattr(agent, 'is_corporation', False) and not getattr(agent, 'is_trader', False)]
        hungry = sum(getattr(agent, 'hungry_steps', 0) > 0 for agent in people)
        reports[nation.name] = {
            'energy': energy,
            'region': getattr(highest, 'display_name', highest.name),
            'driver': driver.replace('_', ' '),
            'legitimacy': float(getattr(nation, 'legitimacy', 0.5)),
            'hunger': hungry / max(1, len(people)),
            'treasury': float(nation.government.agent.cash),
        }
    return reports


def update_foreign_reports(world: dict) -> None:
    state = world.get('scenario_state', {})
    previous = state.get('foreign_previous', {})
    current = _foreign_snapshot(world)
    reports = []
    for name in ('Britain', 'France'):
        if name not in current:
            continue
        info = current[name]
        energy = info['energy']
        stage = ('riot risk' if energy >= 6.5 else 'organized protests' if energy >= 4.0
                 else 'elevated unrest' if energy >= 2.0 else 'quiet')
        delta = energy - float(previous.get(name, {}).get('energy', energy))
        delta_label = '0.0' if abs(delta) < 0.05 else f'{delta:+.1f}'
        reports.append({**info, 'nation': name, 'stage': stage, 'delta': delta, 'delta_label': delta_label,
                        'summary': f'{name}: {stage} in {info["region"]} ({energy:.1f}/10, {delta_label}).',
                        'detail': f'Main measured grievance: {info["driver"]}. Hunger {info["hunger"]:.0%}; '
                                  f'legitimacy {info["legitimacy"]:.0%}; treasury {info["treasury"]:,.0f}. '
                                  'This is a foreign country report; its unrest does not determine Egypt’s breakdown.'})
    state['foreign_reports'] = reports
    state['foreign_previous'] = current
