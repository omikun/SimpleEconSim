# Compact causal trace

New simulation runs write `tmp/traces/<run-id>.ctr`. Existing `.jsonl` traces
still open in the same reader. The event schema, IDs, sequence, formulas, and
turn checkpoints are unchanged when decoded.

The compact file starts with `COCTRACE2\n`, followed by a continuous raw
DEFLATE stream of UTF-8 JSON lines. Each event ends in a synchronous flush,
so completed records can be queried before the run ends. The reader rejects a
truncated final flush or incomplete JSON line. Checkpoints continue to hash
the decoded canonical JSON payloads, so verification has the same meaning in
both formats. This format uses only Python's standard library.

## Read or decode

```bash
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --turn 12 --entity tile:Delta --good cloth --metric goods.price
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --verify
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --storage-stats
venv/bin/python trace_report.py --run tmp/traces/RUN_ID.ctr --decode-jsonl tmp/decoded-run.jsonl
```

`--decode-jsonl -` writes the complete decoded JSONL to standard output.
The web API `/api/trace` reads compact traces directly. `/api/trace/download`
exports decoded JSONL for existing tools; add `?format=compact` to download
the smaller `.ctr` file. Both links are available in the web client.

In a generated one-turn test run on 2026-10-16, the compact file was 677,011
bytes versus 10,481,917 decoded JSONL bytes (6.5% of the original size).
Actual ratios depend on how many repeated events a scenario emits. This
storage change does not remove events or reduce their recorded detail.
