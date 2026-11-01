"""Read-only previews and existing action routing for the governing view."""

from goods import Goods
from nutrition import deficit_fraction
from governing_network import is_governing


def project_actions(world):
    if not is_governing(world):
        raise ValueError('Policy previews require a governing-mode campaign.')
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    state, cash = world['scenario_state'], float(nation.government.agent.cash)
    econ = state['political_economy']
    public = int(nation.government.food_inventory)
    held, offers = 0, []
    for tile in nation.tiles:
        holder = next((p for p in tile.agents if p.id == econ['warehouse_by_tile'].get(tile.name)
                       and getattr(p, 'alive', True)), None)
        units = max(0, min(int(econ['private_reserve_by_tile'].get(tile.name, 0)),
                           int(holder.inv_get(Goods.food, 0)) if holder else 0))
        held += units
        offers.append((units, max(.25, float(tile.recipes.get(Goods.food, {}).get('price', 1.))) * 1.2))
    remaining, budget, purchased, paid = min(held, 80), cash, 0, 0.
    for units, price in offers:
        take = max(0, min(units, remaining, int(budget / price)))
        purchased += take
        paid += take * price
        budget -= take * price
        remaining -= take
    hungry = sum(deficit_fraction(p) > 0 for tile in nation.tiles for p in tile.agents
                 if getattr(p, 'alive', True) and not getattr(p, 'is_government', False)
                 and not getattr(p, 'is_corporation', False) and not getattr(p, 'is_trader', False))
    meals = min(hungry, public // 4, int(state['relief_units_per_turn']))
    spent = state.get('last_action_turn') == int(world['turn'])
    ended = bool(state.get('ending'))

    def option(action, label, detail, consequence, available, reason='', tile=None):
        enabled = available and not spent and not ended
        return dict(id=action, label=label, detail=detail, consequence=consequence,
                    enabled=enabled, tile=tile,
                    reason=('Campaign ended.' if ended else 'One decision is already recorded this turn.'
                            if spent else reason))

    food = [
        option('release_maize', 'Distribute maize', f'{meals} households · {meals * 4} maize',
               'Fund next-turn meals', meals > 0, 'Needs public maize and underfed households.'),
        option('buy_private_grain', 'Buy private maize', f'{purchased} maize · {paid:.1f} treasury',
               'Then distribute it', purchased > 0, 'No affordable reserved maize.'),
        option('requisition_private_grain', 'Requisition maize', f'{min(80, held)} maize · no payment',
               'Owners lose their stocks', held > 0, 'No reserved private maize.'),
        option('open_private_grain_market', 'Open private sales', f'{held} maize currently reserved',
               'Buyers still need cash', econ['grain_policy'] != 'open', 'Standing private sales are already open.'),
    ]
    from governing_network import project
    disputes = project(world)['disputes']
    responses = {}
    for dispute in disputes:
        tile = next(t for t in nation.tiles if t.name == dispute['tile'])
        if dispute['id'] == 'arrears':
            ids = set(state['governing_network']['observation']['districts'][tile.name]['members']['households'])
            arrears = sum(row['balance'] for pid, row in econ['arrears'].items() if pid in ids)
            responses['arrears'] = option('district_arrears_relief', 'Forgive local tax arrears',
                f'Write off {arrears:.1f} in {dispute["name"]}', 'Future tax receipts fall',
                arrears > 0, 'No current local arrears.', tile=tile.name)
        else:
            owners = [a for a in tile.agents if getattr(a, 'alive', True)
                      and (getattr(a, 'is_corporation', False) or getattr(a, 'is_lord', False))]
            payment = sum(min(5., max(0., float(a.cash)) * .02) for a in owners)
            responses['food'] = option('district_bargain_workers', 'Seek funded worker terms',
                f'Owners pay {payment:.1f} in {dispute["name"]}', 'People may reject the offer',
                payment > 0, 'Local owners cannot fund a payment.', tile=tile.name)
    debt = []
    if (int(world['turn']) >= int(state['payment_window_turn'])
            and state['payment_status'] in ('upcoming', 'unpaid')):
        amount = float(state['scheduled_remittance'])
        from scenario_situation import situation_template
        rules = situation_template()['debt_rules']
        from scenario_egypt_1877 import campaign_horizon
        can_defer = (state.get('deferral_count', 0) < rules['maximum_deferrals']
                     and int(world['turn']) + rules['deferral_delay_turns'] <= campaign_horizon(world))
        debt = [option('pay_remittance', 'Pay debt service', f'{amount:.0f} treasury',
                       'Protect creditor relations', cash >= amount, 'Treasury cannot cover payment.'),
                option('concede_revenue', 'Concede revenue', f'{amount * .5:.0f} treasury',
                       'Accept foreign oversight', cash >= amount * .5, 'Treasury cannot cover concession.'),
                option('defer_remittance', 'Defer debt service', 'Surcharge and later payment',
                       'Creditors lose confidence', can_defer, 'No further deferral is available.'),
                option('default_remittance', 'Default on debt', 'Keep treasury cash',
                       'Legitimacy & creditor loss', True)]
    return dict(food=food, responses=responses, debt=debt, treasury=cash,
                public_maize=public, private_maize=held, spent=spent,
                payment_status=state['payment_status'], due_turn=state['payment_window_turn'],
                purchase_quote={'units': purchased, 'treasury_cost': paid},
                release_quote={'households': meals, 'food_units': meals * 4})


def execute(world, action_id, tile_id=None):
    if not is_governing(world):
        return False, 'Start a governing-mode campaign to use this view.'
    nation = next(n for n in world['nations'] if n.name == 'Egypt')
    target = next((t for t in nation.tiles if t.name == tile_id), None) if tile_id else None
    if tile_id is not None and target is None:
        return False, 'That district is outside the Egyptian government\'s authority.'
    old = world.get('selected_region')
    try:
        if target is not None:
            world['selected_region'] = target
        from scenario_egypt_1877 import apply_action
        return apply_action(world, action_id)
    finally:
        world['selected_region'] = old
