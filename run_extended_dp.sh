#!/usr/bin/env bash
# Wait for two-angle gadget generator to finish, then run extended DP and merge.
# Usage: bash run_extended_dp.sh
set -e
ROOT="/Users/fabrianivan/kaggle-squares-in-squares"
cd "$ROOT"

GADGET_LOG="output/two_angle_gen.log"
GADGET_NPY="output/two_angle_gadgets.npy"

echo "Waiting for gadget generator to finish..."
while [ ! -f "$GADGET_NPY" ]; do
    sleep 30
    LAST=$(tail -1 "$GADGET_LOG" 2>/dev/null)
    echo "  $(date +%H:%M:%S) -- $LAST"
done
echo "Gadget file found: $GADGET_NPY"

# Find the current best submission (lowest score)
BEST=$(ls output/submission_22.2*.csv 2>/dev/null | sort | head -1)
echo "Best submission: $BEST"

# Run extended DP with the new two-angle gadget library
mkdir -p output/dp_extended_wins
echo "Running extended DP for n=901-1000 with two-angle gadgets..."
.venv/bin/python -u src/engine/dp_with_harvest.py \
    --base "$BEST" \
    --dirs data/harvest_nov_6_9 \
    --extra-gadgets "$GADGET_NPY" \
    --nmin 901 --nmax 1000 \
    --workers 8 \
    --outdir output/dp_extended_wins \
    2>&1 | tee output/dp_extended_run.log

# Count wins
WINS=$(ls output/dp_extended_wins/*.csv 2>/dev/null | wc -l | tr -d ' ')
echo "DP produced $WINS win files"

if [ "$WINS" -gt 0 ]; then
    echo "Merging DP wins..."
    .venv/bin/python -u src/tools/merge_harvest.py \
        --base "$BEST" \
        --dirs output/dp_extended_wins \
        --workers 8 \
        2>&1 | tee output/dp_extended_merge.log
    echo "Merge complete — check output/ for new submission_22.*.csv"
else
    echo "No DP wins found."
fi
