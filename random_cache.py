"""
Cached randomness: pre-generates random floats to avoid per-call Python overhead.

Replace `random.random()` / `random.choice()` in hot loops with rand.random()
and rand.choice() for ~3-5x speedup on the random calls themselves.
"""

import random


class RandomCache:
    """Pre-allocated random number cache.

    Call reset(n) once per turn to refill.  Use random() to consume values
    sequentially.  When the cache is exhausted, falls back to random.random().
    """

    def __init__(self, seed=42, capacity=200000):
        self._seed = seed
        self._capacity = capacity
        self._buf = [0.0] * capacity
        self._idx = capacity  # force refill on first use
        random.seed(seed)

    def _refill(self):
        """Refill the buffer with fresh random floats."""
        b = self._buf
        for i in range(self._capacity):
            b[i] = random.random()
        self._idx = 0

    def _ensure(self, n=1):
        """Ensure at least *n* values are available."""
        if self._idx + n > self._capacity:
            self._refill()

    # ---- Public API ----

    def reset(self):
        """Refill buffer at the start of a new turn."""
        self._refill()

    def random(self):
        """Return the next cached random float in [0.0, 1.0)."""
        self._ensure(1)
        v = self._buf[self._idx]
        self._idx += 1
        return v

    def random_n(self, n):
        """Return a list of *n* cached random floats."""
        if n <= 0:
            return []
        # For large n, slice directly from buffer
        result = []
        while n > 0:
            self._ensure(1)
            avail = self._capacity - self._idx
            take = min(n, avail)
            result.extend(self._buf[self._idx:self._idx + take])
            self._idx += take
            n -= take
        return result

    def choice(self, seq):
        """random.choice() equivalent using cached random."""
        if not seq:
            raise IndexError('Cannot choose from an empty sequence')
        return seq[int(self.random() * len(seq))]

    def randint(self, a, b):
        """random.randint(a, b) equivalent (inclusive)."""
        return a + int(self.random() * (b - a + 1))


# Global singleton — import and use in hot paths
rand = RandomCache(seed=42)