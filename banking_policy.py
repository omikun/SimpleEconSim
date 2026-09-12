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

    return {
        'total_capital': total_capital,
        'total_deposits': total_deposits,
        'total_liabilities': total_liabilities,
        'total_sovereign_exposure': total_exposure,
        'frozen_banks_count': frozen_count,
        'total_banks_count': len(banks),
        'recapitalization_cost': recap_cost,
        'is_system_frozen': frozen_count > 0,
    }


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

    # Conserved transfer: Sovereign Treasury -> Bank Capital
    gov_agent.cash -= total_cost
    for b in troubled_banks:
        shortfall = max(0.0, target_capital - b.capital)
        b.recapitalize(shortfall)

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

    total_haircut = sum(b.apply_bail_in_haircut(haircut_pct, exemption_floor) for b in frozen_banks)

    # Political and Class fallout
    if hasattr(nation, 'factions'):
        for f in getattr(nation, 'factions', []):
            fname = getattr(f, 'name', '').lower()
            if 'bourgeois' in fname or 'capitalist' in fname:
                f.loyalty = max(0.0, getattr(f, 'loyalty', 0.5) - 0.25)
            elif 'aristocra' in fname or 'lord' in fname:
                f.loyalty = max(0.0, getattr(f, 'loyalty', 0.5) - 0.20)
            elif 'labor' in fname or 'peasant' in fname:
                f.loyalty = max(0.0, getattr(f, 'loyalty', 0.5) - 0.05)

    nation.legitimacy = max(0.10, getattr(nation, 'legitimacy', 0.5) - 0.15)

    return True, f"Bail-in resolution executed! Enacted 25% haircut on large deposits (${total_haircut:,.0f} converted to capital). Bank solvency restored; Bourgeoisie enraged."
