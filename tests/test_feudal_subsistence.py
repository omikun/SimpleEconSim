"""Seasonal harvest assessments and conserved food support on owned estates."""
import pickle
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent import Agent, initialize_agent
from demographics_consumption import consume_daily_food
from economic_replay import replay
from econsim_live import Live, LiveContext
from feudal_tribute import collect_tribute, estate_residents, feed_estate_residents
from goods import Goods
from land_tenure import LandPlot, TenureStatus, TileTenure
from tests.test_tribute_trace import MemoryTrace


def person(ident, *, food=0, lord=False, plot=None):
    a = Agent(0)
    initialize_agent(a, Goods.food, 0, food, 0)
    a.id, a.is_lord, a.assigned_plot_id = ident, lord, plot
    a.region = 'Estate'
    return a


def fixture(*, traced=False):
    lord = person(1, food=20, lord=True)
    tenant = person(2, food=20, plot='home')
    plot = LandPlot('home', 'Estate', 1, 1.0, TenureStatus.FEUDAL, tenant_ids=[2])
    region = SimpleNamespace(name='Estate', home_currency='E', agents=[lord, tenant],
                             tenure=TileTenure([plot]), production_receipts=[],
                             household_food_reserve_turns=0, protest_energy_log=[],
                             police_employed=0, military_units=[])
    if traced:
        region._run_trace = MemoryTrace()
        region._collective_trace_clock = {'turn': 7, 'phase': 'test', 'next': 1}
    return region, lord, tenant, plot


def harvest(region, tenant, turn, units, good=Goods.food):
    region.production_receipts = [{'turn': turn, 'person_id': tenant.id,
                                   'good': good, 'quantity': units}]
    return collect_tribute(region, turn)


class SeasonalTributeTests(unittest.TestCase):
    def test_harvest_accumulates_and_is_collected_once_each_ten_turns(self):
        r, lord, tenant, _ = fixture()
        lord.inv_set(Goods.food, 0)
        self.assertEqual(harvest(r, tenant, 2, 4), {})
        self.assertEqual(harvest(r, tenant, 6, 6), {})
        self.assertEqual(lord.inv_get(Goods.food), 0)
        due = harvest(r, tenant, 7, 2)
        self.assertEqual(due, {lord.id: {Goods.food: 6}})
        self.assertEqual(collect_tribute(r, 7), {})
        self.assertEqual(lord.inv_get(Goods.food), 6)
        self.assertEqual(harvest(r, tenant, 16, 4), {})
        self.assertEqual(harvest(r, tenant, 17, 0), {lord.id: {Goods.food: 2}})

    def test_old_reserves_and_purchased_or_gifted_grain_do_not_create_tax(self):
        r, lord, tenant, _ = fixture()
        tenant.inv_set(Goods.food, 100)
        self.assertEqual(collect_tribute(r, 7), {})
        tenant.inv_add(Goods.food, 30)  # A purchase or gift, not a harvest receipt.
        self.assertEqual(collect_tribute(r, 17), {})
        self.assertEqual(lord.inv_get(Goods.food), 20)
        self.assertEqual(tenant.inv_get(Goods.food), 130)

    def test_previously_assessed_harvest_is_not_taxed_next_year(self):
        r, lord, tenant, _ = fixture()
        harvest(r, tenant, 7, 10)
        balance = tenant.inv_get(Goods.food)
        r.production_receipts = []
        self.assertEqual(collect_tribute(r, 17), {})
        self.assertEqual(tenant.inv_get(Goods.food), balance)

    def test_tax_protects_dependents_and_does_not_create_goods_or_arrears(self):
        r, lord, tenant, _ = fixture(traced=True)
        child = person(3)
        child.is_native_child, child.birth_round, child.parent = True, 6, tenant
        child.calorie_need_kcal = 1000
        tenant.descendants = [child]
        tenant.inv_set(Goods.food, 7)
        r.agents.append(child)
        total = sum(a.inv_get(Goods.food) for a in r.agents)
        result = harvest(r, tenant, 7, 20)
        self.assertEqual(result, {lord.id: {Goods.food: 1}})
        self.assertEqual(tenant.inv_get(Goods.food), 6)
        self.assertEqual(sum(a.inv_get(Goods.food) for a in r.agents), total)
        unpaid = next(row for row in r._run_trace.rows if row['kind'] == 'feudal_tribute_unpaid')
        self.assertEqual(unpaid['after'], 9)
        self.assertFalse(unpaid['inputs']['arrears_created'])

    def test_taxpayer_is_linked_to_actual_plot_not_agent_order_or_fraction(self):
        r, lord, tenant, p = fixture()
        other_lord = person(4, food=0, lord=True)
        p.fraction = .5
        second = LandPlot('other', 'Estate', 4, .5, TenureStatus.FEUDAL)
        r.tenure.plots.append(second)
        r.agents = [tenant, other_lord, lord]
        harvest(r, tenant, 7, 8)
        self.assertEqual(lord.inv_get(Goods.food), 24)
        self.assertEqual(other_lord.inv_get(Goods.food), 0)

    def test_receipts_and_unfinished_assessments_survive_save_restore(self):
        r, lord, tenant, _ = fixture()
        harvest(r, tenant, 2, 8)
        restored = pickle.loads(pickle.dumps(r))
        restored_lord, restored_tenant = restored.agents
        collect_tribute(restored, 2)  # Same receipt cannot accrue twice.
        self.assertEqual(harvest(restored, restored_tenant, 7, 2), {lord.id: {Goods.food: 5}})
        self.assertEqual(restored_lord.inv_get(Goods.food), 25)


