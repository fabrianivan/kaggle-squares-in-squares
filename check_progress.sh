#!/bin/bash
# Progress checker for optimization runs

echo "=========================================="
echo "OPTIMIZATION PROGRESS CHECK"
echo "=========================================="
echo ""

echo "📊 Process Status:"
ps aux | grep -E "final_push|fast_track|mega" | grep python | grep -v grep || echo "  No optimization processes running"
echo ""

echo "📁 Output Files:"
echo "  Logs:"
ls -lh output/*_log.txt 2>/dev/null | awk '{print "    " $9 " - " $5}' || echo "    No log files yet"
echo "  Summaries:"
ls -lh output/*summary.json 2>/dev/null | awk '{print "    " $9 " - " $5}' || echo "    No summaries yet"
echo "  Wins:"
ls -lh output/*wins.npz 2>/dev/null | awk '{print "    " $9 " - " $5}' || echo "    No wins saved yet"
echo ""

echo "📝 Recent Log Output (last 20 lines):"
if [ -f output/final_push_log.txt ]; then
    echo "  From final_push_log.txt:"
    tail -20 output/final_push_log.txt | sed 's/^/    /'
elif [ -f output/fast_track_log.txt ]; then
    echo "  From fast_track_log.txt:"
    tail -20 output/fast_track_log.txt | sed 's/^/    /'
else
    echo "    No logs available yet"
fi
echo ""

echo "✅ To check again, run: bash check_progress.sh"
