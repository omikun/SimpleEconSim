# Read a game's causal evidence

## Web and iPad

Select a point in a history chart, then inspect its records. Treasury records show
opening/closing balances, recorded receipts and spending, confirmed internal
cash/deposit transfers, ownership/account membership effects and the remaining
flow residual. Open the named source buttons to follow account writes and their
linked decisions. The raw record remains in the evidence disclosure.

Pages and source navigation stay tied to the original published trace boundary.
**Show records** refreshes that boundary. Empty results, missing causes and request
errors have explicit messages. Touch targets are at least 44 pixels high.

A verified account chain and a zero flow residual do not establish complete
receipt/spending classification. The inspector reports those statuses separately.
Treasury follows the game's existing unconverted cash-plus-deposit accounting.

## Native desktop

Press **F11** in either desktop entry point. Choose Treasury, Prices, Unrest, FX
or Nation AI. Earlier/Later selects the recorded turn; Previous/Next record pages
through matching records. Open source buttons and use Back to return. Sources
also have paging. Refresh includes newly published events. Esc or F11 closes.

The desktop builders now attach a recorder. Actions between ticks close their
own stock boundary before the next tick. Historical nation charts prefer the
membership recorded at that turn, including tiles subsequently transferred.

## CLI

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --turn 12 --entity nation:NAME --metric finance.treasury --explain
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --event-id EVENT_ID --explain
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --verify
venv/bin/python trace_report.py --run tmp/traces/RUN.ctr --decode-jsonl -
```

CLI reports and snapshot comparisons stream with bounded buffers. `.ctr` is the
source; JSONL is only an export. Earlier compact formats are not accepted.

## Evidence labels

- **Observation:** a measured or sampled value.
- **Forecast / Recorded decision:** an actor's recorded estimate or choice.
- **Verified formula:** arithmetic matches its recorded inputs; this alone does
  not verify every input's provenance.
- **Verified local chain:** this boundary's arithmetic and required source links
  were checked. Open the sources to inspect their own evidence.
- **Unverified calculation:** the named formula has no supported replay yet.
- **Missing or inconsistent evidence:** an exact missing link, mismatching
  source, broken stock chain or formula problem is listed.

## Reproduce the browser check

Use a completed current-format run containing a treasury closure at turn 1:

```bash
venv/bin/python trace_ui_fixture.py --run tmp/traces/RUN.ctr
node test_trace_inspector_browser.js
```

The browser check requires Playwright on `NODE_PATH` and an installed Chrome. It
uses an isolated headless browser, actual recorded fixture values, iPad-sized
1024×768 touch emulation, source navigation, empty results and a request failure.
It writes `tmp/ipad-causal-evidence.png`. This is browser emulation, not a physical
iPad device test. `node test_web_ui_utils.js` checks transport retries separately.
