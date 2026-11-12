#!/usr/bin/env python3
"""
IMMEDIATE BOOST - Fast intensive optimization
Strategy: 60 diverse attempts per puzzle on 150 high-value targets
Runtime: ~2-4 hours
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

def optimize_immediate():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"IMMEDIATE BOOST - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target puzzles 2-151 (skip trivial puzzle 1)
    target_puzzles = list(range(2, 152))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 60 diverse attempts per puzzle
        for attempt in range(60):
            seed = 1000 + attempt * 7
            
            # Strategy rotation every 10 attempts
            strategy = attempt % 6
            
            if strategy == 0:
                # Ultra-tight polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=30,
                                        trust_start=0.02, regularization=1e-13)
            elif strategy == 1:
                # Aggressive reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.45, 
                                            tie=0.2, rounds=6, seconds=30)
            elif strategy == 2:
                # Balanced combo
                temp, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=20,
                                   trust_start=0.1, regularization=5e-12)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.3,
                                            tie=0.25, rounds=4, seconds=20)
            elif strategy == 3:
                # Deep polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=40,
                                        trust_start=0.05, regularization=2e-12)
            elif strategy == 4:
                # Fast reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.35,
                                            tie=0.18, rounds=8, seconds=25)
            else:
                # Triple pass
                temp1, _, _ = polish.polish(p, seed=seed, rounds=4, max_seconds=15,
                                    trust_start=0.08, regularization=8e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.25,
                                        tie=0.22, rounds=3, seconds=15)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=4, max_seconds=15,
                                        trust_start=0.04, regularization=3e-12)
            
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
        print(f"IMMEDIATE BOOST COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_immediate()
