"""Server-owned work that runs around the canonical world turn."""

import forex as fx
import sim_engine

from sim_server.protocol import ServerEvent


def advance(server) -> int:
    """Advance one turn, then apply server-level phases and publish the result."""
    with server._lock:
        if (server.scenario_id in ('labor_frontier_rivalry', 'supply_rivalry')
                and getattr(server, 'scenario_state', {}).get('ending')):
            return server.turn
        server.turn += 1
        turn = server.turn

        def on_event(event_turn, kind, text):
            color = (120, 240, 150)
            if kind in ('OVERRUN', 'DELAY'):
                color = (245, 180, 80)
            elif kind in ('REVOLT', 'CANCEL', 'STRIKE'):
                color = (240, 90, 90)
            server.push_ticker(event_turn, kind, text, color)

        violations, claim_events = sim_engine.step_turn(
            t=turn,
            tiles=server.tiles,
            nations=server.nations,
            pair_orders=server.pair_orders,
            currencies=server.currencies,
            on_event=on_event,
            ledger_exempt=True,
            gameplay_flags=server.gameplay_flags,
        )
        server.violations = violations

        _advance_scenario(server, turn)
        _record_claims(server, turn, claim_events)
        _advance_bond_market(server, turn)
        _record_turn(server, turn)
        return turn


def _advance_scenario(server, turn):
    if not server.gameplay_flags.scenario_progression:
        return
    if server.scenario_id == 'labor_frontier_rivalry':
        from scenario_labor_frontier_rivalry import advance_after_engine
        advance_after_engine(server.get_world_dict(), turn)
        from trace_phase import treasury_boundary
        treasury_boundary(server.tiles, server.nations, 'scenario_after_hook')
        server.currency_totals = {
            currency: fx.audit_currency_total(server.tiles, currency)
            for currency in server.currencies
        }
    elif server.scenario_id == 'supply_rivalry':
        from scenario_supply_rivalry import advance_after_engine
        advance_after_engine(server.get_world_dict(), turn)
        server.currency_totals = {
            currency: fx.audit_currency_total(server.tiles, currency)
            for currency in server.currencies
        }


def _record_claims(server, turn, claim_events):
    if not claim_events:
        return
    server.pair_orders = [
        (region, other)
        for region in server.tiles
        for other in server.tiles
        if other is not region
        and region.neighbors.get(other.name) is not None
        and not getattr(other, 'wilderness', False)
        and not getattr(region, 'wilderness', False)
    ]
    for event in claim_events:
        server.push_ticker(turn, 'CLAIM', event, (245, 210, 95))


def _advance_bond_market(server, turn):
    if server.gameplay_flags.sovereign_bonds:
        try:
            from sovereign_bonds import get_bond_market
            get_bond_market().step(server.get_world_dict(), turn)
        except Exception:
            pass
    from trace_phase import treasury_boundary
    treasury_boundary(server.tiles, server.nations, 'bond_market')


def _record_turn(server, turn):
    server._record_history(turn)
    if server.run_trace is not None:
        from trace_snapshots import record
        record(server)
    if server.tiles and server.run_trace is not None:
        server.run_trace.checkpoint(server.tiles[0]._collective_trace_clock)
    server.state_revision += 1
    server._broadcast(ServerEvent.TURN_ADVANCED, {'turn': turn})
