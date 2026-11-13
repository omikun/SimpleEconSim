"""Pure local asking terms; tracing remains in the market owner."""


def ask_terms(reference, stock, maximum, hungry, lower, upper):
    scarcity = 1.10 - .30 * max(0.0, min(1.0, stock / max(1, maximum)))
    urgency = max(0.0, 1.0 - .12 * hungry)
    multiplier = max(lower, min(upper, scarcity * urgency))
    return reference * multiplier, scarcity, urgency, multiplier
