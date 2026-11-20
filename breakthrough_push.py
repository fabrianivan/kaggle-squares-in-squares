#!/usr/bin/env python3
"""
BREAKTHROUGH PUSH - Next generation from NEW BEST
Starting from: 22.250441 (massive improvement!)
Strategy: 250 ultra-intensive attempts on all puzzles
Features: Every technique at maximum intensity
Runtime: ~6-8 hours
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

def optimize_breakthrough():
    baseline = pd.read_csv('output/submission_22.250441.csv')
    current_score = compute_score(baseline)
    print(f"BREAKTHROUGH PUSH - Starting from NEW BEST {current_score:.6f}")
    print(f"This is a MASSIVE improvement! Pushing even further...")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target ALL high-value puzzles
    target_puzzles = list(range(10, 601))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 250 breakthrough attempts
        for attempt in range(250):
            seed = 20000 + attempt * 59
            strategy = attempt % 30
            
            try:
                if strategy == 0:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=35, max_seconds=80,
                                            trust_start=0.006, regularization=4e-15)
                elif strategy == 1:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.61,
                                                tie=0.135, rounds=20, seconds=80)
                elif strategy == 2:
                    temp, _, _ = polish.polish(p, seed=seed, rounds=18, max_seconds=42,
                                       trust_start=0.015, regularization=8e-14)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=18, max_seconds=42,
                                            trust_start=0.011, regularization=2e-14)
                elif strategy == 3:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=32,
                                       trust_start=0.028, regularization=5e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.52, tie=0.16,
                                            rounds=10, seconds=32)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=12, max_seconds=32,
                                        trust_start=0.019, regularization=3e-13)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.44, tie=0.19,
                                                rounds=10, seconds=32)
                elif strategy == 4:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=32, max_seconds=75,
                                            trust_start=0.007, regularization=6e-15)
                elif strategy == 5:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.60,
                                                tie=0.138, rounds=19, seconds=75)
                elif strategy == 6:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=28,
                                       trust_start=0.035, regularization=8e-12)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=10, max_seconds=28,
                                        trust_start=0.024, regularization=4e-12)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=10, max_seconds=28,
                                        trust_start=0.017, regularization=1e-12)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=10, max_seconds=28,
                                            trust_start=0.012, regularization=3e-13)
                elif strategy == 7:
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.55, tie=0.15,
                                            rounds=11, seconds=35)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.51, tie=0.165,
                                            rounds=10, seconds=35)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.47, tie=0.18,
                                            rounds=10, seconds=35)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.43, tie=0.195,
                                                rounds=9, seconds=35)
                elif strategy == 8:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=30, max_seconds=70,
                                            trust_start=0.008, regularization=8e-15)
                elif strategy == 9:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.595,
                                                tie=0.14, rounds=18, seconds=70)
                elif strategy == 10:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=24,
                                       trust_start=0.042, regularization=1e-11)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.48, tie=0.175,
                                            rounds=8, seconds=24)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=8, max_seconds=24,
                                        trust_start=0.029, regularization=6e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.42, tie=0.20,
                                            rounds=7, seconds=24)
                    temp5, _, _ = polish.polish(temp4, seed=seed+4, rounds=8, max_seconds=24,
                                        trust_start=0.020, regularization=4e-13)
                    candidate, _, _ = reclosure.reclose(temp5, seed=seed+5, trust=0.38, tie=0.21,
                                                rounds=7, seconds=24)
                elif strategy == 11:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=28, max_seconds=68,
                                            trust_start=0.009, regularization=1e-14)
                elif strategy == 12:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.585,
                                                tie=0.142, rounds=17, seconds=68)
                elif strategy == 13:
                    temp, _, _ = polish.polish(p, seed=seed, rounds=16, max_seconds=40,
                                       trust_start=0.017, regularization=1e-13)
                    candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.54, tie=0.155,
                                                rounds=12, seconds=45)
                elif strategy == 14:
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.56, tie=0.148,
                                            rounds=13, seconds=45)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=16, max_seconds=40,
                                            trust_start=0.015, regularization=5e-14)
                elif strategy == 15:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=26, max_seconds=65,
                                            trust_start=0.010, regularization=1.5e-14)
                elif strategy == 16:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.575,
                                                tie=0.145, rounds=16, seconds=65)
                elif strategy == 17:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=26,
                                       trust_start=0.038, regularization=9e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.46, tie=0.18,
                                            rounds=8, seconds=26)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=9, max_seconds=26,
                                        trust_start=0.026, regularization=5e-12)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.40, tie=0.20,
                                                rounds=7, seconds=26)
                elif strategy == 18:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=24, max_seconds=60,
                                            trust_start=0.011, regularization=2e-14)
                elif strategy == 19:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.57,
                                                tie=0.146, rounds=15, seconds=60)
                elif strategy == 20:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=22,
                                       trust_start=0.048, regularization=1.5e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=7, max_seconds=22,
                                        trust_start=0.033, regularization=7e-12)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=22,
                                        trust_start=0.023, regularization=3e-12)
                    temp4, _, _ = polish.polish(temp3, seed=seed+3, rounds=7, max_seconds=22,
                                        trust_start=0.016, regularization=9e-13)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=7, max_seconds=22,
                                            trust_start=0.011, regularization=2e-13)
                elif strategy == 21:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=22, max_seconds=58,
                                            trust_start=0.012, regularization=3e-14)
                elif strategy == 22:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.565,
                                                tie=0.148, rounds=14, seconds=58)
                elif strategy == 23:
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.53, tie=0.16,
                                            rounds=9, seconds=30)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=11, max_seconds=30,
                                       trust_start=0.028, regularization=6e-12)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.45, tie=0.185,
                                            rounds=8, seconds=30)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=11, max_seconds=30,
                                            trust_start=0.019, regularization=3e-13)
                elif strategy == 24:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=20, max_seconds=55,
                                            trust_start=0.013, regularization=4e-14)
                elif strategy == 25:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.56,
                                                tie=0.15, rounds=13, seconds=55)
                elif strategy == 26:
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=11, max_seconds=30,
                                       trust_start=0.032, regularization=7e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.48, tie=0.175,
                                            rounds=9, seconds=30)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=11, max_seconds=30,
                                            trust_start=0.021, regularization=4e-13)
                elif strategy == 27:
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=38, max_seconds=85,
                                            trust_start=0.0055, regularization=3e-15)
                elif strategy == 28:
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.62,
                                                tie=0.133, rounds=21, seconds=85)
                else:  # strategy == 29
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=13, max_seconds=35,
                                       trust_start=0.025, regularization=4e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.50, tie=0.17,
                                            rounds=10, seconds=35)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=13, max_seconds=35,
                                        trust_start=0.018, regularization=2e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.44, tie=0.19,
                                            rounds=9, seconds=35)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=13, max_seconds=35,
                                            trust_start=0.013, regularization=4e-13)
                
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
        print(f"BREAKTHROUGH PUSH COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found from this excellent baseline")

if __name__ == '__main__':
    optimize_breakthrough()
