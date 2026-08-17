#!/bin/zsh
# Milestone E gate: 40-turn province world + full legacy regression suite.
# All outputs to tmp/mdE_*.out.  Fail fast on shift/leak.

set -e
cd /Users/sli/Code
PY=/Users/sli/Code/venv/bin/python3
export PYTHONPATH=/Users/sli/Code

echo "=== [1/6] province world 40 turns ==="
$PY sim_world.py 40 > tmp/mdE_world40.out 2>&1
SHIFTS=$(grep -cE "SUPPLY SHIFT|CASH AUDIT" tmp/mdE_world40.out || true)
echo "shifts/audits: $SHIFTS"
grep -E "SUPPLY SHIFT|CASH AUDIT" tmp/mdE_world40.out || true
[ "$SHIFTS" = "0" ]

echo "=== [2/6] sim_nation 100 ==="
$PY sim_nation.py 100 > tmp/mdE_nation.out 2>&1
grep -icE "LEAK|SHIFT|INSOLV" tmp/mdE_nation.out || true

echo "=== [3/6] sim_ring 300 ==="
$PY sim_ring.py 300 > tmp/mdE_ring.out 2>&1
grep -icE "LEAK|SHIFT|INSOLV" tmp/mdE_ring.out || true

echo "=== [4/6] behavior_drift 3x300 ==="
$PY tmp/behavior_drift.py > tmp/mdE_drift.out 2>&1
grep "GATE PASS" tmp/mdE_drift.out

echo "=== [5/6] probe_m2 / probe_m3 ==="
$PY tmp/probe_m2.py > tmp/mdE_m2.out 2>&1
grep "M2 GATE PASS" tmp/mdE_m2.out
$PY tmp/probe_m3.py > tmp/mdE_m3.out 2>&1
grep "M3 GATE PASS" tmp/mdE_m3.out

echo "=== [6/6] probe_hex / probe_worldview / verify_milestone_e ==="
$PY tmp/probe_hex.py > tmp/mdE_hex.out 2>&1
grep "PROBE PASS" tmp/mdE_hex.out
$PY tmp/probe_worldview.py > tmp/mdE_wv.out 2>&1
grep "WORLDVIEW PROBE PASS" tmp/mdE_wv.out
$PY tmp/verify_milestone_e.py > tmp/mdE_verify.out 2>&1
grep "MILESTONE E VERIFY PASS" tmp/mdE_verify.out

echo "ALL GATES GREEN"