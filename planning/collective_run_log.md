# Reading a corporation conflict run

The same bargaining rules apply to every corporation. For a seeded 20-turn labor frontier run:

```sh
MPLCONFIGDIR=/private/tmp/regnum-mpl venv/bin/python collective_report.py --scenario labor-frontier-rivalry --seed 612 --turns 20 --output /private/tmp/collective_run_612.jsonl
```

In the web client, open a territory’s **Citizens → Labor** panel to see organizations, demands, recent events, and **Download current run log**. The download reflects the current live world, including any player decisions. A saved JSON Lines file has one `run` header with seed, scenario, final turn, and event count, followed by one event per line.

Each collective row has a stable event ID, turn, territory, corporation ID, strike ID if relevant, message, and `facts`. `organization_check` records employee pressure and why no vote occurred; it stays in the full log so routine checks do not bury important events in the panel. `strike_vote` and `participation` distinguish assent from labor actually withheld. `production_observed` records the firm's own output inventory change before trade. `needs_observed` names participants who met or missed food needs. `support_transfer` and `public_support_transfer` name the source and recipients of actual existing assets.

`owner_decision` includes cash on hand, proposed wage, payroll requirement, and an estimated sales exposure. That estimate is a **forecast**, not a charged loss. `agreement_signed` records promised cash pay, hours, payer, and review date. `payroll_observed` measures cash reaching each worker after actual payroll. `payroll_breach` records any shortfall, including a later switch to company scrip. `settlement_review` scores delivered purchasing power and hours once at the review deadline. The organization and confidence updates use that delivered result, never the signed promise alone.

The report also includes scenario paid market sales, paid cotton purchases, labor offers, and relevant national labor-policy records. Within a territory, collective event IDs preserve their actual append order. Rows from different subsystems have an approximate phase order for reading, because the older ledgers have no global event clock; use their source and turn before claiming a precise cross-system sequence. The direct event evidence supports observed changes, not a counterfactual claim about sales that would otherwise have occurred.

Political incidents are separate `authority_incident` rows. They name affected residents, the responsible authority, event-specific breach/repression/reform strengths, and before/after independence preference where a colonial authority is explicit. A private company's wage bargain alone cannot change the independence preference. The displayed mobilization index measures a deduplicated coalition’s agenda strength and is not a probability or an automatic sovereignty change.
