# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-optimized core functions for Region.
The hottest pure-computation loops are extracted here.
"""

from goods import Goods


# Inventory helpers (list-based, goods indexed by value)
# These are thin wrappers since inventory is a Python list on the Agent object.

def produce_corporation_slots(active_slots, chance, rand_vals):
    """Count successful production slots from cached random values.
    
    Pure Cython: avoids Python for-loop and random.random() overhead.
    
    Args:
        active_slots: int, number of production slots
        chance: float, probability per slot
        rand_vals: list of random floats (pre-fetched)
    Returns:
        int: number of successful slots
    """
    cdef int i
    cdef int count = 0
    cdef double c = chance
    cdef int n = active_slots
    for i in range(n):
        if rand_vals[i] < c:
            count += 1
    return count


def produce_independent_check(chance, rand_val):
    """Check if independent production succeeds.
    
    Args:
        chance: float
        rand_val: float (single random value)
    Returns:
        bool (as int: 0 or 1)
    """
    return 1 if rand_val < chance else 0


def check_random(rand_val, threshold):
    """Generic random check: returns 1 if rand_val < threshold, else 0."""
    return 1 if rand_val < threshold else 0