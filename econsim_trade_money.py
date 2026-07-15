import math
import bisect
import random
from collections import defaultdict
from goods import Goods
from logger import *
from econsim_states import *
import econsim_states

inventoryLimit = 10


def GetInputCom(agent, recipes):
    recipe = recipes[agent.output]
    inputCom = recipe.get('input', Goods.none)
    return inputCom


def GetOutputCom(agent):
    return agent.output


class Offer:
    def __init__(self, isBid, agent, price, quantity):
        self.isBid = isBid
        self.agent = agent
        self.price = price
        self.quantity = quantity


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, minx, maxx):
    return max(minx, min(x, maxx))


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
        remainingPrinciple = self.principle - self.principle_paid
        return self.interest_rate * remainingPrinciple

    def getPaymentAmount(self):
        remainingPrinciple = self.principle - self.principle_paid
        interest = self.getInterest()
        payment = interest + self.principle / self.num_payments
        return payment

    def pay(self, amount):
        interest_paid = min(self.getInterest(), amount)
        principlePaid = max(0, amount - interest_paid)
        self.principle_paid += principlePaid
        self.interest_paid += interest_paid
        bank.PayPrinciple(principlePaid)
        bank.PayInterest(interest_paid)


class Bank():
    def __init__(self):
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

    def Borrow(self, t, agent, amount):
        borrowableAmount = (self.total_deposits * (1 - self.reserve_fraction)
                            - self.total_liabilities)
        amount = clamp(amount, 0, borrowableAmount)
        loginfo(t, "borrowing from bank with $", self.total_deposits,
                " deposit and $", self.total_liabilities,
                "borrowable: $", borrowableAmount, " lending: $", amount)
        if amount <= 0:
            return
        loan = Loan(self, agent, amount, self.interest_rate)
        agent.cash += amount
        agent.loans.append(loan)
        self.loans.append(loan)
        self.total_liabilities += amount

    def PayPrinciple(self, amount):
        self.total_liabilities -= amount

    def PayInterest(self, amount):
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
            gov = econsim_states.default_gov
            if gov is not None:
                actual = min(amount, gov.agent.cash)
                gov.agent.cash -= actual
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
        Capped to 60% of estimated loan interest so bank keeps 40% margin."""
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
        max_total_payout = estimated_loan_interest * 0.6
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


def Borrow(t, agent, foodPrice, bank):
    amount = foodPrice * 1.2
    bank.Borrow(t, agent, amount)


def BorrowIfNeedTo(t, agent):
    wealth = agent.wealth()
    if wealth < agent.oweThisTurn():
        needed = agent.oweThisTurn() - wealth
        Borrow(t, agent, needed * 2, bank)


def PayLoans(agent):
    total_wealth = agent.cash + bank.deposits[agent]
    remaining_wealth = total_wealth
    total_paid = 0
    for loan in agent.loans:
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


mostDemand = Goods.none


# =============================================================================
# TRADE — entry point
# =============================================================================

def Trade(t, agents, recipes, demand_ratio_log, demand_log,
          supply_log, sold_log, bought_log):
    prevTotalCash = getTotalCash(agents)
    global bank, mostDemand
    mostDemand = Goods.gov
    maxDemandRatio = 0
    goods = [Goods.food, Goods.wood, Goods.furn]
    num_desired = 16
    allGoodsPrice = sum(recipes[good]['price'] for good in goods)
    foodPrice = recipes[Goods.food]['price']
    random.shuffle(agents)
    interest_paid = bank.PayDepositInterest(agents)
    if interest_paid > 0:
        loginfo(t, "Bank paid $", round(interest_paid, 2),
                "in deposit interest at rate", bank.deposit_interest_rate)
    reportCash(t, agents, prevTotalCash, "pre borrow and deposit", True)
    DecideBorrowDeposit(agents, allGoodsPrice, bank, foodPrice,
                        prevTotalCash, t)
    reportCash(t, agents, prevTotalCash, "post borrow and deposit")
    for good in goods:
        if good == Goods.food:
            current_desired = 16
        elif good == Goods.wood:
            current_desired = 10
        else:
            current_desired = max(1, int(16 / max(1, recipes[good]['price'])))
        loginfo(t, 'bids and asks for ', good)
        price = recipes[good]['price']
        totalAsks, totalBids = GatherBidsAsks(t, agents, good, price,
                                              current_desired, recipes,
                                              0, 0)
        totalTrades = min(totalAsks, totalBids)
        if totalAsks == 0 and totalBids == 0:
            _price_default_decay(good, recipes)
            continue
        demandRatio = 5.0 if totalAsks == 0 else totalBids / totalAsks
        if maxDemandRatio < demandRatio and totalBids > 0:
            maxDemandRatio = demandRatio
            mostDemand = good
        demand_ratio_log.setdefault(good, [])
        demand_ratio_log[good].append(demandRatio)
        demand_log[good].append(totalBids)
        supply_log[good].append(totalAsks)
        price = SetMarketPrice(demandRatio, good, recipes, agents)
        if totalTrades == 0:
            continue
        logdebug(t, "trading ", good, " at $", round(price, 2),
                 "demandRatio:", round(demandRatio, 2),
                 " asks: ", round(totalAsks, 2),
                 " bids: ", round(totalBids, 2))
        totalBought, totalCashPurchase = \
            BiddersBuyGood(t, agents, good, bought_log, price, totalAsks, 0)
        askers = sorted(agents, key=lambda a: a.ask, reverse=True)
        totalCashSold, totalSold = \
            AskersSellGood(askers, good, price, t, totalBought,
                           totalCashPurchase, 0, 0)
        diff = math.fabs(totalCashSold - totalCashPurchase)
        if diff > .1:
            logwarning(t, "traded", good, "demand:", demandRatio,
                       "price:", price, "trades: ", good, " traded: ", 0,
                       "total bought", totalBought, "totalSold", totalSold,
                       "cash bought $", totalCashPurchase,
                       "cash sold $", totalCashSold, "diff",
                       math.fabs(totalCashSold - totalCashPurchase))
        sold_log[good].append(totalSold)
        reportCash(t, agents, prevTotalCash, "post primary trade " + str(good))
        sec_traded, sec_value = SecondaryTrade(t, agents, good, price, recipes)
        if sec_traded > 0:
            logdebug(t, "secondary traded", good, "vol:", sec_traded,
                     "value:$", round(sec_value, 2))
        reportCash(t, agents, prevTotalCash, "post secondary trade " + str(good))


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

def GatherBidsAsks(t, agents, good, goodPrice, num_desired, recipes,
                   totalAsks, totalBids):
    for agent in agents:
        agent_rec = recipes[agent.output]
        is_employee = getattr(agent, 'employer', None) is not None
        _withdraw_if_low_cash(agent, goodPrice, num_desired)
        mult = getattr(agent, 'consumption_mult', 1.0)
        bid = _compute_bid(agent, good, goodPrice, num_desired, agent_rec,
                           is_employee, mult, recipes)
        agent.bid = bid
        agent.remainingCash -= agent.bid * goodPrice
        loginfo(t, agent.name(), 'bid', agent.bid, 'input',
                GetInputCom(agent, recipes), 'recipe for',
                agent_rec['commodity'], 'num input', agent_rec['numInput'],
                agent.inv[good])
        totalBids += agent.bid
        ask = _compute_ask(agent, good, goodPrice, recipes, is_employee)
        agent.ask = ask
        totalAsks += agent.ask
    return totalAsks, totalBids


def _withdraw_if_low_cash(agent, goodPrice, num_desired):
    """Withdraw from bank deposits if cash is low for purchasing."""
    bank_balance = bank.deposits.get(agent, 0)
    if bank_balance > 0:
        desired_cash = goodPrice * num_desired
        if agent.remainingCash < desired_cash:
            needed = desired_cash - agent.remainingCash
            bank.Withdraw(agent, min(bank_balance, needed))


def _compute_bid(agent, good, goodPrice, num_desired, agent_rec, is_employee,
                 mult, recipes):
    """Compute how much *agent* wants to buy of *good* at *goodPrice*."""
    if not is_employee and GetInputCom(agent, recipes) == good:
        # Corporate/Independent producer input bidding
        num_employees = len(agent.employees) if getattr(agent, 'is_corp',
                                                        False) else 0
        multiplier = 1 + num_employees
        desired = max(0, agent_rec['numInput'] * multiplier
                      - agent.inv.get(good, 0))
        if mult > 1.0:
            desired = int(desired * mult)
        affordable = agent.remainingCash // goodPrice if goodPrice > 0 else desired
        return int(min(desired, affordable))
    elif (is_employee or agent.output != good) and agent.remainingCash > goodPrice:
        # Consumer bidding
        maxinv_limit = agent_rec['maxinv']
        if getattr(agent, 'is_corp', False):
            maxinv_limit *= (1 + len(agent.employees))
        if mult > 1.0:
            maxinv_limit = int(maxinv_limit * min(mult, 3.0))
        num_storable = max(0, maxinv_limit - agent.inv.get(good, 0))
        base_desire = min(num_desired,
                          agent.remainingCash // goodPrice)
        scaled_desire = int(base_desire * mult)
        bid = min(scaled_desire, num_storable)
        if mult > 2.0 and good != Goods.food:
            extra_affordable = min(
                int(num_desired * (mult - 1.0)),
                agent.remainingCash // goodPrice
            ) if goodPrice > 0 else 0
            bid += min(extra_affordable, num_storable - bid)
            loginfo('', agent.name(),
                    'wealth consumption (mult=' + str(round(mult, 2))
                    + ') bid extra for', good)
        return max(0, min(bid, num_storable))
    return 0


def _compute_ask(agent, good, goodPrice, recipes, is_employee):
    """Compute how much *agent* wants to sell of *good* at *goodPrice*."""
    if is_employee:
        return 0
    if agent.output != good and agent.output != Goods.gov:
        if agent.inv.get(good, 0) <= 0:
            return 0
    if agent.output == good or (agent.output == Goods.gov
                                and agent.inv.get(good, 0) > 0):
        cost_to_make = 0
        agent_rec = recipes.get(good, {})
        if agent.output == good and agent_rec.get('numInput', 0) > 0 \
           and agent_rec.get('production', 0) > 0:
            input_com = agent_rec['input']
            input_cost = agent.cost_basis.get(input_com, 0)
            cost_to_make = ((agent_rec['numInput'] * input_cost)
                            / agent_rec['production'])
        if good == Goods.food and agent.output == Goods.food:
            return max(0, agent.inv.get(good, 0) - 2)
        elif goodPrice >= cost_to_make:
            return max(0, agent.inv.get(good, 0))
    return 0


# =============================================================================
# EXECUTION: buyers & sellers
# =============================================================================

def AskersSellGood(askers, good, price, t, totalBought, totalCashPurchase,
                   totalCashSold, totalSold):
    for agent in askers:
        if totalSold < totalBought and totalCashPurchase > totalCashSold:
            ask = agent.ask
            remaining = totalBought - totalSold
            sold = min(ask, remaining)
            assert sold >= 0, 'neg sold ' + str(sold)
            totalSold += sold
            agent.cash += sold * price
            agent.inv[good] -= sold
            totalCashSold += sold * price
            if sold > 0:
                loginfo(t, agent.name(), 'sold ', sold, good, ', ask: ', ask)
    return totalCashSold, totalSold


def BiddersBuyGood(t, agents, good, bought_log, price, totalAsks,
                   totalBought):
    bidders = sorted(agents, key=lambda a: a.hungry_steps, reverse=True)
    totalCashPurchase = 0
    for agent in bidders:
        if totalAsks > totalBought:
            prevCash = agent.cash
            bid = agent.bid
            remaining = totalAsks - totalBought
            affordable = int(agent.cash / price)
            bought = max(0, min(bid, min(remaining, affordable)))
            cash = bought * price
            agent.cash = max(0.0, agent.cash - cash)
            assert agent.cash >= -1e-5, (
                'neg cash, bought $' + str(cash) + ' of ' + str(good)
                + ' now has ' + str(agent.cash))
            totalCashPurchase += cash
            if bought > 0:
                logdebug(t, agent.name(), 'had $', prevCash, 'now',
                         agent.cash, 'bought ', bought, good, ', bid: ',
                         bid, 'affordable: ', affordable, 'remaining:',
                         remaining)
                old_qty = agent.inv.get(good, 0)
                old_cost = agent.cost_basis.get(good, 0)
                total_qty = old_qty + bought
                if total_qty > 0:
                    agent.cost_basis[good] = ((old_qty * old_cost
                                               + bought * price) / total_qty)
                else:
                    agent.cost_basis[good] = price
                agent.inv[good] += bought
                totalBought += bought
                bought_log[agent.output][good][-1] += bought
            else:
                logdebug(t, agent.name(), 'had $', prevCash, 'now',
                         agent.cash, 'bought ', bought, good, ', bid: ',
                         bid, 'affordable: ', affordable, 'remaining:',
                         remaining)
    return totalBought, totalCashPurchase


# =============================================================================
# MARKET PRICE
# =============================================================================

def SetMarketPrice(demandRatio, good, recipes, agents=None):
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
    if demandRatio >= 1:
        clamped_ratio = min(5.0, demandRatio - 1)
        price *= lerp(1.01, 1.20, clamped_ratio / 5.0)
    elif demandRatio < 0.2:
        price *= lerp(0.90, 0.95, demandRatio / 0.2)
    elif demandRatio < .5:
        price *= lerp(0.95, 1.0, (demandRatio - 0.2) / 0.3)
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

def DecideBorrowDeposit(agents, allGoodsPrice, bank, foodPrice,
                        prevTotalCash, t):
    for agent in agents:
        BorrowIfNeedTo(t, agent)
        PayLoans(agent)
        _maybe_borrow_food_money(t, agent, foodPrice)
        _maybe_borrow_inputs(t, agent)
        _deposit_excess_cash(t, agent, allGoodsPrice)
        agent.remainingCash = agent.cash


def _maybe_borrow_food_money(t, agent, foodPrice):
    """Borrow for food if starving and no cash."""
    if agent.output != Goods.food and agent.cash < foodPrice \
       and agent.hungry_steps > 10:
        bank_balance = bank.deposits.get(agent, 0)
        if bank_balance > 0:
            needed = foodPrice - agent.cash
            bank.Withdraw(agent, min(bank_balance, needed))
        if agent.cash < foodPrice:
            Borrow(t, agent, foodPrice, bank)


def _maybe_borrow_inputs(t, agent):
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


def _deposit_excess_cash(t, agent, allGoodsPrice):
    """Deposit excess cash above a consumption-multiplier-based floor."""
    mult = getattr(agent, 'consumption_mult', 1.0)
    total_liquid = agent.cash + bank.deposits.get(agent, 0)
    current_deposits = bank.deposits.get(agent, 0)
    deposit_frac = max(0.30, min(0.70, 0.70 / max(1.0, mult)))
    cash_floor = int(allGoodsPrice * (100 / max(1.0, mult)))
    max_deposits = total_liquid * deposit_frac
    excess_deposit_capacity = max(0, max_deposits - current_deposits)
    if agent.cash > cash_floor and excess_deposit_capacity > 0:
        amount = min(agent.cash - cash_floor, excess_deposit_capacity)
        bank.Deposit(agent, amount)


# =============================================================================
# SECONDARY MARKET
# =============================================================================

def SecondaryTrade(t, agents, good, current_market_price, recipes):
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
        remaining_inv = agent.inv.get(good, 0)
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
        if not is_employee and GetInputCom(agent, recipes) == good:
            num_employees = len(agent.employees) if getattr(agent, 'is_corp',
                                                            False) else 0
            agent_rec = recipes[agent.output]
            desired = max(0, recipes[good]['numInput'] * (1 + num_employees)
                          - agent.inv.get(good, 0))
        else:
            maxinv_limit = recipes[good]['maxinv']
            if getattr(agent, 'is_corp', False):
                maxinv_limit *= (1 + len(agent.employees))
            num_storable = max(0, maxinv_limit - agent.inv.get(good, 0))
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
    mult = getattr(agent, 'consumption_mult', 1.0)
    if good == Goods.food and agent.hungry_steps > 0:
        base_premium = 1.0 + 0.5 * agent.hungry_steps
        return min(10.0, base_premium * mult * 0.5)
    elif (not is_employee and agent.output in recipes
          and GetInputCom(agent, recipes) == good
          and agent.inv.get(good, 0) == 0):
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
                bid.agent.inv[good] += trade_qty
                ask.agent.inv[good] -= trade_qty
                old_qty = bid.agent.inv.get(good, 0) - trade_qty
                old_cost = bid.agent.cost_basis.get(good, 0)
                if bid.agent.inv[good] > 0:
                    bid.agent.cost_basis[good] = (
                        (old_qty * old_cost + cost)
                        / bid.agent.inv[good]
                    )
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

def reportCash(t, agents, prevTotalCash, msg, print=False):
    tempTotalCash = getTotalCash(agents)
    diff = math.fabs(tempTotalCash - prevTotalCash)
    epsilon = 1e-8
    if diff > epsilon or print:
        loginfo(t, msg, "total cash", prevTotalCash, '!=', tempTotalCash,
                diff)


def getTotalCash(agents):
    bankCash = bank.total_deposits - bank.total_liabilities
    return sum(agent.cash for agent in agents) + bankCash