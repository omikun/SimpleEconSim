"""National treasury reports count actual public accounts exactly once."""

import json
import random
from types import SimpleNamespace
import unittest

from econsim_trade_money import Bank
from government import Government
from nation import Nation


def _government(name, cash, food=0):
    government = Government(name, 0, initial_cash=cash)
    government.food_inventory = food
    return government


def _shared_province():
    nation = Nation('Nation', initial_cash=100.0, register=False)
    nation.government.food_inventory = 2
    provincial = _government('Province', 50.0, 3)
    bank = Bank(gov=provincial)
    province = SimpleNamespace(name='Province', gov=provincial, bank=bank)
    nation.tiles = [SimpleNamespace(name=name, gov=provincial, bank=bank, province=province)
                    for name in ('North', 'South')]
    nation.government._bank_ref = bank
    nation.government.agent._bank_ref = bank
    bank.deposits[nation.government.agent] = 20.0
    bank.deposits[provincial.agent] = 10.0
    return nation, provincial, bank


class TreasuryAccountTests(unittest.TestCase):
    def test_shared_province_counts_cash_deposits_and_food_once(self):
        nation, _provincial, _bank = _shared_province()
        treasury = nation.treasury()
        self.assertEqual(treasury['sovereign_cash'], 100.0)
        self.assertEqual(treasury['provincial_cash'], 50.0)
        self.assertEqual(treasury['municipal_cash'], 0.0)
        self.assertEqual(treasury['cash'], 150.0)
        self.assertEqual(treasury['deposits'], 30.0)
        self.assertEqual(treasury['total'], 180.0)
        self.assertEqual(treasury['food'], 5)
        self.assertEqual(len(treasury['accounts']), 2)
        self.assertTrue(all(len(row['deposit_accounts']) == 1
                            for row in treasury['accounts']))
        json.dumps(treasury, allow_nan=False)

    def test_distinct_tiers_and_same_named_governments_remain_separate(self):
        nation = Nation('Nation', initial_cash=100.0, register=False)
        provincial = _government('Same name', 40.0)
        local_a = _government('Same name', 10.0)
        local_b = _government('Same name', 20.0)
        province_bank = Bank(gov=provincial)
        bank_a, bank_b = Bank(gov=local_a), Bank(gov=local_b)
        sovereign_bank = Bank(gov=nation.government)
        nation.government._bank_ref = sovereign_bank
        province = SimpleNamespace(name='Province', gov=provincial, bank=province_bank)
        nation.tiles = [SimpleNamespace(name='A', gov=local_a, bank=bank_a, province=province),
                        SimpleNamespace(name='B', gov=local_b, bank=bank_b, province=province)]
        sovereign_bank.deposits[nation.government.agent] = 2.0
        province_bank.deposits[nation.government.agent] = 5.0
        province_bank.deposits[provincial.agent] = 3.0
        bank_a.deposits[local_a.agent] = 7.0
        bank_b.deposits[local_b.agent] = 11.0
        treasury = nation.treasury()
        self.assertEqual(treasury['cash'], 170.0)
        self.assertEqual(treasury['provincial_cash'], 40.0)
        self.assertEqual(treasury['municipal_cash'], 30.0)
        self.assertEqual(treasury['deposits'], 28.0)
        self.assertEqual(treasury['total'], 198.0)
        self.assertEqual(len(treasury['accounts']), 4)
        sovereign = next(row for row in treasury['accounts'] if row['tier'] == 'sovereign')
        self.assertEqual(len(sovereign['deposit_accounts']), 2)

    def test_loss_of_one_shared_tile_does_not_change_the_money_total(self):
        nation, _provincial, _bank = _shared_province()
        before = nation.treasury()
        nation.tiles.pop()
        self.assertEqual(nation.treasury(), before)
        nation.tiles.clear()
        # The sovereign's directly referenced bank deposit remains its asset.
        treasury = nation.treasury()
        self.assertEqual(treasury['total'], 120.0)
        self.assertEqual(treasury['food'], 2)
        self.assertEqual(len(treasury['accounts']), 1)

    def test_sovereign_aliases_do_not_become_extra_tiers(self):
        nation = Nation('Nation', initial_cash=100.0, register=False)
        bank = Bank(gov=nation.government)
        nation.government._bank_ref = bank
        bank.deposits[nation.government.agent] = 12.0
        province = SimpleNamespace(gov=nation.government, bank=bank)
        nation.tiles = [SimpleNamespace(gov=nation.government, bank=bank, province=province)]
        treasury = nation.treasury()
        self.assertEqual(treasury['total'], 112.0)
        self.assertEqual(treasury['provincial_cash'], 0.0)
        self.assertEqual(treasury['municipal_cash'], 0.0)
        self.assertEqual(len(treasury['accounts']), 1)

    def test_reporting_is_read_only_and_returns_detached_evidence(self):
        nation, provincial, bank = _shared_province()
        private_bank = Bank()
        nation.tiles.append(SimpleNamespace(name='Empty', gov=None, bank=private_bank, province=None))
        before = (nation.government.agent.cash, provincial.agent.cash,
                  dict(bank.deposits), dict(private_bank.deposits),
                  bank.capital, bank.total_deposits, bank.total_liabilities)
        rng = random.getstate()
        first = nation.treasury()
        self.assertEqual(nation.treasury(), first)
        self.assertEqual(random.getstate(), rng)
        first['accounts'][0]['cash'] = -999.0
        first['accounts'][0]['deposit_accounts'].clear()
        after = (nation.government.agent.cash, provincial.agent.cash,
                 dict(bank.deposits), dict(private_bank.deposits),
                 bank.capital, bank.total_deposits, bank.total_liabilities)
        self.assertEqual(after, before)
        self.assertEqual(nation.treasury()['total'], 180.0)


if __name__ == '__main__':
    unittest.main()
