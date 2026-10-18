"""
trade_settle.py — trader wilderness settlement (v3_wilderness, Call of Capital).

Rulings locked with the user (2026-08-13):
  - Traders are a NO-INTEREST wilderness bank.  A trader sells goods to
    homesteaders ALWAYS at ``(market price + transport) x 1.20`` in the
    trader's home currency, credited to the homesteader's wallet (the
    homesteader "owes").
  - The trader COLLECTS the homesteader's outputs; each leg is a real
    inventory/cash transfer — nothing is created.
  - Value differential = value of goods collected minus value of goods
    loaned (both valued at the trader's price).  When positive, the trader
    pays HALF the differential to the homesteader at market rate in the
    trader's HOME currency.
  - Foreign homesteaders are NOT skipped: wallets are multi-currency;
    homesteaders NEVER pay cash — they only receive money from traders
    when they have a surplus.  No FX conversion ever happens.

Conservation: every function only MOVES money/goods between agents.  The
trader's home currency moves from trader.cash/deposits to the homesteader's
FX wallet (audit-counted); goods move from trader inventory to homesteader
inventory and back.  Nothing is printed or destroyed.
"""

from goods import Goods
import forex as fx


# Trader wilderness markup: always (price + transport) x WILD_MARKUP.
WILD_MARKUP = 1.20
# Outputs collected from homesteaders each settlement (food + wood only).
WILD_COLLECT_GOODS = (Goods.food, Goods.wood)


def _market_value(tile, good, qty):
    """Market value of *qty* of *good* on *tile* (in tile's home currency).

    Wilderness tiles have ``recipes[Goods.food]['price']`` as a live sector
    reference (region keeps recipe prices synced even on wilderness).  For a
    claimed/normal tile this is the normal price.
    """
    price = tile.recipes.get(good, {}).get('price', 1.0)
    return qty * price


def _transport_cost(tile):
    """Per-unit transport cost on *tile* (capacity-aware)."""
    cap = tile.recipes.get(Goods.transport, {}).get('capacity', 10)
    return max(0.05, tile.recipes.get(Goods.transport, {}).get('price', 1.0) / max(1, cap))


def _credit_wallet(agent, currency, amount):
    """Credit *amount* of *currency* to *agent*'s FX wallet (audit-counted)."""
    fx.fx_add(agent, currency, amount)


def _record_wallet_transfer(source_region, destination_region, trader,
                           homesteader, currency, amount, t, transfer_id,
                           payment_kind, cash_before, wallet_before, detail):
    """Post the cash and wallet sides of one frontier payment."""
    from economy.actor_accounts import record as record_economic_event

    cash_after = float(trader.cash)
    wallet_after = float(fx.fx_balance(homesteader, currency))
    journal_detail = {
        **detail,
        'transfer_id': transfer_id,
        'payment_kind': payment_kind,
        'tender': 'trader_cash_to_homesteader_wallet',
        'trader_id': trader.id,
        'homesteader_id': homesteader.id,
        'currency': currency,
        'amount': float(amount),
        'trader_cash_before': float(cash_before),
        'trader_cash_after': cash_after,
        'homesteader_wallet_before': float(wallet_before),
        'homesteader_wallet_after': wallet_after,
    }
    source_event = record_economic_event(
        source_region, 'wilderness_trade_payment', turn=t,
        payer_id=trader.id, amount=amount, asset_id=transfer_id,
        source_id=transfer_id, currency=currency,
        detail={**journal_detail, 'settlement_leg': 'trader_cash_debit'})
    destination_event = record_economic_event(
        destination_region, 'wallet_transfer_in', turn=t,
        recipient_id=homesteader.id, amount=amount, asset_id=transfer_id,
        source_id=transfer_id, currency=currency,
        detail={**journal_detail, 'settlement_leg': 'homesteader_wallet_credit'})

    from run_trace import emit
    emit(source_region, kind='wilderness_wallet_payment',
         record_class='transfer', phase='trade',
         subject={'type': 'wilderness_settlement', 'id': transfer_id,
                  'tile': destination_region.name,
                  'trader_id': trader.id, 'homesteader_id': homesteader.id},
         metric_id='trade.wilderness_settlement', unit=currency,
         before=float(wallet_before), after=wallet_after,
         inputs={**journal_detail,
                 'source_region': source_region.name,
                 'destination_region': destination_region.name,
                 'cash_event': {'tile': source_region.name,
                                'event_id': source_event['id']},
                 'wallet_event': {'tile': destination_region.name,
                                  'event_id': destination_event['id']}})


