"""Abstract service sinks and actual soldier wallets have distinct accounting."""
import unittest
from unittest.mock import patch
from army import MilitaryUnit,step_armies
from nation import Nation
from region import Region
from agent import Agent,initialize_agent
from goods import Goods
from forex import audit_currency_total
import ledger


class AbstractMilitaryCurrencyTests(unittest.TestCase):
    def test_full_partial_unpaid_and_concrete_personnel_currency_conservation(self):
        for cash,concrete in ((10,False),(2,False),(0,False),(10,True)):
            with self.subTest(cash=cash,concrete=concrete),patch.object(ledger,'_destruction',[]):
                nation=Nation('Military audit','EGP',initial_cash=cash,register=False)
                tile=Region('Fort',0,number_of_agents=0);nation.add_tile(tile)
                tile.home_currency='EGP';nation.government.agent.home_currency='EGP'
                unit=MilitaryUnit('abstract-payroll',nation.name,tile.name,soldiers=1,
                                  wage_per_soldier=5,food_per_soldier=0)
                if concrete:
                    person=Agent(0);initialize_agent(person,Goods.none,0,0,0)
                    tile.agents.append(person);unit.person_ids=[person.id];unit.scenario_personnel=True
                nation.military_units=[unit];tile.military_units=[unit]
                before=audit_currency_total([tile],'EGP')
                step_armies([tile],[nation],t=2)
                delta=audit_currency_total([tile],'EGP')-before
                self.assertAlmostEqual(0,delta+ledger.cleared(2,'EGP'))
                self.assertEqual(0 if concrete else min(5,cash),ledger.cleared(2,'EGP'))
                self.assertEqual(max(0,cash-5),nation.government.agent.cash)


if __name__=='__main__':unittest.main()
