#!/bin/bash
# Monitor all running optimizers

echo "========================================"
echo "OPTIMIZER STATUS MONITOR"
echo "========================================"
date
echo ""

echo "Running Processes:"
ps aux | grep python | grep -v grep | grep -E "(surgical|mega_large|elite)" || echo "  No optimizers currently running"
echo ""

echo "Latest Submissions:"
ls -lht output/submission_*.csv 2>/dev/null | head -5 || echo "  No submissions yet"
echo ""

echo "Best Score So Far:"
ls -1 output/submission_*.csv 2>/dev/null | sed 's/.*submission_//' | sed 's/.csv//' | sort -n | head -1 || echo "  No scores yet"
echo ""

echo "Recent Wins:"
ls -lht output/*wins*.npz 2>/dev/null | head -5 || echo "  No wins files yet"
echo ""

echo "Log Files Status:"
for log in output/surgical_strike_run.log output/mega_large_run.log output/elite_sweep_run.log; do
    if [ -f "$log" ]; then
        lines=$(wc -l < "$log")
        size=$(du -h "$log" | cut -f1)
        echo "  $log: $lines lines, $size"
    fi
done
echo ""

echo "========================================"
