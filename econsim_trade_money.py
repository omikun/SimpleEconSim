import math
import bisect
import random
from collections import defaultdict
from goods import Goods
from logger import *
from econsim_states import recipes

inventory_limit = 10


def get_input_commodity(agent, recipes):
    recipe = recipes[agent.output]
    input_com = recipe.get('input', Goods.none)
    return input_com


def get_output_commodity(agent):
    return agent.output


class Offer:
    def __init__(self, is_bid, agent, price, quantity):
        self.is_bid = is_bid
        self.agent = agent
        self.price = price
        self.quantity = quantity


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, min_x, max_x):
    return max(min_x, min(x, max_x))


class Loan:
    def __init__(self, bank, agent, principle, interest_rate):
        self.bank = bank
        self.agent = agent
        self.principle = principle
        self.interest_rate = interest_rate
        self.interest_paid = 0
        self.principle_paid = 0
        self.num_payments = 100

    def isPaid(self):
        return self.principle_paid >= self.principle

    def getInterest(self):
        remaining_principle = self.principle - self.principle_paid
        return self.interest_rate * remaining_principle

    def getPaymentAmount(self):
        remaining_principle = self.principle - self.principle_paid
        interest = self.getInterest()
        payment = interest + self.principle / self.num_payments
        return payment

    def pay(self, amount):
        # Conservation guard: a negative "payment" (possible when the agent's
        # total wealth fell below zero) would pay NEGATIVE interest into the
        # bank — destroying deposits without any cash transfer.  Clamp to 0.
        if amount <= 0:
            return
        interest_paid = min(self.getInterest(), amount)
        principle_paid = max(0, amount - interest_paid)
        self.principle_paid += principle_paid
        self.interest_paid += interest_paid
        self.bank.pay_principle(principle_paid)
        self.bank.pay_interest(interest_paid)


class Bank():
    def __init__(self, gov=None):
        self.interest_rate = .001
        self.deposit_interest_rate = 0.0005
        self.base_deposit_interest_rate = 0.0005
        self.total_deposits = 2000
        self.reserve_fraction = .1
        self.loans = []
        self.total_liabilities = 0
        self.deposits = defaultdict(int)
        self.total_interest_earned = 0
        self.total_deposit_interest_paid = 0
        self.turn_loan_interest = 0
        self.gov = gov  # Reference to government for bailout decisions

        # ---- Multi-currency FX (Phase 1) ----
        self.foreign_reserves = defaultdict(float)   # currency -> holdings
        self.fx_pool = 0.0                           # domestic money for FX desk

    def Borrow(self, t, agent, amount):
        borrowable_amount = (self.total_deposits * (1 - self.reserve_fraction)
                             - self.total_liabilities)
        amount = clamp(amount, 0, borrowable_amount)
        loginfo(t, "borrowing from bank with $", self.total_deposits,
                " deposit and $", self.total_liabilities,
                "borrowable: $", borrowable_amount, " lending: $", amount)
        if amount <= 0:
            return amount
        loan = Loan(self, agent, amount, self.interest_rate)
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount
        return amount

    def pay_principle(self, amount):
        self.total_liabilities -= amount

    def pay_interest(self, amount):
        self.total_deposits += amount
        self.total_interest_earned += amount

    def Deposit(self, agent, amount):
        assert (agent.cash >= amount)
        agent.cash -= amount
        self.total_deposits += amount
        self.deposits[agent] += amount

    def Withdraw(self, agent, amount):
        amount = clamp(amount, 0, self.deposits[agent])
        agent.cash += amount
        self.total_deposits -= amount
        self.deposits[agent] -= amount

    def RequestBailout(self, t, loss_amount):
        deficit = max(0, loss_amount - self.total_deposits)
        buffer = self.total_liabilities * 0.2
        bailout_amount = deficit + buffer
        bailout_amount = max(bailout_amount, loss_amount)
        approved, amount = gov_decide_bailout(t, self, bailout_amount)
        if approved and amount > 0:
            gov = getattr(self, 'gov', None)
            if gov is not None:
                actual = min(amount, gov.agent.cash)
                gov.agent.cash -= actual
                # Credit the government's per-agent deposit ledger too, so the
                # deposit DICT stays in sync with the scalar (the dict is the
                # true withdrawable pool used by bad-debt forgiveness).
                self.deposits[gov.agent] += actual
            else:
                actual = 0
            self.total_deposits += actual
            logwarning(t, "BAILOUT: government injected $", round(actual, 2),
                       "into bank. gov cash now $",
                       round(gov.agent.cash if gov else 0, 2))
            return actual > 0
        return False

    def PayDepositInterest(self, agents):
        """Pay interest to all depositors based on their deposit balance.
        Interest rate is reduced as deposit ratio increases (Fix F).
        Capped to 60% of estimated loan interest so bank keeps 40% margin,
        AND to the available deposit pool so total_deposits can never go
        negative (a negative deposit ledger would mint currency)."""
        circulating_cash = max(1, sum(agent.cash for agent in agents))
        deposit_ratio = self.total_deposits / circulating_cash
        if deposit_ratio < 5:
            self.deposit_interest_rate = self.base_deposit_interest_rate
        elif deposit_ratio < 10:
            self.deposit_interest_rate = self.base_deposit_interest_rate * 0.4
        else:
            self.deposit_interest_rate = self.base_deposit_interest_rate * 0.1
        estimated_loan_interest = sum(
            loan.getInterest() for loan in self.loans
        )
        max_total_payout = min(
            estimated_loan_interest * 0.6,
            max(0.0, self.total_deposits),
        )
        total_payout = 0
        for agent, amount in list(self.deposits.items()):
            interest = amount * self.deposit_interest_rate
            if interest > 0:
                remaining_capacity = max(0, max_total_payout - total_payout)
                interest = min(interest, remaining_capacity)
                if interest > 0:
                    agent.cash += interest
                    self.total_deposits -= interest
                    self.total_deposit_interest_paid += interest
                    total_payout += interest
        return total_payout


