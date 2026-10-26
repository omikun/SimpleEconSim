"""Behavioral checks for general corporation bargaining and its causal log."""

import pickle
import json
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from goods import Goods
from collective_action import transfer_support, record_payroll_and_review
from collective_action import step_collectives, record_essential_needs
from collective_politics import record_authority_incident, political_summary
from scenario_labor_frontier_rivalry import create_world, step_world
from labor_frontier_labor import apply_action
from collective_report import export_trace
from labor_frontier_projection import project


class CollectiveActionTest(unittest.TestCase):
    def _fixture(self):
        world = create_world(seed=612)
        self.assertEqual(step_world(world), [])
        firm = next(a for region in world['tiles'] for a in region.agents
                    if a.alive and a.is_corporation and a.employees)
        region = next(r for r in world['tiles'] if firm in r.agents)
        # The scenario now hires one worker during its opening turn. Collective
        # action needs at least two participants, so add an existing free adult
        # to this fixture instead of depending on a particular hiring cadence.
        while len(firm.employees) < 2:
            worker = next(a for a in region.agents
                          if a.alive and not a.is_corporation and not a.is_trader
                          and not a.is_government and a.employer is None
                          and not getattr(a, 'military_unit_id', None)
                          and not getattr(a, 'is_native_child', False))
            worker.employer = firm
            worker.shift_hours = getattr(firm, 'shift_hours', 8.0)
            worker.wage = firm.wage
            firm.employees.append(worker)
        for worker in firm.employees:
            worker.class_consciousness = 1.0
            worker.alienation = 1.0
            worker.hungry_steps = 0
            worker.inv_add(Goods.food, 4)
        firm.cash = max(firm.cash, 100.0)
        return world, region, firm

    def test_all_corporation_types_use_persistent_votes_and_observed_work(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        org = region.collective_organizations[firm.id]
        strike = org.strikes[-1]
        events = [e for e in region.collective_log if e['strike_id'] == strike.id]
        kinds = [e['kind'] for e in events]
        self.assertIn('strike_started', kinds)
        self.assertIn('participation', kinds)
        self.assertIn('production_observed', kinds)
        self.assertIn('needs_observed', kinds)
        self.assertEqual(len(set(e['id'] for e in events)), len(events))
        self.assertTrue(all(e['firm_id'] == firm.id for e in events))
        self.assertTrue(any(e.is_striking for e in firm.employees))
        restored = pickle.loads(pickle.dumps(world))
        restored_region = next(r for r in restored['tiles'] if r.name == region.name)
        self.assertEqual(restored_region.collective_organizations[firm.id].strikes[-1].id,
                         strike.id)
        self.assertEqual(restored_region.collective_log[-1]['id'], region.collective_log[-1]['id'])

    def test_support_moves_existing_stock_and_is_logged_once(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        striker = next(e for e in firm.employees if e.is_striking)
        donor = next(a for a in region.agents if a.alive and a.id != striker.id
                     and not a.is_corporation and not a.is_government
                     and a.cash >= 1 and a.inv_get(Goods.food, 0) >= 1)
        cash_sum = donor.cash + striker.cash
        food_sum = donor.inv_get(Goods.food, 0) + striker.inv_get(Goods.food, 0)
        self.assertTrue(transfer_support(region, world['turn'], donor.id, striker.id,
                                         cash=1.0, food=1))
        self.assertAlmostEqual(donor.cash + striker.cash, cash_sum)
        self.assertEqual(donor.inv_get(Goods.food, 0) + striker.inv_get(Goods.food, 0),
                         food_sum)
        self.assertFalse(transfer_support(region, world['turn'], donor.id, striker.id,
                                          cash=donor.cash + 1))
        self.assertEqual(region.collective_log[-1]['kind'], 'support_transfer')

    def test_settlement_review_uses_paid_wages_and_applies_once(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        org = region.collective_organizations[firm.id]
        strike = org.strikes[-1]
        self.assertEqual(step_world(world), [])
        self.assertEqual(strike.status, 'review')
        self.assertTrue(any(e['kind'] == 'agreement_signed' and e['strike_id'] == strike.id
                            for e in region.collective_log))
        self.assertEqual(step_world(world), [])
        self.assertEqual(step_world(world), [])
        self.assertTrue(strike.settlement_applied)
        first_confidence = org.confidence
        prior_events = len(region.collective_log)
        record_payroll_and_review(region, world['turn'], {})
        self.assertEqual(org.confidence, first_confidence)
        self.assertEqual(len(region.collective_log), prior_events)
        review = [e for e in region.collective_log
                  if e['kind'] == 'settlement_review' and e['strike_id'] == strike.id]
        self.assertEqual(len(review), 1)
        self.assertIn('actual_real_wage', review[0]['facts'])

    def test_public_food_support_is_finite_and_appears_in_export(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        nation = region.owner_nation
        initial_food = nation.government.food_inventory
        initial_cash = nation.government.agent.cash
        ok, _ = apply_action(world, 'support_strikers')
        self.assertTrue(ok)
        self.assertFalse(apply_action(world, 'support_strikers')[0])
        transfer = next(e for e in reversed(region.collective_log)
                        if e['kind'] == 'public_support_transfer')
        self.assertEqual(initial_food - nation.government.food_inventory,
                         transfer['facts']['food_units'])
        self.assertEqual(nation.government.agent.cash, initial_cash)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'run.jsonl'
            count = export_trace(world, path, seed=612)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(count, len(rows) - 1)
        self.assertEqual(rows[0]['schema'], 1)
        sequences = [row['sequence'] for row in rows[1:] if 'sequence' in row]
        self.assertEqual(sequences, sorted(sequences))
        self.assertEqual(len(sequences), len(set(sequences)))
        self.assertEqual(rows[0]['ordered_rows'], len(sequences))
        self.assertTrue(any(row.get('kind') == 'public_support_transfer' for row in rows))
        self.assertTrue(any(row.get('kind') == 'strike_started' for row in rows))

    def test_cotton_estate_and_textile_mill_both_can_strike(self):
        world, mill_region, mill = self._fixture()
        estate_region = world['tiles'][1]
        estate = next(a for a in estate_region.agents
                      if a.alive and a.is_corporation and a.output == Goods.cotton)
        candidates = [a for a in estate_region.agents if a.alive and a.employer is None
                      and not a.is_corporation and not a.is_government
                      and not a.is_trader and not getattr(a, 'is_lord', False)
                      and not getattr(a, 'military_unit_id', None)]
        self.assertGreaterEqual(len(candidates), 2)
        for worker in candidates[:2]:
            worker.employer = estate
            estate.employees.append(worker)
            worker.class_consciousness = 1.0
            worker.alienation = 1.0
            worker.hungry_steps = 0
            worker.inv_add(Goods.food, 4)
        estate.cash = max(estate.cash, 100.0)
        self.assertEqual(step_world(world), [])
        self.assertTrue(mill_region.collective_organizations[mill.id].active_strike_id)
        self.assertTrue(estate_region.collective_organizations[estate.id].active_strike_id)
        self.assertNotEqual(mill.id, estate.id)

    def test_closed_firm_releases_participants_and_records_reason(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        org = region.collective_organizations[firm.id]
        participants = [a for a in firm.employees if a.is_striking]
        firm.is_corporation = False
        self.assertEqual(step_world(world), [])
        self.assertIsNone(org.active_strike_id)
        self.assertTrue(all(not person.is_striking for person in participants if person.alive))
        self.assertTrue(any(e['kind'] == 'strike_ended'
                            and e['facts'].get('reason') == 'firm_closed'
                            for e in region.collective_log))

    def test_shared_projection_and_server_tile_expose_the_same_evidence(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        projected = project(world)['collective_info']
        self.assertTrue(any(e['firm_id'] == firm.id for e in projected['events']))
        from sim_server.sim_server import SimServer
        server = SimServer(seed=612, scenario_id='labor_frontier_rivalry')
        server_region = next(r for r in server.tiles if r.name == region.name)
        # The server's serializer is used by both browser asset paths.
        server_region.collective_organizations = region.collective_organizations
        server_region.collective_log = region.collective_log
        payload = server.serialize_tile(server_region, layout=server.layout, turn=world['turn'])
        json.dumps(payload)
        events = payload['collective_action']['events']
        self.assertEqual(events[-1]['id'], region.collective_log[-1]['id'])
        self.assertEqual(payload['collective_action']['organizations'][0]['firm_id'], firm.id)

    def test_political_incident_requires_colonial_authority_and_applies_once(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        member_ids = [person.id for person in firm.employees]
        nation = region.owner_nation
        self.assertIsNone(political_summary(region)['mobilization_index'])
        self.assertEqual(record_authority_incident(region, world['turn'], 'law:1', nation,
                                                   member_ids, repression=.5),
                         len(member_ids))
        self.assertIsNone(political_summary(region)['mobilization_index'])
        region.colonial_authority = nation.name
        before = political_summary(region)
        self.assertEqual(before['covered_residents'], len(set(member_ids)))
        self.assertEqual(record_authority_incident(region, world['turn'], 'reform:1', nation,
                                                   member_ids, reform=.8), len(member_ids))
        after_reform = political_summary(region)
        self.assertLess(after_reform['mobilization_index'], before['mobilization_index'])
        self.assertEqual(record_authority_incident(region, world['turn'], 'reform:1', nation,
                                                   member_ids, reform=.8), 0)
        with self.assertRaises(ValueError):
            record_authority_incident(region, world['turn'], 'breach:invalid', nation,
                                      member_ids, breach=.8)
        self.assertEqual(record_authority_incident(
            region, world['turn'], 'breach:1', nation, member_ids,
            breach=.8, accepted_commitment_id='agreement:1'), len(member_ids))
        after_breach = political_summary(region)
        self.assertGreater(after_breach['mobilization_index'],
                           after_reform['mobilization_index'])
        for person_id in member_ids:
            shares = region.constitutional_preferences[person_id]
            self.assertAlmostEqual(sum(shares.values()), 1.0)
        restored = pickle.loads(pickle.dumps(region))
        self.assertEqual(political_summary(restored), after_breach)

    def test_step_and_needs_observation_are_once_per_turn(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        events_before = len(region.collective_log)
        step_collectives(region, world['turn'])
        record_essential_needs(region, world['turn'])
        self.assertEqual(len(region.collective_log), events_before)

    def test_cash_promise_paid_in_scrip_is_logged_as_breach(self):
        world, region, firm = self._fixture()
        self.assertEqual(step_world(world), [])
        self.assertEqual(step_world(world), [])
        strike = region.collective_organizations[firm.id].strikes[-1]
        self.assertEqual(strike.status, 'review')
        firm.pay_mode = 'scrip'
        before = {person.id: person.cash for person in firm.employees}
        next_turn = world['turn'] + 1
        record_payroll_and_review(region, next_turn, before)
        breaches = [event for event in region.collective_log
                    if event['kind'] == 'payroll_breach' and event['strike_id'] == strike.id]
        self.assertEqual(len(breaches), 1)
        self.assertTrue(breaches[0]['facts']['cash_shortfall_by_person'])
        count = len(region.collective_log)
        record_payroll_and_review(region, next_turn, before)
        self.assertEqual(len(region.collective_log), count)


if __name__ == '__main__':
    unittest.main()