class EstateSubsistenceTests(unittest.TestCase):
    def test_feeds_basic_meal_without_cash_debt_or_duplicate_delivery(self):
        r, lord, tenant, _ = fixture()
        tenant.inv_set(Goods.food, 0)
        tenant.energy_reserve_kcal, tenant.hungry_steps = 0, 20
        before = sum(a.inv_get(Goods.food) for a in r.agents)
        self.assertEqual(feed_estate_residents(r, 4), 4)
        self.assertEqual(feed_estate_residents(r, 4), 0)
        self.assertEqual(tenant.cash, 0)
        self.assertEqual(tenant.company_debt, 0)
        self.assertEqual(sum(a.inv_get(Goods.food) for a in r.agents), before)
        consume_daily_food(tenant, region=r, turn=4)
        self.assertEqual(tenant.calorie_deficit_kcal, 0)

    def test_only_own_local_residents_receive_food(self):
        r, lord, tenant, p = fixture()
        tenant.inv_set(Goods.food, 0)
        outsider = person(3)
        other = person(4, plot='other')
        p.fraction = .5
        r.tenure.plots.append(LandPlot('other', 'Estate', 99, .5, TenureStatus.FEUDAL, tenant_ids=[4]))
        r.agents += [outsider, other]
        feed_estate_residents(r, 4)
        self.assertEqual(tenant.inv_get(Goods.food), 4)
        self.assertEqual(outsider.inv_get(Goods.food), 0)
        self.assertEqual(other.inv_get(Goods.food), 0)

    def test_family_residence_and_new_explicit_assignment(self):
        r, lord, tenant, p = fixture()
        child = person(3)
        child.parent = tenant
        r.agents.append(child)
        self.assertIn(child, estate_residents(r)['home'])
        p.fraction = .5
        r.tenure.plots.append(LandPlot('other', 'Estate', 99, .5, TenureStatus.FEUDAL))
        child.assigned_plot_id = 'other'
        feed_estate_residents(r, 4)
        self.assertEqual(child.inv_get(Goods.food), 0)

    def test_prepared_and_queued_meals_already_cover_need(self):
        r, lord, tenant, _ = fixture()
        tenant.inv_set(Goods.food, 0)
        tenant.inv_set(Goods.prepared_food, 2)
        tenant.emergency_food_units = 2
        self.assertEqual(feed_estate_residents(r, 4), 0)
        self.assertEqual(lord.inv_get(Goods.food), 20)

    def test_donor_keeps_own_meal_and_prioritizes_residents_nearest_starvation(self):
        r, lord, tenant, _ = fixture()
        lord.inv_set(Goods.food, 6)
        tenant.inv_set(Goods.food, 0)
        urgent = person(3, plot='home')
        urgent.energy_reserve_kcal = 0
        r.agents.append(urgent)
        self.assertEqual(feed_estate_residents(r, 4), 2)
        self.assertEqual(lord.inv_get(Goods.food), 4)
        self.assertEqual(urgent.inv_get(Goods.food), 2)
        self.assertEqual(tenant.inv_get(Goods.food), 0)

    def test_dead_owner_and_commons_do_not_provide_private_estate_relief(self):
        r, lord, tenant, p = fixture()
        tenant.inv_set(Goods.food, 0)
        lord.alive = False
        self.assertEqual(feed_estate_residents(r, 4), 0)
        lord.alive, p.tenure = True, TenureStatus.COMMONS
        self.assertEqual(feed_estate_residents(r, 5), 0)

    def test_transfers_and_harvest_tax_have_exact_replayable_inventory_legs(self):
        r, lord, tenant, _ = fixture(traced=True)
        harvest(r, tenant, 7, 8)
        tenant.inv_set(Goods.food, 0)
        feed_estate_residents(r, 7)
        for row in r._run_trace.rows:
            if row.get('formula_id') not in ('feudal_tribute.harvest_share_transfer.v2',
                                             'feudal_tribute.estate_relief.v1'):
                continue
            self.assertEqual(replay({**row, 'value_before': row['before']}), row['after'])
            contract = row['inputs']['transfer_contract']
            payer, payee = contract['payer_account'], contract['payee_account']
            self.assertEqual(payer['balance_before']-payer['balance_after'], contract['amount'])
            self.assertEqual(payee['balance_after']-payee['balance_before'], contract['amount'])

    def test_lifecycle_feeds_before_starvation_mortality_check(self):
        r, lord, tenant, _ = fixture()
        tenant.inv_set(Goods.food, 0)
        tenant.energy_reserve_kcal, tenant.hungry_steps = 0, 20
        context = LiveContext(recipes={}, goods=[Goods.food], governments=[], default_gov=None,
            hungry_log={Goods.food: []}, dead_pop=[], deadstarve_pop=[0], production_log={},
            starve_limit=1, profession={}, max_career_switches=0, p_birth=0, birth_gap=1,
            bank=None, most_demand=None, source_region=r)
        seen = []
        def death(_ctx, _turn, actor, _agents):
            seen.append(actor.id)
            self.assertEqual(actor.calorie_deficit_kcal, 0)
            return False
        with (patch('econsim_live.compute_bottleneck_weights', return_value=[]),
              patch('econsim_live.consume_goods', side_effect=lambda _c, _a, f, w, n: (f, w, n)),
              patch('econsim_live.handle_career_switching', side_effect=lambda *args: (0, args[-1])),
              patch('econsim_live.handle_job_seeking'),
              patch('econsim_live.handle_reproduction', return_value=0),
              patch('econsim_live.handle_death', side_effect=death),
              patch('econsim_live.build_employer_cache', return_value={}),
              patch('econsim_live.random.shuffle')):
            Live(4, r.agents, context)
        self.assertIn(tenant.id, seen)


if __name__ == '__main__':
    unittest.main()
