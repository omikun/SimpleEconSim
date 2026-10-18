"""
banking_policy.py — Domestic Banking Contagion Health & Sovereign Resolution Decrees.

Implements:
- get_banking_system_health: Aggregates domestic bank capital, sovereign debt holdings, and freeze status.
- recapitalize_domestic_banks: Sovereign treasury injection to restore bank equity and lift Corralito.
- enact_deposit_bailin_haircut: Statutory Cyprus-style bail-in haircut on large deposits to re-equitize banks.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Tuple, Dict, Any

if TYPE_CHECKING:
    from nation import Nation


def get_banking_system_health(nation: Nation | None) -> Dict[str, Any]:
    """Calculate aggregate solvency, exposure, and freeze metrics for a nation's banks."""
    if not nation or not getattr(nation, 'tiles', None):
        return {
            'total_capital': 0.0,
            'total_deposits': 0.0,
            'total_liabilities': 0.0,
            'total_sovereign_exposure': 0.0,
            'frozen_banks_count': 0,
            'total_banks_count': 0,
            'recapitalization_cost': 0.0,
            'is_system_frozen': False,
        }

    banks = [r.bank for r in nation.tiles if getattr(r, 'bank', None)]
    total_capital = sum(b.capital for b in banks)
    total_deposits = sum(b.total_deposits for b in banks)
    total_liabilities = sum(b.total_liabilities for b in banks)
    total_exposure = sum(
        sum(item.get('principal', 0.0) for item in getattr(b, 'sovereign_bonds_held', []))
        for b in banks
    )
    frozen_count = sum(1 for b in banks if getattr(b, 'is_frozen', False))

    target_cap = 500.0
    recap_cost = sum(max(0.0, target_cap - b.capital) for b in banks if getattr(b, 'is_frozen', False) or b.capital < target_cap)
    panic_risk = "CRITICAL (Spreading Runs)" if frozen_count > 0 else "STABLE (No Contagion)"

    return {
        'total_capital': total_capital,
        'total_deposits': total_deposits,
        'total_liabilities': total_liabilities,
        'total_sovereign_exposure': total_exposure,
        'frozen_banks_count': frozen_count,
        'total_banks_count': len(banks),
        'recapitalization_cost': recap_cost,
        'is_system_frozen': frozen_count > 0,
        'panic_risk': panic_risk,
    }


def evaluate_banking_contagion(nation: Nation, world: dict | None = None, t: int = 0) -> List[Dict[str, Any]]:
    """Simulate panic bank run contagion when domestic bank(s) are frozen under Corralito."""
    events = []
    if not nation or not getattr(nation, 'tiles', None):
        return events

    banks = [r.bank for r in nation.tiles if getattr(r, 'bank', None)]
    frozen_banks = [b for b in banks if getattr(b, 'is_frozen', False)]
    if not frozen_banks:
        return events

    # Panic spreads to solvent banks in the same nation
    solvent_tiles = [r for r in nation.tiles if getattr(r, 'bank', None) and not getattr(r.bank, 'is_frozen', False)]
    for tile in solvent_tiles:
        b = tile.bank
        total_run = 0.0
        # Depositors panic and attempt to withdraw 20% of their deposits
        for agent, dep in list(getattr(b, 'deposits', {}).items()):
            if dep > 5.0 and getattr(agent, 'alive', True) and not getattr(agent, 'is_government', False):
                run_amount = min(dep * 0.20, dep - 5.0)
                if run_amount > 0:
                    b.Withdraw(agent, run_amount, trace_region=tile, t=t,
                               reason='panic_bank_run')
                    total_run += run_amount

        if total_run > 0:
            events.append({
                'turn': t,
                'tile': tile.name,
                'nation': nation.name,
                'kind': 'BANK_RUN',
                'amount': total_run,
                'msg': f"⚠️ PANIC BANK RUN: Depositors in {tile.name} withdrew ${total_run:,.0f} fearing Corralito freeze!"
            })
            if world:
                from client.desktop.engine import ticker_push
                ticker_push(world, t, 'ALERT', f"⚠️ BANK RUN: Panic deposit run in {tile.name} (${total_run:,.0f} withdrawn)!", (245, 180, 50))

            # If bank capital is depleted during run, it freezes too
            if b.capital <= 0.0:
                b.is_frozen = True
                events.append({
                    'turn': t,
                    'tile': tile.name,
                    'nation': nation.name,
                    'kind': 'CONTAGION_FREEZE',
                    'msg': f"🚨 CONTAGION COLLAPSE: {tile.name} bank depleted reserves and entered emergency Corralito freeze!"
                })

    return events


