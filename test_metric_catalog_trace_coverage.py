"""Keep literal production trace metrics registered and marked as instrumented."""

import ast
from pathlib import Path
import subprocess
import unittest

from metric_catalog import (LEGACY_HISTORY_TO_METRIC, METRICS,
                            TRACE_INSTRUMENTED)


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


if __name__ == '__main__':
    unittest.main()
