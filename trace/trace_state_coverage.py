"""Bounded checked-state groups with lazily resolved historical sample IDs.

Cells are facts about an exact turn/epoch, not inferred carry-forward. Each
group is self-contained and at most 512 cells / a 512 KiB capture budget.
"""
import math
from trace_packing import (PreparedEvent, freeze, expand_rule, COVERAGE_RULE, BASELINE_RULE,
                           PRICE_IDLE_RULE, GINI_ZERO_RULE, GINI_RETAIN_RULE,
                           DISEASE_EMPTY_RULE, TAX_EMPTY_RULE)

MAX_CELLS = 512
MAX_BYTES = 512 * 1024
RULE_KINDS = {COVERAGE_RULE:'metric_snapshot', BASELINE_RULE:'metric_snapshot', PRICE_IDLE_RULE:'price_bridge',
              GINI_ZERO_RULE:'gini_series_calculation', GINI_RETAIN_RULE:'gini_series_calculation',
              DISEASE_EMPTY_RULE:'closing_active_disease_census', TAX_EMPTY_RULE:'tax_revenue_distribution_calculation'}


def identity(context):
    return context['run_id'] + (':' + context['branch_id'] if context['branch_id'] != 'main' else '')


def expand_cell(context, cell):
    sequence, rule, metric, unit, subject, value, detail = cell
    row = {**context, 'sequence':sequence, 'event_id':identity(context)+':'+str(sequence),
           'subject':subject, 'metric_id':metric, 'value_after':value}
    if unit is not None: row['unit'] = unit
    if rule in (COVERAGE_RULE,BASELINE_RULE): row['@source'] = detail
    elif rule in (GINI_ZERO_RULE, GINI_RETAIN_RULE):
        if detail is not None: row['cause_event_ids'] = detail
    elif rule == TAX_EMPTY_RULE:
        row['@tax_turn'], row['@tax_reason'], causes = detail
        if causes is not None: row['cause_event_ids'] = causes
    expand_rule(row, rule)
    return row


class CoverageSample(PreparedEvent):
    """Only the bounded recent-view queue keeps these lightweight handles."""
    def __init__(self, context, cell):
        self.context, self.cell = context, cell

    def expand(self):
        return expand_cell(self.context, freeze(self.cell, [0]))


class CoverageGroup(dict):
    """Private captured cells need no second freeze before entering the writer."""
    def __init__(self, context, subject, cells, size):
        self.size = size
        super().__init__(context, record_class='coverage', kind='state_coverage',
            event_id=identity(context)+':coverage:'+str(cells[-1][0]), sequence=cells[-1][0], subject=subject,
            inputs={'coverage_version':1, 'identity_prefix':identity(context),
                    'sequence_min':cells[0][0], 'sequence_max':cells[-1][0], 'cells':cells})


class CoverageBuffer:
    def __init__(self, context, subject):
        self.context = context
        self.subject = {key:subject[key] for key in ('type','id')}
        self.cells = []; self.size = 512

    def accepts(self, context, subject, size):
        return (self.context == context and all(type(subject.get(key)) is type(value)
                and subject.get(key) == value for key,value in self.subject.items())
                and len(self.cells) < MAX_CELLS and self.size+size <= MAX_BYTES)

    def group(self):
        return CoverageGroup(self.context, self.subject, self.cells, self.size)


def capture_cell(rule, fields):
    if rule not in RULE_KINDS: raise ValueError('unsupported state coverage rule')
    if rule in (COVERAGE_RULE,BASELINE_RULE): detail = fields['@source']
    elif rule in (GINI_ZERO_RULE, GINI_RETAIN_RULE): detail = fields.get('cause_event_ids')
    elif rule == TAX_EMPTY_RULE: detail = [fields['@tax_turn'], fields['@tax_reason'], fields.get('cause_event_ids')]
    else: detail = None
    budget = [0]
    cell = freeze([fields['sequence'],rule,fields['metric_id'],fields.get('unit'),
                   fields['subject'],fields['value_after'],detail], budget)
    if type(cell[0]) is not int or cell[0] < 0: raise ValueError('invalid coverage sequence')
    return cell, budget[0]


def context_of(group):
    return {key:group[key] for key in ('schema_version','run_id','branch_id','turn','epoch','phase')}


def validate_group(group):
    inputs = group['inputs']; cells = inputs['cells']
    if (inputs.get('coverage_version') != 1 or not isinstance(cells,list)
            or not 1 <= len(cells) <= MAX_CELLS or inputs['identity_prefix'] != identity(group)
            or group['record_class'] != 'coverage' or not isinstance(group.get('subject'),dict)
            or set(group['subject']) != {'type','id'}):
        raise ValueError('invalid state coverage group')
    context_of(group)  # Require the complete self-contained historical context.
    last = -1
    for cell in cells:
        if (not isinstance(cell,list) or len(cell) != 7 or type(cell[0]) is not int or cell[0] <= last
                or cell[1] not in RULE_KINDS or not isinstance(cell[2],str)
                or not isinstance(cell[4],dict)
                or any(type(cell[4].get(key)) is not type(value) or cell[4].get(key) != value
                       for key,value in group['subject'].items())):
            raise ValueError('invalid checked state cell')
        # Validate cells without allocating virtual event dictionaries. Index
        # building must remain proportional to stored groups, not expanded rows.
        rule, value, detail = cell[1], cell[5], cell[6]
        if type(value) not in (str,int,float,bool) or (type(value) is float and not math.isfinite(value)):
            raise ValueError('invalid checked state value')
        if rule in (COVERAGE_RULE,BASELINE_RULE):
            if detail is not None and type(detail) is not str: raise ValueError('invalid coverage source')
        elif rule in (GINI_ZERO_RULE,GINI_RETAIN_RULE):
            if (type(value) not in (int,float) or (rule == GINI_ZERO_RULE and value != 0)
                    or 'good' not in cell[4] or (detail is not None
                    and (not isinstance(detail,list) or not all(type(item) is str for item in detail)))):
                raise ValueError('invalid checked Gini sample')
        elif rule == PRICE_IDLE_RULE:
            if type(value) not in (int,float) or detail is not None: raise ValueError('invalid no-write price check')
        elif rule == DISEASE_EMPTY_RULE:
            if type(value) is not int or value != 0 or detail is not None or 'disease' not in cell[4]:
                raise ValueError('invalid empty disease check')
        elif rule == TAX_EMPTY_RULE:
            if (type(value) is not float or value != 0.0 or not isinstance(detail,list) or len(detail) != 3
                    or 'tax_tier' not in cell[4] or (detail[2] is not None
                    and (not isinstance(detail[2],list) or not all(type(item) is str for item in detail[2])))):
                raise ValueError('invalid empty tax check')
        last = cell[0]
    if (inputs['sequence_min'] != cells[0][0] or inputs['sequence_max'] != last
            or group['sequence'] != last or group['event_id'] != identity(group)+':coverage:'+str(last)):
        raise ValueError('invalid coverage sequence range')
    return cells


def expanded_count(row):
    return len(row['inputs']['cells']) if row.get('kind') == 'state_coverage' else 1
