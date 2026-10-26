"""Small playable crop-supply rivalry with named growers, two mills, and a route."""
from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

import random

import forex as fx
import sim_engine
from agent import Agent, seed_traits
from economy.map_generator import setup_capitalism_institutions
from goods import Goods
from hexmap import hex_bbox
from livelihood_access import seed_access_rights
from land_tenure import LandPlot, TenureStatus
from market_concessions import submit_concession_petition, decide_concession_petitions
from nation import Nation
from region import Region


SCENARIO_ID = 'supply_rivalry'


def _mill(region, owner, name, capital):
    mill = Agent(0)
    seed_traits(mill)
    mill.is_corporation = True
    mill.company_name = name
    mill.output = Goods.cloth
    mill.owner = owner
    mill.region = region.name
    mill.home_currency = region.home_currency
    mill._bank_ref = region.bank
    _public_write = begin_public_change(None, mill)
    mill.cash = min(float(capital), max(0.0, float(owner.cash)))
    finish_public_change(_public_write, 'scenario_supply_rivalry:_mill',
                         inputs={'source_writer': 'scenario_supply_rivalry.py:_mill:c131c323802f8ad9:1', 'semantic_operation_id': locals().get('operation_id')})
    _public_write = begin_public_change(None, owner)
    owner.cash -= mill.cash
    finish_public_change(_public_write, 'scenario_supply_rivalry:_mill',
                         inputs={'source_writer': 'scenario_supply_rivalry.py:_mill:39c131f9bade53b1:1', 'semantic_operation_id': locals().get('operation_id')})
    owner.company_owned = mill
    mill.wage = 2.0
    mill.max_employees = 5
    mill.inv_add(Goods.cotton, 2)
    mill.cost_set(Goods.cotton, 4.0)
    region.agents.append(mill)
    region.owner_nation.government._add_citizen(mill)
    from labor_contract import ensure_labor_agreement
    workers = [a for a in region.agents if a is not mill and a.alive
               and not a.is_government and not a.is_trader and not a.is_lord
               and not a.is_corporation and getattr(a, 'employer', None) is None
               and a.output != Goods.cotton][:2]
    for worker in workers:
        worker.employer = mill
        mill.employees.append(worker)
        ensure_labor_agreement(worker, mill, 0)
    return mill


