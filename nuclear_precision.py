#!/usr/bin/env python3
"""
NUCLEAR PRECISION - Seventh wave super-aggressive optimizer
Strategy: 120 maximum-effort attempts on critical range (100-250)
Uses most aggressive parameters and longest timeouts
Runtime: ~4-6 hours
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

def optimize_nuclear():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"NUCLEAR PRECISION - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target critical range
    target_puzzles = list(range(100, 251))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 120 nuclear attempts
        for attempt in range(120):
            seed = 7000 + attempt * 29
            
            # 12 strategy rotation
            strategy = attempt % 12
            
            if strategy == 0:
                # Extreme precision polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=20, max_seconds=50,
                                        trust_start=0.01, regularization=3e-14)
            elif strategy == 1:
                # Maximum reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.56, 
                                            tie=0.14, rounds=12, seconds=50)
            elif strategy == 2:
                # Quad polish combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=15,
                                   trust_start=0.06, regularization=6e-12)
                temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=6, max_seconds=15,
                                        trust_start=0.04, regularization=3e-12)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                        trust_start=0.025, regularization=8e-13)
                candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=6, max_seconds=15,
                                        trust_start=0.015, regularization=4e-13)
            elif strategy == 3:
                # Alternating mega combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=18,
                                   trust_start=0.045, regularization=5e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.4,
                                        tie=0.2, rounds=6, seconds=18)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=18,
                                        trust_start=0.03, regularization=3e-12)
                candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.34,
                                            tie=0.22, rounds=6, seconds=18)
            elif strategy == 4:
                # Reverse alternating
                temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.47,
                                        tie=0.175, rounds=6, seconds=18)
                temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=7, max_seconds=18,
                                   trust_start=0.035, regularization=4e-12)
                temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.38,
                                            tie=0.21, rounds=6, seconds=18)
                candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=7, max_seconds=18,
                                        trust_start=0.022, regularization=5e-13)
            elif strategy == 5:
                # Ultimate precision
                candidate, _, _ = polish.polish(p, seed=seed, rounds=25, max_seconds=60,
                                        trust_start=0.008, regularization=2e-14)
            elif strategy == 6:
                # Extreme trust reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.58,
                                            tie=0.135, rounds=14, seconds=55)
            elif strategy == 7:
                # Pentagon combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=12,
                                    trust_start=0.07, regularization=1.5e-11)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.36,
                                        tie=0.22, rounds=4, seconds=12)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=12,
                                        trust_start=0.04, regularization=7e-12)
                temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.31,
                                            tie=0.24, rounds=4, seconds=12)
                candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=5, max_seconds=12,
                                        trust_start=0.02, regularization=3e-13)
            elif strategy == 8:
                # Triple ultra precision
                temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=20,
                                   trust_start=0.03, regularization=2e-12)
                temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=8, max_seconds=20,
                                        trust_start=0.02, regularization=8e-13)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=8, max_seconds=20,
                                        trust_start=0.015, regularization=4e-13)
            elif strategy == 9:
                # Double high trust
                temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.51,
                                        tie=0.16, rounds=8, seconds=28)
                candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.48,
                                            tie=0.17, rounds=8, seconds=28)
            elif strategy == 10:
                # Balanced nuclear
                temp1, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=25,
                                   trust_start=0.025, regularization=5e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.42,
                                        tie=0.19, rounds=7, seconds=25)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=10, max_seconds=25,
                                        trust_start=0.018, regularization=3e-13)
            else:
                # Hexagon combo (6-step)
                temp1, _, _ = polish.polish(p, seed=seed, rounds=4, max_seconds=10,
                                    trust_start=0.08, regularization=2e-11)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.37,
                                        tie=0.22, rounds=3, seconds=10)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=4, max_seconds=10,
                                        trust_start=0.045, regularization=1e-11)
                temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.32,
                                            tie=0.24, rounds=3, seconds=10)
                temp5, _, _ = polish.polish(temp4, seed=seed+4, rounds=4, max_seconds=10,
                                        trust_start=0.025, regularization=6e-12)
                candidate, _, _ = reclosure.reclose(temp5, seed=seed+5, trust=0.28,
                                            tie=0.25, rounds=3, seconds=10)
            
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
        print(f"NUCLEAR PRECISION COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_nuclear()