def recapitalize_domestic_banks(nation: Nation, target_capital: float = 500.0) -> Tuple[bool, str]:
    """Inject sovereign treasury cash into under-capitalized or frozen domestic banks.

    Strictly conserved: transferred 1-for-1 from nation.government.agent.cash into bank.capital.
    Lifts the Corralito emergency deposit freeze.
    """
    if not nation or not getattr(nation, 'tiles', None):
        return False, "Invalid sovereign state."

    banks = [r.bank for r in nation.tiles if getattr(r, 'bank', None)]
    if not banks:
        return False, "No domestic commercial banks exist in this nation."

    troubled_banks = [b for b in banks if getattr(b, 'is_frozen', False) or b.capital < target_capital]
    if not troubled_banks:
        return False, "All domestic commercial banks are already solvent and well-capitalized."

    total_cost = sum(max(0.0, target_capital - b.capital) for b in troubled_banks)
    gov_agent = nation.government.agent
    if gov_agent.cash < total_cost:
        return False, f"Insufficient Treasury: Requires ${total_cost:,.0f} (Current: ${gov_agent.cash:,.0f})."

    # Trace each conserved transfer separately so the treasury debit and bank
    # capital increase can be reconciled to one operation.
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract

    turn = 0
    for b in troubled_banks:
        shortfall = max(0.0, target_capital - b.capital)
        trace_region = next((tile for tile in nation.tiles if tile.bank is b), nation.tiles[0])
        clock = getattr(trace_region, '_collective_trace_clock', {}) or {}
        turn = int(clock.get('turn', getattr(trace_region, '_last_turn', 0)))
        operation_id = (f'bank-recapitalization:{nation.name}:{turn}:'
                        f'{trace_region.name}')
        treasury_before = float(gov_agent.cash)
        bank_capital_before = float(b.capital)
        was_frozen = bool(getattr(b, 'is_frozen', False))
        gov_agent.cash -= shortfall
        _solvent, bank_event_id = b.recapitalize(
            shortfall, trace_region=trace_region, operation_id=operation_id,
            return_event_id=True)
        currency = (getattr(nation, 'currency', None)
                    or getattr(trace_region, 'home_currency', None)
                    or 'local_currency')
        payer = account_ref(
            'government_treasury', nation.name, currency,
            subaccount='government_agent.cash',
            balance_before=treasury_before, balance_after=float(gov_agent.cash),
            balance_scope='government_agent.cash')
        payee = account_ref(
            'bank_capital', trace_region.name, currency,
            balance_before=bank_capital_before, balance_after=float(b.capital),
            balance_scope='capital')
        contract = transfer_contract(
            operation_id, 'bank_recapitalization', side='payer',
            amount=shortfall, amount_currency=currency,
            payer_account=payer, payee_account=payee,
            local_cash_leg_amount=shortfall, local_cash_leg_currency=currency,
            counterparty_leg_status='bank_capital_balance_captured',
            mutation_reference={'turn': turn, 'bank_tile': trace_region.name,
                                'target_capital': float(target_capital),
                                'capital_increase': float(b.capital)
                                - bank_capital_before})
        emit_treasury_leg(
            trace_region, kind='bank_recapitalization_funding',
            nation_name=nation.name, currency=currency,
            signed_amount=-shortfall, contract=contract,
            phase='banking_policy', cause_event_ids=(
                [bank_event_id] if bank_event_id is not None else None),
            inputs={'bank_tile': trace_region.name, 'bank_count': len(troubled_banks),
                    'target_capital': float(target_capital),
                    'capital_before': bank_capital_before,
                    'capital_after': float(b.capital),
                    'was_frozen': was_frozen,
                    'is_frozen_after': bool(getattr(b, 'is_frozen', False)),
                    'source': 'sovereign_treasury'})

    return True, f"Injected ${total_cost:,.0f} recapitalization into {len(troubled_banks)} domestic banks! All deposit freezes lifted."


