"""Keep literal production trace metrics registered and marked as instrumented."""

import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest

from metric_catalog import (LEGACY_HISTORY_TO_METRIC, METRICS,
                            TRACE_INSTRUMENTED, inventory_region_histories)


class MetricCatalogTraceCoverageTests(unittest.TestCase):
    def test_literal_production_trace_metrics_have_catalog_and_coverage(self):
        root = Path(__file__).resolve().parent
        ignored_dirs = {'.git', 'venv', '__pycache__', 'node_modules',
                        'dist', 'build', 'epub_build'}
        emitted_metrics = set()

        tracked = subprocess.check_output(
            ['git', '-C', str(root), 'ls-files', '-z', '--', '*.py'])
        for item in tracked.decode('utf-8').split('\0'):
            if not item:
                continue
            relative = Path(item)
            source = root / relative
            if (relative.name.startswith('test_')
                    or any(part in ignored_dirs for part in relative.parts)):
                continue
            tree = ast.parse(source.read_text(encoding='utf-8'),
                             filename=str(relative))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    value = keyword.value
                    if (keyword.arg == 'metric_id' and isinstance(value, ast.Constant)
                            and isinstance(value.value, str)):
                        emitted_metrics.add(value.value)

        self.assertEqual(sorted(emitted_metrics - set(METRICS)), [])
        self.assertEqual(sorted(emitted_metrics - TRACE_INSTRUMENTED), [])
        self.assertEqual(sorted(TRACE_INSTRUMENTED - set(METRICS)), [])

    def test_surplus_history_and_firm_metric_are_explained(self):
        self.assertEqual(LEGACY_HISTORY_TO_METRIC['surplus_value_log'],
                         'labor.surplus_value')
        self.assertIn('labor.surplus_value', TRACE_INSTRUMENTED)
        self.assertIn('labor.firm_surplus_value', TRACE_INSTRUMENTED)
        self.assertIn('labor.surplus_value', METRICS)
        self.assertIn('labor.firm_surplus_value', METRICS)

    def test_existing_histories_with_live_trace_sources_are_mapped(self):
        expected = {
            'bank_cash_log': 'finance.bank_equity',
            'total_cash_log': 'finance.total_cash',
            'demand_ratio_log': 'goods.demand_ratio',
            'market_demand_ratio_chart_log': 'goods.demand_ratio',
            'population_log': 'people.profession_population',
            'collective_log': 'labor.collective_action',
            'grievance_sources_log': 'politics.grievance',
            'trade_flow_log': 'trade.net_value',
            'workhouse_inmates_log': 'labor.workhouse_inmates',
            'pasture_fraction_log': 'land.pasture_fraction',
            'population_change_rate_log': 'people.population_change_rate',
            'trader_cash_log': 'trade.trader_cash',
            'pipeline_depth_log': 'trade.pipeline_depth',
            'borrow_log': 'finance.fiscal_gap',
            'tax_rate_log': 'finance.tax_rate',
            'income_log': 'finance.government_income',
            'tax_distribution_log': 'finance.tax_distribution',
        }
        for field, metric_id in expected.items():
            with self.subTest(field=field):
                self.assertEqual(LEGACY_HISTORY_TO_METRIC[field], metric_id)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)

    def test_inventory_includes_government_history_owners(self):
        region = SimpleNamespace(gov=SimpleNamespace(
            borrow_log=[], tax_rate_log=[], income_log=[]))
        fields = {row['field']: row for row in inventory_region_histories(region)}
        for field in ('gov.borrow_log', 'gov.tax_rate_log', 'gov.income_log'):
            self.assertEqual(fields[field]['coverage'], 'instrumented')

    def test_workhouse_metrics_have_replayable_trace_coverage(self):
        for metric_id in ('labor.workhouse_inmates',
                          'labor.forced_labor_hours'):
            with self.subTest(metric_id=metric_id):
                self.assertIn(metric_id, METRICS)
                self.assertIn(metric_id, TRACE_INSTRUMENTED)


if __name__ == '__main__':
    unittest.main()
