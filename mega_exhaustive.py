#!/usr/bin/env python3
"""
MEGA EXHAUSTIVE - Comprehensive systematic search
Strategy: 180 exhaustive attempts covering all parameter space
Starting from: 22.250922
Features: Systematic grid search + random exploration
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
    total = 0.0
    for n in range(1, 1001):
        p = df[df['n'] == n][['x', 'y', 'angle']].values
        if len(p) == n:
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def optimize_exhaustive():
    baseline = pd.read_csv('output/submission_22.250922.csv')
    current_score = compute_score(baseline)
    print(f"MEGA EXHAUSTIVE - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Systematic parameter grids
    trust_grid = [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05]
    reg_grid = [5e-15, 1e-14, 3e-14, 8e-14, 2e-13, 5e-13, 1e-12, 3e-12]
    tie_grid = [0.14, 0.16, 0.18, 0.20, 0.22, 0.24]
    recl_trust_grid = [0.35, 0.40, 0.45, 0.50, 0.55, 0.58]
    
    # Target medium-high value puzzles
    target_puzzles = list(range(40, 451))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 180 exhaustive attempts
        for attempt in range(180):
            seed = 13000 + attempt * 53
            
            try:
                if attempt < 60:
                    # Grid search polish (systematic)
                    idx = attempt % len(trust_grid)
                    reg_idx = (attempt // len(trust_grid)) % len(reg_grid)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=14, max_seconds=40,
                                            trust_start=trust_grid[idx],
                                            regularization=reg_grid[reg_idx])
                
                elif attempt < 120:
                    # Grid search reclosure (systematic)
                    adj_attempt = attempt - 60
                    trust_idx = adj_attempt % len(recl_trust_grid)
                    tie_idx = (adj_attempt // len(recl_trust_grid)) % len(tie_grid)
                    candidate, _, _ = reclosure.reclose(p, seed=seed,
                                                trust=recl_trust_grid[trust_idx],
                                                tie=tie_grid[tie_idx],
                                                rounds=10, seconds=40)
                
                else:
                    # Random exploration from best regions (last 60 attempts)
                    strategy = (attempt - 120) % 12
                    
                    if strategy == 0:
                        # Best polish region
                        trust = np.random.choice([0.015, 0.02, 0.025])
                        reg = np.random.choice([1e-14, 2e-14, 5e-14, 1e-13])
                        candidate, _, _ = polish.polish(p, seed=seed, rounds=16, max_seconds=45,
                                                trust_start=trust, regularization=reg)
                    
                    elif strategy == 1:
                        # Best reclosure region
                        trust = np.random.choice([0.45, 0.48, 0.50, 0.52])
                        tie = np.random.choice([0.16, 0.18, 0.19, 0.20])
                        candidate, _, _ = reclosure.reclose(p, seed=seed, trust=trust, tie=tie,
                                                    rounds=11, seconds=45)
                    
                    elif strategy == 2:
                        # Combo from grid best
                        temp, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=28,
                                           trust_start=0.025, regularization=2e-13)
                        candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.48, tie=0.18,
                                                    rounds=8, seconds=28)
                    
                    elif strategy == 3:
                        # Reverse combo
                        temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.50, tie=0.17,
                                                rounds=8, seconds=28)
                        candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=10, max_seconds=28,
                                                trust_start=0.022, regularization=3e-13)
                    
                    elif strategy == 4:
                        # Triple polish
                        temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=20,
                                           trust_start=0.04, regularization=8e-12)
                        temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=7, max_seconds=20,
                                            trust_start=0.027, regularization=4e-12)
                        candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=20,
                                                trust_start=0.018, regularization=1e-13)
                    
                    elif strategy == 5:
                        # Triple reclosure
                        temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.52, tie=0.16,
                                                rounds=7, seconds=24)
                        temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.46, tie=0.18,
                                                rounds=6, seconds=24)
                        candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.41, tie=0.20,
                                                    rounds=6, seconds=24)
                    
                    elif strategy == 6:
                        # Quad alternating
                        temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=18,
                                           trust_start=0.038, regularization=7e-12)
                        temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.44, tie=0.19,
                                                rounds=5, seconds=18)
                        temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=18,
                                            trust_start=0.026, regularization=4e-12)
                        candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.39, tie=0.21,
                                                    rounds=5, seconds=18)
                    
                    elif strategy == 7:
                        # Extreme precision
                        candidate, _, _ = polish.polish(p, seed=seed, rounds=22, max_seconds=55,
                                                trust_start=0.011, regularization=4e-14)
                    
                    elif strategy == 8:
                        # Extreme reclosure
                        candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.57, tie=0.148,
                                                    rounds=14, seconds=55)
                    
                    elif strategy == 9:
                        # Balanced intensive
                        temp1, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=26,
                                           trust_start=0.032, regularization=6e-12)
                        temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.46, tie=0.18,
                                                rounds=7, seconds=26)
                        candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=9, max_seconds=26,
                                                trust_start=0.021, regularization=3e-13)
                    
                    elif strategy == 10:
                        # Pentagon combo
                        temp1, _, _ = polish.polish(p, seed=seed, rounds=5, max_seconds=15,
                                           trust_start=0.045, regularization=1e-11)
                        temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.42, tie=0.20,
                                                rounds=4, seconds=15)
                        temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=5, max_seconds=15,
                                            trust_start=0.030, regularization=5e-12)
                        temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.37, tie=0.22,
                                                rounds=4, seconds=15)
                        candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=5, max_seconds=15,
                                                trust_start=0.019, regularization=8e-13)
                    
                    else:  # strategy == 11
                        # Ultra deep
                        candidate, _, _ = polish.polish(p, seed=seed, rounds=26, max_seconds=62,
                                                trust_start=0.009, regularization=1.5e-14)
                
                cand_side = pg.side(candidate)
                
                if cand_side < best_side - 1e-11:
                    improvement = current_side - cand_side
                    best_side = cand_side
                    best_p = candidate.copy()
                    print(f"  → WIN attempt {attempt}: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
            
            except Exception as e:
                continue
        
        if best_side < current_side - 1e-11:
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f}", flush=True)
    
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"MEGA EXHAUSTIVE COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found")

if __name__ == '__main__':
    optimize_exhaustive()
