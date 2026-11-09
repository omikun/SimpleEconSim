import unittest
from types import SimpleNamespace

from economy.credit_policy import assessment, record_borrow, record_turn_result


class CreditPolicyTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=7, is_government=False,
                                     is_corporation=False,
                                     credit_unprofitable_borrow_turns=0,
                                     credit_last_unprofitable_borrow_turn=None)
        self.region = SimpleNamespace(actor_account_history=[
            {'actor_id': 7, 'turn': turn, 'credit_operating_result': -2.0}
            for turn in range(3)])

    def test_unprofitable_borrowing_expires_after_twenty_distinct_turns(self):
        for turn in range(20):
            result = assessment(self.region, self.actor, turn)
            self.assertTrue(result['allowed'])
            record_borrow(self.region, self.actor, turn, result)
        self.assertEqual(20, self.actor.credit_unprofitable_borrow_turns)
        self.assertFalse(assessment(self.region, self.actor, 20)['allowed'])

    def test_multiple_loans_in_one_loss_turn_count_once(self):
        result = assessment(self.region, self.actor, 4)
        record_borrow(self.region, self.actor, 4, result)
        record_borrow(self.region, self.actor, 4, result)
        self.assertEqual(1, self.actor.credit_unprofitable_borrow_turns)

    def test_recent_profit_resets_temporary_loss_counter(self):
        self.actor.credit_unprofitable_borrow_turns = 12
        self.region.actor_account_history = [
            {'actor_id': 7, 'turn': turn, 'credit_operating_result': 3.0}
            for turn in range(3)]
        result = assessment(self.region, self.actor, 4)
        self.assertTrue(result['allowed'])
        self.assertTrue(result['profitable'])
        record_turn_result(self.actor, result['result'])
        self.assertEqual(0, self.actor.credit_unprofitable_borrow_turns)

    def test_loss_window_allows_additional_loans_on_last_borrow_turn(self):
        self.actor.credit_unprofitable_borrow_turns = 20
        self.actor.credit_last_unprofitable_borrow_turn = 6
        self.assertTrue(assessment(self.region, self.actor, 6)['allowed'])
        self.assertFalse(assessment(self.region, self.actor, 7)['allowed'])


if __name__ == '__main__':
    unittest.main()
