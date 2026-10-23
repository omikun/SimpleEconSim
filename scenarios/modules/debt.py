"""Generalized debt, sovereign bonds, and revenue intercept dynamics."""

from __future__ import annotations
from treasury_trace import begin_public_change, finish_public_change

from typing import Any, Dict
from scenarios.modules.base import BaseDynamicModule


class DebtClaimsModule(BaseDynamicModule):
    """Manages debt claims, sovereign bond representations, and assigned revenue collection."""

    def initialize(self, world: dict, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        player = context.get('player_nation')
        creditors = context.get('creditor_nations', [])
        if not player or not creditors:
            return

        initial_payment = float(self.config.get('initial_payment', 200.0))
        first_due_turn = int(self.config.get('first_due_turn', 6))

        state['scheduled_remittance'] = initial_payment
        state['payment_window_turn'] = first_due_turn
        state['payment_status'] = 'upcoming'
        state['deferral_count'] = 0
        state['creditor_levy_per_turn'] = 0.0
        state['creditor_levy_remaining'] = 0.0
        state['debt_ledger'] = []
        state['assigned_revenues'] = self.config.get('assigned_revenues', {'tax': 0.25, 'tariff': 0.50})

        # Register sovereign bonds in engine bond market
        try:
            from sovereign_bonds import SovereignBond, get_bond_market
            market = get_bond_market()
            bond_ids = []
            per_creditor = round(initial_payment / len(creditors), 2)
            for cred in creditors:
                bid = f"{player.name.lower()}_debt_{cred.name.lower()}"
                market.bonds[:] = [b for b in market.bonds if b.bond_id != bid]
                market.bonds.append(SovereignBond(
                    bond_id=bid,
                    issuer_nation=player.name,
                    holder_nation=cred.name,
                    principal=per_creditor,
                    coupon_rate=0.0,
                    duration_turns=first_due_turn - 1,
                    issued_turn=1,
                    maturity_turn=first_due_turn,
                    status='active',
                    bond_purpose='scenario_debt',
                ))
                bond_ids.append(bid)
            state['debt_bond_ids'] = bond_ids
        except Exception:
            pass

    def advance_turn(self, world: dict, turn: int, ticker_push, context: Dict[str, Any]) -> None:
        state = world.setdefault('scenario_state', {})
        player = context.get('player_nation')
        creditors = context.get('creditor_nations', [])
        if not player:
            return

        # 1. Execute assigned revenue levy if active
        levy = float(state.get('creditor_levy_per_turn', 0.0))
        if levy > 0:
            gov_cash = float(getattr(player.government.agent, 'cash', 0.0))
            collected = min(levy, gov_cash)
            if collected > 0:
                _public_write = begin_public_change(None, player.government.agent)
                player.government.agent.cash -= collected
                finish_public_change(_public_write, 'scenarios.modules.debt:DebtClaimsModule.advance_turn',
                                     inputs={'source_writer': 'scenarios/modules/debt.py:DebtClaimsModule.advance_turn:5c42538baaa0afe5:1', 'semantic_operation_id': locals().get('operation_id')})
                if creditors:
                    split_cash = collected / len(creditors)
                    for c in creditors:
                        _public_write = begin_public_change(None, c.government.agent)
                        c.government.agent.cash += split_cash
                        finish_public_change(_public_write, 'scenarios.modules.debt:DebtClaimsModule.advance_turn',
                                             inputs={'source_writer': 'scenarios/modules/debt.py:DebtClaimsModule.advance_turn:4e294aa9e415c19f:1', 'semantic_operation_id': locals().get('operation_id')})
                state.setdefault('debt_ledger', []).append({
                    'turn': turn,
                    'kind': 'levy_collection',
                    'amount': round(collected, 2),
                })
                if ticker_push:
                    ticker_push(world, turn, 'CREDITOR', f"Creditors collected {collected:,.0f} units from revenue intercepts.", (225, 178, 87))

        # 2. Check debt service payment window
        due_turn = int(state.get('payment_window_turn', 6))
        status = state.get('payment_status', 'upcoming')

        if turn >= due_turn and status in ('upcoming', 'deferred'):
            state['payment_status'] = 'unpaid'
            world['playing'] = False
            world['scenario_warning_modal'] = {'kind': 'debt_due'}
            if ticker_push:
                ticker_push(world, turn, 'ALERT', "Debt service is due. Choose payment, concession, deferral, or default.", (240, 180, 72))
        elif turn > due_turn and status == 'unpaid':
            state['payment_status'] = 'defaulted'
            state['creditor_confidence'] = 0.0
            player.legitimacy = max(0.0, float(getattr(player, 'legitimacy', 0.5)) - 0.15)
            if ticker_push:
                ticker_push(world, turn, 'ALERT', "The government missed the debt-service window; default triggered.", (240, 90, 82))

    def snapshot_metrics(self, world: dict, context: Dict[str, Any]) -> Dict[str, Any]:
        state = world.get('scenario_state', {})
        return {
            'scheduled_remittance': float(state.get('scheduled_remittance', 0.0)),
            'payment_status': state.get('payment_status', 'unknown'),
            'deferral_count': int(state.get('deferral_count', 0)),
            'creditor_levy_per_turn': float(state.get('creditor_levy_per_turn', 0.0)),
        }
