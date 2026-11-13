"""Journal explicit funding and receipts inside one operator settlement."""
from collections import deque
import math

from state_handler import adjust_cash
from economy.actor_accounts import record


class CashDistribution:
    """Match actual payout legs to their named funders, including split funding."""

    def __init__(self, region, turn, kind, mutation_kind, detail=None):
        self.region, self.turn, self.kind = region, turn, kind
        self.mutation_kind, self.detail = mutation_kind, detail or {}
        self.funding = deque()

    def debit(self, actor, amount, *, source_writer):
        adjust_cash(actor, -amount, kind=self.mutation_kind, source_writer=source_writer)
        if amount > 0:
            self.funding.append([actor.id, float(amount)])

    def credit(self, actor, amount, *, source_writer):
        available = sum(balance for _, balance in self.funding)
        if amount > available and not math.isclose(amount, available, abs_tol=1e-8):
            raise ValueError('Operator payout exceeds its recorded funding')
        adjust_cash(actor, amount, kind=self.mutation_kind, source_writer=source_writer)
        left = float(amount)
        while left > 1e-10 and self.funding:
            payer_id, balance = self.funding[0]
            paid = min(left, balance)
            if payer_id != actor.id:
                record(self.region, self.kind, turn=self.turn, payer_id=payer_id,
                       recipient_id=actor.id, amount=paid, detail=self.detail)
            left -= paid
            self.funding[0][1] -= paid
            if self.funding[0][1] <= 1e-10:
                self.funding.popleft()

    def finish(self):
        if sum(balance for _, balance in self.funding) > 1e-8:
            raise ValueError('Operator funding has an unrecorded recipient')