def enact_deposit_bailin_haircut(nation: Nation, haircut_pct: float = 0.25, exemption_floor: float = 50.0) -> Tuple[bool, str]:
    """Execute a statutory bail-in haircut on large deposits (Cyprus resolution model).

    Converts uninsured deposit liabilities into bank Tier-1 capital without using treasury funds.
    Consequence: severe elite backlash (-25 Bourgeoisie & Lords faction approval) and loss of legitimacy.
    """
    if not nation or not getattr(nation, 'tiles', None):
        return False, "Invalid sovereign state."

    banks = [r.bank for r in nation.tiles if getattr(r, 'bank', None)]
    frozen_banks = [b for b in banks if getattr(b, 'is_frozen', False) or b.capital <= 0.0]
    if not frozen_banks:
        return False, "No domestic banks are currently insolvent or frozen; bail-in resolution not permitted."

    total_haircut = 0.0
    bank_event_ids = []
    for bank in frozen_banks:
        trace_region = next((tile for tile in nation.tiles if tile.bank is bank), nation.tiles[0])
        amount, bank_event_id = bank.apply_bail_in_haircut(
            haircut_pct, exemption_floor, trace_region=trace_region,
            return_event_id=True)
        total_haircut += amount
        if bank_event_id is not None:
            bank_event_ids.append(bank_event_id)

    # Political and Class fallout
    from run_trace import emit
    trace_region = nation.tiles[0]
    clock = getattr(trace_region, '_collective_trace_clock', {}) or {}
    turn = int(clock.get('turn', getattr(trace_region, '_last_turn', 0)))
    if hasattr(nation, 'factions'):
        for f in getattr(nation, 'factions', []):
            fname = getattr(f, 'name', '').lower()
            loyalty_before = float(getattr(f, 'loyalty', 0.5))
            if 'bourgeois' in fname or 'capitalist' in fname:
                f.loyalty = max(0.0, loyalty_before - 0.25)
            elif 'aristocra' in fname or 'lord' in fname:
                f.loyalty = max(0.0, loyalty_before - 0.20)
            elif 'labor' in fname or 'peasant' in fname:
                f.loyalty = max(0.0, loyalty_before - 0.05)
            if float(getattr(f, 'loyalty', loyalty_before)) != loyalty_before:
                emit(trace_region, kind='bank_bailin_faction_loyalty',
                     record_class='outcome', phase='banking_policy',
                     subject={'type': 'tile/faction', 'id': getattr(f, 'name', 'unknown')},
                     metric_id='politics.faction_loyalty', unit='ratio',
                     before=loyalty_before, after=float(f.loyalty),
                     formula_id='banking_policy.bailin_faction_backlash.v1',
                     inputs={'faction': getattr(f, 'name', 'unknown'),
                             'turn': turn, 'bank_bailin_event_ids': bank_event_ids},
                     cause_event_ids=bank_event_ids or None)

    legitimacy_before = float(getattr(nation, 'legitimacy', 0.5))
    nation.legitimacy = max(0.10, legitimacy_before - 0.15)
    emit(trace_region, kind='bank_bailin_legitimacy',
         record_class='outcome', phase='banking_policy',
         subject={'type': 'nation', 'id': nation.name},
         metric_id='politics.legitimacy', unit='ratio',
         before=legitimacy_before, after=float(nation.legitimacy),
         formula_id='banking_policy.bailin_legitimacy_loss.v1',
         inputs={'turn': turn, 'bank_bailin_event_ids': bank_event_ids,
                 'legitimacy_loss': legitimacy_before - float(nation.legitimacy)},
         cause_event_ids=bank_event_ids or None)

    return True, f"Bail-in resolution executed! Enacted 25% haircut on large deposits (${total_haircut:,.0f} converted to capital). Bank solvency restored; Bourgeoisie enraged."
