#!/usr/bin/env python3
"""
Simulated Annealing Optimizer - More aggressive exploration
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
import time
import math

sys.path.insert(0, str(Path(__file__).parent / 'tools'))
import packing_geometry as pg

def simulated_annealing(n, p_base, seed, iterations=10000, T_start=0.1, T_end=0.001):
    """Simulated annealing with aggressive exploration"""
    rng = np.random.default_rng(seed)
    
    current = p_base.copy()
    current_L = pg.side(current)
    best = current.copy()
    best_L = current_L
    
    T = T_start
    alpha = (T_end / T_start) ** (1.0 / iterations)
    
    accepts = 0
    improvements = 0
    
    for i in range(iterations):
        # Generate candidate by perturbing
        scale = T * 0.05  # Scale perturbation with temperature
        candidate = current.copy()
        candidate[:, 0] += rng.normal(0, scale, n)
        candidate[:, 1] += rng.normal(0, scale, n)
        candidate[:, 2] += rng.normal(0, scale * 2, n)
        candidate = pg.normalize(candidate)
        
        # Repair and evaluate
        candidate = pg.repair(candidate, clearance=1e-9)
        if candidate is None:
            continue
            
        candidate_L = pg.side(candidate)
        delta_L = candidate_L - current_L
        
        # Accept if better, or with probability based on temperature
        if delta_L < 0 or rng.random() < np.exp(-delta_L / (T * current_L)):
            current = candidate
            current_L = candidate_L
            accepts += 1
            
            if candidate_L < best_L - 1e-10:
                best = candidate.copy()
                best_L = candidate_L
                improvements += 1
        
        T *= alpha
    
    return n, pg.side(p_base), best_L, best if best_L < pg.side(p_base) - 1e-10 else None, accepts, improvements

def optimize_puzzle(args):
    n, p_base, seed = args
    try:
        result = simulated_annealing(n, p_base, seed, iterations=50000)
        n, L0, L_best, p_best, accepts, improvements = result
        if p_best is not None:
            print(f"n={n}: {L0:.8f} -> {L_best:.8f} (gain={L0-L_best:.8f}, accepts={accepts}, improvements={improvements})")
            return (n, L0, L_best, p_best)
    except Exception as e:
        print(f"Error n={n}: {e}")
    return None

def main():
    print("=" * 80)
    print("SIMULATED ANNEALING OPTIMIZER")
    print("=" * 80)
    
    # Load baseline
    baseline = 'output/submission_final.csv'
    print(f"\nLoading {baseline}...")
    df = pd.read_csv(baseline)
    
    # Get top 100 worst puzzles by waste
    puzzles = []
    for n in range(1, 1001):
        g = df[df['n'] == n].sort_values('square_id')
        if len(g) > 0:
            p = g[['x', 'y', 'angle']].to_numpy(float)
            L = pg.side(p)
            waste = L / math.sqrt(n) - 1
            puzzles.append((waste, n, p))
    
    puzzles.sort(reverse=True)
    targets = [(n, p, i*7) for i, (waste, n, p) in enumerate(puzzles[:100])]
    
    print(f"Targeting {len(targets)} puzzles with 50k iterations each...")
    print(f"First 10 targets: {[n for _, n, _ in puzzles[:10]]}")
    
    # Run optimization
    wins = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(optimize_puzzle, args) for args in targets]
        for future in futures:
            result = future.result()
            if result is not None:
                wins.append(result)
    
    print(f"\n{'=' * 80}")
    print(f"FOUND {len(wins)} IMPROVEMENTS!")
    
    if wins:
        # Save wins
        import numpy as np
        patch_data = {str(n): p for n, L0, L_best, p in wins}
        np.savez('output/sa_wins.npz', **patch_data)
        print(f"Saved to output/sa_wins.npz")
        
        total_gain = sum(L0 - L_best for n, L0, L_best, p in wins)
        print(f"Total gain: {total_gain:.10f}")
    else:
        print("No improvements found")

if __name__ == '__main__':
    main()
