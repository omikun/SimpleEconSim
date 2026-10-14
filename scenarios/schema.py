"""Schema definitions and validation for coc.scenario.v2 specifications."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


SUPPORTED_FORMATS = frozenset({'coc.scenario.v2', 'coc.situation.v1'})

RECOGNIZED_EFFECT_KEYS = frozenset({
    'confidence_delta',
    'autonomy_delta',
    'legitimacy_delta',
    'palace_authority_delta',
    'cabinet_authority_delta',
    'military_loyalty_delta',
    'nationalist_movement_delta',
    'treasury_cost',
    'transfer_cash',
    'distribute_food',
    'set_export_fraction',
    'set_tax_rate_delta',
    'set_unrest_delta',
    'debt_payment_multiplier',
    'debt_due_in',
    'debt_status',
    'debt_forgive_remainder',
    'levy_per_turn',
    'set_state_flag',
    'begin_coercion',
    'withdraw_coercion',
    'reinforce_batteries',
    'transition_cabinet',
    'execute_transformation_op',
    'grant_frontier_charter',
    'procure_captive_labor',
    'mandate_plantation_labor',
    'enforce_wage_cap',
    'issue_trade_bill',
    'discount_trade_bill',
    'incorporate_manufacturing_firm',
    'optimize_estate_portfolio',
    'repair_broken_machinery',
    'cotton_reserves_delta',
})


@dataclass
class ActionResponse:
    id: str
    label: str
    tooltip: str
    requires_cash: float = 0.0
    precondition: Optional[str] = None
    effects: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReactionSpec:
    headline: str
    body: str
    effects: Dict[str, Any] = field(default_factory=dict)
    responses: List[ActionResponse] = field(default_factory=list)


@dataclass
class BranchSpec:
    action_id: str
    delay_turns: int
    reaction: ReactionSpec
    condition: Optional[str] = None
    fallback_reaction: Optional[ReactionSpec] = None


@dataclass
class ActionSpec:
    id: str
    title: str
    category: str = 'general'
    precondition: Optional[str] = None
    turn_cost: int = 1
    requires_cash: float = 0.0
    effects: Dict[str, Any] = field(default_factory=dict)
    feedback: str = ''
    tooltip: str = ''


@dataclass
class PressureSpec:
    id: str
    title: str
    metric: str
    target: str = ''
    status_format: str = '{value}'


@dataclass
class OutcomeSpec:
    id: str
    title: str
    summary: str
    when: str
    descriptors: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScenarioSpec:
    format: str
    id: str
    meta: Dict[str, Any]
    roles: Dict[str, Any]
    modules: Dict[str, Any]
    pressures: List[PressureSpec]
    actions: List[ActionSpec]
    branches: Dict[str, BranchSpec]
    outcomes: List[OutcomeSpec]
    raw_data: Dict[str, Any] = field(default_factory=dict)


def validate_scenario_dict(data: dict) -> None:
    """Validate a parsed scenario dictionary against coc.scenario.v2 rules."""
    fmt = data.get('format')
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f'Unsupported scenario format "{fmt}". Expected one of: {sorted(SUPPORTED_FORMATS)}')

    scenario_id = data.get('id') or data.get('scenario_id')
    if not scenario_id:
        raise ValueError('Scenario must define an "id" or "scenario_id".')

    # Validate action reaction branches
    branches = data.get('branches', {})
    if not isinstance(branches, dict):
        raise ValueError('"branches" must be a dictionary.')

    response_ids: Set[str] = set()
    for action_id, branch in branches.items():
        if not isinstance(branch, dict):
            raise ValueError(f'Branch {action_id} must be a dictionary.')
        delay = branch.get('delay_turns', 1)
        if not isinstance(delay, int) or delay < 1:
            raise ValueError(f'{action_id}: delay_turns must be an integer >= 1.')

        reaction = branch.get('reaction', {})
        if not isinstance(reaction, dict) or not reaction.get('headline') or not reaction.get('body'):
            raise ValueError(f'{action_id}: reaction requires a headline and body.')

        responses = reaction.get('responses', [])
        for response in responses:
            rid = response.get('id')
            if not rid or rid in response_ids:
                raise ValueError(f'{action_id}: response id "{rid}" must be unique and non-empty.')
            if not response.get('label') or not response.get('tooltip'):
                raise ValueError(f'{action_id}: response "{rid}" requires label and tooltip.')
            req_cash = float(response.get('requires_cash', 0.0))
            treasury_cost = float(response.get('effects', {}).get('treasury_cost', 0.0))
            if req_cash < treasury_cost:
                raise ValueError(f'{action_id}: response "{rid}" requires_cash ({req_cash}) is less than treasury_cost ({treasury_cost}).')
            response_ids.add(rid)

        if 'fallback_reaction' in branch:
            fallback = branch['fallback_reaction']
            if not isinstance(fallback, dict) or not fallback.get('headline') or not fallback.get('body'):
                raise ValueError(f'{action_id}: fallback_reaction requires a headline and body.')
            fb_responses = fallback.get('responses', [])
            for response in fb_responses:
                rid = response.get('id')
                if not rid or rid in response_ids:
                    raise ValueError(f'{action_id}: response id "{rid}" in fallback_reaction must be unique and non-empty.')
                if not response.get('label') or not response.get('tooltip'):
                    raise ValueError(f'{action_id}: response "{rid}" in fallback_reaction requires label and tooltip.')
                req_cash = float(response.get('requires_cash', 0.0))
                treasury_cost = float(response.get('effects', {}).get('treasury_cost', 0.0))
                if req_cash < treasury_cost:
                    raise ValueError(f'{action_id}: response "{rid}" requires_cash ({req_cash}) is less than treasury_cost ({treasury_cost}).')
                response_ids.add(rid)


def load_scenario_spec(source: str | Path | dict) -> ScenarioSpec:
    """Load, validate, and instantiate a ScenarioSpec from a path or dictionary."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError(f'Expected str, Path, or dict, got {type(source)}')

    validate_scenario_dict(data)

    scenario_id = data.get('id') or data.get('scenario_id', 'unknown_scenario')
    fmt = data.get('format', 'coc.scenario.v2')
    meta = data.get('meta', {})
    if not meta and 'title' in data:
        meta = {
            'title': data.get('title', ''),
            'year': data.get('year', 0),
            'horizon_turns': data.get('horizon_turns', 20),
            'briefing': data.get('briefing', ''),
            'actors': data.get('actors', []),
        }

    roles = data.get('roles', {
        'actors': {'$player': {'type': 'player'}},
        'geography': {},
    })

    modules = data.get('modules', {})
    if not modules:
        # Migrate v1 modular rules into modules dict if present
        modules = {}
        if 'debt_rules' in data:
            modules['debt'] = data['debt_rules']
        if 'naval_crisis' in data:
            modules['naval_coercion'] = data['naval_crisis']
        if 'politics' in data:
            modules['politics'] = data['politics']

    pressures = []
    for p in data.get('pressures', []):
        pressures.append(PressureSpec(
            id=p.get('id', ''),
            title=p.get('title', ''),
            metric=p.get('metric', ''),
            target=p.get('target', ''),
            status_format=p.get('status_format', '{value}'),
        ))

    actions = []
    for a in data.get('actions', []):
        actions.append(ActionSpec(
            id=a.get('id', ''),
            title=a.get('title', ''),
            category=a.get('category', 'general'),
            precondition=a.get('precondition'),
            turn_cost=a.get('turn_cost', 1),
            requires_cash=float(a.get('requires_cash', 0.0)),
            effects=a.get('effects', {}),
            feedback=a.get('feedback', ''),
            tooltip=a.get('tooltip', ''),
        ))

    branches = {}
    for action_id, branch_data in data.get('branches', {}).items():
        reaction_data = branch_data.get('reaction', {})
        responses = [
            ActionResponse(
                id=r.get('id', ''),
                label=r.get('label', ''),
                tooltip=r.get('tooltip', ''),
                requires_cash=float(r.get('requires_cash', 0.0)),
                precondition=r.get('precondition'),
                effects=r.get('effects', {}),
            )
            for r in reaction_data.get('responses', [])
        ]
        reaction_spec = ReactionSpec(
            headline=reaction_data.get('headline', ''),
            body=reaction_data.get('body', ''),
            effects=reaction_data.get('effects', {}),
            responses=responses,
        )

        fallback_spec = None
        if 'fallback_reaction' in branch_data:
            fb_data = branch_data['fallback_reaction']
            fb_responses = [
                ActionResponse(
                    id=r.get('id', ''),
                    label=r.get('label', ''),
                    tooltip=r.get('tooltip', ''),
                    requires_cash=float(r.get('requires_cash', 0.0)),
                    precondition=r.get('precondition'),
                    effects=r.get('effects', {}),
                )
                for r in fb_data.get('responses', [])
            ]
            fallback_spec = ReactionSpec(
                headline=fb_data.get('headline', ''),
                body=fb_data.get('body', ''),
                effects=fb_data.get('effects', {}),
                responses=fb_responses,
            )

        branches[action_id] = BranchSpec(
            action_id=action_id,
            delay_turns=int(branch_data.get('delay_turns', 1)),
            reaction=reaction_spec,
            condition=branch_data.get('condition'),
            fallback_reaction=fallback_spec,
        )

    outcomes = []
    for o in data.get('outcomes', []):
        outcomes.append(OutcomeSpec(
            id=o.get('id', ''),
            title=o.get('title', o.get('id', '')),
            summary=o.get('summary', ''),
            when=o.get('when', ''),
            descriptors=o.get('descriptors', {}),
        ))

    return ScenarioSpec(
        format=fmt,
        id=scenario_id,
        meta=meta,
        roles=roles,
        modules=modules,
        pressures=pressures,
        actions=actions,
        branches=branches,
        outcomes=outcomes,
        raw_data=data,
    )
