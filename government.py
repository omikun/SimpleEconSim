"""
Government class wrapping an Agent for proper money-conserving operations.
Supports multiple governments for future multi-nation simulation.
Each Government has configurable population policy attributes that gate
pronatalist measures, enabling/disabling specific mechanisms at runtime.
"""

import math
import random
import hashlib
import json

import econsim_states
from agent import Agent, initialize_agent, seed_traits
from goods import Goods
from logger import loginfo, logwarning, logdebug
import econsim_trade_money as trade


def _trace_public_transfer(government, kind, amount, recipients, *, outflow=True,
                           trace_region=None, operation_id=None,
                           cause_event_ids=None, **inputs):
    """Trace public cash transfers at their treasury mutation point."""
    regions = getattr(government, 'regions', [])
    region = trace_region or next((candidate for candidate in regions
                                  if getattr(candidate, '_run_trace', None) is not None),
                                 regions[0] if regions else None)
    if region is None:
        return
    nation = getattr(region, 'owner_nation', None)
    subject = ({'type': 'nation', 'id': nation.name} if nation is not None
               else {'type': 'tile', 'id': getattr(region, 'name', government.name)})
    unit = getattr(nation, 'currency', None) or getattr(region, 'home_currency', None) or 'local_currency'
    recipient_ids = [str(getattr(item, 'id', item)) for item in recipients]
    turn = inputs.pop('turn', getattr(region, '_last_turn', 0))
    fingerprint = json.dumps({'government': government.name, 'kind': kind,
                              'turn': turn, 'amount': float(amount),
                              'recipients': sorted(recipient_ids), 'inputs': inputs},
                             sort_keys=True, separators=(',', ':'))
    operation_id = (operation_id or 'public:'
                    + hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16])
    local_cash_after = float(government.agent.cash)
    local_cash_before = (local_cash_after + float(amount) if outflow
                         else local_cash_after - float(amount))
    from finance_trace import account_ref, emit_treasury_leg, transfer_contract
    treasury_account = account_ref(
        'government_treasury', government.name, unit,
        nation_id=getattr(nation, 'name', None),
        government_name=government.name,
        subaccount='government_agent.cash', balance_before=local_cash_before,
        balance_after=local_cash_after, balance_scope='government_agent.cash')
    external_account = account_ref(
        'agent_group' if outflow else 'public_revenue_source', operation_id, unit,
        member_count=len(recipient_ids) if outflow else None,
        member_ids=recipient_ids if outflow else None,
        balance_status='individual_balances_not_captured' if outflow
        else 'source_accounts_not_identified')
    if outflow:
        payer_account, payee_account, side = treasury_account, external_account, 'payer'
    else:
        payer_account, payee_account, side = external_account, treasury_account, 'payee'
    contract = transfer_contract(
        operation_id, kind, side=side, amount=amount, amount_currency=unit,
        payer_account=payer_account, payee_account=payee_account,
        local_cash_leg_amount=amount, local_cash_leg_currency=unit,
        counterparty_leg_status=('recipient_ids_listed' if outflow
                                 else 'revenue_source_aggregate_only'),
        mutation_reference={'government': government.name, 'turn': turn,
                            'kind': kind})
    return emit_treasury_leg(
        region, kind=kind, nation_name=subject['id'], currency=unit,
        signed_amount=-float(amount) if outflow else float(amount),
        contract=contract, phase='government', subject_type=subject['type'],
        cause_event_ids=cause_event_ids,
        inputs={'government': government.name, 'recipients': recipient_ids,
                'recipient_count': len(recipient_ids), 'amount': float(amount),
                'turn': turn, **inputs})


def _record_public_cash_transfer(region, turn, kind, payer, recipient, amount,
                                 detail=None, cause_event_ids=None):
    if region is None or amount <= 0:
        return None
    operation_id = (f'public-benefit:{region.name}:{int(turn)}:{kind}:'
                    f'{getattr(payer, "id", "government")}:'
                    f'{getattr(recipient, "id", "recipient")}')
    currency = (getattr(region, 'home_currency', None) or 'local_currency')
    payer_currency = (getattr(payer, 'home_currency', None) or currency)
    recipient_currency = (getattr(recipient, 'home_currency', None) or currency)
    recipient_cash_after = float(getattr(recipient, 'cash', 0.0))
    recipient_cash_before = recipient_cash_after - float(amount)
    aggregate_linked = bool(cause_event_ids)
    from economy.actor_accounts import record as record_economic_event
    journal_event = record_economic_event(
        region, kind, turn=turn, payer_id=getattr(payer, 'id', None),
        recipient_id=getattr(recipient, 'id', None), amount=amount,
        source_id=operation_id, currency=currency, detail=detail or {})
    from finance_trace import account_ref, cash_transfer_contract, emit_cash_transfer
    contract = cash_transfer_contract(
        operation_id, kind, amount=float(amount), currency=currency,
        payer_account=account_ref(
            'government_wallet', str(getattr(payer, 'id', 'government')),
            payer_currency, agent_id=str(getattr(payer, 'id', 'government')),
            balance_status=('see_linked_aggregate_treasury_leg'
                            if aggregate_linked
                            else 'aggregate_treasury_leg_not_recorded'),
            aggregate_treasury_event_ids=list(cause_event_ids or [])),
        payee_account=account_ref(
            'agent_wallet', str(getattr(recipient, 'id', 'recipient')),
            recipient_currency, agent_id=str(getattr(recipient, 'id', 'recipient')),
            tile=region.name, balance_before=recipient_cash_before,
            balance_after=recipient_cash_after, balance_scope='cash_wallet'),
        counterparty_leg_status=(
            'exact_recipient_wallet_and_linked_aggregate_payer_balance'
            if aggregate_linked else
            'exact_recipient_wallet_payer_aggregate_balance_unavailable'),
        benefit_kind=kind)
    return emit_cash_transfer(
        region, kind=f'{kind}_recipient_payment', contract=contract,
        phase='government',
        subject={'type': 'agent', 'id': str(getattr(recipient, 'id', 'recipient')),
                 'tile': region.name},
        inputs={'turn': int(turn), 'benefit_kind': kind,
                'government_name': (detail or {}).get('government'),
                'recipient_id': str(getattr(recipient, 'id', 'recipient')),
                'actor_account_event_id': journal_event['id']
                if journal_event is not None else None,
                'payment_detail': detail or {}},
        cause_event_ids=cause_event_ids)


