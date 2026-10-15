"""Read-only end-of-turn observations and explicit provenance gaps."""

from goods import Goods


def sample(tiles, nations):
    values = {}
    for tile in tiles:
        tile_subject = {'type': 'tile', 'id': tile.name}
        for good in (Goods.food, Goods.wood, Goods.furniture, Goods.transport):
            recipe = tile.recipes.get(good)
            if recipe is not None and 'price' in recipe:
                subject = {**tile_subject, 'good': good.name}
                values[('goods.price', tile.name, good.name)] = (
                    subject, 'local_currency_per_unit', float(recipe['price']))
                for metric_id, field, unit in (
                        ('goods.production', 'production_log', 'units_per_turn'),
                        ('goods.demand', 'demand_log', 'units_offered'),
                        ('goods.supply', 'supply_log', 'units_offered'),
                        ('goods.sold', 'sold_log', 'units'),
                        ('goods.producer_inventory', 'inventory_log', 'units')):
                    history = getattr(tile, field, {}).get(good, ())
                    if history:
                        values[(metric_id, tile.name, good.name)] = (
                            subject, unit, float(history[-1]))
        values[('people.population', tile.name)] = (
            tile_subject, 'people', tile.total_population[-1]
            if getattr(tile, 'total_population', None) else len(tile.agents))
        if tile.protest_energy_log:
            values[('politics.protest_energy', tile.name)] = (
                tile_subject, 'score', float(tile.protest_energy_log[-1]))
        if tile.unrest_log:
            values[('politics.unrest_event', tile.name)] = (
                tile_subject, 'stage', tile.unrest_log[-1].get('stage', 'calm'))
        if getattr(tile, 'gdp_log', None):
            values[('economy.gdp_nominal', tile.name)] = (
                tile_subject, 'local_currency_per_turn', float(tile.gdp_log[-1]))
        if getattr(tile, 'cost_of_living', None) is not None:
            values[('living.cost_of_living', tile.name)] = (
                tile_subject, 'local_currency_per_basket', float(tile.cost_of_living))
    for nation in nations:
        subject = {'type': 'nation', 'id': nation.name}
        values[('finance.treasury', nation.name)] = (
            subject, nation.currency, float(nation.treasury()['total']))
        values[('politics.legitimacy', nation.name)] = (
            subject, 'ratio', float(nation.legitimacy))
        members = list(nation.tiles)
        values[('people.population', nation.name)] = (
            subject, 'people', sum(tile.total_population[-1]
                                   if getattr(tile, 'total_population', None) else len(tile.agents)
                                   for tile in members))
        values[('economy.gdp_nominal', nation.name)] = (
            subject, nation.currency + '_per_turn',
            sum(tile.gdp_log[-1] if getattr(tile, 'gdp_log', None) else 0.0
                for tile in members))
        values[('politics.protest_energy', nation.name)] = (
            subject, 'mean_score',
            sum(tile.protest_energy_log[-1] if getattr(tile, 'protest_energy_log', None)
                else 0.0 for tile in members) / max(1, len(members)))
        values[('living.cost_of_living', nation.name)] = (
            subject, 'mean_local_currency_per_basket',
            sum(tile.cost_of_living for tile in members) / max(1, len(members))
            if members else 1.0)
    return values


def record(server):
    current = sample(server.tiles, server.nations)
    previous = getattr(server, '_trace_previous', {})
    clock = getattr(server.tiles[0], '_collective_trace_clock', None) if server.tiles else None
    if clock is not None:
        clock['phase'] = 'snapshot'
        for nation in server.nations:
            members = [tile.name for tile in nation.tiles]
            treasury = nation.treasury()
            old_treasury = previous.get(('finance.treasury', nation.name))
            if old_treasury is not None:
                actual_delta = treasury['total'] - old_treasury[2]
                flows = server.run_trace._treasury_flows.get(nation.name, [])
                known_delta = sum(flow['amount'] for flow in flows)
                by_kind = {}
                for flow in flows:
                    by_kind[flow['kind']] = by_kind.get(flow['kind'], 0.0) + flow['amount']
                server.run_trace.emit(clock, kind='treasury_reconciliation',
                                      record_class='audit', phase='snapshot',
                                      subject={'type': 'nation', 'id': nation.name},
                                      metric_id='finance.treasury', unit=nation.currency,
                                      before=old_treasury[2], after=treasury['total'],
                                      confidence='exact' if abs(actual_delta - known_delta) < 1e-8
                                      else 'unknown',
                                      inputs={'known_flow_total': known_delta,
                                              'unattributed_residual': actual_delta - known_delta,
                                              'flow_totals_by_kind': by_kind},
                                      cause_event_ids=[flow['event_id'] for flow in flows])
            server.run_trace.emit(clock, kind='treasury_components',
                                  record_class='observation', phase='snapshot',
                                  subject={'type': 'nation', 'id': nation.name},
                                  metric_id='finance.treasury', unit=nation.currency,
                                  after=treasury['total'],
                                  inputs={'sovereign_cash': treasury['sovereign_cash'],
                                          'provincial_cash': treasury['provincial_cash'],
                                          'municipal_cash': treasury['municipal_cash'],
                                          'cash_total': treasury['cash'],
                                          'deposits': treasury['deposits'],
                                          'member_tiles': members})
            for metric_id, unit, values_by_tile, reducer in (
                    ('people.population', 'people',
                     [current[('people.population', tile)][2] for tile in members], 'sum'),
                    ('economy.gdp_nominal', nation.currency + '_per_turn',
                     [current.get(('economy.gdp_nominal', tile), (None, None, 0.0))[2]
                      for tile in members], 'sum'),
                    ('politics.protest_energy', 'mean_score',
                     [current.get(('politics.protest_energy', tile), (None, None, 0.0))[2]
                      for tile in members], 'mean'),
                    ('living.cost_of_living', 'mean_local_currency_per_basket',
                     [current.get(('living.cost_of_living', tile), (None, None, 1.0))[2]
                      for tile in members], 'mean')):
                key = (metric_id, nation.name)
                if key not in current:
                    continue
                server.run_trace.emit(clock, kind='national_aggregate',
                                      record_class='calculation', phase='snapshot',
                                      subject={'type': 'nation', 'id': nation.name},
                                      metric_id=metric_id, unit=unit,
                                      after=current[key][2],
                                      formula_id=f'aggregate.{reducer}.v1',
                                      inputs={'member_tiles': members,
                                              'member_values': values_by_tile,
                                              'denominator': max(1, len(members)) if reducer == 'mean' else None})
        for key, (subject, unit, after) in current.items():
            before = previous[key][2] if key in previous else None
            server.run_trace.snapshot(clock, subject=subject, metric_id=key[0],
                                      unit=unit, before=before, after=after)
    server._trace_previous = current