def gov_decide_bailout(t, bank, requested_amount):
    """Government decides whether to approve a bank bailout.
    Currently defaults to auto-approve. Returns (approved, amount)."""
    return True, requested_amount


bank = Bank()


def Borrow(t, agent, food_price, bank):
    amount = food_price * 1.2
    bank.Borrow(t, agent, amount)


def borrow_if_needed(t, agent, bank=None):
    if bank is None:
        bank = globals().get('bank', None)
        if bank is None:
            return
    wealth = agent.wealth()
    if wealth < agent.owed_this_turn():
        needed = agent.owed_this_turn() - wealth
        Borrow(t, agent, needed * 2, bank)


def PayLoans(agent, bank=None):
    if bank is None:
        bank = globals().get('bank', None)
        if bank is None:
            return
    total_wealth = agent.cash + bank.deposits[agent]
    remaining_wealth = total_wealth
    total_paid = 0
    for loan in agent.loans:
        # Conservation guard: never pay more than the agent actually holds.
        # A negative remaining_wealth (overdrawn agent) must not produce a
        # negative "payment" — that would flow negative interest into the
        # bank and destroy deposits without any cash transfer.  Also ensures
        # agent.cash can't be driven further negative by the Withdraw path.
        if remaining_wealth <= 0:
            break
        payment = min(remaining_wealth, loan.getPaymentAmount())
        loan.pay(payment)
        total_paid += payment
        remaining_wealth -= payment
    if total_paid > 0:
        if total_paid > agent.cash:
            needed_from_bank = total_paid - agent.cash
            bank.Withdraw(agent, needed_from_bank)
        agent.cash -= total_paid
    agent.loans = [l for l in agent.loans if not l.isPaid()]


# =============================================================================
# TRADE — entry point
# =============================================================================