def _record_goods_transfer(tile, trader, homesteader, good, quantity, t,
                           transfer_id, kind, reference_value, detail):
    """Record a frontier goods movement and its reference valuation."""
    from economy.actor_accounts import record as record_economic_event

    is_advance = kind == 'wilderness_goods_advance'
    event = record_economic_event(
        tile, kind, turn=t,
        payer_id=trader.id if is_advance else homesteader.id,
        recipient_id=homesteader.id if is_advance else trader.id,
        good=good, quantity=quantity, amount=reference_value,
        asset_id=transfer_id, source_id=transfer_id,
        currency=getattr(trader, 'home_currency', None),
        detail={**detail, 'transfer_id': transfer_id,
                'trader_id': trader.id, 'homesteader_id': homesteader.id,
                'reference_value': float(reference_value),
                'valuation_currency': getattr(trader, 'home_currency', None)})

    from run_trace import emit
    emit(tile, kind=kind, record_class='transfer', phase='trade',
         subject={'type': 'wilderness_goods', 'id': transfer_id,
                  'tile': tile.name, 'good': good.name,
                  'trader_id': trader.id, 'homesteader_id': homesteader.id},
         metric_id='trade.wilderness_goods', unit='units',
         before=0.0, after=float(quantity),
         inputs={**detail, 'quantity': int(quantity),
                 'reference_value': float(reference_value),
                 'valuation_currency': getattr(trader, 'home_currency', None),
                 'journal_event': {'tile': tile.name,
                                   'event_id': event['id']}})


