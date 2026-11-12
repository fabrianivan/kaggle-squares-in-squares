#!/usr/bin/env python3
"""
BASIN HOPPING OPTIMIZER - Escape local minima
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import json

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

def basin_hopping_optimize(n, p_base, n_hops=100):
    """Basin hopping to escape local minima"""
    try:
        L0 = pg.side(p_base)
        best_L = L0
        best_p = p_base.copy()
        current = best_p.copy()
        
        rng = np.random.default_rng(n)
        
        for hop in range(n_hops):
            # Large perturbation to hop to new basin
            hop_scale = 0.01 * (1 + hop/n_hops)
            candidate = current.copy()
            candidate[:, 0] += rng.normal(0, hop_scale, n)
            candidate[:, 1] += rng.normal(0, hop_scale, n)
            candidate[:, 2] += rng.uniform(-0.1, 0.1, n)
            candidate = pg.normalize(candidate)
            
            # Local optimization
            try:
                candidate, _, _ = reclosure.reclose(candidate, seed=hop, trust=0.4, tie=0.2, rounds=30, seconds=3.0)
                candidate, _, _ = polish.polish(candidate, seed=hop, rounds=60, max_seconds=3.0, trust_start=0.02)
                candidate = pg.repair(candidate, clearance=1e-10)
                
                if candidate is not None:
                    L_cand = pg.side(candidate)
                    
                    # Accept if better
                    if L_cand < best_L - 1e-11:
                        best_L = L_cand
                        best_p = candidate.copy()
                        current = candidate.copy()
                        print(f"    Hop {hop}: NEW BEST {L_cand:.12f}")
                    # Or accept with probability if not too worse
                    elif L_cand < best_L + 0.01:
                        if rng.random() < 0.3:
                            current = candidate.copy()
            except:
                pass
        
        if best_L < L0 - 1e-11:
            return (n, L0, best_L, best_p)
    except:
        pass
    return None

def main():
    print("=" * 80)
    print("BASIN HOPPING OPTIMIZER")
    print("=" * 80)
    
    baseline_path = 'output/submission_22.251122.csv'
    df = pd.read_csv(baseline_path)
    
    puzzles = []
    for n in range(300, 601, 5):  # Every 5th puzzle
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            puzzles.append((n, p))
    
    print(f"\nTargeting {len(puzzles)} puzzles with basin hopping\n")
    
    wins = []
    for i, (n, p) in enumerate(puzzles):
        print(f"[{i+1}/{len(puzzles)}] Basin hopping n={n}...")
        result = basin_hopping_optimize(n, p, n_hops=100)
        if result is not None:
            wins.append(result)
    
    print(f"\nBasin hopping: {len(wins)} wins")
    if wins:
        np.savez('output/basin_wins.npz', **{str(n): p for n, _, _, p in wins})

if __name__ == '__main__':
    main()