def Trade(t, agents, recipes, demand_ratio_log, demand_log,
          supply_log, sold_log, bought_log):
    previous_total_cash = get_total_cash(agents, bank)
    max_demand_ratio = 0
    goods = [Goods.food, Goods.wood, Goods.furniture]
    number_desired = 16
    all_goods_price = sum(recipes[good]['price'] for good in goods)
    food_price = recipes[Goods.food]['price']
    random.shuffle(agents)
    interest_paid = bank.PayDepositInterest(agents)
    if interest_paid > 0:
        loginfo(t, "Bank paid $", round(interest_paid, 2),
                "in deposit interest at rate", bank.deposit_interest_rate)
    report_cash(t, agents, previous_total_cash, "pre borrow and deposit", True)
    decide_borrow_deposit(agents, all_goods_price, bank, food_price,
                          previous_total_cash, t)
    report_cash(t, agents, previous_total_cash, "post borrow and deposit")
    for good in goods:
        if good == Goods.food:
            current_desired = 16
        elif good == Goods.wood:
            current_desired = 10
        else:
            current_desired = max(1, int(16 / max(1, recipes[good]['price'])))
        loginfo(t, 'bids and asks for ', good)
        price = recipes[good]['price']
        total_asks, total_bids = gather_bids_asks(t, agents, good, price,
                                                   current_desired, recipes,
                                                   0, 0)
        total_trades = min(total_asks, total_bids)
        if total_asks == 0 and total_bids == 0:
            _price_default_decay(good, recipes)
            continue
        demand_ratio = 5.0 if total_asks == 0 else total_bids / total_asks
        if max_demand_ratio < demand_ratio and total_bids > 0:
            max_demand_ratio = demand_ratio
        demand_ratio_log.setdefault(good, [])
        demand_ratio_log[good].append(demand_ratio)
        demand_log[good].append(total_bids)
        supply_log[good].append(total_asks)
        price = set_market_price(demand_ratio, good, recipes, agents)
        if total_trades == 0:
            continue
        logdebug(t, "trading ", good, " at $", round(price, 2),
                 "demand_ratio:", round(demand_ratio, 2),
                 " asks: ", round(total_asks, 2),
                 " bids: ", round(total_bids, 2))
        total_bought, total_cash_purchases = \
            bidders_buy_good(t, agents, good, bought_log, price, total_asks, 0)
        askers = sorted(agents, key=lambda a: a.ask, reverse=True)
        total_cash_sales, total_sold = \
            askers_sell_good(askers, good, price, t, total_bought,
                             total_cash_purchases, 0, 0)
        diff = math.fabs(total_cash_sales - total_cash_purchases)
        if diff > .1:
            logwarning(t, "traded", good, "demand:", demand_ratio,
                       "price:", price, "trades: ", good, " traded: ", 0,
                       "total bought", total_bought, "totalSold", total_sold,
                       "cash bought $", total_cash_purchases,
                       "cash sold $", total_cash_sales, "diff",
                       math.fabs(total_cash_sales - total_cash_purchases))
        sold_log[good].append(total_sold)
        report_cash(t, agents, previous_total_cash, "post primary trade " + str(good))
        sec_traded, sec_value = secondary_trade(t, agents, good, price, recipes)
        if sec_traded > 0:
            logdebug(t, "secondary traded", good, "vol:", sec_traded,
                     "value:$", round(sec_value, 2))
        report_cash(t, agents, previous_total_cash, "post secondary trade " + str(good))


# =============================================================================
# PRICE DEFAULT DECAY
# =============================================================================

def _price_default_decay(good, recipes):
    """When no bids and no asks, price decays toward fundamental cost."""
    recipe = recipes[good]
    cost_to_make = 1.0
    if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
        input_cost = recipes[recipe['input']]['price']
        cost_to_make = (recipe['numInput'] * input_cost) / recipe['production']
    if recipe['price'] > cost_to_make * 1.05:
        recipe['price'] = max(cost_to_make, recipe['price'] * 0.95)
    recipe['price'] = max(cost_to_make, recipe['price'])


# =============================================================================
# BIDS & ASKS
# =============================================================================

def gather_bids_asks(t, agents, good, good_price, number_desired, recipes,
                    total_asks, total_bids):
    for agent in agents:
        agent_rec = recipes[agent.output]
        is_employee = getattr(agent, 'employer', None) is not None
        _withdraw_if_low_cash(agent, good_price, number_desired, bank)
        mult = getattr(agent, 'consumption_multiplier', 1.0)
        bid = _compute_bid(agent, good, good_price, number_desired, agent_rec,
                           is_employee, mult, recipes)
        agent.bid = bid
        agent.remainingCash -= agent.bid * good_price
        loginfo(t, agent.name(), 'bid', agent.bid, 'input',
                get_input_commodity(agent, recipes), 'recipe for',
                agent_rec['commodity'], 'num input', agent_rec['numInput'],
                agent.inventory[good.value])
        total_bids += agent.bid
        ask = _compute_ask(agent, good, good_price, recipes, is_employee)
        agent.ask = ask
        total_asks += agent.ask
    return total_asks, total_bids


