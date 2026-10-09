"""Small, serializable records for named labor-market institutions."""
from dataclasses import dataclass


@dataclass
class AccessRight:
    person_id: int
    plot_id: str
    resource: str
    legal_share: float = 1.0
    usable_share: float = 1.0
    source: str = 'customary'


@dataclass
class CashObligation:
    id: int
    debtor_id: int
    creditor_id: int
    origin: str
    original_principal: float
    balance: float
    interest_rate: float = 0.0
    due_turn: int = 0
    collateral_plot_id: str | None = None
    status: str = 'active'
    last_accrued_turn: int = -1
    last_settled_turn: int = -1


@dataclass
class TenancyAgreement:
    tenant_id: int
    landlord_id: int
    plot_id: str
    type: str = 'cash_rent'
    cash_rent: float = 0.0
    crop_share: float = 0.0
    active: bool = True


@dataclass
class EnforcementCase:
    id: int
    kind: str
    target_person_id: int
    target_plot_id: str | None
    claim_id: int | None
    requested_turn: int
    earliest_turn: int
    state: str = 'pending'
    officer_cost: float = 0.0
    outcome: str = ''


@dataclass
class LaborAgreement:
    worker_id: int
    firm_id: int
    regime: str = 'wage'
    start_turn: int = 0
    term_turns: int = 0
    hours: float = 8.0
    pay_mode: str = 'cash'
    pay_rate: float = 0.0
    deduction_rule: str = 'none'
    exit_rule: str = 'voluntary'
    active: bool = True
    pace: float = 1.0
    piece_rate: float = 0.0
    quota: float = 0.0