def create_world(seed=812):
    random.seed(seed)
    player = Nation('Meridian', currency='Supply Crown', initial_cash=150.0)
    rival = Nation('Vesper', currency='Supply Crown', initial_cash=150.0)
    fields = Region('Cotton Fields', t=0, number_of_agents=18, number_of_traders=1)
    port = Region('Rival Port', t=0, number_of_agents=16, number_of_traders=1)
    player.add_tile(fields)
    rival.add_tile(port)
    for region in (fields, port):
        region.elevation = .12
        region.biome = 'plains'
        region.wilderness = False
        region.scenario_owner_policy = True
        setup_capitalism_institutions(region)
        region.recipes[Goods.cotton]['price'] = 4.0 if region is fields else 6.0
        region.recipes[Goods.cloth]['input'] = Goods.cotton
        region.recipes[Goods.cloth]['numInput'] = 2
        region.recipes[Goods.cloth]['production'] = 3
        region.recipes[Goods.cloth]['price'] = 13.0
    fields.canal_condition = .75
    fields.seasonal_rainfall = .8
    owners = []
    for region in (fields, port):
        holder = next(a for a in region.agents if not a.is_government
                      and not a.is_trader and not a.is_corporation)
        holder.is_lord = True
        endowment = max(0.0, 100.0 - holder.cash)
        _public_write = begin_public_change(None, region.gov.agent)
        region.gov.agent.cash -= endowment
        finish_public_change(_public_write, 'scenario_supply_rivalry:create_world',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:create_world:6513e2ae0c11eb67:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, holder)
        holder.cash += endowment
        finish_public_change(_public_write, 'scenario_supply_rivalry:create_world',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:create_world:fb71ec86752656b5:1', 'semantic_operation_id': locals().get('operation_id')})
        owners.append(holder)
    # Two real tenants keep named plots, food reserves, crop stock and unlike cash needs.
    ordinary = [a for a in fields.agents if not a.is_government and not a.is_trader
                and not a.is_lord and not a.is_corporation]
    growers = ordinary[:2]
    if len(growers) < 2:
        raise RuntimeError('Supply rivalry requires two cultivators')
    for index, grower in enumerate(growers):
        plot = LandPlot(f'cotton_plot_{index + 1}', fields.name, owners[0].id,
                        .5, TenureStatus.FEUDAL, tenant_ids=[grower.id])
        fields.tenure.plots.append(plot)
        plot.tenant_ids = [grower.id]
        grower.assigned_plot_id = plot.plot_id
        grower.output = Goods.cotton
        grower.inv_add(Goods.cotton, 3)
        grower.inv_add(Goods.food, 6 if index == 0 else 1)
        target_cash = 18.0 if index == 0 else 1.0
        _public_write = begin_public_change(None, fields.gov.agent)
        fields.gov.agent.cash -= target_cash - grower.cash
        finish_public_change(_public_write, 'scenario_supply_rivalry:create_world',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:create_world:63a8e6ef3a3197bc:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, grower)
        grower.cash = target_cash
        finish_public_change(_public_write, 'scenario_supply_rivalry:create_world',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:create_world:b695db0b1af62e0a:1', 'semantic_operation_id': locals().get('operation_id')})
        grower.display_name = 'Amina, secure grower' if index == 0 else 'Binta, cash-poor grower'
    seed_access_rights(fields)
    seed_access_rights(port)
    home_owner, rival_owner = owners
    domestic = _mill(fields, home_owner, 'Meridian Mill', 70)
    competing = _mill(port, rival_owner, 'Vesper Mill', 75)
    fields.add_neighbor(port)
    port.add_neighbor(fields)
    petition = submit_concession_petition(domestic, fields, Goods.cotton,
                                           'exclusive_buying', 10, 8, 0)
    if petition:
        petition['player_review'] = True
        petition['decision_turn'] = 2
    layout = {fields.name: (0, 0), port.name: (1, 0)}
    world = {'scenario_id': SCENARIO_ID, 'player_nation_name': player.name,
             'tiles': [fields, port], 'nations': [player, rival],
             'grid': [[fields, port]], 'layout': layout, 'bbox': hex_bbox(layout, 48),
             'by_name': {r.name: r for r in (fields, port)},
             'pair_orders': [(fields, port), (port, fields)],
             'currencies': [player.currency], 'turn': 0, 'playing': False,
             'events': [], 'scenario_state': {
                 'grower_ids': [a.id for a in growers], 'domestic_mill_id': domestic.id,
                 'rival_mill_id': competing.id, 'major_action_turn': -1,
                 'timeline': [], 'ending': False},
             'currency_totals': {player.currency: fx.audit_currency_total([fields, port], player.currency)}}
    return world


def _actor(region, ident):
    return next((a for a in region.agents if a.id == ident and a.alive), None)


def apply_action(world, action_id):
    """A funded public response; charter approval uses the existing petition command."""
    fields = world['by_name']['Cotton Fields']
    state = world['scenario_state']
    turn = int(world['turn'])
    if state.get('major_action_turn') == turn or state.get('ending'):
        return False, 'One major decision is available per turn.'
    treasury = fields.gov.agent
    growers = [_actor(fields, ident) for ident in state['grower_ids']]
    if action_id == 'repeal_charter':
        charter = next((c for c in getattr(fields, 'market_charters', [])
                        if c.get('status') == 'active'), None)
        if charter is None:
            return False, 'No active buying charter can be repealed.'
        charter['status'] = 'repealed'
        event = {'turn': turn, 'charter_id': charter['id'], 'status': 'repealed',
                 'reason': 'player_government_repeal', 'good': charter['good']}
        fields.concession_events = (getattr(fields, 'concession_events', []) + [event])[-500:]
        from run_trace import emit
        emit(fields, kind='market_concession_decision', record_class='outcome',
             subject={'type': 'charter', 'id': charter['id']},
             metric_id='market.charter_status', unit='status', after='repealed',
             formula_id='charter.player_repeal.v1', inputs=event)
        message = 'Meridian repealed the buying charter; rival bids can return next auction.'
    elif action_id in ('approve_charter', 'reject_charter'):
        petition = next((p for p in getattr(fields, 'concession_petitions', [])
                         if p['status'] == 'proposed' and p.get('player_review')), None)
        if petition is None or turn > petition['decision_turn']:
            return False, 'No live charter petition awaits the government.'
        petition['player_decision'] = 'approve' if action_id == 'approve_charter' else 'reject'
        petition['decision_turn'] = turn
        decide_concession_petitions(fields, turn)
        message = ('Meridian approved exclusive cotton buying rights.'
                   if action_id == 'approve_charter' else
                   'Meridian rejected exclusive cotton buying rights.')
    elif action_id == 'public_crop_purchase':
        grower = next((a for a in growers if a is not None and a.inv_get(Goods.cotton, 0) >= 2), None)
        price = float(fields.recipes[Goods.cotton]['price']) * 1.1
        cost = 2 * price
        if grower is None or treasury.cash < cost:
            return False, 'Needs a grower with two unpledged cotton units and a funded treasury.'
        pledged = sum(c.get('remaining', 0) for c in getattr(fields, 'offtake_contracts', [])
                      if c.get('status') == 'active' and c.get('grower_id') == grower.id)
        if grower.inv_get(Goods.cotton, 0) - pledged < 2:
            return False, 'This crop is already pledged.'
        _public_write = begin_public_change(None, treasury)
        treasury.cash -= cost
        finish_public_change(_public_write, 'scenario_supply_rivalry:apply_action',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:apply_action:77fdfcd20dd67727:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, grower)
        grower.cash += cost
        finish_public_change(_public_write, 'scenario_supply_rivalry:apply_action',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:apply_action:307930d6b9f3cda4:1', 'semantic_operation_id': locals().get('operation_id')})
        grower.inv_add(Goods.cotton, -2)
        treasury.inv_add(Goods.cotton, 2)
        from economy.actor_accounts import record
        record(fields, 'public_crop_purchase', turn=turn, payer_id=treasury.id,
               recipient_id=grower.id, good=Goods.cotton, quantity=2,
               amount=cost, detail={'unit_price': price})
        message = f'Public buyer paid {grower.display_name} ${cost:.2f} for 2 cotton; public stores gained 2.'
    elif action_id == 'fund_irrigation':
        builder = next((a for a in fields.agents if a.alive and not a.is_government
                        and not a.is_corporation and not a.is_trader and a not in growers), None)
        if builder is None or treasury.cash < 12 or fields.canal_condition >= 1:
            return False, 'Needs a builder, $12 public cash, and a canal below full condition.'
        _public_write = begin_public_change(None, treasury)
        treasury.cash -= 12
        finish_public_change(_public_write, 'scenario_supply_rivalry:apply_action',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:apply_action:b25576d57cda2883:1', 'semantic_operation_id': locals().get('operation_id')})
        _public_write = begin_public_change(None, builder)
        builder.cash += 12
        finish_public_change(_public_write, 'scenario_supply_rivalry:apply_action',
                             inputs={'source_writer': 'scenario_supply_rivalry.py:apply_action:a941bc7691c7c06a:1', 'semantic_operation_id': locals().get('operation_id')})
        fields.canal_condition = min(1.0, fields.canal_condition + .2)
        from economy.actor_accounts import record
        record(fields, 'irrigation_work', turn=turn, payer_id=treasury.id,
               recipient_id=builder.id, amount=12,
               detail={'canal_condition_after': fields.canal_condition})
        message = f'Public works paid a local builder $12; canal condition rose to {fields.canal_condition:.2f}.'
    else:
        return False, 'Unknown supply decision.'
    state['major_action_turn'] = turn
    state['timeline'] = (state.get('timeline', []) +
                         [{'turn': turn, 'text': message}])[-20:]
    return True, message


def advance_after_engine(world, turn):
    """Review corporate input strategy after settled observations, every five turns."""
    world['turn'] = turn
    fields, port = world['tiles']
    for region, ident in ((fields, world['scenario_state']['domestic_mill_id']),
                          (port, world['scenario_state']['rival_mill_id'])):
        firm = _actor(region, ident)
        if firm is not None and (turn == 1 or turn % 5 == 0):
            if not hasattr(region, 'elite_planner'):
                from economy.capitalist_planner import EliteCapitalistPlanner
                region.elite_planner = EliteCapitalistPlanner()
            region.elite_planner._execute_input_control(firm, region, turn)
    if turn >= 20:
        world['scenario_state']['ending'] = True


def step_world(world):
    if world['scenario_state'].get('ending'):
        return []
    turn = int(world['turn']) + 1
    violations, _ = sim_engine.step_turn(turn, world['tiles'], nations=world['nations'],
                                          pair_orders=world['pair_orders'],
                                          currencies=world['currencies'], ledger_exempt=True)
    advance_after_engine(world, turn)
    world['currency_totals'] = {c: fx.audit_currency_total(world['tiles'], c)
                                for c in world['currencies']}
    return violations


def project(world):
    fields, port = world['tiles']
    state = world['scenario_state']
    domestic = _actor(fields, state['domestic_mill_id'])
    rival = _actor(port, state['rival_mill_id'])
    growers = [_actor(fields, ident) for ident in state['grower_ids']]
    grower_names = [g.display_name if g else 'Departed grower' for g in growers]
    grower_cash = [round(g.cash, 1) if g else 0 for g in growers]
    food = [g.inv_get(Goods.food, 0) if g else 0 for g in growers]
    recent = [e for e in getattr(fields, 'market_trade_events', [])
              if e['good'] == Goods.cotton.name and e['turn'] == world['turn']]
    units = sum(e['quantity'] for e in recent)
    paid = sum(e['total_paid'] for e in recent) / units if units else None
    petition = next((p for p in getattr(fields, 'concession_petitions', [])
                     if p['status'] == 'proposed' and p.get('player_review')), None)
    domestic_input_fills = sum(e['quantity'] for e in recent
                               if domestic and e['buyer_id'] == domestic.id)
    rival_input_fills = sum(e['quantity'] for e in getattr(port, 'market_trade_events', [])
                            if rival and e['turn'] == world['turn']
                            and e['good'] == Goods.cotton.name and e['buyer_id'] == rival.id)
    cards = [
        {'title': 'Cotton market', 'value': (f'{units} paid units @ ${paid:.2f}' if paid is not None else 'No paid cotton fill yet'),
         'cause': (f'Meridian quote ${fields.recipes[Goods.cotton]["price"]:.2f}; rival route reaches Vesper at ${port.recipes[Goods.cotton]["price"]:.2f}.'
                   + (f' Charter decision due turn {petition["decision_turn"]}.' if petition else '')),
         'tone': 'warning' if not units else 'good'},
        {'title': 'Grower livelihoods', 'value': f'{grower_names[0]} ${grower_cash[0]}, food {food[0]} · {grower_names[1]} ${grower_cash[1]}, food {food[1]}',
         'cause': 'An advance helps liquidity but pledges a future crop; sellers may reject or counter offers.',
         'tone': 'urgent' if min(food) < 2 else 'good'},
        {'title': 'Industry and rival', 'value': f'Cotton filled: Meridian {domestic_input_fills} vs Vesper {rival_input_fills}' if domestic and rival else 'Mill status changed',
         'cause': (f'Mill cash: Meridian ${domestic.cash:.0f}, Vesper ${rival.cash:.0f}. Paid fills and payroll determine output.'
                   if domestic and rival else 'A mill is unavailable.'),
         'tone': 'warning' if domestic and rival and domestic.cash < rival.cash else 'good'},
    ]
    spent = state.get('major_action_turn') == world['turn']
    actions = [
        {'id': 'public_crop_purchase', 'label': 'Buy crop for public stores',
         'detail': 'Pay a named grower for two existing cotton units; public stores receive the crop.',
         'enabled': not spent and any(g and g.inv_get(Goods.cotton, 0) >= 2 for g in growers)
                    and fields.gov.agent.cash >= 2 * fields.recipes[Goods.cotton]['price'] * 1.1,
         'reason': 'Requires unpledged crop, funded treasury, and an unused decision this turn.'},
        {'id': 'fund_irrigation', 'label': 'Fund canal repairs',
         'detail': 'Pay $12 to a local builder; better canal condition increases seasonal water supply.',
         'enabled': not spent and fields.gov.agent.cash >= 12 and fields.canal_condition < 1,
         'reason': 'Requires $12, a damaged canal, and an unused decision this turn.'},
    ]
    if petition:
        actions = [
            {'id': 'approve_charter', 'label': 'Approve buying charter',
             'detail': 'Limit rival cotton bids for eight turns; enforcement and grower opposition are uncertain.',
             'enabled': not spent and world['turn'] <= petition['decision_turn'],
             'reason': 'Petition deadline passed or one decision already used.'},
            {'id': 'reject_charter', 'label': 'Keep cotton buying open',
             'detail': 'Rival buyers may bid for crop; growers retain another outlet.',
             'enabled': not spent and world['turn'] <= petition['decision_turn'],
             'reason': 'Petition deadline passed or one decision already used.'},
        ] + actions
    active_charter = any(c.get('status') == 'active'
                         for c in getattr(fields, 'market_charters', []))
    if active_charter:
        actions.append({'id': 'repeal_charter', 'label': 'Repeal buying charter',
                        'detail': 'End exclusive buying before expiry; the original fee stays spent.',
                        'enabled': not spent, 'reason': 'One decision already used this turn.'})
    if state.get('ending'):
        for action in actions:
            action['enabled'] = False
            action['reason'] = 'Scenario ended.'
    return {'scenario_name': 'Cotton Supply Rivalry',
            'mandate': 'Secure inputs and compete with Vesper while preserving named growers and public legitimacy.',
            'turn': world['turn'], 'horizon_turns': 20,
            'countdown_turns': max(0, 20 - world['turn']),
            'pressures': cards, 'actions': actions,
            'timeline': state.get('timeline', [])[-8:],
            'petition_deadline': petition['decision_turn'] if petition else None,
            'districts': [{'name': r.name, 'owner': r.owner_nation.name,
                           'people': len([a for a in r.agents if a.alive]),
                           'units': 0, 'commons_rights': 0} for r in (fields, port)],
            'major_action_spent': spent, 'ending': bool(state.get('ending')),
            'debrief': None,
            'active': True}
