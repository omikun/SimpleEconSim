"""Run a 50-turn default three-nation supply-control sanity audit."""
from __future__ import annotations

import json
import sys

import forex
import sim_engine
from goods import Goods
from sim_world import build_world
from world_names import assign_world_identities


def run(turns=50, seed=4242):
    import ledger
    ledger.reset()
    tiles, nations, _ = build_world(seed=seed, terrain_seed=seed, nation_seed=seed)
    assign_world_identities(tiles, nations, seed=seed)
    pairs = [(r, o) for r in tiles for o in r.neighbors.values()
             if o is not r and not getattr(r, 'wilderness', False)
             and not getattr(o, 'wilderness', False)]
    currencies = [n.currency for n in nations]
    start_cash = {c: forex.audit_currency_total(tiles, c) for c in currencies}
    violations = []
    violation_phases = []
    for turn in range(1, turns + 1):
        previous = {c: forex.audit_currency_total(tiles, c) for c in currencies}
        phase_deltas = {}
        def on_phase(name):
            nonlocal previous
            current = {c: forex.audit_currency_total(tiles, c) for c in currencies}
            phase_deltas[name] = {c: round(current[c] - previous[c], 4) for c in currencies}
            previous = current
        bad, _ = sim_engine.step_turn(turn, tiles, nations=nations,
                                       pair_orders=pairs, currencies=currencies,
                                       ledger_exempt=True, on_phase=on_phase)
        current = {c: forex.audit_currency_total(tiles, c) for c in currencies}
        phase_deltas['post_resistance_forex_audit'] = {
            c: round(current[c] - previous[c], 4) for c in currencies}
        violations.extend(bad)
        if bad:
            violation_phases.append({'turn': turn, 'phase_deltas': phase_deltas,
                                     'reported': [str(row) for row in bad]})
    accounts = [row for tile in tiles for row in getattr(tile, 'actor_turn_accounts', [])]
    tile_by_name = {tile.name: tile for tile in tiles}
    actor_by_key = {(tile.name, actor.id): actor for tile in tiles for actor in tile.agents}
    account_history = [row for tile in tiles
                       for row in getattr(tile, 'actor_account_history', [])]
    def event_kinds(account):
        tile = tile_by_name.get(account['tile'])
        events = [e for e in getattr(tile, 'economic_events', [])
                  if e['turn'] == account['turn'] and account['actor_id'] in
                  (e.get('payer_id'), e.get('recipient_id'))]
        return {kind: sum(e['kind'] == kind for e in events)
                for kind in sorted({e['kind'] for e in events})}
    firms = [row for row in accounts if row['type'] == 'corporation']
    growers = [row for row in accounts if row['type'] == 'grower']
    def actor_profile(account):
        actor = actor_by_key.get((account['tile'], account['actor_id']))
        if actor is None:
            return {}
        return {'government': bool(getattr(actor, 'is_government', False)),
                'charity': bool(getattr(actor, 'is_charity', False)),
                'trader': bool(getattr(actor, 'is_trader', False)),
                'corporation': bool(getattr(actor, 'is_corporation', False)),
                'lord': bool(getattr(actor, 'is_lord', False)),
                'output': getattr(getattr(actor, 'output', None), 'name', None),
                'employer_id': getattr(getattr(actor, 'employer', None), 'id', None),
                'owner_id': getattr(getattr(actor, 'owner', None), 'id', None),
                'social_class': getattr(actor, 'social_class', None),
                'home_currency': getattr(actor, 'home_currency', None)}
    return {'turns': turns, 'seed': seed, 'nations': len(nations), 'tiles': len(tiles),
            'violations': len(violations),
            'violation_details': [str(v) for v in violations[:5]],
            'violation_phases': violation_phases[:5],
            'currency_start': {k: round(v, 2) for k, v in start_cash.items()},
            'currency_end': {c: round(forex.audit_currency_total(tiles, c), 2)
                             for c in currencies},
            'active_contracts': sum(c.get('status') == 'active' for tile in tiles
                                    for c in getattr(tile, 'offtake_contracts', [])),
            'active_charters': sum(c.get('status') == 'active' for tile in tiles
                                   for c in getattr(tile, 'market_charters', [])),
            'supply_proposals': sum(len(getattr(tile, 'supply_proposals', [])) for tile in tiles),
            'rejected_proposals': sum(p.get('status') == 'rejected' for tile in tiles
                                      for p in getattr(tile, 'supply_proposals', [])),
            'settled_proposals': sum(p.get('status') == 'settled' for tile in tiles
                                     for p in getattr(tile, 'supply_proposals', [])),
            'firm_accounts': len(firms), 'grower_accounts': len(growers),
            'firm_sales_cash_last_turn': round(sum(a['sales_cash'] for a in firms), 2),
            'grower_crop_value_last_turn': round(sum(a['crop_value'] for a in growers), 2),
            'unposted_cash_last_turn': round(sum(abs(a['unposted_cash_change'])
                                                 for a in accounts), 2),
            'largest_unposted_cash_accounts': [
                {'tile': a['tile'], 'actor': a['actor_name'], 'type': a['type'],
                 'actor_id': a['actor_id'], 'profile': actor_profile(a),
                 'cash_change': a['cash_change'], 'posted_change': a['posted_cash_change'],
                 'unposted_change': a['unposted_cash_change'],
                 'posted_event_kinds': event_kinds(a)}
                for a in sorted(accounts, key=lambda row: abs(row['unposted_cash_change']),
                                reverse=True)[:8]],
            'largest_unposted_cash_turns': [
                {'turn': a['turn'], 'tile': a['tile'], 'actor': a['actor_name'],
                 'actor_id': a['actor_id'], 'type': a['type'],
                 'unposted_change': a['unposted_cash_change'],
                 'posted_event_kinds': event_kinds(a)}
                for a in sorted(account_history,
                                key=lambda row: abs(row['unposted_cash_change']),
                                reverse=True)[:12]],
            'cotton_spot_units_last_turn': sum(e['quantity'] for tile in tiles
                                               for e in getattr(tile, 'market_trade_events', [])
                                               if e['good'] == Goods.cotton.name and e['turn'] == turns)}


if __name__ == '__main__':
    turns = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 4242
    print(json.dumps(run(turns, seed), sort_keys=True))
