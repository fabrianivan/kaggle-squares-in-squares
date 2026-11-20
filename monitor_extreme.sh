#!/bin/bash
# Real-time monitoring dashboard for extreme optimization

while true; do
    clear
    echo "══════════════════════════════════════════════════════════════════════════"
    echo "🚀 EXTREME OPTIMIZATION CAMPAIGN - LIVE DASHBOARD"
    echo "══════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "⏰ Time: $(date '+%H:%M:%S')"
    echo ""
    
    echo "📊 OPTIMIZER STATUS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check each optimizer
    if ps aux | grep "extreme_exhaustive_optimizer.py" | grep -v grep > /dev/null; then
        extreme_time=$(ps -p $(pgrep -f extreme_exhaustive_optimizer.py) -o etime= 2>/dev/null | tr -d ' ')
        extreme_cpu=$(ps -p $(pgrep -f extreme_exhaustive_optimizer.py) -o time= 2>/dev/null | tr -d ' ')
        echo "  ✅ Extreme Exhaustive (Terminal 7)"
        echo "     Elapsed: $extreme_time | CPU: $extreme_cpu"
    else
        echo "  ✓ Extreme Exhaustive (Terminal 7) - COMPLETED"
    fi
    
    if ps aux | grep "ultra_aggressive_optimizer.py" | grep -v grep > /dev/null; then
        ultra_time=$(ps -p $(pgrep -f ultra_aggressive_optimizer.py) -o etime= 2>/dev/null | tr -d ' ')
        echo "  ✅ Ultra Aggressive (Terminal 5)"
        echo "     Elapsed: $ultra_time"
    else
        echo "  ✓ Ultra Aggressive (Terminal 5) - COMPLETED"
    fi
    
    if ps aux | grep "small_puzzle_intensive.py" | grep -v grep > /dev/null; then
        small_time=$(ps -p $(pgrep -f small_puzzle_intensive.py) -o etime= 2>/dev/null | tr -d ' ')
        echo "  ✅ Small Puzzle Intensive (Terminal 8)"
        echo "     Elapsed: $small_time"
    else
        echo "  ✓ Small Puzzle Intensive (Terminal 8) - COMPLETED"
    fi
    
    if ps aux | grep "final_push_optimizer.py" | grep -v grep > /dev/null; then
        final_time=$(ps -p $(pgrep -f final_push_optimizer.py) -o etime= 2>/dev/null | tr -d ' ')
        echo "  ✅ Final Push (Terminal 4)"
        echo "     Elapsed: $final_time"
    else
        echo "  ✓ Final Push (Terminal 4) - COMPLETED"
    fi
    
    echo ""
    echo "🏆 RESULTS FOUND:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ -f output/extreme_exhaustive_wins.npz ]; then
        extreme_summary=$(cat output/extreme_exhaustive_summary.json 2>/dev/null)
        if [ ! -z "$extreme_summary" ]; then
            wins=$(echo "$extreme_summary" | grep -o '"wins": [0-9]*' | grep -o '[0-9]*')
            gain=$(echo "$extreme_summary" | grep -o '"total_gain": [0-9.e-]*' | awk '{print $2}' | tr -d ',')
            echo "  ✨ Extreme Exhaustive: $wins wins, gain=$gain"
        fi
    else
        echo "  ⏳ Extreme Exhaustive: Still searching..."
    fi
    
    if [ -f output/ultra_aggressive_wins.npz ]; then
        echo "  ✨ Ultra Aggressive: WINS FOUND! (check summary)"
    else
        echo "  ⏳ Ultra Aggressive: Still searching..."
    fi
    
    if [ -f output/small_puzzle_wins.npz ]; then
        small_summary=$(cat output/small_puzzle_summary.json 2>/dev/null)
        if [ ! -z "$small_summary" ]; then
            wins=$(echo "$small_summary" | grep -o '"wins": [0-9]*' | grep -o '[0-9]*')
            echo "  ✨ Small Puzzle: $wins wins found!"
        fi
    else
        echo "  ⏳ Small Puzzle: Still searching..."
    fi
    
    if [ -f output/final_push_wins.npz ]; then
        echo "  ✨ Final Push: WINS FOUND!"
    else
        echo "  ⏳ Final Push: Still searching..."
    fi
    
    echo ""
    echo "📈 LATEST SUBMISSIONS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ls -lht output/submission_*.csv 2>/dev/null | head -3 | while read line; do
        filename=$(echo "$line" | awk '{print $9}')
        size=$(echo "$line" | awk '{print $5}')
        time=$(echo "$line" | awk '{print $6, $7, $8}')
        echo "  $filename"
        echo "    Created: $time | Size: $size"
    done
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo "Press Ctrl+C to stop monitoring (optimizers will continue running)"
    echo "Refreshing every 30 seconds..."
    echo ""
    
    sleep 30
done