class Government:
    """A government entity with its own Agent for proper bank interactions.

    Population policy attributes (all disabled by default) can be tuned per
    Government instance, enabling different regions/nations to pursue
    different demographic strategies.
    """

    def __init__(self, name, t, initial_cash=0):
        self.name = name
        self.agent = Agent(t)
        self.agent.output = Goods.gov
        self.agent.is_corporation = False
        self.agent.is_government = True
        initialize_agent(self.agent, Goods.gov, 0, 0, initial_cash)
        self.food_inventory = 0   # food units gov has purchased and stored
        self.debt = 0  # Optional tracking of total borrowed (not needed for accounting)

        # ========== Multi-Region Support ==========
        # Set of agent IDs under this government's jurisdiction.
        # Populated when agents are born into or immigrate to a region.
        self.citizen_ids = set()
        # List of future Region objects (extensible for multi-nation sim).
        self.regions = []

        # ========== Pronatalist / Population Policy Configuration ==========
        # All default to off/neutral so existing simulation behavior is unchanged.

        # 1. Baby Bonus (Singapore / Hungary / France model)
        #     Direct cash transfer to parent upon birth.
        self.baby_bonus_enabled = False
        self.baby_bonus_amount = 50.0

        # 2. Universal Basic Income (Alaska Permanent Fund / Finland model)
        #     Per-turn cash to every non-corp citizen.
        self.ubi_enabled = False
        self.ubi_amount_per_turn = 2.0

        # 3. Extended Child Food Aid (Sweden / France model)
        #     Overrides the hardcoded age-10 cutoff in provide_food_aid.
        self.child_food_aid_max_age = 10  # default matches current hardcoded value

        # 4. Fertility Multiplier (direct pronatalist incentive)
        #     Scales probability_birth for this government's citizens.
        self.fertility_multiplier = 1.0

        # 5. Immigration (Canada / Australia points-based model)
        #     Injects new Agent objects at fixed intervals.
        self.immigration_enabled = False
        self.immigration_per_interval = 5
        self.immigration_interval = 50
        self._last_immigration_turn = 0

        # 6. Child Tax Deduction (Hungary / France quotient familial model)
        #     Reduces taxable income per child (living descendant).
        self.child_tax_deduction_enabled = False
        self.child_tax_deduction_per_child = 10.0

        # 7. Parental Leave (Nordic model)
        #     Pays the parent a per-turn cash amount for a fixed duration after birth.
        self.parental_leave_enabled = False
        self.parental_leave_duration = 10          # turns
        self.parental_leave_amount_per_turn = 3.0

        # 8. Mortality Reduction (Universal Healthcare model)
        #     Multiplier applied to base death probability; < 1.0 lengthens lifespan.
        self.mortality_multiplier = 1.0

        # ========== Trade Policy Configuration ==========
        # All default to enabled for backward compatibility.

        # 9. Import Tariff (revenue on foreign goods entering the region)
        #     When enabled, a fraction of each import sale goes to the
        #     destination government.  Reduced from 10% to 3% (trade
        #     liberalization / FTA-style tariff cut).
        self.import_tariff_enabled = True
        self.import_tariff_rate = 0.03   # fraction of import sale to gov

        # 9b. Duty Drawback (tariff recycling)
        #     Real-world: importing firms get refunds on duties when the
        #     goods are re-sold (US duty drawback, EU bonded warehouses).
        #     The seller keeps this fraction of the tariff; only the
        #     remainder is government revenue.  Reduced tariff income AND
        #     better trader margins.
        self.import_drawback_enabled = True
        self.import_drawback_rate = 0.70  # fraction of tariff refunded to seller

        # 12. Probate Fee (heirless estates)
        #     Real-world: people without family leave bequests to charity;
        #     the state only takes a probate fee (bona vacantia escheat is a
        #     last resort).  The government keeps this fraction of each
        #     heirless estate; the rest goes to the regional charity.
        self.probate_fee_rate = 0.30  # fraction of heirless estate to gov

        # 10. Trader Profit Recycling (capital controls / reserve requirement)
        #     When enabled, a fraction of each import sale is deposited
        #     directly into the destination region's bank to keep liquidity
        #     in the local economy (currently 20% in foreign_sell).
        self.trader_recycling_enabled = True
        self.trader_recycling_rate = 0.20  # fraction of import sale to bank

        # 11. FX regime (Phase 1: central-bank quote with reserves)
        #     'fixed'    - mid pinned at parity; convertibility reserve-capped.
        #     'managed'  (default) - reserve-pressure rule moves the mid.
        #     'floating' - Phase 3 order book; for now behaves like managed.
        self.floating_exchange_rate_enabled = True  # legacy alias
        self.fx_regime = 'managed'

        # ========== Food Aid / Welfare Configuration ==========

        # Number of food units the gov tries to keep in inventory as a buffer
        # for lean turns. Combined with cash reserve, this ensures gov can
        # provide emergency food for at least ~10 turns at low revenue.
        self.target_food_reserve = 100
        # Minimum fraction of starving agents to feed (even if low on funds)
        self.food_aid_min_coverage = 0.1
        # Maximum fraction to feed (capped even with ample funds)
        self.food_aid_max_coverage = 0.5
        # Sovereign food-security policy. The public buyer and aid path may
        # cover an actual meal gap when an AI or player enables emergency aid.
        self.emergency_food_policy = False
        self.emergency_meal_target = 0
        self.food_aid_last_turn = 0
        self._food_aid_turn = -1
        self.food_levy_last_turn = 0

        # ========== Fiscal Policy Configuration ==========
        # Tax rate applied to top 10% taxable income (0.05 - 0.75 range).
        self.tax_rate = 0.25
        # How often (in turns) the government re-evaluates its tax rate.
        self.tax_adjust_interval = 100
        # Per-turn requested financing gap after tax, before bank approval.
        self.borrow_log = []
        # Log of (turn, tax_rate) after each adjustment.
        self.tax_rate_log = []
        # Per-turn income decomposition (monetary income credited to gov cash /
        # deposits).  Lists of {turn, tax, tariff, inheritance} dicts, one per
        # turn, appended by seal_income() at the end of each Region.step().
        self.income_log = []
        # Accumulators for the current turn (reset by seal_income).
        self._income_pending = {}

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _is_citizen(self, agent):
        """Check whether an agent is under this government's jurisdiction."""
        return agent.id in self.citizen_ids

    def _add_citizen(self, agent):
        """Register an agent as a citizen of this government."""
        self.citizen_ids.add(agent.id)

    # ------------------------------------------------------------------
    #  1. Baby Bonus  (Singapore / Hungary / France)
    # ------------------------------------------------------------------
    def provide_baby_bonus(self, t, parent, newborn, region=None):
        """Transfer a one-time cash bonus to the parent after childbirth.

        Args:
            parent: Agent who just reproduced.
            newborn: The newly created Agent.
        Returns:
            float: Amount actually transferred.
        """
        if not self.baby_bonus_enabled or self.baby_bonus_amount <= 0:
            return 0.0
        if self.agent.cash < self.baby_bonus_amount:
            loginfo(t, f"Government({self.name}) insufficient cash for baby bonus")
            return 0.0
        self.agent.cash -= self.baby_bonus_amount
        parent.cash += self.baby_bonus_amount
        treasury_event_id = _trace_public_transfer(
            self, 'baby_bonus_paid', self.baby_bonus_amount, [parent.id],
            newborn_id=str(newborn.id),
            amount_per_recipient=self.baby_bonus_amount, turn=t)
        _record_public_cash_transfer(
            region, t, 'baby_bonus', self.agent, parent, self.baby_bonus_amount,
            {'newborn_id': newborn.id, 'government': self.name},
            cause_event_ids=([treasury_event_id] if treasury_event_id else None))
        loginfo(t, f"Government({self.name}) paid ${self.baby_bonus_amount:.2f} baby bonus to "
                f"{parent.name()} for newborn {newborn.name()}")
        return self.baby_bonus_amount

    # ------------------------------------------------------------------
    #  2. Universal Basic Income  (Alaska / Finland)
    # ------------------------------------------------------------------
    def distribute_ubi(self, t, agents, region=None):
        """Give every eligible non-corp citizen a per-turn cash amount.

        Args:
            agents: Full agent list (filtered internally by citizenship).
        Returns:
            float: Total UBI distributed this turn.
        """
        if not self.ubi_enabled or self.ubi_amount_per_turn <= 0:
            return 0.0

        total = 0.0
        scaled_for_shortfall = False
        paid_fraction = 1.0
        for agent in agents:
            if agent.is_corporation or agent.alive is False:
                continue
            if not self._is_citizen(agent):
                continue
            agent.cash += self.ubi_amount_per_turn
            total += self.ubi_amount_per_turn

        if total > 0 and self.agent.cash >= total:
            self.agent.cash -= total
            logdebug(t, f"Government({self.name}) distributed ${total:.2f} UBI "
                     f"to {len([a for a in agents if self._is_citizen(a) and not a.is_corporation])} citizens")
        elif total > 0:
            scaled_for_shortfall = True
            # Gov can't fully fund — distribute whatever is available
            shortfall = total - self.agent.cash
            # Scale down proportionally
            if self.agent.cash > 0:
                scale = self.agent.cash / total
                paid_fraction = scale
                for agent in agents:
                    if agent.is_corporation or agent.alive is False:
                        continue
                    if not self._is_citizen(agent):
                        continue
                    agent.cash -= self.ubi_amount_per_turn  # undo
                    paid = self.ubi_amount_per_turn * scale
                    agent.cash += paid
            else:
                paid_fraction = 0.0
            self.agent.cash = 0.0
            logwarning(t, f"Government({self.name}) UBI shortfall ${shortfall:.2f}, scaled payments")
            total -= shortfall
        if total > 0:
            recipients = [agent.id for agent in agents
                          if not agent.is_corporation and agent.alive is not False
                          and self._is_citizen(agent)]
            treasury_event_id = _trace_public_transfer(
                self, 'ubi_distributed', total, recipients,
                scheduled_per_person=self.ubi_amount_per_turn,
                scaled_for_shortfall=scaled_for_shortfall, turn=t)
            for agent in agents:
                if not agent.is_corporation and agent.alive is not False \
                        and self._is_citizen(agent):
                    _record_public_cash_transfer(
                        region, t, 'ubi_payment', self.agent, agent,
                        self.ubi_amount_per_turn * paid_fraction,
                        {'scheduled_per_person': self.ubi_amount_per_turn,
                         'scaled_for_shortfall': scaled_for_shortfall,
                         'government': self.name},
                        cause_event_ids=([treasury_event_id]
                                         if treasury_event_id else None))
        return total

    # ------------------------------------------------------------------
    #  3. Child Food Aid Max Age  (Sweden / France)
    # ------------------------------------------------------------------
    def get_child_food_aid_max_age(self):
        """Return the maximum age (in turns) for automatic newborn food aid.

        Overrides the hardcoded value ``10`` in ``provide_food_aid``.
        """
        return self.child_food_aid_max_age

    # ------------------------------------------------------------------
    #  4. Fertility Multiplier
    # ------------------------------------------------------------------
    def get_fertility_multiplier(self):
        """Return the multiplier applied to the base ``probability_birth`` probability."""
        return max(0.0, self.fertility_multiplier)

    # ------------------------------------------------------------------
    #  5. Immigration  (Canada / Australia points-based)
    # ------------------------------------------------------------------
    def spawn_immigrants(self, t, agents):
        """Create new immigrant agents if the immigration interval has elapsed.

        Conservation-safe: immigrants are NEVER minted out of thin air.  Each
        is derived from an existing adult citizen (a "chain migrant" split
        off a resident), inheriting traits+identity and a conservative share
        of the parent's cash — so every agent traces to another agent and the
        per-currency total never changes.

        Returns:
            list[Agent]: Newly created immigrant agents (empty list if interval
                          not reached, feature disabled, or no eligible parent).
        """
        if not self.immigration_enabled:
            return []

        if t - self._last_immigration_turn < self.immigration_interval:
            return []
        self._last_immigration_turn = t

        # Eligible resident adults (non-corp, non-gov) we can split off.
        from labor_choice import career_lifecycle_age
        parents = [a for a in agents
                   if getattr(a, 'alive', True)
                   and not getattr(a, 'is_corporation', False)
                   and not getattr(a, 'is_government', False)
                   and not getattr(a, 'is_trader', False)
                   and career_lifecycle_age(a, t) > 20
                   and a.cash > 40]
        if not parents:
            return []

        new_agents = []
        for _ in range(self.immigration_per_interval):
            parent = random.choice(parents)
            # Split the parent's cash: the child takes a bounded share, the
            # parent keeps the rest — a pure transfer, no money created.
            share = min(parent.cash * 0.3, 50.0)
            share = min(share, parent.cash - 10.0)
            share = max(0.0, share)

            immigrant = Agent(t)
            immigrant.founding_age_offset = 22 + ((int(immigrant.id) * 11) % 24)
            immigrant.parent = parent
            # v3: homeland inherited from the sponsor (set once; never re-pointed).
            immigrant.origin_nation = getattr(parent, 'origin_nation', None)
            immigrant.home_currency = getattr(parent, 'home_currency', None)
            immigrant._bank_ref = getattr(parent, '_bank_ref', None)
            immigrant.region = getattr(parent, 'region', None)
            immigrant.output = parent.output
            seed_traits(immigrant, parent=parent)
            initialize_agent(immigrant, parent.output, 0, 0, share)

            parent.cash -= share
            if parent.descendants is None:
                parent.descendants = []
            parent.descendants.append(immigrant)
            # Transfer a small food grant from the parent (conserved — the
            # parent's inventory falls by exactly what the child receives).
            food_grant = max(0, min(4, parent.inv_get(Goods.food, 0) // 2))
            if food_grant > 0:
                parent.inv_add(Goods.food, -food_grant)
                immigrant.inv_set(Goods.food, food_grant)

            # Register as citizen
            self._add_citizen(immigrant)

            new_agents.append(immigrant)
            loginfo(t, f"Government({self.name}) accepted immigrant {immigrant.name()} "
                    f"derived from {parent.name()} (share ${share:.2f})")

        return new_agents

    # ------------------------------------------------------------------
    #  6. Child Tax Deduction  (Hungary / France)
    # ------------------------------------------------------------------
    def compute_child_tax_deduction(self, agent):
        """Return the amount to subtract from an agent's taxable income
        based on number of living descendants.

        Only active when ``child_tax_deduction_enabled`` is ``True``.
        """
        if not self.child_tax_deduction_enabled:
            return 0.0
        living_descendants = [d for d in getattr(agent, 'descendants', []) if d.alive]
        num_children = len(living_descendants)
        deduction = num_children * self.child_tax_deduction_per_child
        return max(0.0, deduction)

    # ------------------------------------------------------------------
    #  7. Parental Leave  (Nordic model)
    # ------------------------------------------------------------------
    def grant_parental_leave(self, t, parent):
        """Mark a parent as eligible for parental leave cash transfers.

        Sets ``_parental_leave_turns_remaining`` on the parent agent.
        """
        if not self.parental_leave_enabled or self.parental_leave_duration <= 0:
            return

        parent._parental_leave_turns_remaining = self.parental_leave_duration
        loginfo(t, f"Government({self.name}) granted {self.parental_leave_duration} turns of "
                f"parental leave to {parent.name()}")

    def process_parental_leave(self, t, agents, region=None):
        """Pay parental leave cash to all eligible parents and decrement their counter.

        Returns:
            float: Total leave payments made this turn.
        """
        if not self.parental_leave_enabled:
            return 0.0

        total = 0.0
        recipients = []
        payments = []
        for agent in agents:
            if agent.is_corporation or agent.alive is False:
                continue
            remaining = getattr(agent, '_parental_leave_turns_remaining', 0)
            if remaining <= 0:
                continue

            pay = self.parental_leave_amount_per_turn
            if self.agent.cash < pay:
                pay = max(0.0, self.agent.cash)
            if pay > 0:
                self.agent.cash -= pay
                agent.cash += pay
                total += pay
                recipients.append(agent.id)
                payments.append((agent, pay))

            agent._parental_leave_turns_remaining = remaining - 1
            logdebug(t, f"Government({self.name}) paid ${pay:.2f} parental leave to "
                     f"{agent.name()} ({agent._parental_leave_turns_remaining} turns remaining)")

        if total > 0:
            treasury_event_id = _trace_public_transfer(
                self, 'parental_leave_paid', total, recipients,
                amount_per_turn=self.parental_leave_amount_per_turn, turn=t)
            for agent, pay in payments:
                _record_public_cash_transfer(
                    region, t, 'parental_leave', self.agent, agent, pay,
                    {'scheduled_per_turn': self.parental_leave_amount_per_turn,
                     'government': self.name},
                    cause_event_ids=([treasury_event_id]
                                     if treasury_event_id else None))
        return total

    # ------------------------------------------------------------------
    #  8. Mortality Reduction  (Universal Healthcare)
    # ------------------------------------------------------------------
    def get_death_probability(self, agent, base_probability):
        """Return the adjusted death probability for an agent.

        The base probability (from the age-based mortality table) is multiplied
        by ``mortality_multiplier``.  Values < 1.0 extend lifespan.

        Args:
            agent: The agent subject to death.
            base_probability: Value from the standard mortality table (0-1).
        Returns:
            float: Adjusted probability, clamped to [0, 1].
        """
        return max(0.0, min(1.0, base_probability * self.mortality_multiplier))

    # ==================================================================
    #  Existing methods (refactored to use config where applicable)
    # ==================================================================

    def __repr__(self):
        return f"Government({self.name})"

    def get_trade_fee_multiplier(self, source_nation: str | None = None, source_region=None,
                                 *, include_import_tariff=True):
        """Return the net fraction of a trader's sale price they actually keep
        after all destination-region fees (recycling, tariff, ask discount).

        A region's traders use this when deciding whether a cross-region
        trade is profitable. Callers that apply the statutory tariff and
        drawback separately can exclude it here with ``include_import_tariff``.
        """
        m = 0.95  # base ask discount (sell at 95% of dest price)
        if self.trader_recycling_enabled:
            m *= (1 - self.trader_recycling_rate)
        if include_import_tariff and self.import_tariff_enabled:
            discount = 0.0
            src_n = source_nation
            if src_n is None and source_region is not None:
                owner = getattr(source_region, 'owner_nation', None)
                src_n = owner.name if owner else None
            
            # Destination nation identifier
            dest_n = getattr(self, 'nation_name', None) or getattr(self, 'name', None)
            if src_n and dest_n:
                try:
                    import diplomacy
                    discount = diplomacy.get_diplomacy().get_tariff_discount(dest_n, src_n)
                except Exception:
                    discount = 0.0

            # Net tariff hit after duty drawback and trade pact discount
            effective_tariff_rate = self.import_tariff_rate * (1.0 - discount)
            net_tariff = effective_tariff_rate * (1.0 - self.import_drawback_rate)
            m *= (1.0 - net_tariff)
        return m

    def collect_tax(self, t, amount):
        """Receive tax revenue. Returns amount received."""
        if amount > 0:
            self.agent.cash += amount
            self.record_income(t, 'tax', amount)
            _trace_public_transfer(self, 'legacy_tax_collected', amount, [],
                                   outflow=False, tax_source='legacy_collect_tax',
                                   turn=t)
            loginfo(t, f"Government({self.name}) collected ${amount:.2f} in taxes")
        return amount

    def receive_tariff(self, t, amount, region=None):
        """Credit import-tariff revenue. Splits 80% to National Sovereign and 20% to local port tile."""
        if amount <= 0:
            return
        gross_amount = amount
        owner_nation = getattr(region, 'owner_nation', None) if region else None
        intercepted = 0.0
        creditor_name = None
        interception_event_ids = []
        if owner_nation:
            try:
                from imperialism import get_imperialism_manager
                imp_mgr = get_imperialism_manager()
            except Exception:
                imp_mgr = None
            if imp_mgr is not None:
                amount, intercepted, creditor_name = imp_mgr.intercept_revenue(
                    owner_nation.name, amount, t, trace_region=region,
                    trace_event_ids=interception_event_ids, source='tariff')
        if amount <= 0:
            return
        nat_gov = getattr(owner_nation, 'government', None) if owner_nation else None
        operation_id = None
        if region is not None:
            clock = getattr(region, '_collective_trace_clock', {}) or {}
            sequence = int(clock.get('next', 0))
            operation_id = f'tariff:{region.name}:{int(t)}:{sequence}'
        if nat_gov is not None and nat_gov is not self:
            nat_share = round(amount * 0.80, 6)
            local_share = amount - nat_share
            nat_gov.agent.cash += nat_share
            _trace_public_transfer(
                nat_gov, 'tariff_collected', nat_share, [], outflow=False,
                trace_region=region, operation_id=operation_id, turn=t,
                cause_event_ids=interception_event_ids or None,
                tariff_allocation='national', gross_tariff=gross_amount,
                net_after_interception=amount, intercepted_tariff=intercepted,
                interception_creditor=creditor_name
                if owner_nation else None, national_share=nat_share,
                local_share=local_share, source='import_customs')
            nat_gov.record_income(t, 'tariff', nat_share)
            self.agent.cash += local_share
            _trace_public_transfer(
                self, 'tariff_collected', local_share, [], outflow=False,
                trace_region=region, operation_id=operation_id, turn=t,
                cause_event_ids=interception_event_ids or None,
                tariff_allocation='local_port', gross_tariff=gross_amount,
                net_after_interception=amount, intercepted_tariff=intercepted,
                interception_creditor=creditor_name
                if owner_nation else None, national_share=nat_share,
                local_share=local_share, source='import_customs')
            self.record_income(t, 'tariff', local_share)
        else:
            self.agent.cash += amount
            if owner_nation is not None and region is not None:
                _trace_public_transfer(
                    self, 'tariff_collected', amount, [], outflow=False,
                    trace_region=region, operation_id=operation_id, turn=t,
                    cause_event_ids=interception_event_ids or None,
                    tariff_allocation='single_treasury', gross_tariff=gross_amount,
                    net_after_interception=amount, intercepted_tariff=intercepted,
                    interception_creditor=creditor_name,
                    national_share=amount if nat_gov is self else 0.0,
                    local_share=amount if nat_gov is not self else 0.0,
                    source='import_customs')
            self.record_income(t, 'tariff', amount)

    def record_income(self, t, source, amount):
        """Accumulate a per-turn income amount under *source*.

        Sources: 'tax', 'tariff', 'inheritance'.  Amounts are summed into
        _income_pending for the current turn and snapshotted by seal_income().
        """
        if amount <= 0:
            return
        scenario_world = getattr(self, 'scenario_debt_world', None)
        if scenario_world is not None:
            from scenario_debt import intercept_assigned_revenue
            amount -= intercept_assigned_revenue(scenario_world, self, source, amount, t)
            from scenario_occupation import intercept_revenue
            amount -= intercept_revenue(scenario_world, self, source, amount, t)
            from scenario_projects import allocate_revenue
            amount = allocate_revenue(scenario_world, self, source, amount, t)
        pending = self._income_pending
        pending[source] = pending.get(source, 0.0) + amount

    def seal_income(self, t):
        """Append this turn's income snapshot to income_log and reset.

        Must be called exactly once per turn, after every income source for
        that turn has recorded (Region.step() calls this at the very end of
        the turn body).
        """
        pending = self._income_pending
        snapshot = {
            'turn': t,
            'tax': pending.get('tax', 0.0),
            'tariff': pending.get('tariff', 0.0),
            'inheritance': pending.get('inheritance', 0.0),
        }
        self.income_log.append(snapshot)
        self._income_pending = {}
        return snapshot
    # ==================================================================
    #  Food Purchasing (called by region._trade, like charity)
    # ==================================================================

    def bid_food(self, food_price, current_desired, bank, *,
                 trace_region=None, t=None):
        """Return the quantity of food this government wants to buy this turn.

        Gov tries to maintain target_food_reserve as a buffer. Withdraws
        cash from bank as needed.
        """
        emergency_target = (max(0, int(self.emergency_meal_target))
                            if self.emergency_food_policy else 0)
        max_inventory = max(self.target_food_reserve * 2, emergency_target)
        space = max_inventory - self.food_inventory
        if space <= 0:
            return 0

        gov_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        if gov_wealth < food_price:
            return 0

        affordable = gov_wealth // food_price
        needed = max(0, max(self.target_food_reserve, emergency_target) - self.food_inventory)
        purchase_limit = (max(current_desired, emergency_target)
                          if self.emergency_food_policy else current_desired)
        potential_bid = min(space, affordable, purchase_limit, needed)
        if potential_bid <= 0:
            return 0

        # Withdraw enough cash from bank to cover the bid
        needed_cash = potential_bid * food_price
        if self.agent.cash < needed_cash:
            from_bank = min(needed_cash - self.agent.cash,
                            bank.deposits.get(self.agent, 0))
            if from_bank > 0:
                bank.Withdraw(self.agent, from_bank, trace_region=trace_region,
                              t=t, reason='government_food_purchase')

        return potential_bid

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased."""
        self.agent.cash -= cost

    def deposit_remaining(self, bank, *, trace_region=None, t=None):
        """Deposit leftover hand cash back into bank."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash,
                         trace_region=trace_region, t=t,
                         reason='government_post_market_cash_sweep')

    # ==================================================================
    #  Food Aid (post-lifecycle, uses inventory + scales by funds)
    # ==================================================================

    def provide_food_aid(self, t, agents, food_price, region=None):
        """Move public food to residents before this turn's meal and mortality.

        Coverage ranges from food_aid_min_coverage (0.1) to
        food_aid_max_coverage (0.5) depending on how much excess
        food inventory + cash the government has above its target reserve.

        Children under child_food_aid_max_age get 1 food unconditionally
        if inventory permits.

        Returns total food given.
        """
        child_max_age = self.get_child_food_aid_max_age()
        if getattr(self, '_food_aid_turn', -1) != t:
            self.food_aid_last_turn = 0
            self.food_levy_last_turn = 0
            self._food_aid_turn = t
            for agent in agents:
                agent.food_aid_received_this_turn = 0
        cumulative_aid_before = int(self.food_aid_last_turn)
        if self.emergency_food_policy and region is not None:
            self._levy_emergency_food(t, agents, region)
        inventory_before = self.food_inventory
        operation_region = getattr(region, 'name', self.name)
        operation_id = (f'government-food-aid:{operation_region}:{int(t)}:'
                        f'{cumulative_aid_before}')
        transfers = []
        recipient_event_ids = []

        # Separate candidates: children and starving agents
        candidates = [a for a in agents
                      if not a.is_corporation and not a.is_government]
        if self.emergency_food_policy:
            from nutrition import appetite_units
            needy = sorted((a for a in candidates
                            if a.inv_get(Goods.food, 0) < appetite_units(a)),
                           key=lambda a: (-a.hungry_steps, a.energy_reserve_kcal,
                                          a.inv_get(Goods.food, 0), a.id))
            for agent in needy:
                if self.food_inventory <= 0:
                    break
                missing = max(0, appetite_units(agent) - agent.inv_get(Goods.food, 0))
                given = min(missing, self.food_inventory)
                if given:
                    government_food_before = int(self.food_inventory)
                    recipient_food_before = int(agent.inv_get(Goods.food, 0))
                    self.food_inventory -= given
                    agent.inv_add(Goods.food, given)
                    agent.food_aid_received_this_turn = (
                        getattr(agent, 'food_aid_received_this_turn', 0) + given)
                    transfer = {
                        'agent_id': agent.id, 'units': given,
                        'government_food_before': government_food_before,
                        'government_food_after': int(self.food_inventory),
                        'recipient_food_before': recipient_food_before,
                        'recipient_food_after': int(agent.inv_get(Goods.food, 0)),
                    }
                    event_id = self._trace_food_aid_recipient(
                        t, region, operation_id, len(transfers), agent, given,
                        government_food_before, int(self.food_inventory),
                        recipient_food_before, int(agent.inv_get(Goods.food, 0)),
                        emergency=True)
                    if event_id is not None:
                        transfer['trace_event_id'] = event_id
                        recipient_event_ids.append(event_id)
                    transfers.append(transfer)
            total_food_given = inventory_before - self.food_inventory
            self.food_aid_last_turn += total_food_given
            self._trace_food_aid(t, inventory_before, transfers, region,
                                 operation_id=operation_id,
                                 recipient_event_ids=recipient_event_ids)
            return total_food_given

        children = [a for a in candidates
                    if getattr(a, 'is_native_child', False)
                    and a.age(t) <= child_max_age and a.hungry_steps == 0]
        starving = [a for a in candidates if a.hungry_steps > 0]

        total_food_given = 0

        # 1. Children: feed all if we have enough food
        for child in children:
            if self.food_inventory <= 0:
                break
            government_food_before = int(self.food_inventory)
            recipient_food_before = int(child.inv_get(Goods.food, 0))
            self.food_inventory -= 1
            child.inv_add(Goods.food, 1)
            total_food_given += 1
            transfer = {
                'agent_id': child.id, 'units': 1,
                'government_food_before': government_food_before,
                'government_food_after': int(self.food_inventory),
                'recipient_food_before': recipient_food_before,
                'recipient_food_after': int(child.inv_get(Goods.food, 0)),
            }
            event_id = self._trace_food_aid_recipient(
                t, region, operation_id, len(transfers), child, 1,
                government_food_before, int(self.food_inventory),
                recipient_food_before, int(child.inv_get(Goods.food, 0)),
                emergency=False)
            if event_id is not None:
                transfer['trace_event_id'] = event_id
                recipient_event_ids.append(event_id)
            transfers.append(transfer)
            loginfo(t, f"Government({self.name}) child food aid to {child.name()}")

        # 2. Determine how many starving to feed based on available surplus
        if self.food_inventory > 0 and starving:
            # Compute surplus: food + cash reserves above target
            cash_above_reserve = max(0, self.agent.cash
                                     - self.target_food_reserve * food_price)
            food_surplus = self.food_inventory + (cash_above_reserve / max(0.01, food_price))
            desired_feed = len(starving)
            import math
            capacity = max(1.0, desired_feed * self.food_aid_max_coverage)
            coverage = (self.food_aid_min_coverage
                        + (self.food_aid_max_coverage - self.food_aid_min_coverage)
                        * (1.0 - math.exp(-food_surplus / capacity)))
            feed_count = max(1, int(desired_feed * coverage))

            feed_count = min(int(feed_count), self.food_inventory, len(starving))

            # Randomly select starving agents to feed
            if feed_count < len(starving):
                random.shuffle(starving)
            fed = starving[:int(feed_count)]

            for agent in fed:
                government_food_before = int(self.food_inventory)
                recipient_food_before = int(agent.inv_get(Goods.food, 0))
                self.food_inventory -= 1
                agent.inv_add(Goods.food, 1)
                agent.food_aid_received_this_turn = (
                    getattr(agent, 'food_aid_received_this_turn', 0) + 1)
                total_food_given += 1
                transfer = {
                    'agent_id': agent.id, 'units': 1,
                    'government_food_before': government_food_before,
                    'government_food_after': int(self.food_inventory),
                    'recipient_food_before': recipient_food_before,
                    'recipient_food_after': int(agent.inv_get(Goods.food, 0)),
                }
                event_id = self._trace_food_aid_recipient(
                    t, region, operation_id, len(transfers), agent, 1,
                    government_food_before, int(self.food_inventory),
                    recipient_food_before, int(agent.inv_get(Goods.food, 0)),
                    emergency=False)
                if event_id is not None:
                    transfer['trace_event_id'] = event_id
                    recipient_event_ids.append(event_id)
                transfers.append(transfer)
                loginfo(t, f"Government({self.name}) food aid to {agent.name()} "
                        f"(hungry_steps={agent.hungry_steps})")

        if total_food_given > 0:
            loginfo(t, f"Government({self.name}) distributed {total_food_given} food "
                    f"(remaining inventory: {self.food_inventory}, "
                    f"cash: ${self.agent.cash:.2f})")

        self._trace_food_aid(t, inventory_before, transfers, region,
                             operation_id=operation_id,
                             recipient_event_ids=recipient_event_ids)
        self.food_aid_last_turn += total_food_given
        return total_food_given

    def _levy_emergency_food(self, t, agents, region):
        """Collect a bounded in-kind surplus tax for residents' current meals."""
        from food_levy import levy_capacity, record_levy
        from nutrition import appetite_units
        from run_trace import emit

        residents = [a for a in agents if a.alive and not a.is_corporation
                     and not a.is_government and not getattr(a, 'military_unit_id', None)]
        meal_gap = sum(max(0, appetite_units(a) - a.inv_get(Goods.food, 0))
                       for a in residents)
        needed = max(0, meal_gap - self.food_inventory)
        if needed == 0:
            return 0
        donors = []
        for a in agents:
            if (not a.alive or a.is_government
                    or getattr(a, 'military_unit_id', None)):
                continue
            reserve = 0 if a.is_corporation else appetite_units(a)
            surplus = max(0, a.inv_get(Goods.food, 0) - reserve)
            if surplus > 0:
                donors.append((a, surplus))
        donors.sort(key=lambda row: (-int(row[0].is_corporation), -row[1], row[0].id))
        inventory_before = self.food_inventory
        levies = []
        for donor, surplus in donors:
            if needed <= 0:
                break
            reserve = 0 if donor.is_corporation else appetite_units(donor)
            food_before = int(donor.inv_get(Goods.food, 0))
            levy_capacity_before = levy_capacity(donor, reserve)
            taken = min(needed, levy_capacity_before)
            if taken <= 0:
                continue
            donor.inv_add(Goods.food, -taken)
            record_levy(donor, taken)
            self.food_inventory += taken
            needed -= taken
            levies.append({'donor_id': donor.id, 'units': taken,
                           'corporation': bool(donor.is_corporation),
                           'food_before': food_before,
                           'food_after': int(donor.inv_get(Goods.food, 0)),
                           'protected_reserve_units': reserve,
                           'available_surplus_before': max(0, food_before - reserve),
                           'levy_capacity_before': levy_capacity_before})
        collected = self.food_inventory - inventory_before
        if collected:
            self.food_levy_last_turn += collected
            region.emergency_grain_levy_units = (
                getattr(region, 'emergency_grain_levy_units', 0) + collected)
            clock = getattr(region, '_collective_trace_clock', {}) or {}
            sequence = int(clock.get('next', 0))
            operation_id = f'emergency-food-levy:{region.name}:{int(t)}:{sequence}'
            levy_contract = {
                'contract_version': 'goods_transfer.v1',
                'operation_id': operation_id,
                'operation_type': 'emergency_food_levy',
                'good': Goods.food.name,
                'unit': 'units',
                'amount': int(collected),
                'payer_account': {
                    'type': 'agent_group', 'id': operation_id,
                    'member_count': len(levies),
                    'member_ids': [str(row['donor_id']) for row in levies],
                    'balance_scope': 'individual_food_inventory',
                },
                'payee_account': {
                    'type': 'government_food_inventory', 'id': self.name,
                    'balance_before': int(inventory_before),
                    'balance_after': int(self.food_inventory),
                    'balance_scope': 'food_inventory',
                },
                'donor_legs': levies,
                'counterparty_leg_status': 'donor_and_public_inventory_balances_captured',
            }
            emit(region, kind='emergency_food_levy', record_class='transfer',
                 phase='livelihood',
                 subject={'type': 'tile', 'id': region.name, 'good': Goods.food.name},
                 metric_id='goods.emergency_levy', unit='units',
                 before=inventory_before, after=self.food_inventory,
                 inputs={'turn': t, 'operation_id': operation_id,
                         'transfer_contract': levy_contract,
                         'meal_gap_units': meal_gap,
                         'units_collected': collected,
                         'remaining_meal_gap_units': needed,
                         'donor_cap_fraction': 0.25,
                         'donors': levies})
        return collected

    def _trace_food_aid_recipient(self, t, region, operation_id, index, agent,
                                  units, government_before, government_after,
                                  recipient_before, recipient_after, *, emergency):
        if region is None:
            region = next((candidate for candidate in self.regions
                           if getattr(candidate, 'gov', None) is self
                           and getattr(candidate, '_run_trace', None) is not None), None)
        if region is None:
            return None
        from run_trace import emit
        from finance_trace import account_ref

        transfer_id = f'{operation_id}:recipient:{agent.id}'
        contract = {
            'contract_version': 'goods_transfer.v1',
            'operation_id': transfer_id,
            'operation_type': 'government_food_aid',
            'good': Goods.food.name,
            'unit': 'food_units',
            'amount': int(units),
            'payer_account': account_ref(
                'government_food_inventory', self.name, 'food_units',
                balance_before=int(government_before),
                balance_after=int(government_after),
                balance_scope='food_inventory'),
            'payee_account': account_ref(
                'agent_inventory', agent.id, 'food_units',
                balance_before=int(recipient_before),
                balance_after=int(recipient_after),
                balance_scope='inventory.food'),
            'counterparty_leg_status': 'both food inventory balances captured',
        }
        return emit(
            region, kind='government_food_aid_recipient',
            record_class='transfer', phase='livelihood',
            subject={'type': 'tile/agent', 'id': str(agent.id),
                     'tile': region.name, 'good': Goods.food.name},
            metric_id='goods.food_aid_recipient', unit='food_units',
            before=int(recipient_before), after=int(recipient_after),
            formula_id='government.food_aid_recipient_transfer.v1',
            inputs={'operation_id': transfer_id, 'aid_operation_id': operation_id,
                    'turn': int(t), 'transfer_index': int(index),
                    'agent_id': agent.id, 'units': int(units),
                    'government': self.name, 'emergency_policy': bool(emergency),
                    'recipient_food_before': int(recipient_before),
                    'recipient_food_after': int(recipient_after),
                    'government_food_before': int(government_before),
                    'government_food_after': int(government_after),
                    'transfer_contract': contract})

    def _trace_food_aid(self, t, inventory_before, transfers, region=None, *,
                        operation_id=None, recipient_event_ids=None):
        if not transfers:
            return
        from run_trace import emit
        if region is None:
            region = next((r for r in self.regions if getattr(r, 'gov', None) is self), None)
        if region is None:
            return
        emit(region, kind='government_food_aid', record_class='transfer',
             subject={'type': 'tile', 'id': region.name, 'good': Goods.food.name},
             metric_id='goods.food_aid', unit='units',
             before=inventory_before, after=self.food_inventory,
             inputs={'turn': t, 'operation_id': operation_id,
                     'emergency': self.emergency_food_policy,
                     'units_delivered': inventory_before - self.food_inventory,
                     'recipients': transfers},
             cause_event_ids=recipient_event_ids or None)

    def distribute_welfare(self, t, agents, min_reserve=0, region=None):
        """Distribute all excess cash above min_reserve to starving agents.

        Args:
            agents: list of agents to consider for welfare
            min_reserve: minimum cash to keep for next turn's food aid
        """
        distributable = max(0, self.agent.cash - min_reserve)
        if distributable <= 0:
            return 0

        starving_agents = [agent for agent in agents
                           if agent.hungry_steps > 0 and not agent.is_corporation]
        if not starving_agents:
            return 0

        welfare = distributable / len(starving_agents)
        total_distributed = 0
        for agent in starving_agents:
            agent.cash += welfare
            total_distributed += welfare

        self.agent.cash -= total_distributed
        treasury_event_id = _trace_public_transfer(
            self, 'welfare_distributed', total_distributed,
            [agent.id for agent in starving_agents],
            minimum_reserve=min_reserve,
            eligible_starving=len(starving_agents), turn=t)
        for agent in starving_agents:
            _record_public_cash_transfer(
                region, t, 'welfare_payment', self.agent, agent, welfare,
                {'minimum_reserve': min_reserve,
                 'eligible_starving': len(starving_agents),
                 'government': self.name},
                cause_event_ids=([treasury_event_id]
                                 if treasury_event_id else None))
        logdebug(t, f"Government({self.name}) distributed ${total_distributed:.2f} welfare "
                    f"to {len(starving_agents)} agents")
        return total_distributed


def trace_income_snapshot(government, region, snapshot, t, *, scope,
                          member_tiles=None):
    """Explain the retained revenue snapshot shown in government charts."""
    from run_trace import emit
    categories = ('tax', 'tariff', 'inheritance')
    components = {key: float(snapshot.get(key, 0.0)) for key in categories}
    total = sum(components.values())
    history = getattr(government, 'income_log', ())
    previous = history[-2] if len(history) > 1 else None
    before = (sum(float(previous.get(key, 0.0)) for key in categories)
              if previous is not None else None)
    return emit(
        region, kind='government_income_calculation',
        record_class='calculation', phase='local',
        subject={'type': 'tile', 'id': region.name},
        metric_id='finance.government_income',
        unit=getattr(region, 'home_currency', None) or 'local_currency',
        before=before, after=total,
        formula_id='government.income_components.v1',
        inputs={'government_id': government.name,
                'scope': scope,
                'member_tiles': list(member_tiles or (region.name,)),
                'snapshot_turn': int(snapshot.get('turn', t)),
                'components': components,
                'component_basis': 'retained_income_after_revenue_interceptions',
                'formula_result': total})


def create_default_government(t, initial_cash=200):
    """Create the default government for the simulation."""
    gov = Government("Default", t, initial_cash)
    econsim_states.governments.append(gov)
    econsim_states.default_government = gov
    loginfo(t, f"Created default government with ${initial_cash:.2f}")
    return gov


# ======================================================================
#  Convenience: find the government responsible for an agent
# ======================================================================

def find_government_for_agent(agent):
    """Return the Government that claims the given agent as a citizen,
    or the default government if none do."""
    for gov in econsim_states.governments:
        if agent.id in gov.citizen_ids:
            return gov
    return econsim_states.default_government
