# Egypt society observations: implementation and verification

Date: October 31, 2026.

The first observation delivery in milestones 1–2 of the [governing plan](../governing_network_implementation_plan.md) is implemented. A creation-time `observe` mode shows three communities over Egypt's terrain and records their actual material inputs alongside a small diagnostic pressure graph. Existing economic and political authorities continue resolving the campaign. `governing` remains disabled pending the strike-source contract and integrated dispute interface in the [ownership register](../governing_network_ownership_register.md).

## Verification

**53 tests passed** on a frozen copy of the October 31 working tree: 20 new observation, presentation and checkpoint tests, plus 33 existing scenario-presentation, politics, campaign, grain-transfer, private-sale and worker-bargain regressions.

```sh
MPLCONFIGDIR=/private/tmp/regnum-mpl SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  venv/bin/python -m unittest \
  tests.test_governing_network tests.test_governing_network_ui \
  tests.test_governing_network_native tests.test_scenario_presentation \
  tests.test_scenario_politics tests.test_scenario_campaign \
  tests.test_scenario_grain_transfer_trace tests.test_scenario_private_grain_release_trace \
  tests.test_scenario_bargain_trace -q
```

**All 12 paired campaign comparisons passed**, together with **all six recorded/unrecorded diagnostic comparisons**. The matrix compares observations off/on for buying private maize, requisitioning private maize and opening private sales. It runs each route in both native engines, with causal recording off/on, from opening turn 1 through turn 8: 24 fresh campaigns and 96 paired turn samples. Each comparison uses fixed Python, NumPy and hash seeds. It compares policy results, all sampled economic metrics every turn and the full canonical economic graph at the end, including RNG and gameplay globals. The [JSON summary](governing_network_observation.json) records the completed comparisons and cross-recording diagnostic checks.

```sh
venv/bin/python -m scripts.verify_governing_network --steps 7
```

The canonical comparison retains the repository's existing observational normalization, removes the new observation sidecar and relabels the exact native recorder run UUID consistently. Event/operation suffixes, sequence ordering, money, goods, participation, obligations and random state remain in the comparison. A focused test checks that different event suffixes, money amounts and unrelated identities remain distinguishable.

Initial harness comparisons exposed an unseeded NumPy state and independently generated recorder UUIDs. Those were corrected in verification without changing gameplay. Later cross-run comparisons also encountered economic source changes in the shared workspace. The final verification used a frozen 693-file source copy, preserved locally as `outputs/governing_network/verified-sources.zip` with its manifest. Its source fingerprint is `b19b6204c4ea8ddbec61e61118a584c207e1332c56d045d098b5dae89ed9ced1`. This includes existing economic work in the shared tree; it is not a pristine-branch release certification.

## Native UI playthrough

The actual primary-client renderer and button targets were exercised at 1400×900:

1. Read the three communities on the opening terrain map.
2. Click the existing **Release maize reserves** decision.
3. Click **Next** and verify the observation follows the completed food/tax turn.
4. Hide the community panel and advance another real turn.
5. Reopen it and verify the data continued updating while hidden.

The playthrough passed. The rendered image was visually inspected: all three community titles, counts, concerns and explanations are visible together, with no person selection. The panel consumes clicks on its body so an obscured district is not selected accidentally. The test uses real scenario actions and normal turns; it does not force votes, food delivery, political results or population state.

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy MPLCONFIGDIR=/private/tmp/regnum-mpl \
  venv/bin/python -m scripts.playtest_governing_network_observation
```

Its report and opening/after-relief/hidden/reopened screenshots are generated under `outputs/governing_network/ui/`. Voronoi rendering required graphics access in this execution environment. The default observed campaign had 15 active organization nodes and 18 directed authored contacts. The primary interface's shorter decision list remains distinct from the legacy interface; the three-policy matrix uses the real action dispatcher, while the rendered primary playthrough exercises reserve release.

## Boundaries and remaining gates

The observer does not call reserve-clamping helpers, move money/food, change strike flags, add support bonuses or advance the authoritative trace clock. Its separate 24-observation journal retains material membership/source inputs and exact diffusion contributions. Directed reachability, weak components, connected/fragmented propagation and one-contact-per-update lag are tested. Native checkpoints preserve the mode, membership, graph and journal, and continue to the same diagnostic state after restore.

The authored contacts are experimental scenario setup. The three community views remain incomplete political models. Opposing pressure competition, actual autonomous petition/strike recruitment, group bargaining, representatives' mandates, a unified governing interface and opposition/return are still pending. The connected/fragmented test establishes a diagnostic propagation difference; real mobilization and production effects require the next implementation gate.

The matrix covers one fixed seed and a short crisis. Human usability testing and fun remain future gates. Start the observation campaign using the [short guide](../../docs/governing_network_observation.md).
