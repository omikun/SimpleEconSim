"""Acceptance-only manufacturing-cost observation; never writes simulation assets."""
from goods import Goods


class FirmAccounts:
    def __init__(self, firm):
        self.output_quantity = firm.inv_get(firm.output, 0)
        self.output_cost = self.output_quantity * firm.cost_get(firm.output, 0)

    def observe_turn(self, firm, events):
        produced = material = payroll = 0
        for event in events:
            if event['kind'] == 'spot_sale' and event['recipient_id'] == firm.id and event['good'] == firm.output.name:
                sold = event['quantity']
                if sold > self.output_quantity + 1e-8:
                    raise AssertionError('Sold output without observed stock')
                self.output_cost *= (self.output_quantity - sold) / self.output_quantity if self.output_quantity else 0
                self.output_quantity -= sold
            elif event['kind'] == 'input_consumed' and event['payer_id'] == firm.id:
                material += event['amount']
            elif event['kind'] == 'production' and event['recipient_id'] == firm.id:
                produced += event['quantity']
            elif event['kind'] == 'wage' and event['payer_id'] == firm.id:
                payroll += event['amount']
        self.output_quantity += produced
        if produced:
            self.output_cost += material + payroll
        if abs(self.output_quantity - firm.inv_get(firm.output, 0)) > 1e-8:
            raise AssertionError('Output cost observation diverged from physical stock')

    def balance_sheet(self, firm, region, common_prices):
        inventory = {}
        for good in Goods:
            quantity = firm.inv_get(good, 0)
            if not quantity:
                continue
            cost = self.output_cost if good == firm.output else quantity * firm.cost_get(good, 0)
            inventory[good.name] = {'quantity': quantity, 'manufacturing_cost': cost,
                                   'common_reference_value': quantity * common_prices.get(good, 0)}
        debt = sum(max(0, loan.principle - loan.principle_paid) for loan in firm.loans)
        obligations = sum(c.balance for c in getattr(region, 'cash_obligations', ())
                          if c.debtor_id == firm.id and c.status == 'active')
        arrears = max(0, getattr(firm, 'wage_arrears_balance', 0))
        deposits = region.bank.deposits.get(firm, 0)
        financial = firm.cash + deposits - debt - obligations - arrears
        return dict(cash=firm.cash, deposits=deposits, bank_principal=debt,
                    cash_obligations=obligations, wage_arrears=arrears, inventory=inventory,
                    net_assets_at_manufacturing_cost=financial + sum(v['manufacturing_cost'] for v in inventory.values()),
                    net_assets_at_common_prices=financial + sum(v['common_reference_value'] for v in inventory.values()))
