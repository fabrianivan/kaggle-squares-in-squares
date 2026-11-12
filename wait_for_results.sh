#!/bin/bash
# Wait for optimization to complete and show results

echo "🔄 Monitoring optimization processes..."
echo ""

while true; do
    # Check if processes are still running
    if ps -p 72764 > /dev/null 2>&1 || ps -p 68996 > /dev/null 2>&1; then
        clear
        echo "⏳ OPTIMIZATION STILL RUNNING..."
        echo ""
        echo "Time: $(date '+%H:%M:%S')"
        echo ""
        
        # Show process details
        echo "📊 Process Status:"
        ps -p 72764,68996 -o pid,etime,time,pcpu,comm 2>/dev/null | grep -v "PID" || echo "  All processes completed!"
        echo ""
        
        # Show any wins found
        echo "🎯 Results So Far:"
        if ls output/*wins*.npz 2>/dev/null | grep -q .; then
            echo "  ✓ Wins found!"
            ls -lh output/*wins*.npz 2>/dev/null | awk '{print "    " $9 " - " $5}'
        else
            echo "  ⏳ No wins yet (still searching...)"
        fi
        
        echo ""
        echo "Press Ctrl+C to stop monitoring (optimizers will continue)"
        echo "---"
        
        sleep 30
    else
        clear
        echo "✅ OPTIMIZATION COMPLETE!"
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        echo ""
        
        # Check for results
        if ls output/*wins*.npz 2>/dev/null | grep -q .; then
            echo "🎉 IMPROVEMENTS FOUND!"
            echo ""
            echo "📁 Result Files:"
            ls -lh output/*wins*.npz output/*summary.json 2>/dev/null | awk '{print "  " $9 " - " $5}'
            echo ""
            
            # Show summary if it exists
            if [ -f output/final_push_summary.json ]; then
                echo "📊 Final Push Results:"
                cat output/final_push_summary.json | grep -E '"wins"|"total_gain"|"new_score"' | sed 's/^/  /'
            fi
            
            if [ -f output/fast_track_summary.json ]; then
                echo ""
                echo "📊 Fast Track Results:"
                cat output/fast_track_summary.json | grep -E '"wins"|"total_gain"' | sed 's/^/  /'
            fi
            
            echo ""
            echo "🚀 NEW SUBMISSION CREATED!"
            echo ""
            ls -lh output/submission_*.csv | tail -3
            echo ""
            echo "✅ Upload the file with the LOWEST score number to Kaggle!"
            
        else
            echo "❌ No improvements found"
            echo ""
            echo "This means your current submission at 22.251602 is"
            echo "already at a very strong local optimum!"
            echo ""
            echo "✅ Your current submission is ready to upload:"
            echo "   output/submission_final.csv (22.251602)"
        fi
        
        echo ""
        echo "═══════════════════════════════════════════════════════════"
        
        break
    fi
done
