#!/bin/bash
# Monitor Maximum Effort Campaign

clear
echo "================================================================================"
echo "⚡ MAXIMUM EFFORT CAMPAIGN - LIVE MONITOR ⚡"
echo "================================================================================"
date
echo ""

echo "📊 ACTIVE OPTIMIZERS:"
ps aux | grep python | grep -E "(ultra_intensive|final_assault|nuclear_option|titan_optimizer)" | grep -v grep | awk '{print "  ✓", $11, $12, $13}' | head -4
echo ""

echo "📈 CURRENT BEST SCORE:"
ls -t output/submission_22.*.csv 2>/dev/null | head -1 | sed 's/.*submission_/  Score: /' | sed 's/.csv//'
echo ""

echo "💾 LATEST WINS FILES:"
ls -lht output/*wins*.npz 2>/dev/null | head -5 | awk '{print "  ", $9, "-", $5, "-", $6, $7, $8}' || echo "  (None yet)"
echo ""

echo "📝 LOG PROGRESS:"
for log in ultra_boost_run.log final_assault_run.log nuclear_run.log titan_run.log; do
    if [ -f "output/$log" ]; then
        lines=$(wc -l < "output/$log" 2>/dev/null)
        size=$(du -h "output/$log" 2>/dev/null | cut -f1)
        echo "  $log: $lines lines, $size"
    fi
done
echo ""

echo "💻 RESOURCE USAGE:"
echo "  CPU: $(ps aux | grep python | grep -E "(ultra_intensive|final_assault|nuclear|titan)" | awk '{sum+=$3} END {printf "%.1f%%", sum}')"
echo "  Memory: $(ps aux | grep python | grep -E "(ultra_intensive|final_assault|nuclear|titan)" | awk '{sum+=$4} END {printf "%.1f%%", sum}')"
echo ""

echo "⏱️  ESTIMATED COMPLETION:"
echo "  Ultra Intensive: 2-3 hours"
echo "  Final Assault: 3-5 hours"
echo "  Nuclear: 4-6 hours"
echo "  Titan: 8-12 hours"
echo ""

echo "================================================================================"
echo "Run this script again to see updated progress"
echo "================================================================================"
