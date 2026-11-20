#!/usr/bin/env bash
# Continuous harvest-and-merge loop.
# Polls Kaggle every 10 minutes for new/updated competition sources and merges any gains.
# Run with: bash poll_and_merge.sh > output/poll_merge.log 2>&1 &
set -euo pipefail
ROOT="/Users/fabrianivan/kaggle-squares-in-squares"
cd "$ROOT"

POLL_INTERVAL=600   # 10 minutes
MAX_ROUNDS=60       # 10 hours max

find_best() {
    ls output/submission_22.2*.csv 2>/dev/null | sort | head -1
}

last_run_stamp() {
    # returns the most recent lastRunTime from competition kernels (UTC epoch)
    .venv/bin/python - 2>/dev/null << 'PYEOF'
import subprocess, json, re, sys
result = subprocess.run(
    ["kaggle","kernels","list","-s","squares in squares","--sort-by","dateRun","--page-size","5"],
    capture_output=True, text=True, timeout=30
)
# parse first competition kernel date from output
for line in result.stdout.splitlines()[2:]:
    m = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if m:
        print(m.group(1))
        break
PYEOF
}

LAST_SEEN=$(last_run_stamp)
echo "$(date +%H:%M:%S) Starting poll loop. Best: $(find_best). Last kernel: $LAST_SEEN"

for round in $(seq 1 $MAX_ROUNDS); do
    sleep $POLL_INTERVAL

    echo "$(date +%H:%M:%S) [Round $round] Checking for new sources..."

    NEW_STAMP=$(last_run_stamp)
    if [ "$NEW_STAMP" = "$LAST_SEEN" ]; then
        echo "  No new kernels (last: $LAST_SEEN)"
        # Still check for new datasets
    else
        echo "  NEW kernel activity! Was: $LAST_SEEN  Now: $NEW_STAMP"
        LAST_SEEN="$NEW_STAMP"
    fi

    # Always attempt a fresh daily merge pull (kmmmvs updates throughout the day)
    ROUND_DIR="data/poll_round_${round}"
    mkdir -p "$ROUND_DIR"

    kaggle kernels output kmmmvs/squares-public-merge-daily \
        -p "$ROUND_DIR/kmmmvs_daily/" --force 2>/dev/null
    kaggle kernels output malyshevdanil/squares-in-squares-living-atlas-of-tight-packings \
        -p "$ROUND_DIR/danil_atlas/" --force 2>/dev/null

    # Also pull top 5 kernels by dateRun
    TOP_KERNELS=$(.venv/bin/python - 2>/dev/null << 'PYEOF'
import subprocess, re
result = subprocess.run(
    ["kaggle","kernels","list","-s","squares in squares","--sort-by","dateRun","--page-size","8"],
    capture_output=True, text=True, timeout=30
)
kernels = []
for line in result.stdout.splitlines()[2:]:
    parts = line.split()
    if parts and '/' in parts[0] and ('kirilltym' in parts[0] or 'penguin' in parts[0] 
                                        or 'seshurajup' in parts[0] or 'nilanjan' in parts[0]
                                        or 'udishiken' in parts[0] or 'jazivxt' in parts[0]
                                        or 'lucifer' in parts[0]):
        kernels.append(parts[0])
for k in kernels[:4]:
    print(k)
PYEOF
)
    for kernel in $TOP_KERNELS; do
        slug=$(echo "$kernel" | tr '/' '__')
        kaggle kernels output "$kernel" -p "$ROUND_DIR/$slug/" --force 2>/dev/null || true
    done

    # Find current best and merge
    BEST=$(find_best)
    if [ -z "$BEST" ]; then
        echo "  No baseline found!"
        continue
    fi

    echo "  Merging against $BEST ..."
    .venv/bin/python -u src/tools/merge_harvest.py \
        --base "$BEST" \
        --dirs "$ROUND_DIR" \
        --workers 8 2>&1 | grep -E "certified|CERTIFIED|no candidate|gain"

    NEW_BEST=$(find_best)
    if [ "$NEW_BEST" != "$BEST" ]; then
        echo "  IMPROVEMENT: $BEST -> $NEW_BEST"
    fi
done

echo "$(date +%H:%M:%S) Poll loop finished after $MAX_ROUNDS rounds."
