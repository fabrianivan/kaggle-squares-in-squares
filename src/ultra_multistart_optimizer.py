#!/usr/bin/env python3
"""
ULTRA MULTISTART OPTIMIZER
Try optimization from many random starting points
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def ultra_multistart(n, p_base, n_starts=200):
    """Ultra multistart optimization"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        rng = np.random.default_rng(n)
        
        for start in range(n_starts):
            # Random perturbation as starting point
            scale = 0.002 * rng.random() + 0.001
            p_start = p_base.copy()
            p_start[:, 0] += rng.normal(0, scale, n)
            p_start[:, 1] += rng.normal(0, scale, n)
            p_start[:, 2] += rng.uniform(-0.05, 0.05, n)
            p_start = pg.normalize(p_start)
            
            # Quick local optimization
            try:
                trust = 0.3 + 0.3 * rng.random()
                tie = 0.15 + 0.15 * rng.random()
                p_opt, _, _ = reclosure.reclose(p_start, seed=start, trust=trust, tie=tie, rounds=20, seconds=2.0)
                p_opt, _, _ = polish.polish(p_opt, seed=start, rounds=40, max_seconds=2.0, trust_start=0.02)
                p_opt = pg.repair(p_opt, clearance=1e-10)
                
                if p_opt is not None:
                    L = pg.side(p_opt)
                    if L < best_L - 1e-11:
                        best_L = L
                        best_p = p_opt.copy()
            except:
                pass
        
        if best_L < L0 - 1e-11:
            return (n, L0, best_L, best_p)
    except:
        pass
    return None

def main():
    print("="*80)
    print("ULTRA MULTISTART OPTIMIZER - 200 random starts per puzzle")
    print("="*80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    # Target gaps in coverage
    puzzles = []
    for n in list(range(100, 201, 3)) + list(range(600, 801, 5)):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            puzzles.append((n, p))
    
    print(f"\nTargeting {len(puzzles)} puzzles\n")
    
    wins = []
    for i, (n, p) in enumerate(puzzles):
        result = ultra_multistart(n, p)
        if result is not None:
            wins.append(result)
            print(f"✓ n={n}: gain={result[1]-result[2]:.12e}")
        if (i+1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(puzzles)}")
    
    print(f"\nMultistart: {len(wins)} wins")
    if wins:
        np.savez('output/multistart_wins.npz', **{str(n): p for n, _, _, p in wins})

if __name__ == '__main__':
    main()
