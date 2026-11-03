# Seasonal tribute and estate subsistence

Feudal in-kind tribute is collected once per ten-turn agricultural cycle, at
late-harvest phase 7: turns 7, 17, 27, and so on. Other government taxes and cash
rents retain their existing schedules.

Completed production receipts accrue to the estate where the producer lives.
The collection base includes only new grain, wood, and furniture production
since the previous collection. Existing reserves, purchases, gifts, relief,
inheritances, and commons foraging do not create new harvest assessments.
Previously assessed output is not reassessed in later cycles. Repeating a turn
cannot accrue receipts or collect the same assessment twice.

The existing tribute rate determines the assessed share. Collection is limited
by available goods, with the household's existing food reserve and dependent
needs protected. An unaffordable share is recorded as unpaid and closed without
creating arrears; it does not become a future tax on stored reserves. Existing
resistance and enforcement rules still apply on collection turns.

Tax attribution and private relief use actual estate residence rather than a
proportional slice of the shuffled population. Explicit plot assignments take
priority, followed by tenant lists and local family residence. Newborns inherit
their parent's plot assignment, so residence persists if a parent later dies.
An explicit move to another plot overrides the family link. Corporations,
traders, public agents, and other estates' residents are not counted as peasants
on that estate. Commons land has no private estate owner collecting tribute or
providing this relief.

Every turn, after public aid and charity but before meals and starvation checks,
estate owners supply grain to their own residents who lack a basic meal. Support
covers ordinary calorie requirements, including age-specific needs, rather than
wealth-related extra appetite. Existing prepared meals and queued public food
reduce the gap. Owners keep a basic meal for themselves and their dependent
children. If grain is limited, residents with the least energy reserve relative
to their needs receive priority.

Relief is a direct transfer of owned grain, without payment, debt, or creation of
food. Ownership of several plots does not duplicate a resident's entitlement.
An owner without available grain cannot guarantee subsistence. Enclosed and
leasehold residents remain eligible for help from their actual private owner;
the in-kind harvest tax itself applies only to feudal tenure.

Trace records capture both inventory balances for tax and relief, the new
harvest base, household protection, and unpaid assessments. The replay engine
supports the new formulas and retains support for historical stock-tax traces.
Accrued harvests and per-turn guards persist through save and restore.

Tests: `venv/bin/python -m unittest tests.test_feudal_subsistence tests.test_tribute_trace -q`.
The unchanged abundance runner provides matched 60-turn comparisons. The
read-only `scripts/audit_feudal_subsistence.py` verifies collection dates and
landlord feeding against an unobserved reference run.
