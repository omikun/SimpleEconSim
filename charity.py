"""
Charity: a non-government entity that collects donations from wealthy agents
and corporations, buys food at market price, and distributes it to the hungry
and young.

Uses an Agent instance internally. All unspent cash is deposited in the bank
to keep total_deposits healthy. Cash is withdrawn as needed for food purchases.
"""
from treasury_trace import begin_public_change as _trace_public_begin, finish_public_change as _trace_public_finish

import random

from goods import Goods
from logger import loginfo
from agent import Agent


class Charity:
    """Independent charity that redistributes food to the needy.

    Cash is held in an internal Agent (not in region.agents list).
    Unspent cash is deposited in the bank; it is withdrawn as needed
    for food purchases. _total_cash() adds charity.agent.cash to
    compensate for the bank deposit reduction when cash is in hand.
    """

    def __init__(self, name, recipes):
        self.name = f"{name}-Charity"
        self.recipes = recipes

        # Internal Agent for cash management. NOT added to region.agents.
        self.agent = Agent(0)
        self.agent.output = Goods.food
        self.agent.is_charity = True

        self.food_inventory = 0
        self.log = {"donations_collected": 0.0, "food_purchased": 0,
                     "food_distributed": 0, "recipients": 0}

        # Config
        self.low_cash_threshold_multiplier = 50
        self.corp_donate_normal_pct = 0.05
        self.corp_donate_emergency_pct = 0.10
        self.wealthy_donate_normal_pct = 0.02
        self.wealthy_donate_emergency_pct = 0.04
        self.wealth_donation_threshold = 100.0
        self.wealthy_fraction = 0.20
        self.max_food_per_agent = 1

    # ------------------------------------------------------------------
    # Cash helpers
    # ------------------------------------------------------------------

    @property
    def cash(self):
        """Current hand cash (agent.cash)."""
        return self.agent.cash

    @property
    def total_liquid(self):
        """Total liquid wealth including bank deposits."""
        bank = getattr(self.agent, '_bank_ref', None)
        deposit = bank.deposits.get(self.agent, 0) if bank else 0
        return self.agent.cash + deposit

    def deposit_all(self, bank, *, trace_region=None, t=None):
        """Move all hand cash into bank deposits."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash, trace_region=trace_region,
                         t=t, reason='charity_cash_sweep')

    def withdraw_for_purchase(self, bank, needed, *, trace_region=None, t=None):
        """Ensure agent has at least *needed* cash for a purchase."""
        if self.agent.cash >= needed:
            return
        shortfall = needed - self.agent.cash
        available = bank.deposits.get(self.agent, 0)
        if available > 0:
            bank.Withdraw(self.agent, min(available, shortfall),
                          trace_region=trace_region, t=t,
                          reason='charity_food_purchase')

    # ------------------------------------------------------------------
    # Donations
    # ------------------------------------------------------------------

    def collect_donations(self, t, agents, bank, regions=None):
        """Collect donations from corporations and wealthy individuals.

        After collection, all cash is deposited into the bank
        (except what's needed for immediate food bidding).
        The _trade loop will withdraw cash when charity bids on food.
        """
        food_price = self.recipes.get(Goods.food, {}).get('price', 1.0)
        char_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        low_cash = char_wealth < food_price * self.low_cash_threshold_multiplier

        # Determine how many hungry agents exist and our food target (150% of 1/3)
        hungry_count = len([a for a in agents if a.alive and a.hungry_steps > 0
                            and not a.is_corporation])
        max_feed = max(1, hungry_count // 3)
        self._food_target = max_feed * 1.5
        self._hungry_count = hungry_count

        # Stop taking donations if we already have enough food-equivalent
        food_value = self.food_inventory + char_wealth / food_price
        if food_value >= self._food_target:
            return

        total_donated = 0.0

        regions = tuple(regions or getattr(bank, '_attached_regions', ()) or ())
        institution_region = regions[0] if regions else None

        def post_donation(donor, donation, source, *, donor_cash_before,
                          charity_cash_before, retained_earnings_before=None,
                          bank_withdrawal_event_ids=(),
                          bank_funding_requested=0.0,
                          bank_funding_settled=0.0):
            # A Province charity can collect from donors in several tiles. Put
            # each posting in the donor's own journal so their turn statement
            # can reconcile even when the shared institution runs once.
            donor_region = next((region for region in regions
                                 if donor in getattr(region, 'agents', ())), None)
            if donor_region is None:
                return None
            currency = (getattr(donor_region, 'home_currency', None)
                        or 'local_currency')
            operation_id = (f'charity-donation:{self.name}:{int(t)}:'
                            f'{donor_region.name}:{donor.id}')
            from economy.actor_accounts import record as record_economic_event
            journal_event = record_economic_event(
                donor_region, 'charity_donation', turn=t,
                payer_id=donor.id, recipient_id=self.agent.id, amount=donation,
                currency=currency, source_id=operation_id,
                detail={'donor_type': source, 'charity': self.name,
                        'charity_agent_id': self.agent.id,
                        'charity_wealth_before': round(char_wealth, 2),
                        'bank_funding_requested': float(bank_funding_requested),
                        'bank_funding_settled': float(bank_funding_settled)})
            from finance_trace import (account_ref, cash_transfer_contract,
                                      emit_cash_transfer)
            donor_currency = (getattr(donor, 'home_currency', None)
                              or currency)
            charity_currency = (getattr(self.agent, 'home_currency', None)
                                or currency)
            contract = cash_transfer_contract(
                operation_id, 'charity_donation', amount=float(donation),
                currency=currency,
                payer_account=account_ref(
                    'agent_wallet', str(donor.id), donor_currency,
                    agent_id=str(donor.id), tile=donor_region.name,
                    balance_before=float(donor_cash_before),
                    balance_after=float(donor.cash), balance_scope='cash_wallet'),
                payee_account=account_ref(
                    'charity_wallet', self.name, charity_currency,
                    charity_agent_id=str(self.agent.id),
                    balance_before=float(charity_cash_before),
                    balance_after=float(self.agent.cash),
                    balance_scope='cash_wallet'),
                counterparty_leg_status='both_cash_balances_captured',
                donor_type=source,
                bank_withdrawal_event_ids=list(bank_withdrawal_event_ids))
            return emit_cash_transfer(
                donor_region, kind='charity_donation', contract=contract,
                phase='welfare',
                subject={'type': 'tile/operation', 'id': operation_id,
                         'tile': donor_region.name},
                inputs={'turn': int(t), 'donor_id': str(donor.id),
                        'donor_type': source, 'charity_name': self.name,
                        'charity_agent_id': str(self.agent.id),
                        'operation_id': operation_id,
                        'charity_wealth_before': round(char_wealth, 2),
                        'retained_earnings_before': retained_earnings_before,
                        'retained_earnings_after': getattr(
                            donor, 'retained_earnings', None),
                        'bank_funding_requested': float(bank_funding_requested),
                        'bank_funding_settled': float(bank_funding_settled),
                        'actor_account_event_id': journal_event['id']
                        if journal_event is not None else None},
                cause_event_ids=list(bank_withdrawal_event_ids) or None)

        # ---- Corporate donations ----
        corps = [a for a in agents if a.is_corporation]
        for corp in corps:
            retained = getattr(corp, 'retained_earnings', 0.0)
            if retained <= 0:
                continue
            donate_pct = self.corp_donate_emergency_pct if low_cash else self.corp_donate_normal_pct
            donation = min(retained * donate_pct, corp.cash)
            if donation > 0:
                donor_cash_before = float(corp.cash)
                retained_before = float(corp.retained_earnings)
                charity_cash_before = float(self.agent.cash)
                _trace_cash_write = _trace_public_begin(None, corp)
                corp.cash -= donation
                _trace_public_finish(_trace_cash_write, 'charity:Charity.collect_donations',
                                     inputs={"source_writer": 'charity.py:Charity.collect_donations:08b12110f8c4592d:1'})
                corp.retained_earnings -= donation
                _trace_cash_write = _trace_public_begin(None, self.agent)
                self.agent.cash += donation
                _trace_public_finish(_trace_cash_write, 'charity:Charity.collect_donations',
                                     inputs={"source_writer": 'charity.py:Charity.collect_donations:da00999c46e6853e:1'})
                total_donated += donation
                post_donation(
                    corp, donation, 'corporation',
                    donor_cash_before=donor_cash_before,
                    charity_cash_before=charity_cash_before,
                    retained_earnings_before=retained_before)
                loginfo(t, f"{self.name} received ${donation:.2f} corp donation from {corp.name()}")

        # ---- Wealthy individual donations ----
        non_corp = [a for a in agents
                    if not a.is_corporation
                    and not a.is_trader
                    and not a.is_government
                    and a.alive]
        non_corp.sort(key=lambda a: a.wealth(), reverse=True)
        top_n = max(1, int(len(non_corp) * self.wealthy_fraction))
        wealthy = non_corp[:top_n]

        for agent in wealthy:
            w = agent.wealth()
            if w <= self.wealth_donation_threshold:
                continue
            excess = w - self.wealth_donation_threshold
            donate_pct = self.wealthy_donate_emergency_pct if low_cash else self.wealthy_donate_normal_pct
            donation = min(excess * donate_pct, agent.cash + bank.deposits.get(agent, 0))
            from_bank = min(donation, max(0, donation - agent.cash), bank.deposits.get(agent, 0))
            donor_region = next((region for region in regions
                                 if agent in getattr(region, 'agents', ())), None)
            bank_withdrawal_event_ids = []
            bank_funding_settled = 0.0
            if from_bank > 0:
                bank_funding_settled = bank.Withdraw(
                    agent, from_bank, trace_region=donor_region, t=t,
                    reason='charity_donation',
                    trace_event_ids=bank_withdrawal_event_ids)
            donor_cash_before = float(agent.cash)
            charity_cash_before = float(self.agent.cash)
            _trace_cash_write = _trace_public_begin(None, agent)
            agent.cash -= donation
            _trace_public_finish(_trace_cash_write, 'charity:Charity.collect_donations',
                                 inputs={"source_writer": 'charity.py:Charity.collect_donations:3a43ad2e923cda74:1'})
            _trace_cash_write = _trace_public_begin(None, self.agent)
            self.agent.cash += donation
            _trace_public_finish(_trace_cash_write, 'charity:Charity.collect_donations',
                                 inputs={"source_writer": 'charity.py:Charity.collect_donations:7d0a305cbdc11fd1:1'})
            total_donated += donation
            post_donation(
                agent, donation, 'wealthy_individual',
                donor_cash_before=donor_cash_before,
                charity_cash_before=charity_cash_before,
                bank_withdrawal_event_ids=bank_withdrawal_event_ids,
                bank_funding_requested=from_bank,
                bank_funding_settled=bank_funding_settled)
            loginfo(t, f"{self.name} received ${donation:.2f} donation from {agent.name()}")

        # Store bank reference on agent so total_liquid property works
        self.agent._bank_ref = bank

        # Deposit all collected cash
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash,
                         trace_region=institution_region, t=t,
                         reason='charity_donation_reserve')

        self.log["donations_collected"] += total_donated
        if total_donated > 0 and t % 50 == 0:
            char_wealth_after = self.agent.cash + bank.deposits.get(self.agent, 0)
            print(f"  {self.name}: collected ${total_donated:.2f} in donations "
                  f"(charity wealth: ${char_wealth_after:.2f})")

    # ------------------------------------------------------------------
    # Food bidding & purchase (called by region._trade)
    # ------------------------------------------------------------------

    def bid_food(self, food_price, current_desired, bank, *,
                 trace_region=None, t=None):
        """Return the quantity of food this charity wants to buy this turn.

        Withdraws enough cash from the bank to cover the bid if needed.
        """
        max_inventory = 50
        space = max_inventory - self.food_inventory
        if space <= 0:
            return 0

        char_wealth = self.agent.cash + bank.deposits.get(self.agent, 0)
        if char_wealth < food_price:
            return 0

        affordable_from_wealth = char_wealth // food_price
        # Cap at the food target (150% of 1/3 of hungry agents)
        target = getattr(self, '_food_target', 50)
        needed = max(0, target - self.food_inventory)
        potential_bid = min(space, affordable_from_wealth, current_desired, needed)
        if potential_bid <= 0:
            return 0

        # Withdraw enough to cover the bid
        needed = potential_bid * food_price
        self.withdraw_for_purchase(bank, needed, trace_region=trace_region, t=t)

        return potential_bid

    def receive_food(self, quantity):
        """Record food purchased during trade."""
        self.food_inventory += quantity
        self.log["food_purchased"] += quantity

    def pay_for_food(self, cost):
        """Deduct cash for food purchased (from agent's hand)."""
        _trace_cash_write = _trace_public_begin(None, self.agent)
        self.agent.cash -= cost
        _trace_public_finish(_trace_cash_write, 'charity:Charity.pay_for_food',
                             inputs={"source_writer": 'charity.py:Charity.pay_for_food:32fff4c4238f7716:1'})

    # ------------------------------------------------------------------
    # Post-trade deposit
    # ------------------------------------------------------------------

    def deposit_remaining(self, bank, *, trace_region=None, t=None):
        """Deposit any leftover hand cash back into the bank."""
        if self.agent.cash > 0:
            bank.Deposit(self.agent, self.agent.cash,
                         trace_region=trace_region, t=t,
                         reason='charity_post_market_cash_sweep')

    # ------------------------------------------------------------------
    # Food distribution
    # ------------------------------------------------------------------

    def distribute_food(self, t, agents, *, regions=None, trace_region=None):
        """Give 1 food per agent to ~1/3 of hungry agents (randomized), then
        to young agents from any remaining inventory."""
        if self.food_inventory <= 0:
            return

        regions = tuple(regions or ())
        if trace_region is not None and not regions:
            regions = (trace_region,)
        trace_region = next((region for region in regions
                             if getattr(region, '_run_trace', None) is not None
                             and getattr(region, '_collective_trace_clock', None)
                             is not None), None)
        stock_before_distribution = self.food_inventory

        hungry = [a for a in agents if a.alive and a.hungry_steps > 0
                  and not a.is_corporation]

        # Randomly select ~1/3 of hungry agents to feed this turn
        max_feed = max(1, len(hungry) // 3)
        if len(hungry) > max_feed:
            random.shuffle(hungry)
            selected = hungry[:max_feed]
        else:
            selected = hungry

        young = [a for a in agents if a.alive and a.age(t) <= 10
                 and a.hungry_steps == 0 and not a.is_corporation]

        recipients = 0
        food_given = 0
        recipient_event_ids = []
        recipient_ids = []
        hungry_recipient_ids = []
        young_recipient_ids = []

        for selection_index, recipient in enumerate(selected + young):
            # One aid transfer is one whole food unit. Fractional stock from
            # market purchases carries forward until it can fund that unit.
            if self.food_inventory < 1:
                break
            stock_before = self.food_inventory
            recipient_food_before = recipient.inv_get(Goods.food, 0)
            self.food_inventory -= 1
            recipient.inv_add(Goods.food, 1)
            stock_after = self.food_inventory
            recipient_food_after = recipient.inv_get(Goods.food, 0)
            food_given += 1
            recipients += 1
            recipient_ids.append(str(recipient.id))
            aid_group = 'hungry' if recipient.hungry_steps > 0 else 'young'
            if aid_group == 'hungry':
                hungry_recipient_ids.append(str(recipient.id))
            else:
                young_recipient_ids.append(str(recipient.id))
            if trace_region is not None:
                actual_recipient_region = next(
                    (region for region in regions
                     if recipient in getattr(region, 'agents', ())), None)
                from run_trace import emit
                operation_id = (f'charity-food-distribution:{self.name}:{int(t)}:'
                                f'{str(recipient.id)}:{selection_index}')
                event_id = emit(
                    trace_region,
                    kind='charity_food_aid_recipient', record_class='transfer',
                    phase='welfare',
                    subject={'type': 'tile/agent', 'id': str(recipient.id),
                             'tile': getattr(actual_recipient_region,
                                             'name', 'unknown')},
                    metric_id='goods.charity_food_distribution',
                    unit='food_units', before=0, after=1,
                    formula_id='charity.food_distribution_transfer.v1',
                    inputs={'operation_id': operation_id,
                            'charity_name': self.name,
                            'recipient_id': str(recipient.id),
                            'recipient_group': aid_group,
                            'food_amount': 1,
                            'charity_inventory_before': stock_before,
                            'charity_inventory_after': stock_after,
                            'recipient_inventory_before': recipient_food_before,
                            'recipient_inventory_after': recipient_food_after,
                            'hungry_steps_before': int(recipient.hungry_steps),
                            'recipient_selection_index': selection_index})
                if event_id is not None:
                    recipient_event_ids.append(event_id)
            if recipient.hungry_steps > 0:
                loginfo(t, f"{self.name} gave 1 food to hungry {recipient.name()} "
                        f"(hungry_steps={recipient.hungry_steps})")
            else:
                loginfo(t, f"{self.name} gave 1 food to young {recipient.name()} "
                        f"(age={recipient.age(t)})")

        self.log["food_distributed"] += food_given
        self.log["recipients"] += recipients

        if food_given > 0 and trace_region is not None:
            from run_trace import emit
            emit(
                trace_region, kind='charity_food_aid',
                record_class='outcome', phase='welfare',
                subject={'type': 'province/charity', 'id': self.name},
                metric_id='goods.charity_food_aid', unit='food_units',
                before=0, after=food_given,
                formula_id='charity.food_aid_allocation.v1',
                inputs={'operation_id':
                        f'charity-food-distribution:{self.name}:{int(t)}',
                        'food_inventory_before': stock_before_distribution,
                        'food_inventory_after': self.food_inventory,
                        'hungry_candidates': len(hungry),
                        'hungry_selection_limit': max_feed,
                        'selected_hungry_ids': [str(a.id) for a in selected],
                        'young_candidates': len(young),
                        'hungry_recipient_ids': hungry_recipient_ids,
                        'young_recipient_ids': young_recipient_ids,
                        'recipients': recipient_ids,
                        'food_given': food_given,
                        'randomized_hungry_selection': len(hungry) > max_feed},
                cause_event_ids=recipient_event_ids or None)

        if food_given > 0 and t % 50 == 0:
            print(f"  {self.name}: distributed {food_given} food to {recipients} agents "
                  f"(remaining food: {self.food_inventory}, cash: ${self.agent.cash:.2f})")

    def print_summary(self):
        """Print summary stats for this charity."""
        print(f"  {self.name}:")
        print(f"    Agent cash: ${self.agent.cash:.2f}")
        print(f"    Food inventory: {self.food_inventory}")
        print(f"    Total donations collected: ${self.log['donations_collected']:.2f}")
        print(f"    Total food purchased: {self.log['food_purchased']}")
        print(f"    Total food distributed: {self.log['food_distributed']}")
        print(f"    Total recipients served: {self.log['recipients']}")
