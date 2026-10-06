# Egypt chapter two: sovereignty and occupation audit

Run `venv/bin/python audit_egypt_chapter_two.py output.json` to replay seven seeded decision paths. The JSON records every turn's ruler and coalition, army loyalty, Caisse claim, treasuries, fleet and fort state, civilian injuries, territorial control, resistance, occupied receipts, garrison supply, and British replies to withdrawal offers. These are playthrough examples, not historical amounts or guarantees across all seeds.

| Path | Decisive Egyptian choices | Ending | Caisse claim | Civilian injuries | Occupied receipts / British garrison supply |
| --- | --- | --- | ---: | ---: | ---: |
| Historical occupation | Accept Tawfiq, back ‘Urabi, default, contest customs, defend Alexandria, evacuate port and Cairo | British occupation | 600 | 2 | 173.4 / 33.0 |
| Organized resistance | Same crisis, then boycott, general strike, insurgency, and offer withdrawal terms | Nationalist victory | 600 | 3 | 22.3 / 14.8 |
| Premature offer | Offer withdrawal before organizing resistance | British occupation | 600 | 2 | 165.1 / 33.0 |
| Canal defense | Default and contest the claim, then defend the canal route | Successful repudiation | 600 | 2 | 0 / 0 |
| Ottoman mediation | Default and contest the claim, then seek mediation | Sovereign compromise | 0 | 0 | 0 / 0 |
| Disarmament | Default and contest the claim, then disarm coastal batteries | Coerced disarmament | 600 | 0 | 0 / 0 |
| Accept foreign control | Default and contest the claim, then accept creditor collection | Imposed financial control | 540 | 0 | 0 / 0 |

The occupation is a fiscal contest. Britain collects from actual Egyptian tax and tariff receipts, at most 20 units per turn, while paying for the land garrison. Boycott and strikes reduce collection; armed resistance raises the civilian cost. In this run, Britain rejected the early 30-unit withdrawal proposal at 22% resistance, before any occupied receipt had been collected. It accepted the later proposal at 87% resistance after boycott, strike, and insurgency. Rejection transferred no cash. Acceptance transferred 30 units and ended territorial control, while the 600-unit claim remained outstanding. The nationalist-victory ending therefore means the expedition withdrew and the nationalist cabinet retained authority; it does not mean the debt disappeared.

The chapter begins when succession, officer mobilization, or naval escalation changes the central question from subsistence and payment to Egyptian authority. Its briefing shows the live political, debt, diplomatic, and military state. Guided mode places authority, foreign demands, and access or occupation ahead of the food card, while preserving every available action. The base campaign ends after turn 20; a chapter that starts late receives at least eight turns, and a newly occupied site receives at least five. The debrief presents civilian and battle injuries, occupied receipts, and supply costs alongside hunger, tax, debt, and land-access statistics.

## Limits visible in this audit

- The seven routes exercise distinct choices but all use one seeded world. They establish reachability and causal contrast, not broad balance across terrain or population seeds.
- The historical route reproduces an order of political, naval, and territorial pressures. Its twenty turns compress years and its treasury units are game units.
- Britain remains solvent even when occupation collection is costly. Sustained resistance crosses the withdrawal threshold in this path; boycotts and strikes also reduce collectible receipts. British insolvency does not drive this result.
- The negotiated withdrawal leaves the Caisse claim unresolved. Future play beyond this campaign would need a postwar debt and constitutional settlement to test whether sovereignty lasts.
