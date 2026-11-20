#!/usr/bin/env python3
"""Quick script to check current progress and merge any improvements"""
import sys
sys.path.insert(0, '.')
import pandas as pd
import numpy as np
from pathlib import Path
from src.metric.metric import score

print("=" * 80)
print("CHECKING OPTIMIZATION PROGRESS")
print("=" * 80)

# Find all submissions
submissions = sorted(Path('output').glob('submission_*.csv'), 
                    key=lambda p: p.stat().st_mtime, reverse=True)

if not submissions:
    print("No submissions found!")
    sys.exit(1)

# Get scores
print("\nRecent submissions:")
scores = []
for sub in submissions[:10]:
    try:
        df = pd.read_csv(sub)
        s = score(df, 'n')
        scores.append((s, sub.name, sub.stat().st_mtime))
        print(f"  {sub.name}: {s:.12f}")
    except:
        pass

if scores:
    best_score, best_file, best_time = min(scores, key=lambda x: x[0])
    print(f"\n✓ Current best: {best_file}")
    print(f"  Score: {best_score:.12f}")
    print(f"  Modified: {pd.to_datetime(best_time, unit='s')}")
    
    # Calculate progress
    baseline = 22.251122
    improvement = baseline - best_score
    gap_to_target = best_score - 22.11
    
    print(f"\n📊 Progress:")
    print(f"  From baseline (22.251122): {improvement:.12f} ({improvement:.2e})")
    print(f"  Gap to 22.11 target: {gap_to_target:.12f}")
    print(f"  Progress: {(improvement / gap_to_target * 100):.4f}% of journey")

# Check for win files
print("\n" + "=" * 80)
print("CHECKING FOR OPTIMIZER WINS")
print("=" * 80)

win_files = list(Path('output').glob('*wins*.npz'))
if win_files:
    print(f"\nFound {len(win_files)} win files:")
    for wf in win_files:
        size = wf.stat().st_size / 1024
        print(f"  {wf.name} ({size:.1f} KB)")
    
    print("\nTo merge all wins, run:")
    print("  python merge_all_wins.py")
else:
    print("\nNo win files found yet. Optimizers still searching...")

# Check running optimizers
import subprocess
try:
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    lines = [l for l in result.stdout.split('\n') 
             if 'python' in l and 'optimizer' in l and 'grep' not in l]
    
    print("\n" + "=" * 80)
    print(f"RUNNING OPTIMIZERS: {len(lines)}")
    print("=" * 80)
    
    for line in lines:
        parts = line.split()
        if len(parts) >= 12:
            cpu = parts[2]
            cmd = parts[11]
            name = cmd.replace('src/', '').replace('.py', '')
            print(f"  {name}: {cpu}% CPU")
except:
    pass

print("\n" + "=" * 80)
