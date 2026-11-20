#!/usr/bin/env python3
"""
PARALLEL INTENSIVE - Second wave optimizer
Strategy: 80 aggressive attempts on puzzles 152-350 + high-value targets
Runs parallel to immediate_boost
Runtime: ~3-4 hours
"""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import pandas as pd
import numpy as np
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

def compute_score(df):
    """Compute overall score manually"""
    total = 0.0
    for n in range(1, 1001):
        p = df[df['n'] == n][['x', 'y', 'angle']].values
        if len(p) == n:  # Must have exactly n squares
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def optimize_parallel():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"PARALLEL INTENSIVE - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target puzzles 152-350 (complementary to immediate_boost)
    target_puzzles = list(range(152, 351))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 80 aggressive attempts per puzzle
        for attempt in range(80):
            seed = 2000 + attempt * 11
            
            # Strategy rotation every 8 attempts
            strategy = attempt % 10
            
            if strategy == 0:
                # Ultra-aggressive polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=35,
                                        trust_start=0.01, regularization=5e-14)
            elif strategy == 1:
                # Deep reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.5, 
                                            tie=0.15, rounds=8, seconds=35)
            elif strategy == 2:
                # Double polish combo
                temp, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=20,
                                   trust_start=0.06, regularization=1e-12)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=6, max_seconds=20,
                                        trust_start=0.03, regularization=3e-13)
            elif strategy == 3:
                # Reclosure then polish
                temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.4,
                                            tie=0.2, rounds=5, seconds=20)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=6, max_seconds=20,
                                        trust_start=0.02, regularization=2e-13)
            elif strategy == 4:
                # Polish then reclosure
                temp, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=20,
                                   trust_start=0.04, regularization=6e-13)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.35,
                                            tie=0.23, rounds=5, seconds=20)
            elif strategy == 5:
                # Extreme precision polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=15, max_seconds=40,
                                        trust_start=0.015, regularization=1e-14)
            elif strategy == 6:
                # High trust reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.55,
                                            tie=0.16, rounds=7, seconds=30)
            elif strategy == 7:
                # Triple combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=4, max_seconds=12,
                                    trust_start=0.07, regularization=9e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.28,
                                        tie=0.24, rounds=3, seconds=12)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=15,
                                        trust_start=0.025, regularization=4e-13)
            elif strategy == 8:
                # Medium balanced
                temp, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=25,
                                   trust_start=0.09, regularization=7e-12)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.32,
                                            tie=0.21, rounds=4, seconds=20)
            else:
                # Aggressive double reclosure
                temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.42,
                                            tie=0.19, rounds=5, seconds=20)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.38,
                                            tie=0.17, rounds=5, seconds=20)
            
            cand_side = pg.side(candidate)
            
            if cand_side < best_side - 1e-11:
                best_side = cand_side
                best_p = candidate.copy()
                improvement = current_side - cand_side
                print(f"  → WIN attempt {attempt}: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
        
        if best_side < current_side - 1e-11:
            # Replace in DataFrame
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f}", flush=True)
    
    # Save if improved
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"PARALLEL INTENSIVE COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_parallel()
