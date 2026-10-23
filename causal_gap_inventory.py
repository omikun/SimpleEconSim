"""Discover financial writes and declared metrics without importing simulation state.

Discovery is a review queue, not proof that a candidate touches public money.
The committed baseline detects new/changed writes; explicit reviews and runtime
fixtures establish coverage. Generated JSON/Markdown reports are reproducible.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / 'planning/coverage/financial_write_baseline.json'
REVIEWS = ROOT / 'planning/coverage/reviewed_financial_writers.json'
BALANCES = {'cash', 'capital', 'total_deposits', 'total_liabilities', 'deposits'}


def target_kind(node):
    if (isinstance(node, ast.Attribute) and node.attr in BALANCES
            and not isinstance(node.ctx, ast.Load)):
        return node.attr
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
        if node.value.attr == 'deposits':
            return 'deposit_account'
    return None


class Discover(ast.NodeVisitor):
    def __init__(self, path):
        self.path, self.scope, self.rows, self.counts = path, [], [], Counter()
        self.histories = []
        self.guards = []
        self.source_probe_literals = set()

    def visit_Dict(self, node):
        for key, value in zip(node.keys, node.values):
            if (isinstance(key, ast.Constant) and key.value == 'source_writer'
                    and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                self.source_probe_literals.add(value.value)
        self.generic_visit(node)

    def visit_If(self, node):
        self.visit(node.test)
        for label, body in (('then', node.body), ('else', node.orelse)):
            self.guards.append(f'if {ast.unparse(node.test)}:{label}')
            for statement in body:
                self.visit(statement)
            self.guards.pop()

    def visit_Attribute(self, node):
        if node.attr.endswith(('_log', '_history')):
            self.histories.append({'field': node.attr, 'path': self.path,
                                   'function': '.'.join(self.scope) or '<module>',
                                   'line': node.lineno, 'usage': type(node.ctx).__name__})
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def write(self, node, targets):
        expanded = []
        for target in targets:
            expanded.extend(ast.walk(target) if isinstance(target, (ast.Tuple, ast.List)) else [target])
        for target in expanded:
            kind = target_kind(target)
            if kind is None:
                continue
            function = '.'.join(self.scope) or '<module>'
            fingerprint = hashlib.sha256(json.dumps(
                [ast.dump(node, include_attributes=False), self.guards]).encode()).hexdigest()[:16]
            prefix = f'{self.path}:{function}:{fingerprint}'
            self.counts[prefix] += 1
            self.rows.append({'id': f'{prefix}:{self.counts[prefix]}', 'path': self.path,
                              'function': function, 'line': node.lineno,
                              'target': ast.unparse(target), 'balance_candidate': kind, 'guard_context': list(self.guards),
                              'statement': ast.unparse(node), 'review': 'needs_review',
                              'writer': 'unknown', 'formula': 'unknown', 'links': 'unknown',
                              'closure': 'unknown', 'ui': 'unknown',
                              'missing_work': 'Classify actual account owner, lifecycle and active caller; attach fixture evidence.'})

    def visit_Assign(self, node):
        self.write(node, node.targets)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.write(node, [node.target])
        self.generic_visit(node)

    visit_AugAssign = visit_AnnAssign

    def visit_Delete(self, node):
        self.write(node, node.targets)
        self.generic_visit(node)

    def visit_Call(self, node):
        # Bulk dictionary mutations are review candidates too.
        if (isinstance(node.func, ast.Attribute) and node.func.attr in ('clear', 'pop', 'update', 'setdefault')
                and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'deposits'):
            self.write(node, [ast.Subscript(value=node.func.value, slice=ast.Constant('<bulk>'))])
        self.generic_visit(node)


def discover_source(source, path):
    visitor = Discover(path)
    visitor.visit(ast.parse(source, filename=path))
    return visitor.rows


def production_paths(root):
    files = subprocess.run(['rg', '--files', '-g', '*.py'], cwd=root, check=True,
                           capture_output=True, text=True).stdout.splitlines()
    excluded = {'venv', '.venv', 'tmp', 'scratch', 'node_modules', '.git', '__pycache__'}
    return sorted(path for path in files if not (excluded & set(Path(path).parts))
                  and not Path(path).name.startswith(('test_', 'audit_', 'benchmark_', 'probe_', 'causal_gap_inventory')))


def inventory(root=ROOT):
    rows, histories = [], []
    for path in production_paths(root):
        visitor = Discover(path)
        visitor.visit(ast.parse((root / path).read_text(), filename=path))
        for row in visitor.rows:
            row['source_probe'] = ('writer_literal_present' if row['id'] in visitor.source_probe_literals
                                   else 'not_detected_by_literal_scan')
        rows.extend(visitor.rows)
        histories.extend(visitor.histories)
    reviews = json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {'writers': {}}
    for row in rows:
        review = reviews['writers'].get(row['id'])
        if review:
            row.update(review)
    # Read catalog declarations as data. This does not construct a world or draw RNG.
    import metric_catalog
    metrics = [{'metric_id': ident, 'scope': value[0], 'unit': value[1], 'definition': value[2],
                'writer': 'declared' if ident in metric_catalog.TRACE_INSTRUMENTED else 'unmapped',
                'formula': 'not_verified_by_inventory', 'links': 'not_verified_by_inventory',
                'closure': 'not_verified_by_inventory', 'ui': 'requires_binding_inventory'}
               for ident, value in sorted(metric_catalog.METRICS.items())]
    grouped_histories = {}
    for row in histories:
        grouped_histories.setdefault(row['field'], []).append(row)
    history_rows = [
        {'field': field, 'references': references,
         'declared_metric': metric_catalog.LEGACY_HISTORY_TO_METRIC.get(field),
         'journal_metrics': list(metric_catalog.EVENT_JOURNAL_TO_METRICS.get(field, ())),
         'status': 'requires_active_path_and_sampling_review'}
        for field, references in sorted(grouped_histories.items())]
    # Literal references locate candidate UI bindings; they do not verify a
    # plotted transform, turn, membership or dynamic binding.
    paths = subprocess.run(['rg', '--files', '-g', '*.py', '-g', '*.js'], cwd=root,
                           check=True, capture_output=True, text=True).stdout.splitlines()
    ui_references = {}
    pattern = re.compile(r'''(['"])([a-z_]+(?:\.[a-z_]+)+)\1''')
    for path in sorted(paths):
        if not (path.startswith(('client/', 'sim_server/', 'web_client/')) or Path(path).name.startswith('worldview')):
            continue
        for match in pattern.finditer((root / path).read_text()):
            metric = match.group(2)
            if metric in metric_catalog.METRICS:
                ui_references.setdefault(metric, set()).add(path)
    for metric in metrics:
        metric['ui_reference_candidates'] = sorted(ui_references.get(metric['metric_id'], ()))
    return {'schema_version': 1, 'writers': rows, 'metrics': metrics, 'histories': history_rows,
            'limits': ['Candidate discovery is not a public-account or active-path classification.',
                       'Reflection, aliases to dictionaries and mutation through external helpers require source review.',
                       'A source_writer literal locates a probe candidate; it does not prove execution, scope or transfer closure.',
                       'Metric declarations are not UI bindings or runtime provenance evidence.'],
            'scenarios': {name: {'status': 'inventory_incomplete',
                                'unreviewed_candidates': sum(row['review'] == 'needs_review' for row in rows),
                                'required_work': 'Classify active caller paths and attach scenario fixtures; no coverage percentage.'}
                          for name in ('default', 'labor_frontier_rivalry', 'supply_rivalry', 'egypt_1877')}}


def render(data):
    counts = Counter(row['review'] for row in data['writers'])
    lines = ['# Financial write and metric gap register', '',
             'Generated by `causal_gap_inventory.py`. Discovery and declared metrics are not verified coverage.', '',
             f"- Financial write candidates: {len(data['writers'])}",
             f"- Reviewed: {sum(value for key, value in counts.items() if key != 'needs_review')}",
             f"- Needs review: {counts['needs_review']}",
             f"- Writer IDs present in probe literals: {sum(row['source_probe'] == 'writer_literal_present' for row in data['writers'])}",
             f"- Declared metrics: {len(data['metrics'])}",
             f"- History fields requiring semantic review: {len(data['histories'])}", '',
             '## Scenario inventory status', '']
    lines.extend(f'- {name}: {row["status"]}' for name, row in data['scenarios'].items())
    lines.extend(['', '## Reviewed writers', '', '| File / function | Target | Writer | Closure evidence |',
                  '|---|---|---|---|'])
    for row in data['writers']:
        if row['review'] != 'needs_review':
            lines.append(f"| {row['path']} / {row['function']} | {row['target']} | {row['writer']} | {row['closure']} |")
    lines.extend(['', '## Limits', '', *['- ' + item for item in data['limits']]])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--markdown', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = inventory()
    if args.check:
        expected = json.loads(BASELINE.read_text())['writer_ids']
        actual = sorted(row['id'] for row in data['writers'])
        if expected != actual:
            raise SystemExit('Financial writes changed: review additions/removals and update the baseline explicitly.')
    if args.json:
        args.json.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    if args.markdown:
        args.markdown.write_text(render(data))
    if not args.json and not args.markdown:
        print(render(data), end='')


if __name__ == '__main__':
    main()
