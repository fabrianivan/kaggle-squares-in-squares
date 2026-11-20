#!/usr/bin/env python3
"""
RAPID STRIKE - Third wave fast optimizer
Strategy: 50 rapid attempts on puzzles 351-600
Complements immediate_boost and parallel_intensive
Runtime: ~2-3 hours
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

def optimize_rapid():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"RAPID STRIKE - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target puzzles 351-600
    target_puzzles = list(range(351, 601))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 50 fast attempts per puzzle
        for attempt in range(50):
            seed = 3000 + attempt * 13
            
            # Fast rotation strategy
            strategy = attempt % 5
            
            if strategy == 0:
                # Fast aggressive polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=25,
                                        trust_start=0.03, regularization=7e-13)
            elif strategy == 1:
                # Quick reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.4, 
                                            tie=0.21, rounds=6, seconds=25)
            elif strategy == 2:
                # Polish + reclosure combo
                temp, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=15,
                                   trust_start=0.05, regularization=4e-12)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.33,
                                            tie=0.22, rounds=4, seconds=15)
            elif strategy == 3:
                # Reclosure + polish combo
                temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.38,
                                            tie=0.19, rounds=4, seconds=15)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=5, max_seconds=15,
                                        trust_start=0.04, regularization=5e-13)
            else:
                # Double polish fast
                temp, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=12,
                                   trust_start=0.08, regularization=1e-11)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=5, max_seconds=12,
                                        trust_start=0.035, regularization=6e-13)
            
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
        print(f"RAPID STRIKE COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_rapid()