def _withdraw_if_low_cash(agent, good_price, number_desired, bank):
    """Withdraw from bank deposits if cash is low for purchasing."""
    bank_balance = bank.deposits.get(agent, 0)
    if bank_balance > 0:
        desired_cash = good_price * number_desired
        if agent.remainingCash < desired_cash:
            needed = desired_cash - agent.remainingCash
            bank.Withdraw(agent, min(bank_balance, needed))


def _compute_bid(agent, good, good_price, number_desired, agent_rec, is_employee,
                 mult, recipes):
    """Compute how much *agent* wants to buy of *good* at *good_price*."""
    if not is_employee and get_input_commodity(agent, recipes) == good:
        # Corporate/Independent producer input bidding
        num_employees = len(agent.employees) if getattr(agent, 'is_corporation',
                                                        False) else 0
        multiplier = 1 + num_employees
        desired = max(0, agent_rec['numInput'] * multiplier
                      - agent.inv_get(good, 0))
        if mult > 1.0:
            desired = int(desired * mult)
        affordable = agent.remainingCash // good_price if good_price > 0 else desired
        return int(min(desired, affordable))
    elif (is_employee or agent.output != good) and agent.remainingCash > good_price:
        # Consumer bidding
        maxinv_limit = agent_rec['maxinv']
        if getattr(agent, 'is_corporation', False):
            maxinv_limit *= (1 + len(agent.employees))
        if mult > 1.0:
            maxinv_limit = int(maxinv_limit * min(mult, 3.0))
        num_storable = max(0, maxinv_limit - agent.inv_get(good, 0))
        base_desire = min(number_desired,
                          agent.remainingCash // good_price)
        scaled_desire = int(base_desire * mult)
        bid = min(scaled_desire, num_storable)
        if mult > 2.0 and good != Goods.food:
            extra_affordable = min(
                int(number_desired * (mult - 1.0)),
                agent.remainingCash // good_price
            ) if good_price > 0 else 0
            bid += min(extra_affordable, num_storable - bid)
            loginfo('', agent.name(),
                    'wealth consumption (mult=' + str(round(mult, 2))
                    + ') bid extra for', good)
        return max(0, min(bid, num_storable))
    return 0


def _compute_ask(agent, good, good_price, recipes, is_employee):
    """Compute how much *agent* wants to sell of *good* at *good_price*."""
    if is_employee:
        return 0
    if agent.output != good and agent.output != Goods.gov:
        if agent.inv_get(good, 0) <= 0:
            return 0
    if agent.output == good or (agent.output == Goods.gov
                                and agent.inv_get(good, 0) > 0):
        cost_to_make = 0
        agent_rec = recipes.get(good, {})
        if agent.output == good and agent_rec.get('numInput', 0) > 0 \
           and agent_rec.get('production', 0) > 0:
            input_com = agent_rec['input']
            input_cost = agent.cost_get(input_com, 0)
            cost_to_make = ((agent_rec['numInput'] * input_cost)
                            / agent_rec['production'])
        if good == Goods.food and agent.output == Goods.food:
            return max(0, agent.inv_get(good, 0) - 2)
        elif good_price >= cost_to_make:
            return max(0, agent.inv_get(good, 0))
    return 0


# =============================================================================
# EXECUTION: buyers & sellers
# =============================================================================

def askers_sell_good(askers, good, price, t, total_bought, total_cash_purchases,
                    total_cash_sales, total_sold):
    for agent in askers:
        if total_sold < total_bought and total_cash_purchases > total_cash_sales:
            ask = agent.ask
            remaining = total_bought - total_sold
            sold = min(ask, remaining)
            assert sold >= 0, 'neg sold ' + str(sold)
            total_sold += sold
            agent.cash += sold * price
            agent.inv_add(good, -sold)
            total_cash_sales += sold * price
            if sold > 0:
                loginfo(t, agent.name(), 'sold ', sold, good, ', ask: ', ask)
    return total_cash_sales, total_sold


def bidders_buy_good(t, agents, good, bought_log, price, total_asks,
                    total_bought):
    bidders = sorted(agents, key=lambda a: a.hungry_steps, reverse=True)
    total_cash_purchases = 0
    for agent in bidders:
        if total_asks > total_bought:
            prevCash = agent.cash
            bid = agent.bid
            remaining = total_asks - total_bought
            affordable = int(agent.cash / price)
            bought = max(0, min(bid, min(remaining, affordable)))
            cash = bought * price
            agent.cash = max(0.0, agent.cash - cash)
            assert agent.cash >= -1e-5, (
                'neg cash, bought $' + str(cash) + ' of ' + str(good)
                + ' now has ' + str(agent.cash))
            total_cash_purchases += cash
            if bought > 0:
                logdebug(t, agent.name(), 'had $', prevCash, 'now',
                         agent.cash, 'bought ', bought, good, ', bid: ',
                         bid, 'affordable: ', affordable, 'remaining:',
                         remaining)
                old_qty = agent.inv_get(good, 0)
                old_cost = agent.cost_get(good, 0)
                total_qty = old_qty + bought
                if total_qty > 0:
                    agent.cost_set(good, (old_qty * old_cost + bought * price) / total_qty)
                else:
                    agent.cost_set(good, price)
                agent.inv_add(good, bought)
                total_bought += bought
                bought_log[agent.output][good][-1] += bought
            else:
                logdebug(t, agent.name(), 'had $', prevCash, 'now',
                         agent.cash, 'bought ', bought, good, ', bid: ',
                         bid, 'affordable: ', affordable, 'remaining:',
                         remaining)
    return total_bought, total_cash_purchases


# =============================================================================
# MARKET PRICE
# =============================================================================

def set_market_price(demand_ratio, good, recipes, agents=None):
    recipe = recipes[good]
    price = recipe['price']
    fundamental_cost = 1.0
    if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
        input_cost = recipes[recipe['input']]['price']
        fundamental_cost = (recipe['numInput'] * input_cost) / recipe['production']
    food_price = recipes.get(Goods.food, {}).get('price', 1.0)
    production_rate = recipe.get('production', 1)
    living_cost_floor = (4 * food_price) / max(1, production_rate)
    if recipe.get('numInput', 0) > 0:
        min_price_floor = max(fundamental_cost * 1.10, living_cost_floor)
    else:
        min_price_floor = max(living_cost_floor, 0.10)
    if demand_ratio >= 1:
        clamped_ratio = min(5.0, demand_ratio - 1)
        price *= lerp(1.01, 1.20, clamped_ratio / 5.0)
    elif demand_ratio < 0.2:
        price *= lerp(0.90, 0.95, demand_ratio / 0.2)
    elif demand_ratio < .5:
        price *= lerp(0.95, 1.0, (demand_ratio - 0.2) / 0.3)
    if agents and good != Goods.gov:
        producers = [a for a in agents if a.output == good]
        if producers:
            total_multiplier = 0
            for a in producers:
                poor_factor = clamp(a.cash / 20.0, 0.2, 1.0)
                hungry_factor = max(0.1, 0.8 ** a.hungry_steps)
                total_multiplier += poor_factor * hungry_factor
            avg_multiplier = total_multiplier / len(producers)
            dynamic_adjusted_price = fundamental_cost * avg_multiplier
            price = max(price, dynamic_adjusted_price)
    price = max(min_price_floor, price)
    price = max(0.1, price)
    recipe['price'] = price
    return price


# =============================================================================
# BORROW / DEPOSIT DECISIONS
# =============================================================================

def decide_borrow_deposit(agents, all_goods_price, bank, food_price,
                          previous_total_cash, t):
    for agent in agents:
        borrow_if_needed(t, agent, bank=bank)
        PayLoans(agent, bank=bank)
        _maybe_borrow_food_money(t, agent, food_price, bank)
        _maybe_borrow_inputs(t, agent, bank)
        _deposit_excess_cash(t, agent, all_goods_price, bank)
        agent.remainingCash = agent.cash


def _maybe_borrow_food_money(t, agent, food_price, bank):
    """Borrow for food if starving and no cash."""
    if agent.output != Goods.food and agent.cash < food_price \
       and agent.hungry_steps > 10:
        bank_balance = bank.deposits.get(agent, 0)
        if bank_balance > 0:
            needed = food_price - agent.cash
            bank.Withdraw(agent, min(bank_balance, needed))
        if agent.cash < food_price:
            Borrow(t, agent, food_price, bank)


def _maybe_borrow_inputs(t, agent, bank):
    """Borrow for business inputs if insufficient cash."""
    if agent.output not in recipes:
        return
    if recipes[agent.output].get('numInput', 0) <= 0:
        return
    input_com = recipes[agent.output]['input']
    input_price = recipes[input_com]['price']
    num_input = recipes[agent.output]['numInput']
    cost = input_price * num_input
    if agent.cash >= cost:
        return
    bank_balance = bank.deposits.get(agent, 0)
    if bank_balance > 0:
        amount_needed = cost - agent.cash
        bank.Withdraw(agent, min(bank_balance, amount_needed))
    if agent.cash < cost:
        amount_needed = cost - agent.cash
        bank.Borrow(t, agent, amount_needed)


def _deposit_excess_cash(t, agent, all_goods_price, bank):
    """Deposit excess cash above a consumption-multiplier-based floor."""
    mult = getattr(agent, 'consumption_multiplier', 1.0)
    total_liquid = agent.cash + bank.deposits.get(agent, 0)
    current_deposits = bank.deposits.get(agent, 0)
    deposit_frac = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
    cash_floor = int(all_goods_price * (100 / max(1.0, mult)))
    max_deposits = total_liquid * deposit_frac
    excess_deposit_capacity = max(0, max_deposits - current_deposits)
    if agent.cash > cash_floor and excess_deposit_capacity > 0:
        amount = min(agent.cash - cash_floor, excess_deposit_capacity)
        bank.Deposit(agent, amount)


# =============================================================================
# SECONDARY MARKET
# =============================================================================

def secondary_trade(t, agents, good, current_market_price, recipes):
    """Execute a secondary market: distressed sellers, premium buyers."""
    recipe = recipes[good]
    fundamental_cost = 1.0
    if recipe.get('numInput', 0) > 0 and recipe.get('production', 0) > 0:
        input_cost = recipes[recipe['input']]['price']
        fundamental_cost = (recipe['numInput'] * input_cost) / recipe['production']
    min_secondary_price = fundamental_cost * 1.05
    secondary_asks = _gather_secondary_asks(agents, good, current_market_price,
                                            min_secondary_price)
    secondary_bids = _gather_secondary_bids(agents, good, current_market_price,
                                            recipes)
    return _match_secondary_orders(secondary_asks, secondary_bids, good, t)


def _gather_secondary_asks(agents, good, market_price, min_price):
    """Collect distressed sellers with discounted prices."""
    asks = []
    for agent in agents:
        is_employee = getattr(agent, 'employer', None) is not None
        remaining_inv = agent.inv_get(good, 0)
        keep_amount = 2 if (good == Goods.food
                            and agent.output == Goods.food) else 0
        sellable = max(0, remaining_inv - keep_amount)
        if sellable > 0 and agent.output == good and not is_employee:
            poor_factor = clamp(agent.cash / 20.0, 0.2, 1.0)
            hungry_factor = max(0.1, 0.8 ** agent.hungry_steps)
            distress_factor = poor_factor * hungry_factor
            min_ask = min_price * distress_factor
            ask_price = max(min_ask, market_price * distress_factor)
            asks.append(Offer(False, agent, ask_price, sellable))
    return asks


def _gather_secondary_bids(agents, good, market_price, recipes):
    """Collect buyers willing to pay a premium."""
    bids = []
    for agent in agents:
        is_employee = getattr(agent, 'employer', None) is not None
        if not is_employee and agent.output == good:
            continue
        desired = 0
        if not is_employee and get_input_commodity(agent, recipes) == good:
            num_employees = len(agent.employees) if getattr(agent, 'is_corporation',
                                                            False) else 0
            agent_rec = recipes[agent.output]
            desired = max(0, recipes[good]['numInput'] * (1 + num_employees)
                          - agent.inv_get(good, 0))
        else:
            maxinv_limit = recipes[good]['maxinv']
            if getattr(agent, 'is_corporation', False):
                maxinv_limit *= (1 + len(agent.employees))
            num_storable = max(0, maxinv_limit - agent.inv_get(good, 0))
            if good == Goods.food:
                desired = min(16, num_storable)
            elif agent.remainingCash > market_price * 2:
                desired = min(1, num_storable)
        if desired > 0 and agent.remainingCash > 0:
            premium = _compute_bid_premium(agent, good, market_price, recipes)
            max_willing = market_price * premium
            affordable_qty = agent.remainingCash / max_willing
            if affordable_qty >= 1:
                bid_qty = min(desired, int(affordable_qty))
                bids.append(Offer(True, agent, max_willing, bid_qty))
            elif agent.remainingCash >= market_price * 0.5:
                bids.append(Offer(True, agent, agent.remainingCash, 1))
    return bids


def _compute_bid_premium(agent, good, market_price, recipes):
    """How much above market price is *agent* willing to pay?"""
    is_employee = getattr(agent, 'employer', None) is not None
    mult = getattr(agent, 'consumption_multiplier', 1.0)
    if good == Goods.food and agent.hungry_steps > 0:
        base_premium = 1.0 + 0.5 * agent.hungry_steps
        return min(10.0, base_premium * mult * 0.5)
    elif (not is_employee and agent.output in recipes
          and get_input_commodity(agent, recipes) == good
          and agent.inv_get(good, 0) == 0):
        premium = 1.0 + (mult - 1.0) * 0.5
        return max(1.5, min(5.5, premium))
    elif mult > 2.0 and good != Goods.food:
        return 1.0 + (mult - 1.0) * 0.3
    return 1.0


def _match_secondary_orders(asks, bids, good, t):
    """Sort and match ask/bid offers; execute trades."""
    asks.sort(key=lambda x: x.price)
    bids.sort(key=lambda x: x.price, reverse=True)
    total_traded = 0
    total_value = 0
    ask_idx = 0
    bid_idx = 0
    while ask_idx < len(asks) and bid_idx < len(bids):
        ask = asks[ask_idx]
        bid = bids[bid_idx]
        if bid.price >= ask.price:
            clear_price = (bid.price + ask.price) / 2.0
            trade_qty = min(ask.quantity, bid.quantity)
            max_affordable = (
                int(bid.agent.remainingCash / clear_price)
                if clear_price > 0 else trade_qty
            )
            trade_qty = min(trade_qty, max_affordable)
            if trade_qty > 0:
                cost = trade_qty * clear_price
                bid.agent.remainingCash -= cost
                bid.agent.cash -= cost
                ask.agent.cash += cost
                bid.agent.inv_add(good, trade_qty)
                ask.agent.inv_add(good, -trade_qty)
                old_qty = bid.agent.inv_get(good, 0) - trade_qty
                old_cost = bid.agent.cost_get(good, 0)
                if bid.agent.inv_get(good, 0) > 0:
                    bid.agent.cost_set(good, (old_qty * old_cost + cost) / bid.agent.inv_get(good, 0))
                total_traded += trade_qty
                total_value += cost
                ask.quantity -= trade_qty
                bid.quantity -= trade_qty
                loginfo(t, "SECONDARY TRADE:", bid.agent.name(),
                        "bought", trade_qty, good, "from",
                        ask.agent.name(), "at $",
                        round(clear_price, 2))
        if ask.quantity <= 0:
            ask_idx += 1
        if bid.quantity <= 0 or bid.price < ask.price:
            bid_idx += 1
    return total_traded, total_value


# =============================================================================
# HELPERS
# =============================================================================

def report_cash(t, agents, previous_total_cash, msg, print=False):
    temp_total_cash = get_total_cash(agents, bank)
    diff = math.fabs(temp_total_cash - previous_total_cash)
    epsilon = 1e-8
    if diff > epsilon or print:
        loginfo(t, msg, "total cash", previous_total_cash, '!=', temp_total_cash,
                diff)


def get_total_cash(agents, bank=None):
    if bank is None:
        bank = globals().get('bank', None)
        if bank is None:
            return sum(agent.cash for agent in agents)
    bank_equity = bank.total_deposits - bank.total_liabilities
    return sum(agent.cash for agent in agents) + bank_equity