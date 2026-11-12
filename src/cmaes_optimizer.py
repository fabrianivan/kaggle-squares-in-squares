#!/usr/bin/env python3
"""
CMA-ES OPTIMIZER - Covariance Matrix Adaptation Evolution Strategy
Advanced evolutionary algorithm
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_contact_polish as polish

def cmaes_optimize(n, p_base, generations=100):
    """Simplified CMA-ES optimization"""
    try:
        L0 = pg.side(p_base)
        rng = np.random.default_rng(n * 23)
        
        # Work in angle space only (simpler)
        angles_base = p_base[:, 2].copy()
        
        # Initialize
        mean = angles_base.copy()
        sigma = 0.05
        best_L = L0
        best_angles = angles_base.copy()
        
        for gen in range(generations):
            # Generate population
            population = []
            for _ in range(10):
                angles = mean + sigma * rng.normal(0, 1, n)
                p_trial = p_base.copy()
                p_trial[:, 2] = angles
                p_trial = pg.normalize(p_trial)
                
                # Quick polish
                try:
                    p_trial, _, _ = polish.polish(p_trial, seed=gen, rounds=30, max_seconds=2.0, trust_start=0.02)
                    p_trial = pg.repair(p_trial, clearance=1e-10)
                except:
                    pass
                
                if p_trial is not None:
                    population.append((p_trial, pg.side(p_trial)))
            
            if not population:
                continue
            
            # Sort by fitness
            population.sort(key=lambda x: x[1])
            
            # Update best
            if population[0][1] < best_L - 1e-11:
                best_L = population[0][1]
                best_angles = population[0][0][:, 2].copy()
            
            # Update mean (weighted average of best)
            weights = np.array([1.0/(i+1) for i in range(min(5, len(population)))])
            weights /= weights.sum()
            
            mean = np.zeros(n)
            for i in range(min(5, len(population))):
                mean += weights[i] * population[i][0][:, 2]
            
            # Adapt sigma
            sigma *= 0.98
        
        if best_L < L0 - 1e-11:
            p_result = p_base.copy()
            p_result[:, 2] = best_angles
            p_result = pg.normalize(p_result)
            return (n, L0, best_L, p_result)
    except:
        pass
    return None

def main():
    print("="*80)
    print("CMA-ES OPTIMIZER")
    print("="*80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    puzzles = []
    for n in range(200, 401, 5):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            puzzles.append((n, p))
    
    print(f"\nTargeting {len(puzzles)} puzzles with CMA-ES\n")
    
    wins = []
    for i, (n, p) in enumerate(puzzles):
        result = cmaes_optimize(n, p)
        if result is not None:
            wins.append(result)
            print(f"✓ n={n}: gain={result[1]-result[2]:.12e}")
        if (i+1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(puzzles)}")
    
    print(f"\nCMA-ES: {len(wins)} wins")
    if wins:
        np.savez('output/cmaes_wins.npz', **{str(n): p for n, _, _, p in wins})

if __name__ == '__main__':
    main()
