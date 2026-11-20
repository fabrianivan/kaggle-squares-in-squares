#!/usr/bin/env python3
"""
ULTIMATE PRECISION - Extreme refinement optimizer
Strategy: 200 ultra-deep attempts targeting puzzles most likely to improve
Starting from: 22.250922 (current best)
Features: Deepest precision, longest timeouts, exhaustive search
Runtime: ~5-7 hours
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

def optimize_ultimate():
    baseline = pd.read_csv('output/submission_22.250922.csv')
    current_score = compute_score(baseline)
    print(f"ULTIMATE PRECISION - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target high-potential puzzles (known to have improvement room)
    target_puzzles = list(range(25, 301))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        best_p = p.copy()
        best_side = current_side
        
        print(f"Puzzle {puzzle_n}: starting {current_side:.10f}", flush=True)
        
        # 200 ultimate precision attempts
        for attempt in range(200):
            seed = 12000 + attempt * 47
            strategy = attempt % 25
            
            try:
                if strategy == 0:
                    # Maximum precision polish
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=30, max_seconds=70,
                                            trust_start=0.007, regularization=8e-15)
                elif strategy == 1:
                    # Extreme reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.6,
                                                tie=0.135, rounds=18, seconds=70)
                elif strategy == 2:
                    # Deep dual polish
                    temp, _, _ = polish.polish(p, seed=seed, rounds=15, max_seconds=35,
                                       trust_start=0.018, regularization=1e-13)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=15, max_seconds=35,
                                            trust_start=0.012, regularization=3e-14)
                elif strategy == 3:
                    # Deep dual reclosure
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.55, tie=0.15,
                                            rounds=12, seconds=38)
                    candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.52, tie=0.155,
                                                rounds=12, seconds=38)
                elif strategy == 4:
                    # Pentagon precision combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=8, max_seconds=22,
                                       trust_start=0.045, regularization=9e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.47, tie=0.175,
                                            rounds=7, seconds=22)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=8, max_seconds=22,
                                        trust_start=0.028, regularization=5e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.40, tie=0.20,
                                            rounds=7, seconds=22)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=8, max_seconds=22,
                                            trust_start=0.017, regularization=7e-13)
                elif strategy == 5:
                    # Extreme ultra polish
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=28, max_seconds=65,
                                            trust_start=0.008, regularization=1e-14)
                elif strategy == 6:
                    # Maximum trust reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.595,
                                                tie=0.14, rounds=16, seconds=65)
                elif strategy == 7:
                    # Triple polish ladder
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=24,
                                       trust_start=0.05, regularization=2e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=9, max_seconds=24,
                                        trust_start=0.03, regularization=8e-12)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=9, max_seconds=24,
                                            trust_start=0.018, regularization=4e-13)
                elif strategy == 8:
                    # Triple reclosure ladder
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.52, tie=0.16,
                                            rounds=8, seconds=26)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.47, tie=0.175,
                                            rounds=7, seconds=26)
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.42, tie=0.195,
                                                rounds=7, seconds=26)
                elif strategy == 9:
                    # Hexagon ultra combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=18,
                                       trust_start=0.055, regularization=2.5e-11)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.44, tie=0.19,
                                            rounds=5, seconds=18)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=18,
                                        trust_start=0.038, regularization=1e-11)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.39, tie=0.21,
                                            rounds=5, seconds=18)
                    temp5, _, _ = polish.polish(temp4, seed=seed+4, rounds=6, max_seconds=18,
                                        trust_start=0.024, regularization=6e-12)
                    candidate, _, _ = reclosure.reclose(temp5, seed=seed+5, trust=0.35, tie=0.22,
                                                rounds=5, seconds=18)
                elif strategy == 10:
                    # Precision cascade
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=32,
                                       trust_start=0.025, regularization=5e-12)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=12, max_seconds=32,
                                        trust_start=0.019, regularization=2e-12)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=12, max_seconds=32,
                                            trust_start=0.014, regularization=5e-13)
                elif strategy == 11:
                    # Trust cascade reclosure
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.54, tie=0.155,
                                            rounds=10, seconds=34)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.49, tie=0.17,
                                            rounds=9, seconds=34)
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.44, tie=0.185,
                                                rounds=9, seconds=34)
                elif strategy == 12:
                    # Ultra precision polish
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=26, max_seconds=62,
                                            trust_start=0.009, regularization=1.5e-14)
                elif strategy == 13:
                    # Extreme trust reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.585,
                                                tie=0.142, rounds=17, seconds=62)
                elif strategy == 14:
                    # Alternating intensive
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=10, max_seconds=28,
                                       trust_start=0.032, regularization=7e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.46, tie=0.18,
                                            rounds=8, seconds=28)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=10, max_seconds=28,
                                        trust_start=0.023, regularization=4e-12)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.41, tie=0.20,
                                                rounds=8, seconds=28)
                elif strategy == 15:
                    # Reverse alternating intensive
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.50, tie=0.17,
                                            rounds=9, seconds=30)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=11, max_seconds=30,
                                       trust_start=0.029, regularization=6e-12)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.43, tie=0.19,
                                            rounds=8, seconds=30)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=11, max_seconds=30,
                                            trust_start=0.020, regularization=3e-13)
                elif strategy == 16:
                    # Quad polish precision
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=20,
                                       trust_start=0.048, regularization=1.2e-11)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=7, max_seconds=20,
                                        trust_start=0.033, regularization=6e-12)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=20,
                                        trust_start=0.022, regularization=3e-12)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=7, max_seconds=20,
                                            trust_start=0.016, regularization=8e-13)
                elif strategy == 17:
                    # Quad reclosure precision
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.51, tie=0.165,
                                            rounds=7, seconds=22)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.47, tie=0.175,
                                            rounds=6, seconds=22)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.43, tie=0.19,
                                            rounds=6, seconds=22)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.39, tie=0.20,
                                                rounds=6, seconds=22)
                elif strategy == 18:
                    # Deep polish from scratch
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=24, max_seconds=58,
                                            trust_start=0.010, regularization=2e-14)
                elif strategy == 19:
                    # Deep reclosure from scratch
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.575,
                                                tie=0.145, rounds=15, seconds=58)
                elif strategy == 20:
                    # Balanced mega combo
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=9, max_seconds=26,
                                       trust_start=0.036, regularization=8e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.45, tie=0.185,
                                            rounds=7, seconds=26)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=9, max_seconds=26,
                                        trust_start=0.026, regularization=5e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.40, tie=0.20,
                                            rounds=7, seconds=26)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=9, max_seconds=26,
                                            trust_start=0.018, regularization=4e-13)
                elif strategy == 21:
                    # Extreme precision polish
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=32, max_seconds=75,
                                            trust_start=0.0065, regularization=6e-15)
                elif strategy == 22:
                    # Extreme trust reclosure
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.605,
                                                tie=0.138, rounds=19, seconds=75)
                elif strategy == 23:
                    # Ultimate alternating
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=11, max_seconds=30,
                                       trust_start=0.030, regularization=7e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.48, tie=0.175,
                                            rounds=9, seconds=30)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=11, max_seconds=30,
                                        trust_start=0.021, regularization=4e-12)
                    temp4, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.42, tie=0.195,
                                            rounds=8, seconds=30)
                    candidate, _, _ = polish.polish(temp4, seed=seed+4, rounds=11, max_seconds=30,
                                            trust_start=0.015, regularization=6e-13)
                else:  # strategy == 24
                    # Nuclear precision
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=35, max_seconds=80,
                                            trust_start=0.006, regularization=5e-15)
                
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
        print(f"ULTIMATE PRECISION COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found")

if __name__ == '__main__':
    optimize_ultimate()
