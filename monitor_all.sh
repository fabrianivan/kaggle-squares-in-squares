#!/bin/bash
# Comprehensive optimization monitoring dashboard

clear
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║     KAGGLE SQUARES-IN-SQUARES: MEGA OPTIMIZATION CAMPAIGN         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

while true; do
    # Clear for refresh
    tput cup 4 0
    
    # Current best score
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BEST SUBMISSION"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    latest=$(ls -t output/submission_*.csv 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        filename=$(basename "$latest")
        score=$(echo "$filename" | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        timestamp=$(ls -lh "$latest" | awk '{print $6, $7, $8}')
        echo "  File: $filename"
        echo "  Score: $score"
        echo "  Time: $timestamp"
        
        # Progress metrics
        baseline=22.251122
        target=22.11
        current=$score
        gap=$(echo "$current - $target" | bc -l)
        progress=$(echo "$baseline - $current" | bc -l)
        echo "  Progress from baseline: $progress"
        echo "  Gap to 22.11 target: $gap"
    else
        echo "  No submissions found"
    fi
    echo ""
    
    # Running optimizers
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚙️  ACTIVE OPTIMIZERS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    num_optimizers=$(ps aux | grep python | grep optimizer | grep -v grep | wc -l | tr -d ' ')
    echo "  Running: $num_optimizers optimizers"
    echo ""
    ps aux | grep python | grep optimizer | grep -v grep | \
        awk '{printf "  %-35s CPU: %5s%%  MEM: %5s%%\n", $12, $3, $4}' | \
        sed 's|src/||g' | sed 's|.py||g' | head -15
    echo ""
    
    # Win files
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🏆 DISCOVERED IMPROVEMENTS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    win_count=$(ls output/*wins*.npz 2>/dev/null | wc -l | tr -d ' ')
    if [ "$win_count" -gt 0 ]; then
        echo "  Total win files: $win_count"
        ls -lh output/*wins*.npz 2>/dev/null | tail -5 | awk '{printf "  %-40s %8s  %s %s %s\n", $9, $5, $6, $7, $8}'
    else
        echo "  No win files yet (optimizers still searching...)"
    fi
    echo ""
    
    # Latest log activity
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 RECENT ACTIVITY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    for log in output/*_log.txt; do
        if [ -f "$log" ] && [ -s "$log" ]; then
            logname=$(basename "$log" | sed 's/_log.txt//')
            last_line=$(tail -1 "$log" 2>/dev/null | cut -c 1-60)
            if [ -n "$last_line" ]; then
                echo "  [$logname] $last_line"
            fi
        fi
    done | head -10
    echo ""
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Press Ctrl+C to exit | Refreshing every 30 seconds..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    sleep 30
done
