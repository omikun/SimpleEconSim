# Historical context cards

Collective action events can carry a sourced historical comparison for the web
popup and event history. The matcher observes the event after it is recorded;
it does not feed back into simulation decisions or consume random numbers.

## Catalog files

Catalog entries are plain JSON so the simulation can load them with its
standard library. Put one case per file in `historical_context/catalog/`.
Each file has a `schema_version`, case `id`, title, period, place, sources,
and a list of independently matchable `moments`. Each moment names a
`category`, optional eligible `actions`, required or preferred `historical_tags`,
factual summary, interpretation, differences, and sources inherited from its
case.

Moment `signals.bloodshed` and `signals.reconciliation` use editorial match
levels from 0 to 4. They are not death counts, injury counts, or claims that
history has a single objective severity score. Leave a signal out when the
available sources do not support a useful rating. Actual casualty counts and
uncertainty belong in the sourced prose or in a later explicit evidence field.

## Matching and extension

`historical_context.matcher.EVENT_TYPES` maps existing strike log kinds to
shared categories and actions. New systems can either add a mapping or include
`historical_category` and `historical_action` in their event facts. Events can
also provide `historical_tags` for distinctions such as `private_guards`,
`workplace_occupation`, or `union_recognition`.

Regions can tune selection with `historical_context_settings`:

```json
{
  "min_bloodshed": 2,
  "max_reconciliation": 1,
  "target_bloodshed": 3,
  "bloodshed_weight": 1.5,
  "target_reconciliation": 0,
  "reconciliation_weight": 0.5
}
```

The minimum and maximum settings filter historical moments; target and weight
settings rank those left. Harm and reconciliation remain separate dimensions.
Settings change which comparison appears, never the simulated consequences.

Every significant collective event receives either the best eligible sourced
moment or a "No close historical match" card. The latter prevents a misleading
analogy from being forced into the popup. Cards identify their source and are
available from the collective event list after the automatic notification.

The initial catalog includes Homestead, Pullman, Lawrence, and Flint. Their
entries are concise starting cards, not comprehensive histories. Add claims
only with a traceable source; keep factual description, cynical interpretation,
and the limits of the comparison visibly distinct in the UI.
