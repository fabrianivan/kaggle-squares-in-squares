#!/usr/bin/env python3
"""Merge All Wins - Combine improvements from all optimizers"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
from collections import defaultdict

print("=" * 80)
print("MERGING ALL OPTIMIZATION WINS")
print("=" * 80)

# Load base submission
submission_files = sorted(Path('output').glob('submission_22.*.csv'))
if not submission_files:
    print("No submission files found!")
    sys.exit(1)

base_file = submission_files[0]
print(f"\nBase: {base_file.name}")
df = pd.read_csv(base_file)

# Find all wins files
wins_files = list(Path('output').glob('*wins*.npz'))
print(f"Found {len(wins_files)} wins files")

# Collect all improvements
all_wins = defaultdict(list)

for wins_file in wins_files:
    print(f"  {wins_file.name}")
    data = np.load(wins_file)
    
    for key in data.files:
        n = int(key)
        packing = data[key]
        current = df[df['n'] == n][['x', 'y', 'angle']].values
        
        try:
            current_L = pg.side(current)
            new_L = pg.side(packing)
            if new_L < current_L - 1e-12:
                all_wins[n].append((packing, new_L))
        except:
            pass

# Select best
merged_wins = {}
total_imp = 0.0

for n, candidates in all_wins.items():
    candidates.sort(key=lambda x: x[1])
    best_pack, best_L = candidates[0]
    
    current = df[df['n'] == n][['x', 'y', 'angle']].values
    current_L = pg.side(current)
    imp = current_L - best_L
    
    if imp > 1e-12:
        merged_wins[n] = best_pack
        total_imp += imp

print(f"\n{len(merged_wins)} improvements, total Δ={total_imp:.9f}")

# Create merged submission
if merged_wins:
    df_new = df.copy()
    for n, pack in merged_wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = pack
    
    # Calculate score
    total_score = 0.0
    for n in range(1, 1001):
        puzzle_df = df_new[df_new['n'] == n]
        if len(puzzle_df) > 0:
            pack = puzzle_df[['x', 'y', 'angle']].values
            L = pg.side(pack)
            total_score += L / np.sqrt(n) - 1
    new_score = total_score
    
    out = f"output/submission_MERGED_{new_score:.6f}.csv"
    df_new.to_csv(out, index=False)
    print(f"\n✓ MERGED: {new_score:.12f}")
    print(f"  File: {out}")
