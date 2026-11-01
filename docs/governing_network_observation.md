# Seeing the people behind Egypt's grain crisis

This is the first observation phase of the simpler governing design. You still govern Egypt through its existing decisions. A new panel on the terrain map shows what is happening to three communities, so you do not have to inspect every person.

Start a new campaign with:

```sh
venv/bin/python -m client.desktop.app --scenario egypt-1877 --ui-mode guided --governing-network observe
```

The panel shows:

- **Cultivators and workers:** how many are underfed and how much tax they still owe. Buying grain into public stores does not feed them until it is distributed and consumed.
- **Grainholders and landowners:** how much reserved maize remains and how much has been requisitioned. Buying pays the owners; requisition takes their stock without a purchase payment.
- **Merchants and exporters:** whether the scenario's private warehouse sales are held or open. Opening sales permits trade, but people still need money to buy food.

These views refer to the existing population. A merchant who owns a warehouse can appear in two communities; they remain one person. The view updates after each turn's food and tax processing. Opening conditions are labeled separately, and selecting a policy does not immediately rewrite the completed observation.

Use **Hide** to see more of the map and **Show communities** to restore the panel. The observations keep updating while hidden. Normal campaign decisions and their costs are unchanged. Launch without the experiment option, or use `--governing-network off`, for the original presentation and behavior.

**Observation mode does not change political behavior.** Existing petitions, strikes and government transitions still resolve through the original campaign systems. A small experimental graph records how community pressure could spread, for development comparison. This mode does not recruit people or create demands. The separate [governing mode](governing_campaign.md) now enables autonomous petitions, next-turn walkouts and funded bargaining through the existing economy. The larger opposition-and-return phase comes later.

For implementation boundaries, test commands and the grain-policy storyboard, see the [ownership register](../planning/governing_network_ownership_register.md) and [full implementation plan](../planning/governing_network_implementation_plan.md).
