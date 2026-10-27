# Output-based pollution, illness petitions and timber inputs

Implemented 2026-10-26. This follows the twenty-turn national-outcome and Japan causal reports. Those reports describe the previous rules; this report describes the changes and their evaluation.

## Behavior

- Logging and furniture production emit no generic industrial smog or industrial effluent. Per-output gameplay coefficients apply to nitrate/chemical supply, coal, ore, iron, ceramics, textiles and distilling. Fertilized crop runoff and pesticide residues scale with actual crop output. Household sewage scales with living people, excluding government and corporate entities.
- Regional ecology uses completed production from the current turn, excluding granary releases and resale. Firm true-cost accounts use the same emission factors and controls. Successful corvee plantation output outside the ordinary production pass is also included. Stale production does not continue to emit.
- The legacy domestic synthetic-fertilizer inflow requires actual nitrate output rather than the presence of a wood/furniture corporation. Mineral fertilizer and synthetic fertilizer remain combined in Goods.nitrates; no new chemical commodity or energy-input circuit was introduced.
- Unique living residents with active respiratory, waterborne or chemical illness after treatment determine local pollution illness prevalence. Five percent triggers a control petition; twenty percent triggers a local revolt, with eligible adult participants withholding production. Multiple diagnoses count once. Unrelated malnutrition or pestilence does not trigger this mechanism. Thresholds are gameplay settings, configurable per region, not medical standards.
- Petitions recur on stage changes or at five-turn intervals; recovery below the petition threshold resolves the petition and releases pollution-specific withholding. Grievances, petitions, revolt participants and assessments are traced. Existing legitimacy and garrison gates still govern regime replacement.
- National AI can commission an affordable scrubber, filtration plant, sewer or chemical-illness clinic in response to petitions during a food emergency. Normal construction cash, labor, materials and approval delays apply; active and pending projects prevent duplication. Player nations require their existing AI-autoplay setting to act automatically.
- Discretionary household consumption protects two production batches of inputs. A furniture artisan therefore retains four wood units, or its entire stock when below four, and can consume only the excess. Corporations scale reserves by workforce. Production can spend the reserve normally. Trace replay accounts for the protected quantity.
- Default base wood production increases from two to three units per agent; the existing output cap remains unchanged. This is a 50% recipe increase; actual output still depends on access, production probability, terrain, inventories and labor.

## Why did people not become loggers?

They did. The earlier Japan trace records 31 independent career-change events into wood (26 from food, five from furniture), but 51 out (19 to food, 32 to furniture). These are events, not unique people. Recorded wood occupation count rises from 106 to 136, also reflecting births and employment classifications. Rising occupation counts did not guarantee more effective timber supply.

The chooser uses observed reachable sales and returns, woodland access, age, cooldowns and switching hurdles. Food also carries a household subsistence value. An observed turn-20 option values food at 11 and wood at 3.369. High wood demand does not automatically outweigh those private returns. Existing mobility rules remain; no forced career assignment or universal shortage override was added.

## Twenty-turn comparison

Three fresh processes use seed 4242: an archive of the pre-change commit, new mechanisms with the old wood recipe (base2), and the final implementation with wood recipe three. Initial configuration digests differ; the recipe is intentionally changed. These are realized seeded paths, not a fixed-cohort or isolated causal welfare estimate. Source and compact-trace fingerprints are in the JSON sidecar.

| Arm | Nation | Wood output | Furniture output | Underfed resident-turns | Deaths |
|---|---|---:|---:|---:|---:|
| before | China | 2100 | 143 | 199 | 0 |
| before | Japan | 2488 | 214 | 555 | 2 |
| before | United States | 1516 | 125 | 31 | 1 |
| base2 | China | 2248 | 147 | 319 | 0 |
| base2 | Japan | 2302 | 220 | 346 | 2 |
| base2 | United States | 1522 | 120 | 7 | 1 |
| final | China | 4208 | 269 | 10 | 1 |
| final | Japan | 4707 | 411 | 926 | 1 |
| final | United States | 2879 | 235 | 294 | 0 |

| Japan turn-20 indicator | Before | Final |
|---|---:|---:|
| Mean air index | 22.8 | 0 |
| Mean water index | 25.1 | 16 |
| Respiratory cases | 99 | 0 |
| Waterborne cases | 108 | 89 |
| Untreated cases | 212 | 122 |

Japan commissions Tokyo water filtration at turn 11 in the final run, responding to illness. Artificial smog disappears because the default economy does not actually produce in the newly designated air-polluting industries. Sewage and upstream water pollution remain.

Furniture output improves substantially, but this does not establish a general welfare improvement. Japan and U.S. underfed resident-turns increase in the final path. Keeping wood production at two produces much less furniture and better food outcomes in this seed. More timber is therefore retained as the requested supply experiment, with food/labor balance explicitly left for further calibration. Missing-input event counts can rise as population, producer numbers and realized paths change; they are not estimates of units lost.

## Validation and limits

All 209 focused tests pass. They cover output-sensitive emissions, idle and nonpolluting producers, runoff and controls, illness thresholds, unique resident counts, petition recovery, real production withholding, workforce trace agreement, pending-project/funding guards, emergency AI response, input reserves and their consumption, economic replay, and existing market, relief, treasury and checkpoint behavior. Ledger footprint tests use deterministic successful production, and their polluting factory fixture is now an iron smelter. A pre-existing planner test double lacked the indexed inventory protocol (also reproduced against the baseline archive); the fixture now provides a consistent view.

- before: 20 verified checkpoints; 7,785 supported pollution/consumption/grievance formula replays matched; 0 mismatches.
- base2: 20 verified checkpoints; 7,729 supported pollution/consumption/grievance formula replays matched; 0 mismatches.
- final: 20 verified checkpoints; 10,844 supported pollution/consumption/grievance formula replays matched; 0 mismatches.

Each run has zero negative stock rows. Wood balances reconcile all twenty intervals. Food and furniture residuals remain; this change does not claim complete material conservation. Final balance counts and maximum residuals are in the JSON.

## Follow-up

1. Evaluate multiple seeds, longer horizons and fixed household cohorts before treating wood recipe three as a stable balance choice. Include crop output, food access, career transitions and discretionary wood use alongside furniture availability.
2. Review whether the household wealth consumption curve consumes timber too aggressively; this implementation protects working inputs but preserves consumption of the excess.
3. Calibrate pollution coefficients in industrial scenarios. Track traded fertilizer, synthetic production, energy inputs and application as distinct physical flows before claiming a complete chemical mass balance.
4. Target upstream sanitation as well as local treatment, and review whether filtration should remove imported or existing contamination. Current filtration reduces local new emissions.
5. Review petition/revolt prevalence thresholds and persistence across ages; a twenty-turn default game cannot validate political calibration. Clinics mitigate chemical illness rather than eliminating the pollution source.
6. Reconcile remaining food/furniture stock residuals using lifecycle, storage and goods-destruction events.

Reproduce the final default arm with:

```sh
MPLCONFIGDIR=/private/tmp/regnum-mpl PYTHONHASHSEED=4242 SDL_VIDEODRIVER=dummy \
venv/bin/python -m economy.economic_policy_experiment --child combined \
  --seed 4242 --turns 20 --out-dir tmp/pollution-reproduction
```

The base2 ablation imports region first, sets `econsim_states.recipes[Goods.wood]["production"] = 2`, then calls `run_arm("combined", 4242, 20, output_path)` in a fresh process. The baseline uses an archive of the commit named in the JSON.
