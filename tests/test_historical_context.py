import unittest
from types import SimpleNamespace

from agents.collective_action import _event
from historical_context.matcher import annotate_event, load_catalog, select_moment


class HistoricalContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def test_walkout_matches_a_specific_sourced_case(self):
        card = select_moment({'kind': 'strike_started', 'facts': {}}, catalog=self.catalog)
        self.assertEqual('homestead_1892:walkout', card['id'])
        self.assertTrue(card['sources'][0]['url'].startswith('https://'))

    def test_agreement_matches_reconciliation_moment(self):
        card = select_moment({'kind': 'agreement_signed', 'facts': {}}, catalog=self.catalog)
        self.assertEqual('flint_1937:negotiated_recognition', card['id'])
        self.assertEqual(4, card['signals']['reconciliation'])

    def test_tuning_filters_historical_moments_by_independent_dimensions(self):
        high_harm = select_moment(
            {'kind': 'strike_started', 'facts': {}},
            settings={'min_bloodshed': 3}, catalog=self.catalog)
        self.assertIsNone(high_harm)
        conciliatory = select_moment(
            {'kind': 'agreement_signed', 'facts': {}},
            settings={'min_reconciliation': 3, 'max_bloodshed': 1},
            catalog=self.catalog)
        self.assertEqual('flint_1937:negotiated_recognition', conciliatory['id'])

    def test_future_event_can_supply_its_own_category_and_action(self):
        moment = {'id': 'declared', 'category': 'politics.emergency',
                  'match': {'actions': ['declared']}, '_case': {'id': 'example',
                  'title': 'Example', 'sources': []}, '_source_path': 'test.json'}
        card = select_moment({'kind': 'new_event', 'facts': {
            'historical_category': 'politics.emergency',
            'historical_action': 'declared'}}, catalog=[moment])
        self.assertEqual('example:declared', card['id'])

    def test_significant_event_without_a_match_still_gets_a_popup_record(self):
        event = {'id': 'region:collective:1', 'kind': 'owner_decision',
                 'message': 'The firm waits.', 'facts': {}}
        annotate_event(event, catalog=[])
        self.assertEqual('No close historical match',
                         event['historical_context']['case_title'])
        self.assertEqual('The firm waits.', event['historical_context']['facts'])

    def test_collective_event_writer_attaches_historical_context(self):
        region = SimpleNamespace(name='Mill District', collective_organizations={},
                                 collective_log=[], _run_trace=None)
        firm = SimpleNamespace(id=12, company_name='Foundry')
        event = _event(region, 3, 'strike_started', firm, strike_id='s1',
                       message='Workers walk out.')
        self.assertEqual('homestead_1892:walkout',
                         event['historical_context']['id'])
        self.assertEqual(1, len(region.collective_log))


if __name__ == '__main__':
    unittest.main()
