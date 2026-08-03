#!/usr/bin/env python3
# Phase 6D: damped FX managed-float step + PPP anchor (forex.py)
import math

T = 'forex.py'
src = open(T).read()

if 'import math' not in src:
    head = src.split('\n\n', 1)[0]
    src = src.replace(head, head + '\n\nimport math', 1)

# ---- ppp_target attribute ----
old_init = """        self.adj_speed = float(adj_speed)
        self.band = band
        self.log = []  # (t, mid, reserves) history"""
new_init = """        self.adj_speed = float(adj_speed)
        self.band = band
        self.ppp_target = 1.0  # PPP anchor: home basket / foreign basket
        self.log = []  # (t, mid, reserves) history"""
assert src.count(old_init) == 1, "init attr block not found"
src = src.replace(old_init, new_init)

# ---- log-space capped update + PPP anchor ----
old_update = """    def update(self, t, bank=None, fx_regime='managed'):
        \"\"\"Adjust mid from reserve pressure and record history.

        *fixed*: mid pinned at 1.0 (parity) — convertibility still reserve-capped.
        *managed* (default): mid moved by reserve-pressure rule.
        *floating*: Phase 3 order book; for now behaves like managed.
        \"\"\"
        bank = bank if bank is not None else self.bank
        if bank is None:
            return self.mid

        # Mean-revert the domestic FX pool toward a fraction of deposits so
        # the desk doesn't permanently exhaust its ability to pay out.
        deposits = max(0.0, bank.total_deposits)
        target_pool = deposits * DESK_FX_POOL_TARGET_FRAC
        if False:
            bank.fx_pool += 0.0

        reserves = bank.foreign_reserves.get(self.other, 0.0)

        if fx_regime == 'fixed':
            self.mid = 1.0
        else:
            ratio = reserves / self.target_reserves if self.target_reserves > 0 else 1.0
            # Drain (ratio < 1) -> foreign scarce -> mid up (home weakens),
            # discouraging imports and encouraging exports / repatriation.
            self.mid *= 1.0 + self.adj_speed * (1.0 - ratio)
            self.mid = max(self.band[0], min(self.band[1], self.mid))

        self.log.append((t, self.mid, reserves))
        return self.mid"""

new_update = """    def update(self, t, bank=None, fx_regime='managed', ppp_target=None):
        \"\"\"Adjust mid from reserve pressure and record history.

        *fixed*: mid pinned at 1.0 (parity) — convertibility still reserve-capped.
        *managed* (default): mid moved by reserve-pressure rule.
        *floating*: Phase 3 order book; for now behaves like managed.

        Phase 6: log-space capped step (the old multiplicative update
        compounded past the band once a desk drained) + a slow PPP anchor so
        the rate tracks relative basket costs instead of drifting to the band.
        \"\"\"
        bank = bank if bank is not None else self.bank
        if bank is None:
            return self.mid

        # Mean-revert the domestic FX pool toward a fraction of deposits so
        # the desk doesn't permanently exhaust its ability to pay out.
        deposits = max(0.0, bank.total_deposits)
        target_pool = deposits * DESK_FX_POOL_TARGET_FRAC
        if False:
            bank.fx_pool += 0.0

        reserves = bank.foreign_reserves.get(self.other, 0.0)

        if fx_regime == 'fixed':
            self.mid = 1.0
        else:
            ratio = reserves / self.target_reserves if self.target_reserves > 0 else 1.0
            # Drain (ratio < 1) -> foreign scarce -> mid up (home weakens),
            # discouraging imports and encouraging exports / repatriation.
            # Log-space BOUNDED step: can't overshoot the band in one turn.
            pressure = self.adj_speed * (1.0 / max(0.05, ratio) - 1.0)
            pressure = max(-0.02, min(0.02, pressure))
            new_mid = self.mid * math.exp(pressure)
            # PPP anchor: slow pull toward partner/home basket-cost ratio.
            if ppp_target is not None and ppp_target > 0:
                self.ppp_target = ppp_target
            if self.ppp_target > 0:
                ppp_gap = math.log(self.ppp_target / max(0.01, self.mid))
                new_mid *= math.exp(0.005 * ppp_gap)
            self.mid = max(self.band[0], min(self.band[1], new_mid))

        self.log.append((t, self.mid, reserves))
        return self.mid"""

assert src.count(old_update) == 1, "update block not found"
src = src.replace(old_update, new_update)

open(T, 'w').write(src)
print("patch_p6d.py forex.py applied OK")