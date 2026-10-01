"""Distinguish source history, tuned quantities, and generated campaign events."""


def initialize(world):
    world['scenario_state']['historical_log'] = [
        {'turn': 1, 'kind': 'documented_history',
         'text': 'The 1876 Caisse assigned Egyptian revenues to debt service; the 1877 low Nile threatened the maize harvest.',
         'source': 'Egypt campaign references in gdd.md and EGYPT_HISTORICAL_MECHANICS_PLAN.md'},
        {'turn': 1, 'kind': 'tuned_game_value',
         'text': 'The 20-turn horizon, 200-unit claim, fleet sizes, costs, and thresholds compress 1876–82 into strategic decisions.',
         'source': 'situation_scenario_template.json'},
    ]


def record(world, text, *, historical_parallel=False):
    world['scenario_state'].setdefault('historical_log', []).append({
        'turn': int(world.get('turn', 0)),
        'kind': 'historical_parallel' if historical_parallel else 'plausible_alternative',
        'text': text,
    })
