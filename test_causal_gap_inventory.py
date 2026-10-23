"""Static discovery is a review queue; runtime coverage is a separate contract."""
import json
from pathlib import Path
import random
import unittest

from causal_gap_inventory import BASELINE, REVIEWS, ROOT, discover_source, inventory, render


class CausalGapInventoryTests(unittest.TestCase):
    def test_aliases_subscripts_bulk_replacement_and_destructuring_are_candidates(self):
        rows = discover_source('''
def settle(treasury, payer, bank, actor):
    treasury.cash -= 3
    payer.capital += 4
    bank.deposits[actor] -= 2
    bank.deposits.clear()
    bank.deposits = {}
    treasury.cash, bank.total_liabilities = 1, 2
''', 'example.py')
        self.assertEqual(7, len(rows))
        self.assertTrue(all(row['review'] == 'needs_review' for row in rows))
        self.assertTrue(all(row['closure'] == 'unknown' for row in rows))
        nested = discover_source('bank.deposits[actor], ignored = 1, 2', 'tuple.py')
        self.assertEqual(['deposit_account'], [row['balance_candidate'] for row in nested])

    def test_lines_do_not_change_ids_but_amount_or_eligibility_change_does(self):
        source = 'def pay(treasury):\n    if treasury.cash > 0:\n        treasury.cash -= 1\n'
        original = discover_source(source, 'writer.py')[0]['id']
        self.assertEqual(original, discover_source('\n\n'+source, 'writer.py')[0]['id'])
        self.assertNotEqual(original, discover_source(source.replace('-= 1','-= 2'), 'writer.py')[0]['id'])
        self.assertNotEqual(original, discover_source(source.replace('> 0','> 5'), 'writer.py')[0]['id'])

    def test_current_writes_match_review_baseline(self):
        state = random.getstate()
        data = inventory()
        self.assertEqual(state, random.getstate())
        expected = json.loads(BASELINE.read_text())['writer_ids']
        self.assertEqual(expected, sorted(row['id'] for row in data['writers']))
        reviewed = json.loads(REVIEWS.read_text())['writers']
        self.assertFalse(set(reviewed) - set(expected), 'stale writer reviews')
        for row in data['writers']:
            if row['id'] in reviewed:
                self.assertTrue(row['fixtures'])
                self.assertTrue(row['owner'])
        self.assertTrue(all(row['closure'] == 'not_verified_by_inventory' for row in data['metrics']))
        self.assertTrue(all(row['status'] == 'inventory_incomplete' for row in data['scenarios'].values()))
        fields = {row['field'] for row in data['histories']}
        self.assertTrue({'cash_log','bought_log','forage_log','gdp_by_profession_log'} <= fields)
        self.assertIn('Needs review:', render(data))


if __name__ == '__main__':
    unittest.main()
