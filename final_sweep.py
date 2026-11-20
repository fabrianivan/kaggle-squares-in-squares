#!/usr/bin/env python3
"""
FINAL SWEEP - Fourth wave comprehensive optimizer
Strategy: 70 attempts on puzzles 601-1000
Completes full coverage of all 1000 puzzles
Runtime: ~3-5 hours
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
        if len(p) == n:
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def optimize_final():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"FINAL SWEEP - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target puzzles 601-1000
    target_puzzles = list(range(601, 1001))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 70 attempts per puzzle
        for attempt in range(70):
            seed = 4000 + attempt * 17
            
            # 7 strategy rotation
            strategy = attempt % 7
            
            if strategy == 0:
                # Precision polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=30,
                                        trust_start=0.025, regularization=3e-13)
            elif strategy == 1:
                # Balanced reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.42, 
                                            tie=0.20, rounds=7, seconds=30)
            elif strategy == 2:
                # Polish-reclosure combo
                temp, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=18,
                                   trust_start=0.06, regularization=8e-12)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.36,
                                            tie=0.23, rounds=5, seconds=18)
            elif strategy == 3:
                # Reclosure-polish combo
                temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.44,
                                            tie=0.18, rounds=5, seconds=18)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=6, max_seconds=18,
                                        trust_start=0.03, regularization=4e-13)
            elif strategy == 4:
                # Ultra precision
                candidate, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=35,
                                        trust_start=0.018, regularization=1.5e-13)
            elif strategy == 5:
                # High trust reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.52,
                                            tie=0.17, rounds=8, seconds=32)
            else:
                # Triple combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=14,
                                    trust_start=0.07, regularization=1e-11)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.3,
                                        tie=0.24, rounds=4, seconds=14)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=14,
                                        trust_start=0.028, regularization=5e-13)
            
            cand_side = pg.side(candidate)
            
            if cand_side < best_side - 1e-11:
                best_side = cand_side
                best_p = candidate.copy()
                improvement = current_side - cand_side
                print(f"  → WIN attempt {attempt}: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
        
        if best_side < current_side - 1e-11:
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f}", flush=True)
    
    # Save if improved
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"FINAL SWEEP COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_final()
