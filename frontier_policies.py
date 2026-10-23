"""Funded policy actions for frontier settlement."""

from __future__ import annotations
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish


EXPEDITION_PIONEERS = 5
EXPEDITION_GRANT_PER_PIONEER = 20.0


def launch_frontier_expedition(world, target):
    """Spend a sovereign grant to establish five frontier homesteaders."""
    nations = world.get('nations') or ()
    sponsor_nation = nations[0] if nations else None
    sponsor_government = getattr(sponsor_nation, 'government', None)
    treasury = getattr(sponsor_government, 'agent', None)
    currency = getattr(sponsor_nation, 'currency', None)
    total_cost = EXPEDITION_PIONEERS * EXPEDITION_GRANT_PER_PIONEER
    turn = int(world.get('turn', 0))

    if sponsor_nation is None or treasury is None or not currency:
        world['policy_feedback'] = (
            'Cannot launch expedition: sponsor treasury or currency is unavailable.',
            (240, 80, 80))
        return False

    treasury_before = float(treasury.cash)
    if treasury_before < total_cost:
        world['policy_feedback'] = (
            f'Insufficient Treasury: Requires {total_cost:.0f} {currency} '
            f'(Current: {treasury_before:.0f} {currency}).', (240, 80, 80))
        from run_trace import emit
        emit(target, kind='frontier_expedition_denied', record_class='outcome',
             phase='policy',
             subject={'type': 'frontier', 'id': target.name},
             metric_id='finance.frontier_expedition', unit=currency,
             before=treasury_before, after=treasury_before,
             inputs={'sponsor_nation': sponsor_nation.name,
                     'required_cost': total_cost,
                     'available_treasury': treasury_before,
                     'reason': 'insufficient_treasury'})
        return False

    sponsor_tiles = tuple(getattr(sponsor_nation, 'tiles', ()) or ())
    source_region = next(
        (region for region in sponsor_tiles
         if treasury in getattr(region, 'agents', ())),
        sponsor_tiles[0] if sponsor_tiles else target)
    expedition_number = int(getattr(target, '_frontier_expedition_count', 0)) + 1
    target._frontier_expedition_count = expedition_number
    expedition_id = f'{sponsor_nation.name}:{target.name}:{turn}:{expedition_number}'

    from agent import Agent, initialize_agent, seed_traits
    from economy.actor_accounts import record as record_economic_event
    from forex import fx_add, fx_balance
    from wilderness import enter_wilderness
    from goods import Goods
    from run_trace import emit

    for _ in range(EXPEDITION_PIONEERS):
        pioneer = Agent(turn)
        initialize_agent(pioneer, Goods.food, 0, 2, 0.0)
        seed_traits(pioneer)
        pioneer.origin_nation = sponsor_nation.name
        enter_wilderness(target, pioneer, turn)

        wallet_before = float(fx_balance(pioneer, currency))
        fx_add(pioneer, currency, EXPEDITION_GRANT_PER_PIONEER)
        wallet_after = float(fx_balance(pioneer, currency))
        treasury_cash_before = float(treasury.cash)
        _trace_cash_write = _trace_public_begin(None, treasury)
        treasury.cash -= EXPEDITION_GRANT_PER_PIONEER
        _trace_public_finish(_trace_cash_write, 'frontier_policies:launch_frontier_expedition',
                             inputs={"source_writer": 'frontier_policies.py:launch_frontier_expedition:745f4d6cdbe1facb:1'})
        treasury_cash_after = float(treasury.cash)
        grant_id = f'{expedition_id}:{pioneer.id}'
        detail = {'expedition_id': expedition_id, 'grant_id': grant_id,
                  'sponsor_nation': sponsor_nation.name,
                  'source_region': getattr(source_region, 'name', None),
                  'destination_region': target.name,
                  'pioneer_id': pioneer.id,
                  'grant_currency': currency,
                  'grant_amount': EXPEDITION_GRANT_PER_PIONEER,
                  'treasury_cash_before': treasury_cash_before,
                  'treasury_cash_after': treasury_cash_after,
                  'pioneer_wallet_before': wallet_before,
                  'pioneer_wallet_after': wallet_after,
                  'reason': 'frontier_expedition'}
        record_economic_event(
            source_region, 'frontier_expedition_spending', turn=turn,
            payer_id=treasury.id, amount=EXPEDITION_GRANT_PER_PIONEER,
            asset_id=grant_id, source_id=expedition_id, currency=currency,
            detail=detail)
        record_economic_event(
            target, 'foreign_wallet_grant', turn=turn,
            recipient_id=pioneer.id, amount=EXPEDITION_GRANT_PER_PIONEER,
            asset_id=grant_id, source_id=expedition_id, currency=currency,
            detail=detail)
        emit(target, kind='frontier_pioneer_grant', record_class='transfer',
             phase='policy',
             subject={'type': 'frontier_pioneer', 'id': pioneer.id,
                      'tile': target.name, 'sponsor': sponsor_nation.name},
             metric_id='finance.frontier_expedition', unit=currency,
             before=treasury_cash_before, after=treasury_cash_after,
             inputs={'expedition_id': expedition_id, 'grant_id': grant_id,
                     'source_region': getattr(source_region, 'name', None),
                     'destination_region': target.name,
                     'treasury_id': treasury.id,
                     'treasury_cash_before': treasury_cash_before,
                     'treasury_cash_after': treasury_cash_after,
                     'pioneer_id': pioneer.id,
                     'grant_amount': EXPEDITION_GRANT_PER_PIONEER,
                     'wallet_currency': currency,
                     'wallet_before': wallet_before,
                     'wallet_after': wallet_after,
                     'reason': 'frontier_expedition'})

    world['policy_feedback'] = (
        f'{EXPEDITION_PIONEERS} {sponsor_nation.name} pioneers arrived at '
        f'{target.name}; {total_cost:.0f} {currency} was spent from the treasury.',
        (120, 240, 150))
    return True
