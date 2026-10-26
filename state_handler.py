"""Centralized Shared-State Mutation Handler & Debugging Infrastructure.

Consolidates shared economic state mutations (`agent.cash`, `agent.inventory`,
and `bank.deposits`) behind guarded, observable operations that:
1. Enforce conservation & numeric invariants (rejecting `NaN`/`Inf`, guarding
   against unpermitted negative balances or mutations on dead agents).
2. Automatically coordinate telemetry across `treasury_trace`, `bank_trace`,
   `economy.actor_accounts`, and `run_trace` without requiring 4 manual wrapper
   blocks at every call site.
3. Provide interactive debugging watchpoints (`watch_agent`, `watch_region`) and
   a bounded ring buffer of recent state mutations with caller provenance.
"""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import math
from typing import Any, Callable

from goods import Goods
from treasury_trace import (
    begin_public_change as _trace_public_begin,
    finish_public_change as _trace_public_finish,
)
from bank_trace import (
    begin_change as _trace_bank_begin,
    finish_change as _trace_bank_finish,
)


class StateInvariantError(AssertionError):
    """Raised when a state mutation violates a financial or inventory invariant."""


class StateMutationHandler:
    """Centralized coordinator, invariant guard, and debugger for shared state."""

    def __init__(self, history_limit: int = 2048):
        self.strict_guards: bool = False
        self.allow_dead_mutations: bool = True
        self.history_enabled: bool = False
        self.history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._agent_watchpoints: dict[int, list[Callable[[dict[str, Any]], None]]] = {}
        self._region_watchpoints: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._global_watchpoints: list[Callable[[dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Configuration & Watchpoints
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all watchpoints, history, and reset flags to default."""
        self.strict_guards = False
        self.allow_dead_mutations = True
        self.history_enabled = False
        self.history.clear()
        self._agent_watchpoints.clear()
        self._region_watchpoints.clear()
        self._global_watchpoints.clear()

    @property
    def has_active_hooks(self) -> bool:
        return bool(
            self.strict_guards
            or self.history_enabled
            or self._agent_watchpoints
            or self._region_watchpoints
            or self._global_watchpoints
        )

    @contextmanager
    def strict_mode(self, *, allow_dead: bool = False):
        """Context manager enabling strict runtime invariant checks."""
        prev_strict = self.strict_guards
        prev_dead = self.allow_dead_mutations
        self.strict_guards = True
        self.allow_dead_mutations = allow_dead
        try:
            yield self
        finally:
            self.strict_guards = prev_strict
            self.allow_dead_mutations = prev_dead

    def watch_agent(self, agent_or_id: Any, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback invoked whenever `agent_or_id`'s cash or inventory changes."""
        aid = int(getattr(agent_or_id, 'id', agent_or_id))
        self._agent_watchpoints.setdefault(aid, []).append(callback)

    def unwatch_agent(self, agent_or_id: Any) -> None:
        aid = int(getattr(agent_or_id, 'id', agent_or_id))
        self._agent_watchpoints.pop(aid, None)

    def watch_region(self, region_or_name: Any, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback invoked whenever a mutation occurs in `region_or_name`."""
        rname = str(getattr(region_or_name, 'name', region_or_name))
        self._region_watchpoints.setdefault(rname, []).append(callback)

    def unwatch_region(self, region_or_name: Any) -> None:
        rname = str(getattr(region_or_name, 'name', region_or_name))
        self._region_watchpoints.pop(rname, None)

    def watch_all(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a global watchpoint callback for all mutations."""
        self._global_watchpoints.append(callback)

    def recent_mutations(self, *, agent_id: int | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        """Query the in-memory ring buffer of recorded state mutations."""
        results = list(self.history)
        if agent_id is not None:
            aid = int(agent_id)
            results = [
                r for r in results
                if r.get('actor_id') == aid
                or r.get('payer_id') == aid
                or r.get('payee_id') == aid
            ]
        if kind is not None:
            results = [r for r in results if r.get('kind') == kind]
        return results

    # ------------------------------------------------------------------
    # Internal Validation & Notification
    # ------------------------------------------------------------------

    def _validate_number(self, value: float | int, label: str, context: str) -> None:
        if not math.isfinite(float(value)):
            raise StateInvariantError(f"Non-finite {label}={value!r} in {context}")

    def _validate_agent_state(
        self,
        agent: Any,
        *,
        context: str,
        check_cash: bool = False,
        allow_negative_cash: bool = False,
        check_good: Goods | str | None = None,
        allow_negative_good: bool = False,
    ) -> None:
        if agent is None:
            raise StateInvariantError(f"Null agent in {context}")
        if self.strict_guards and not self.allow_dead_mutations:
            if not getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False):
                raise StateInvariantError(
                    f"Mutation on dead agent id={getattr(agent, 'id', None)} in {context}"
                )
        if check_cash:
            cash_val = float(getattr(agent, 'cash', 0.0))
            self._validate_number(cash_val, 'cash', context)
            if self.strict_guards and not allow_negative_cash and cash_val < -1e-7:
                raise StateInvariantError(
                    f"Negative cash balance ({cash_val:.6f}) on agent id={getattr(agent, 'id', None)} in {context}"
                )
        if check_good is not None:
            qty_val = float(agent.inv_get(check_good, 0))
            self._validate_number(qty_val, f'inventory[{check_good}]', context)
            if self.strict_guards and not allow_negative_good and qty_val < -1e-7:
                raise StateInvariantError(
                    f"Negative inventory ({qty_val}) for {check_good} on agent id={getattr(agent, 'id', None)} in {context}"
                )

    def _notify(self, entry: dict[str, Any]) -> None:
        if self.history_enabled:
            self.history.append(entry)
        for cb in self._global_watchpoints:
            cb(entry)
        rname = entry.get('region')
        if rname and rname in self._region_watchpoints:
            for cb in self._region_watchpoints[rname]:
                cb(entry)
        if self._agent_watchpoints:
            seen_ids = set()
            for key in ('actor_id', 'payer_id', 'payee_id'):
                aid = entry.get(key)
                if aid is not None and aid not in seen_ids:
                    seen_ids.add(aid)
                    for cb in self._agent_watchpoints.get(int(aid), ()):
                        cb(entry)

    # ------------------------------------------------------------------
    # Guarded Cash Mutations
    # ------------------------------------------------------------------

    def adjust_cash(
        self,
        actor: Any,
        delta: float,
        *,
        region: Any = None,
        kind: str = 'cash_adjustment',
        source_writer: str | None = None,
        trace_inputs: dict[str, Any] | None = None,
        cause_event_ids: list[str] | None = None,
        allow_negative: bool = False,
    ) -> list[str]:
        """Adjust a single actor's cash balance with treasury_trace & invariant guards."""
        self._validate_number(delta, 'delta', kind)
        if delta == 0.0 and not self.has_active_hooks:
            return []
        before = float(getattr(actor, 'cash', 0.0))
        inputs = dict(trace_inputs) if trace_inputs else {}
        if source_writer:
            inputs.setdefault('source_writer', source_writer)
        pub_ctx = _trace_public_begin(region, actor)
        actor.cash = before + float(delta)
        after = float(actor.cash)
        writes = _trace_public_finish(
            pub_ctx, kind, inputs=inputs or None, cause_event_ids=cause_event_ids
        )
        self._validate_agent_state(
            actor, context=kind, check_cash=True, allow_negative_cash=allow_negative
        )
        if self.has_active_hooks:
            self._notify({
                'op': 'adjust_cash',
                'kind': kind,
                'region': getattr(region, 'name', None),
                'actor_id': getattr(actor, 'id', None),
                'delta': float(delta),
                'before': before,
                'after': after,
                'source_writer': source_writer,
            })
        return writes

    def transfer_cash(
        self,
        payer: Any,
        payee: Any,
        amount: float,
        *,
        region: Any = None,
        kind: str = 'cash_transfer',
        payer_source_writer: str | None = None,
        payee_source_writer: str | None = None,
        trace_inputs: dict[str, Any] | None = None,
        cause_event_ids: list[str] | None = None,
        record_event_kind: str | None = None,
        turn: int | None = None,
        currency: str | None = None,
        asset_id: Any = None,
        source_id: str | None = None,
        event_detail: dict[str, Any] | None = None,
        cap_at_payer_cash: bool = False,
        allow_negative_payer: bool = False,
    ) -> float:
        """Atomically transfer cash from `payer` to `payee` with strict conservation."""
        self._validate_number(amount, 'amount', kind)
        amt = float(amount)
        if cap_at_payer_cash:
            amt = min(max(0.0, float(payer.cash)), max(0.0, amt))
        if amt < 0.0:
            raise StateInvariantError(f"transfer_cash amount must be >= 0 (got {amt}) in {kind}")
        payer_before = float(getattr(payer, 'cash', 0.0))
        payee_before = float(getattr(payee, 'cash', 0.0))

        payer_inputs = dict(trace_inputs) if trace_inputs else {}
        if payer_source_writer:
            payer_inputs['source_writer'] = payer_source_writer
        payee_inputs = dict(trace_inputs) if trace_inputs else {}
        if payee_source_writer:
            payee_inputs['source_writer'] = payee_source_writer

        p_ctx = _trace_public_begin(region, payer)
        payer.cash -= amt
        _trace_public_finish(
            p_ctx, kind, inputs=payer_inputs or None, cause_event_ids=cause_event_ids
        )

        r_ctx = _trace_public_begin(region, payee)
        payee.cash += amt
        _trace_public_finish(
            r_ctx, kind, inputs=payee_inputs or None, cause_event_ids=cause_event_ids
        )

        payer_after = float(payer.cash)
        payee_after = float(payee.cash)

        if self.strict_guards:
            net_drift = (payer_after + payee_after) - (payer_before + payee_before)
            if abs(net_drift) > 1e-6:
                raise StateInvariantError(
                    f"Cash conservation drift ({net_drift}) during {kind} between {getattr(payer, 'id', None)} and {getattr(payee, 'id', None)}"
                )

        self._validate_agent_state(
            payer, context=kind, check_cash=True, allow_negative_cash=allow_negative_payer
        )
        self._validate_agent_state(
            payee, context=kind, check_cash=True, allow_negative_cash=True
        )

        if record_event_kind is not None and amt > 0.0 and region is not None:
            from economy.actor_accounts import record as record_economic_event
            record_economic_event(
                region,
                record_event_kind,
                turn=turn,
                payer_id=getattr(payer, 'id', None),
                recipient_id=getattr(payee, 'id', None),
                amount=amt,
                currency=currency,
                asset_id=asset_id,
                source_id=source_id,
                detail=event_detail,
            )

        if self.has_active_hooks:
            self._notify({
                'op': 'transfer_cash',
                'kind': kind,
                'region': getattr(region, 'name', None),
                'payer_id': getattr(payer, 'id', None),
                'payee_id': getattr(payee, 'id', None),
                'amount': amt,
                'payer_before': payer_before,
                'payer_after': payer_after,
                'payee_before': payee_before,
                'payee_after': payee_after,
            })
        return amt

    # ------------------------------------------------------------------
    # Guarded Inventory Mutations
    # ------------------------------------------------------------------

    def adjust_good(
        self,
        actor: Any,
        good: Goods | str,
        delta: int | float,
        *,
        region: Any = None,
        kind: str = 'inventory_adjustment',
        allow_negative: bool = False,
    ) -> float | int:
        """Adjust an actor's inventory of `good` with invariant guards & watchpoints."""
        self._validate_number(delta, 'delta', kind)
        before = actor.inv_get(good, 0)
        actor.inv_add(good, delta)
        after = actor.inv_get(good, 0)
        self._validate_agent_state(
            actor, context=kind, check_good=good, allow_negative_good=allow_negative
        )
        if self.has_active_hooks:
            self._notify({
                'op': 'adjust_good',
                'kind': kind,
                'region': getattr(region, 'name', None),
                'actor_id': getattr(actor, 'id', None),
                'good': good.name if isinstance(good, Goods) else str(good),
                'delta': delta,
                'before': before,
                'after': after,
            })
        return after

    def transfer_good(
        self,
        giver: Any,
        receiver: Any,
        good: Goods | str,
        qty: int | float,
        *,
        region: Any = None,
        kind: str = 'good_transfer',
        cap_at_giver_inventory: bool = False,
        allow_negative_giver: bool = False,
    ) -> int | float:
        """Atomically transfer `qty` of `good` from `giver` to `receiver`."""
        self._validate_number(qty, 'qty', kind)
        giver_before = giver.inv_get(good, 0)
        receiver_before = receiver.inv_get(good, 0)
        actual_qty = min(max(0, giver_before), max(0, qty)) if cap_at_giver_inventory else qty
        if actual_qty < 0:
            raise StateInvariantError(f"transfer_good qty must be >= 0 (got {actual_qty}) in {kind}")
        if actual_qty == 0 and not self.has_active_hooks:
            return 0
        giver.inv_add(good, -actual_qty)
        receiver.inv_add(good, actual_qty)
        giver_after = giver.inv_get(good, 0)
        receiver_after = receiver.inv_get(good, 0)

        if self.strict_guards:
            drift = (giver_after + receiver_after) - (giver_before + receiver_before)
            if abs(float(drift)) > 1e-6:
                raise StateInvariantError(
                    f"Good conservation drift ({drift}) for {good} during {kind}"
                )

        self._validate_agent_state(
            giver, context=kind, check_good=good, allow_negative_good=allow_negative_giver
        )
        self._validate_agent_state(
            receiver, context=kind, check_good=good, allow_negative_good=True
        )
        if self.has_active_hooks:
            self._notify({
                'op': 'transfer_good',
                'kind': kind,
                'region': getattr(region, 'name', None),
                'payer_id': getattr(giver, 'id', None),
                'payee_id': getattr(receiver, 'id', None),
                'good': good.name if isinstance(good, Goods) else str(good),
                'qty': actual_qty,
                'giver_before': giver_before,
                'giver_after': giver_after,
                'receiver_before': receiver_before,
                'receiver_after': receiver_after,
            })
        return actual_qty

    # ------------------------------------------------------------------
    # Guarded Bank Deposit Transfers
    # ------------------------------------------------------------------

    def transfer_deposit(
        self,
        bank: Any,
        payer: Any,
        payee: Any,
        amount: float,
        *,
        region: Any = None,
        kind: str = 'deposit_transfer',
        trace_inputs: dict[str, Any] | None = None,
        cause_event_ids: list[str] | None = None,
    ) -> float:
        """Atomically transfer bank deposits between two account holders."""
        self._validate_number(amount, 'amount', kind)
        amt = float(amount)
        if amt < 0.0:
            raise StateInvariantError(f"transfer_deposit amount must be >= 0 (got {amt}) in {kind}")
        payer_before = float(bank.deposits.get(payer, 0.0))
        payee_before = float(bank.deposits.get(payee, 0.0))
        if self.strict_guards and payer_before + 1e-7 < amt:
            raise StateInvariantError(
                f"Deposit overdraft ({payer_before} < {amt}) on agent id={getattr(payer, 'id', None)} in {kind}"
            )
        p_pub = _trace_public_begin(region, payer, bank=bank, cash=False, deposit=True)
        r_pub = _trace_public_begin(region, payee, bank=bank, cash=False, deposit=True)
        b_ctx = _trace_bank_begin(bank, region)

        bank.deposits[payer] = payer_before - amt
        if abs(bank.deposits[payer]) < 1e-9:
            bank.deposits.pop(payer, None)
        bank.deposits[payee] = payee_before + amt

        _trace_bank_finish(bank, b_ctx, kind, inputs=trace_inputs, cause_event_ids=cause_event_ids)
        _trace_public_finish(p_pub, kind, inputs=trace_inputs, cause_event_ids=cause_event_ids)
        _trace_public_finish(r_pub, kind, inputs=trace_inputs, cause_event_ids=cause_event_ids)

        if self.has_active_hooks:
            self._notify({
                'op': 'transfer_deposit',
                'kind': kind,
                'region': getattr(region, 'name', None),
                'payer_id': getattr(payer, 'id', None),
                'payee_id': getattr(payee, 'id', None),
                'amount': amt,
                'payer_before': payer_before,
                'payer_after': float(bank.deposits.get(payer, 0.0)),
                'payee_before': payee_before,
                'payee_after': float(bank.deposits.get(payee, 0.0)),
            })
        return amt


# Singleton process-level state handler
STATE_HANDLER = StateMutationHandler()

adjust_cash = STATE_HANDLER.adjust_cash
transfer_cash = STATE_HANDLER.transfer_cash
adjust_good = STATE_HANDLER.adjust_good
transfer_good = STATE_HANDLER.transfer_good
transfer_deposit = STATE_HANDLER.transfer_deposit
watch_agent = STATE_HANDLER.watch_agent
unwatch_agent = STATE_HANDLER.unwatch_agent
watch_region = STATE_HANDLER.watch_region
unwatch_region = STATE_HANDLER.unwatch_region
watch_all = STATE_HANDLER.watch_all
strict_mode = STATE_HANDLER.strict_mode
recent_mutations = STATE_HANDLER.recent_mutations
