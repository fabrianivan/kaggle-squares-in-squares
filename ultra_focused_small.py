#!/usr/bin/env python3
"""
ULTRA FOCUSED SMALL - Fifth wave targeting small puzzles
Strategy: 100 ultra-intensive attempts on high-value small puzzles (10-80)
These often have the most room for improvement
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

def optimize_ultra_small():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"ULTRA FOCUSED SMALL - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target high-value small puzzles
    target_puzzles = list(range(10, 81))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 100 ultra-intensive attempts
        for attempt in range(100):
            seed = 5000 + attempt * 19
            
            # 10 strategy rotation
            strategy = attempt % 10
            
            if strategy == 0:
                # Ultra-precision polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=15, max_seconds=40,
                                        trust_start=0.015, regularization=8e-14)
            elif strategy == 1:
                # Extreme reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.53, 
                                            tie=0.16, rounds=9, seconds=40)
            elif strategy == 2:
                # Triple polish
                temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=15,
                                   trust_start=0.06, regularization=5e-12)
                temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=6, max_seconds=15,
                                        trust_start=0.03, regularization=2e-12)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                        trust_start=0.02, regularization=6e-13)
            elif strategy == 3:
                # Polish-reclosure-polish
                temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=15,
                                   trust_start=0.05, regularization=7e-12)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.38,
                                        tie=0.21, rounds=5, seconds=15)
                candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                        trust_start=0.025, regularization=4e-13)
            elif strategy == 4:
                # Reclosure-polish-reclosure
                temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.42,
                                        tie=0.19, rounds=5, seconds=15)
                temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=6, max_seconds=15,
                                   trust_start=0.04, regularization=5e-12)
                candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.35,
                                            tie=0.22, rounds=5, seconds=15)
            elif strategy == 5:
                # Deep ultra polish
                candidate, _, _ = polish.polish(p, seed=seed, rounds=18, max_seconds=45,
                                        trust_start=0.012, regularization=5e-14)
            elif strategy == 6:
                # Maximum trust reclosure
                candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.55,
                                            tie=0.15, rounds=10, seconds=40)
            elif strategy == 7:
                # Balanced mega combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=12,
                                    trust_start=0.08, regularization=1e-11)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.32,
                                        tie=0.23, rounds=4, seconds=12)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=12,
                                        trust_start=0.035, regularization=8e-12)
                candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.28,
                                            tie=0.24, rounds=4, seconds=12)
            elif strategy == 8:
                # Double ultra precision
                temp, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=25,
                                   trust_start=0.02, regularization=1e-12)
                candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=10, max_seconds=25,
                                        trust_start=0.018, regularization=3e-13)
            else:
                # Quad combo
                temp1, _, _ = polish.polish(p, seed=seed, rounds=4, max_seconds=10,
                                    trust_start=0.07, regularization=2e-11)
                temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.35,
                                        tie=0.22, rounds=3, seconds=10)
                temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=4, max_seconds=10,
                                        trust_start=0.04, regularization=9e-12)
                temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.3,
                                            tie=0.24, rounds=3, seconds=10)
                candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=4, max_seconds=10,
                                        trust_start=0.022, regularization=4e-13)
            
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
        print(f"ULTRA FOCUSED SMALL COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_ultra_small()
