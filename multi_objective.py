#!/usr/bin/env python3
"""
MULTI-OBJECTIVE - Advanced optimizer with Pareto optimization
Strategy: Optimizes for multiple objectives simultaneously:
- Minimize bounding box
- Maximize compactness
- Minimize overlap risk
Features: Pareto frontier tracking, multi-criteria selection
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
    total = 0.0
    for n in range(1, 1001):
        p = df[df['n'] == n][['x', 'y', 'angle']].values
        if len(p) == n:
            L = pg.side(p)
            total += L / math.sqrt(n) - 1
    return total

def compute_compactness(p):
    """Measure how compact the packing is"""
    if len(p) == 0:
        return 0.0
    centers = p[:, :2]
    distances = np.sqrt(((centers[:, None] - centers[None, :]) ** 2).sum(axis=2))
    np.fill_diagonal(distances, np.inf)
    return np.mean(np.min(distances, axis=1))

def compute_spread(p):
    """Measure spread of angles"""
    if len(p) == 0:
        return 0.0
    angles = p[:, 2]
    return np.std(angles)

def optimize_multi_objective():
    baseline = pd.read_csv('output/submission_22.250971.csv')
    current_score = compute_score(baseline)
    print(f"MULTI-OBJECTIVE - Starting from {current_score:.6f}")
    
    best_df = baseline.copy()
    wins = 0
    
    # Target puzzles
    target_puzzles = list(range(30, 451))
    
    for puzzle_n in target_puzzles:
        p = baseline[baseline['n'] == puzzle_n][['x', 'y', 'angle']].values
        if len(p) == 0 or len(p) != puzzle_n:
            continue
            
        current_side = pg.side(p)
        current_compactness = compute_compactness(p)
        current_spread = compute_spread(p)
        
        best_p = p.copy()
        best_side = current_side
        pareto_front = [(current_side, current_compactness, current_spread, p.copy())]
        
        print(f"Puzzle {puzzle_n}: L={current_side:.10f}, compact={current_compactness:.4f}", flush=True)
        
        # 80 multi-objective attempts
        for attempt in range(80):
            seed = 9000 + attempt * 37
            strategy = attempt % 12
            
            try:
                if strategy == 0:
                    # Optimize for size only (traditional)
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=12, max_seconds=35,
                                            trust_start=0.025, regularization=3e-13)
                
                elif strategy == 1:
                    # Optimize for compactness (tight clustering)
                    temp, _, _ = reclosure.reclose(p, seed=seed, trust=0.5, tie=0.16,
                                            rounds=10, seconds=38)
                    candidate, _, _ = polish.polish(temp, seed=seed+1, rounds=8, max_seconds=25,
                                            trust_start=0.02, regularization=4e-13)
                
                elif strategy == 2:
                    # Balance size and compactness
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=7, max_seconds=20,
                                       trust_start=0.04, regularization=6e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.42, tie=0.19,
                                            rounds=6, seconds=20)
                    candidate, _, _ = polish.polish(temp2, seed=seed+2, rounds=7, max_seconds=20,
                                            trust_start=0.028, regularization=5e-13)
                
                elif strategy == 3:
                    # Start from best Pareto solution
                    if len(pareto_front) > 1:
                        start_idx = np.random.randint(0, min(3, len(pareto_front)))
                        start_p = pareto_front[start_idx][3]
                    else:
                        start_p = p
                    candidate, _, _ = polish.polish(start_p, seed=seed, rounds=10, max_seconds=30,
                                            trust_start=0.022, regularization=2e-13)
                
                elif strategy == 4:
                    # Weighted multi-objective
                    # Try to improve both size AND compactness
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.48, tie=0.17,
                                            rounds=7, seconds=25)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=8, max_seconds=25,
                                       trust_start=0.03, regularization=7e-12)
                    candidate, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.4, tie=0.20,
                                            rounds=6, seconds=25)
                
                elif strategy == 5:
                    # Minimize spread (uniform angles)
                    candidate, _, _ = reclosure.reclose(p, seed=seed, trust=0.45, tie=0.18,
                                            rounds=9, seconds=35)
                
                elif strategy == 6:
                    # Aggressive size reduction
                    temp, _, _ = polish.polish(p, seed=seed, rounds=15, max_seconds=40,
                                       trust_start=0.015, regularization=8e-14)
                    candidate, _, _ = reclosure.reclose(temp, seed=seed+1, trust=0.52, tie=0.16,
                                            rounds=8, seconds=35)
                
                elif strategy == 7:
                    # Multi-scale from Pareto front
                    if len(pareto_front) > 2:
                        # Interpolate between Pareto solutions
                        idx1, idx2 = np.random.choice(min(4, len(pareto_front)), 2, replace=False)
                        p1, p2 = pareto_front[idx1][3], pareto_front[idx2][3]
                        alpha = np.random.uniform(0.3, 0.7)
                        start_p = alpha * p1 + (1-alpha) * p2
                    else:
                        start_p = p
                    candidate, _, _ = polish.polish(start_p, seed=seed, rounds=12, max_seconds=32,
                                            trust_start=0.024, regularization=4e-13)
                
                elif strategy == 8:
                    # Quad combo for thorough optimization
                    temp1, _, _ = polish.polish(p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=0.05, regularization=8e-12)
                    temp2, _, _ = reclosure.reclose(temp1, seed=seed+1, trust=0.38, tie=0.21,
                                            rounds=5, seconds=15)
                    temp3, _, _ = polish.polish(temp2, seed=seed+2, rounds=6, max_seconds=15,
                                        trust_start=0.032, regularization=4e-12)
                    candidate, _, _ = reclosure.reclose(temp3, seed=seed+3, trust=0.34, tie=0.22,
                                            rounds=5, seconds=15)
                
                elif strategy == 9:
                    # Random exploration
                    trust = np.random.uniform(0.018, 0.055)
                    reg = 10 ** np.random.uniform(-13.5, -11.5)
                    candidate, _, _ = polish.polish(p, seed=seed, 
                                            rounds=np.random.randint(10, 16),
                                            max_seconds=np.random.randint(30, 42),
                                            trust_start=trust, regularization=reg)
                
                elif strategy == 10:
                    # Extreme precision
                    candidate, _, _ = polish.polish(p, seed=seed, rounds=20, max_seconds=50,
                                            trust_start=0.01, regularization=2e-14)
                
                else:  # strategy == 11
                    # Hybrid Pareto
                    temp1, _, _ = reclosure.reclose(p, seed=seed, trust=0.46, tie=0.18,
                                            rounds=7, seconds=22)
                    temp2, _, _ = polish.polish(temp1, seed=seed+1, rounds=8, max_seconds=22,
                                       trust_start=0.028, regularization=5e-12)
                    temp3, _, _ = reclosure.reclose(temp2, seed=seed+2, trust=0.38, tie=0.21,
                                            rounds=6, seconds=22)
                    candidate, _, _ = polish.polish(temp3, seed=seed+3, rounds=8, max_seconds=22,
                                            trust_start=0.02, regularization=3e-13)
                
                cand_side = pg.side(candidate)
                cand_compactness = compute_compactness(candidate)
                cand_spread = compute_spread(candidate)
                
                # Check if it's on Pareto front (dominates in at least one objective)
                is_pareto = False
                if cand_side < best_side - 1e-11:
                    is_pareto = True
                    best_side = cand_side
                    best_p = candidate.copy()
                    improvement = current_side - cand_side
                    print(f"  → WIN attempt {attempt}: L={cand_side:.10f} (Δ {improvement:.2e}), compact={cand_compactness:.4f}", flush=True)
                
                # Also track in Pareto front if it's good in any objective
                if is_pareto or cand_compactness > current_compactness * 1.05:
                    pareto_front.append((cand_side, cand_compactness, cand_spread, candidate.copy()))
                    # Keep only top 10 Pareto solutions
                    pareto_front.sort(key=lambda x: x[0])  # Sort by size
                    pareto_front = pareto_front[:10]
            
            except Exception as e:
                print(f"  Strategy {strategy} failed: {e}", flush=True)
                continue
        
        if best_side < current_side - 1e-11:
            mask = best_df['n'] == puzzle_n
            best_df.loc[mask, ['x', 'y', 'angle']] = best_p
            wins += 1
            print(f"Puzzle {puzzle_n}: IMPROVED {current_side:.10f} → {best_side:.10f} (Pareto front: {len(pareto_front)} solutions)", flush=True)
    
    # Save if improved
    if wins > 0:
        new_score = compute_score(best_df)
        improvement = current_score - new_score
        print(f"\n{'='*60}")
        print(f"MULTI-OBJECTIVE COMPLETE: {wins} puzzles improved")
        print(f"Score: {current_score:.6f} → {new_score:.6f}")
        print(f"Improvement: {improvement:.6f}")
        print(f"{'='*60}")
        
        output_path = f'output/submission_{new_score:.6f}.csv'
        best_df.to_csv(output_path, index=False)
        print(f"Saved: {output_path}")
    else:
        print(f"\nNo improvements found (baseline is very strong)")

if __name__ == '__main__':
    optimize_multi_objective()
