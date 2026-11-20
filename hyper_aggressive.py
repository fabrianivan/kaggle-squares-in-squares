#!/usr/bin/env python3
"""
HYPER AGGRESSIVE - Maximum intensity from NEW BASELINE  
Strategy: 150 ultra-aggressive attempts per puzzle
Starting from: 22.250922 (latest best)
Features: Every extreme strategy possible
Runtime: ~4-5 hours
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

def optimize_hyper():
    baseline = pd.read_csv('output/submission_22.250922.csv')
    current_score = compute_score(baseline)
    print(f"HYPER AGGRESSIVE - Starting from NEW BASELINE {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target critical range
    target_puzzles = list(range(50, 501))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 150 hyper-aggressive attempts
        for attempt in range(150):
            seed = 11000 + attempt * 43
            strategy = attempt % 20
            
            try:
                if strategy == 0:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=25, max_seconds=60,
                                            trust_start=0.008, regularization=1e-14)
                elif strategy == 1:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.59,
                                                tie=0.14, rounds=15, seconds=60)
                elif strategy == 2:
                    temp, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=30,
                                       trust_start=0.02, regularization=2e-13)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=12, max_seconds=30,
                                            trust_start=0.015, regularization=5e-14)
                elif strategy == 3:
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.54, tie=0.155,
                                            rounds=10, seconds=32)
                    candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.51, tie=0.16,
                                                rounds=10, seconds=32)
                elif strategy == 4:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=20,
                                       trust_start=0.04, regularization=8e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.46, tie=0.18,
                                            rounds=7, seconds=22)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=8, max_seconds=20,
                                        trust_start=0.025, regularization=4e-12)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.38, tie=0.21,
                                                rounds=7, seconds=22)
                elif strategy == 5:
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.5, tie=0.17,
                                            rounds=8, seconds=25)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=10, max_seconds=25,
                                       trust_start=0.03, regularization=6e-12)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.42, tie=0.19,
                                            rounds=7, seconds=25)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=10, max_seconds=25,
                                            trust_start=0.02, regularization=3e-13)
                elif strategy == 6:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=20, max_seconds=52,
                                            trust_start=0.012, regularization=3e-14)
                elif strategy == 7:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.57, tie=0.145,
                                                rounds=13, seconds=55)
                elif strategy == 8:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=18,
                                       trust_start=0.05, regularization=1e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=7, max_seconds=18,
                                        trust_start=0.03, regularization=5e-12)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=18,
                                        trust_start=0.02, regularization=2e-12)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=7, max_seconds=18,
                                            trust_start=0.015, regularization=6e-13)
                elif strategy == 9:
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.48, tie=0.175,
                                            rounds=7, seconds=20)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.44, tie=0.19,
                                            rounds=6, seconds=20)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.40, tie=0.20,
                                            rounds=6, seconds=20)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.36, tie=0.22,
                                                rounds=6, seconds=20)
                elif strategy == 10:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=16,
                                       trust_start=0.06, regularization=2e-11)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.40, tie=0.20,
                                            rounds=5, seconds=16)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=16,
                                        trust_start=0.035, regularization=8e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.35, tie=0.22,
                                            rounds=5, seconds=16)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=6, max_seconds=16,
                                            trust_start=0.02, regularization=4e-13)
                elif strategy == 11:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=18, max_seconds=46,
                                            trust_start=0.014, regularization=4e-14)
                elif strategy == 12:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.555, tie=0.15,
                                                rounds=12, seconds=50)
                elif strategy == 13:
                    temp, _, _ = polish.polish(p, seed=seed, rounds=14, max_seconds=38,
                                       trust_start=0.018, regularization=8e-13)
                    candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.5, tie=0.17,
                                                rounds=10, seconds=38)
                elif strategy == 14:
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.52, tie=0.16,
                                            rounds=9, seconds=35)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=13, max_seconds=35,
                                            trust_start=0.02, regularization=5e-13)
                elif strategy == 15:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=16, max_seconds=44,
                                            trust_start=0.016, regularization=6e-14)
                elif strategy == 16:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.56, tie=0.148,
                                                rounds=11, seconds=48)
                elif strategy == 17:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=24,
                                       trust_start=0.032, regularization=7e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.43, tie=0.19,
                                            rounds=7, seconds=24)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=9, max_seconds=24,
                                            trust_start=0.022, regularization=4e-13)
                elif strategy == 18:
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.49, tie=0.17,
                                            rounds=8, seconds=26)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=10, max_seconds=26,
                                       trust_start=0.028, regularization=6e-12)
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.41, tie=0.20,
                                                rounds=7, seconds=26)
                else:  # strategy == 19
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=24, max_seconds=58,
                                            trust_start=0.01, regularization=2e-14)
                
                cand_side = pg.side(candidate)
                
                if cand_side < best_side - 1e-11:
                    improvement = current_side - cand_side
                    best_side = cand_side
                    best_p = candidate.copy()
                    print(f"  → WIN attempt {attempt} [S={strategy}]: {cand_side:.10f} (Δ {improvement:.2e})", flush=True)
            
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
        print(f"HYPER AGGRESSIVE COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found")

if __name__ == '__main__':
    optimize_hyper()