def settle_wilderness(trader, tile, t, source_region=None):
    """One settlement round for *trader* trading with *tile*'s homesteaders.

    Steps:
      1. Sell available inventory to homesteaders at
         (tile price + transport) x WILD_MARKUP, crediting their wallets in
         the trader's home currency.  Each homesteader's share is capped by
         how much they can "owe" (their wallet balance + a credit limit).
      2. Collect homesteader outputs (food/wood) into the trader's export
         inventory — a pure goods transfer.
      3. Track the per-(trader, tile) value differential; when collected
         value > loaned value, pay HALF the surplus to the homesteaders'
         wallets at market rate.
    """
    if getattr(tile, 'is_ocean', False) or getattr(tile, 'elevation', 0.0) < 0.0:
        return {'sold_value': 0.0, 'collected_value': 0.0, 'paid': 0.0}
    source_region = source_region or getattr(trader, 'region', None) or tile
    home_currency = trader.home_currency
    transfer_index = 0

    def next_transfer_id(kind, homesteader_id):
        nonlocal transfer_index
        transfer_index += 1
        return f'wilderness:{t}:{trader.id}:{tile.name}:{kind}:{homesteader_id}:{transfer_index}'

    # ---- 1. Sell: loan goods to homesteaders on credit ----
    sold_value = 0.0
    loaned_qty = {g: 0 for g in (Goods.food, Goods.wood)}
    price_food = tile.recipes.get(Goods.food, {}).get('price', 1.0)
    price_wood = tile.recipes.get(Goods.wood, {}).get('price', 1.0)
    transport = _transport_cost(tile)
    sell_price_food = (price_food + transport) * WILD_MARKUP
    sell_price_wood = (price_wood + transport) * WILD_MARKUP

    homesteaders = [a for a in tile.agents if getattr(a, 'is_homesteader', False)]
    if homesteaders:
        # Distribute the trader's current food/wood inventory across
        # homesteaders (round-robin), crediting their wallets with the loan.
        for good, sell_price in ((Goods.food, sell_price_food),
                                 (Goods.wood, sell_price_wood)):
            avail = trader.inv_get(good, 0)
            if avail <= 0:
                continue
            per_h = max(1, avail // len(homesteaders))
            idx = 0
            while avail > 0 and idx < len(homesteaders) * 5:
                h = homesteaders[idx % len(homesteaders)]
                idx += 1
                take = min(per_h, avail)
                if take <= 0:
                    continue
                # Homesteader "owes": wallet is credited (trader currency).
                cost = take * sell_price
                # Cap the credit extension: homesteaders can owe up to their
                # existing wallet balance + a fixed frontier credit cushion.
                bal = fx.fx_balance(h, home_currency) if home_currency else 0.0
                credit_cap = max(0.0, bal + 25.0)
                if cost > credit_cap:
                    take = max(0, int(credit_cap / sell_price))
                    if take <= 0:
                        continue
                    cost = take * sell_price
                # FUND the loan from the trader's real cash: the homesteader
                # wallet credit must be offset by an equal trader debit, or
                # the currency audit would see money printed from thin air.
                if trader.cash < cost:
                    take = max(0, int(trader.cash / sell_price))
                    if take <= 0:
                        continue
                    cost = take * sell_price
                trader.inv_add(good, -take)
                h.inv_add(good, take)
                if home_currency:
                    cash_before = float(trader.cash)
                    wallet_before = fx.fx_balance(h, home_currency)
                    trader.cash -= cost
                    _credit_wallet(h, home_currency, cost)
                    transfer_id = next_transfer_id('advance-payment', h.id)
                    _record_wallet_transfer(
                        source_region, tile, trader, h, home_currency, cost, t,
                        transfer_id, 'frontier_goods_advance', cash_before,
                        wallet_before,
                        {'good': good.name, 'quantity': int(take),
                         'unit_price': float(sell_price),
                         'goods_value': float(cost),
                         'credit_cap': float(credit_cap),
                         'phase': 'trader_inventory_advance'})
                else:
                    transfer_id = next_transfer_id('goods-advance', h.id)
                _record_goods_transfer(
                    tile, trader, h, good, take, t,
                    f'{transfer_id}:goods', 'wilderness_goods_advance', cost,
                    {'phase': 'trader_inventory_advance',
                     'unit_price': float(sell_price),
                     'payment_transfer_id': transfer_id if home_currency else None})
                sold_value += cost
                loaned_qty[good] += take
                avail -= take

    # ---- 2. Collect homesteader outputs (food/wood surplus) ----
    collected_value = 0.0
    for h in homesteaders:
        for good in WILD_COLLECT_GOODS:
            # Keep 2 food for the homesteader; take the rest.
            keep = 2 if good == Goods.food else 0
            take = max(0, h.inv_get(good, 0) - keep)
            if take <= 0:
                continue
            inventory_before = int(h.inv_get(good, 0))
            h.inv_add(good, -take)
            trader.inv_add(good, take)
            reference_value = _market_value(tile, good, take)
            collected_value += reference_value
            _record_goods_transfer(
                tile, trader, h, good, take, t,
                next_transfer_id('goods-collection', h.id),
                'wilderness_goods_collection', reference_value,
                {'phase': 'homesteader_output_collection',
                 'inventory_before': inventory_before,
                 'inventory_after': int(h.inv_get(good, 0)),
                 'reference_unit_price': float(reference_value / take),
                 'kept_food_units': int(keep) if good == Goods.food else 0})

    # ---- 3. Differential payout: half the surplus to homesteaders ----
    # Conservation: the payout is FUNDED from the trader's real cash (trader
    # cash falls, homesteader wallet rises — same currency, net zero).  If the
    # trader can't fund the full half, pay what the cash allows.
    diff = collected_value - sold_value
    paid = 0.0
    if diff > 0 and home_currency and homesteaders:
        surplus = min(0.5 * diff, max(0.0, trader.cash))
        if surplus > 0:
            share = surplus / len(homesteaders)
            for h in homesteaders:
                if share <= 0:
                    continue
                cash_before = float(trader.cash)
                wallet_before = fx.fx_balance(h, home_currency)
                trader.cash -= share
                _credit_wallet(h, home_currency, share)
                paid += share
                transfer_id = next_transfer_id('surplus-payment', h.id)
                _record_wallet_transfer(
                    source_region, tile, trader, h, home_currency, share, t,
                    transfer_id, 'frontier_surplus_share', cash_before,
                    wallet_before,
                    {'phase': 'surplus_distribution',
                     'collected_value': float(collected_value),
                     'sold_value': float(sold_value),
                     'surplus_before_split': float(surplus),
                     'homesteader_count': len(homesteaders),
                     'share': float(share)})

    # Log the settlement round on the trader + tile (ticker archive).
    tile.settlement_log.append({
        't': t, 'trader': trader.id,
        'sold': sold_value, 'collected': collected_value,
        'diff': diff, 'paid': paid,
        'homesteaders': len(homesteaders),
    })
    return {'sold_value': sold_value, 'collected_value': collected_value,
            'paid': paid}
