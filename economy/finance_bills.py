"""
economy/finance_bills.py — Negotiable Bills of Exchange, Elastic Liquidity & Credit Cycles (Issue-09).

Theoretical Grounding (Sven Beckert / Fernand Braudel):
Merchant capitalism and early industrial capitalism did not expand solely through
static metallic specie. Instead, merchant houses, cotton importers, and industrial
manufacturers created elastic paper liquidity through negotiable Bills of Exchange
(e.g., Manchester cotton bills drawn on Liverpool merchant houses, accepted in London).
Bills were endorsed, passed from hand to hand as currency substitutes, and discounted
at market interest rates before maturity. If a speculative crash occurred, chains of
dishonored bills triggered credit crunches and bank defaults.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class BillOfExchange:
    """A negotiable trade credit instrument payable at a future maturity date."""
    id: str
    drawer_id: int          # Agent who created the debt obligation
    drawee_id: int          # Agent or institution responsible for honoring the bill at maturity
    payee_id: int           # Current legal holder entitled to payment
    face_value: float       # Nominal currency due at maturity ($)
    issue_turn: int
    maturity_turn: int
    discount_rate: float = 0.05    # Annualized/per-cycle discount yield
    endorsements: List[int] = field(default_factory=list) # Prior holders who endorsed
    is_settled: bool = False
    is_defaulted: bool = False
    amount_paid: float = 0.0

    def calculate_discounted_value(self, current_turn: int) -> float:
        """Calculate present market cash value of the bill given turns remaining to maturity."""
        turns_left = max(0, self.maturity_turn - current_turn)
        if turns_left == 0:
            return self.face_value
        # Standard commercial bill discount formula: P = Face / (1 + r * turns)
        pv = self.face_value / (1.0 + (self.discount_rate * turns_left))
        return round(pv, 2)


class CreditMarketManager:
    """Manages creation, negotiable discounting, settlement, and systemic credit monitoring."""

    def __init__(self, baseline_discount_rate: float = 0.04):
        self.baseline_discount_rate = baseline_discount_rate
        self.active_bills: Dict[str, BillOfExchange] = {}
        self.settled_bills: Dict[str, BillOfExchange] = {}
        self.defaulted_bills: Dict[str, BillOfExchange] = {}

    def issue_bill(
        self,
        drawer: Any,
        drawee: Any,
        payee: Any,
        face_value: float,
        current_turn: int,
        tenor_turns: int = 4,
        discount_rate: Optional[float] = None
    ) -> BillOfExchange:
        """Issue a new negotiable bill of exchange extending trade credit."""
        rate = discount_rate if discount_rate is not None else self.baseline_discount_rate
        bill = BillOfExchange(
            id=f"bill_{uuid.uuid4().hex[:8]}",
            drawer_id=drawer.id,
            drawee_id=drawee.id,
            payee_id=payee.id,
            face_value=round(face_value, 2),
            issue_turn=current_turn,
            maturity_turn=current_turn + max(1, tenor_turns),
            discount_rate=rate,
            endorsements=[drawer.id],
        )
        self.active_bills[bill.id] = bill
        return bill

    def discount_bill(
        self,
        holder: Any,
        buyer: Any,
        bill: BillOfExchange,
        current_turn: int
    ) -> Dict[str, Any]:
        """Negotiate and discount the bill to a buyer (bank or merchant) for immediate cash."""
        if bill.id not in self.active_bills or bill.is_settled or bill.is_defaulted:
            return {'success': False, 'message': 'Bill is not actively tradeable'}
        if bill.payee_id != holder.id:
            return {'success': False, 'message': 'Holder does not own this bill'}

        discount_cash = bill.calculate_discounted_value(current_turn)
        if getattr(buyer, 'cash', 0.0) < discount_cash:
            return {'success': False, 'message': 'Buyer has insufficient cash to discount bill'}

        # Strictly conserved transfer of discounted cash
        buyer.cash -= discount_cash
        holder.cash += discount_cash

        # Endorse and transfer ownership to buyer
        bill.endorsements.append(holder.id)
        bill.payee_id = buyer.id

        return {
            'success': True,
            'bill_id': bill.id,
            'face_value': bill.face_value,
            'cash_transferred': discount_cash,
            'haircut': round(bill.face_value - discount_cash, 2),
            'new_payee_id': buyer.id,
        }

    def settle_matured_bills(self, region: Any, current_turn: int) -> Dict[str, Any]:
        """Settle all bills reaching or exceeding maturity turn."""
        agents_by_id = {a.id: a for a in getattr(region, 'agents', [])}
        matured = [b for b in self.active_bills.values() if b.maturity_turn <= current_turn]

        settled_count = 0
        defaulted_count = 0
        total_settled_cash = 0.0

        for bill in matured:
            drawee = agents_by_id.get(bill.drawee_id)
            payee = agents_by_id.get(bill.payee_id)

            if not drawee or not payee:
                # If either agent left or is unavailable, default or Crown liquidation
                bill.is_defaulted = True
                self.defaulted_bills[bill.id] = bill
                del self.active_bills[bill.id]
                defaulted_count += 1
                continue

            if drawee.cash >= bill.face_value:
                # Full honorable settlement
                drawee.cash -= bill.face_value
                payee.cash += bill.face_value
                bill.is_settled = True
                bill.amount_paid = bill.face_value
                self.settled_bills[bill.id] = bill
                del self.active_bills[bill.id]
                settled_count += 1
                total_settled_cash += bill.face_value
            else:
                # Insolvent drawee -> Partial liquidation & Default
                partial = max(0.0, drawee.cash)
                drawee.cash = 0.0
                payee.cash += partial
                bill.amount_paid = partial
                bill.is_defaulted = True
                self.defaulted_bills[bill.id] = bill
                del self.active_bills[bill.id]
                defaulted_count += 1

                # Penalize drawee credit standing
                if hasattr(drawee, 'credit_rating'):
                    drawee.credit_rating = max(0.0, getattr(drawee, 'credit_rating', 1.0) - 0.40)

        return {
            'turn': current_turn,
            'matured_bills': len(matured),
            'settled_count': settled_count,
            'defaulted_count': defaulted_count,
            'total_settled_cash': round(total_settled_cash, 2),
        }

    def get_credit_market_stats(self, region: Any) -> Dict[str, Any]:
        """Compute system-wide elastic credit metrics, leverage, and credit bubble indicators."""
        total_face = sum(b.face_value for b in self.active_bills.values())
        physical_cash = sum(getattr(a, 'cash', 0.0) for a in getattr(region, 'agents', []))
        total_purchasing_power = physical_cash + total_face
        leverage_ratio = round(total_purchasing_power / max(1.0, physical_cash), 3)

        # Bubble detected if bills exceed 1.5x physical cash reserves
        is_bubble = total_face > (physical_cash * 1.5)

        return {
            'active_bills_count': len(self.active_bills),
            'total_face_value': round(total_face, 2),
            'physical_cash': round(physical_cash, 2),
            'total_elastic_liquidity': round(total_purchasing_power, 2),
            'leverage_ratio': leverage_ratio,
            'is_credit_bubble': is_bubble,
        }
