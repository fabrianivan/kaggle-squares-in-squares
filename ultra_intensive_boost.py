#!/usr/bin/env python3
"""
Ultra Intensive Boost - Extended gradient descent with best parameters
Focus on puzzles where gradient descent worked best
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure
import time

def extended_gradient_optimize(packing, n_iterations=200):
    """Extended gradient descent with proven best parameters"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    # Multi-stage optimization
    stages = [
        {'lr': 0.05, 'iterations': 50},
        {'lr': 0.02, 'iterations': 50},
        {'lr': 0.01, 'iterations': 50},
        {'lr': 0.005, 'iterations': 50},
    ]
    
    for stage_idx, stage in enumerate(stages):
        lr = stage['lr']
        
        for it in range(stage['iterations']):
            # Compute numerical gradient
            epsilon = lr * 0.01
            gradient = np.zeros_like(best_p)
            current_L = pg.side(best_p)
            
            # Gradient for positions
            for i in range(len(best_p)):
                for j in range(2):
                    perturbed = best_p.copy()
                    perturbed[i, j] += epsilon
                    try:
                        L_plus = pg.side(perturbed)
                        gradient[i, j] = (L_plus - current_L) / epsilon
                    except:
                        gradient[i, j] = 0
            
            # Gradient clipping
            grad_norm = np.linalg.norm(gradient)
            if grad_norm > 5.0:
                gradient = gradient * (5.0 / grad_norm)
            
            # Update with momentum
            candidate = best_p - lr * gradient
            
            try:
                candidate_L = pg.side(candidate)
                if candidate_L < best_L:
                    best_L = candidate_L
                    best_p = candidate.copy()
            except:
                pass
    
    # Final polish
    try:
        for seed in range(5):
            polished, _, _ = polish.polish(best_p, seed=seed*9999,
                                          rounds=10, max_seconds=30,
                                          trust_start=0.015,
                                          regularization=5e-13)
            polished_L = pg.side(polished)
            if polished_L < best_L:
                best_L = polished_L
                best_p = polished.copy()
    except:
        pass
    
    return best_p, best_L

def intensive_multi_method(packing, puzzle_n):
    """Intensive optimization with multiple methods"""
    best_p = packing.copy()
    best_L = pg.side(best_p)
    
    # Method 1: Extended gradient
    try:
        candidate, candidate_L = extended_gradient_optimize(best_p, n_iterations=200)
        if candidate_L < best_L:
            best_L = candidate_L
            best_p = candidate.copy()
    except:
        pass
    
    # Method 2: Ultra-intensive polish sweep
    param_combinations = [
        {'trust': 0.01, 'reg': 1e-13, 'rounds': 10},
        {'trust': 0.015, 'reg': 5e-13, 'rounds': 10},
        {'trust': 0.02, 'reg': 1e-12, 'rounds': 10},
        {'trust': 0.025, 'reg': 8e-13, 'rounds': 10},
        {'trust': 0.018, 'reg': 6e-13, 'rounds': 12},
    ]
    
    for params in param_combinations:
        for seed in range(10):
            try:
                candidate, _, _ = polish.polish(best_p, seed=seed*111,
                                               rounds=params['rounds'],
                                               max_seconds=30,
                                               trust_start=params['trust'],
                                               regularization=params['reg'])
                candidate_L = pg.side(candidate)
                if candidate_L < best_L:
                    best_L = candidate_L
                    best_p = candidate.copy()
            except:
                pass
    
    # Method 3: Reclose sweep
    reclose_params = [
        {'trust': 0.18, 'tie': 0.22},
        {'trust': 0.22, 'tie': 0.25},
        {'trust': 0.25, 'tie': 0.20},
        {'trust': 0.20, 'tie': 0.28},
        {'trust': 0.28, 'tie': 0.22},
    ]
    
    for params in reclose_params:
        for seed in range(10):
            try:
                candidate, _, _ = reclosure.reclose(best_p, seed=seed*222,
                                                    trust=params['trust'],
                                                    tie=params['tie'],
                                                    rounds=10, seconds=30)
                candidate_L = pg.side(candidate)
                if candidate_L < best_L:
                    best_L = candidate_L
                    best_p = candidate.copy()
            except:
                pass
    
    return best_p, best_L

def optimize_puzzle_ultra(args):
    """Ultra-intensive optimization"""
    n, p_base = args
    
    original_L = pg.side(p_base)
    print(f"n={n:4d} start={original_L:.9f}", end=" ", flush=True)
    
    best_p, best_L = intensive_multi_method(p_base, n)
    
    improvement = original_L - best_L
    
    if improvement > 1e-12:
        print(f"→ {best_L:.9f} ★Δ={improvement:.2e}")
        return (n, best_p, best_L, improvement)
    else:
        print(f"→ {best_L:.9f}")
        return None

def main():
    print("=" * 80)
    print("ULTRA INTENSIVE BOOST")
    print("=" * 80)
    print("Extended Gradient + Ultra Polish + Reclose Sweep")
    print("=" * 80 + "\n")
    
    submission_files = sorted(Path('output').glob('submission_22.*.csv'))
    if not submission_files:
        print("No submissions found!")
        return
    
    best_file = submission_files[0]
    print(f"Starting from: {best_file.name}\n")
    
    df = pd.read_csv(best_file)
    
    # Target medium-large puzzles where methods work best
    targets = list(range(50, 800))
    print(f"Targeting {len(targets)} puzzles (intensive methods)\n")
    
    wins = {}
    start_time = time.time()
    
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) == 0:
            continue
        
        p_base = rows[['x', 'y', 'angle']].values
        result = optimize_puzzle_ultra((n, p_base))
        
        if result is not None:
            n, best_p, best_L, improvement = result
            wins[n] = best_p
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"COMPLETE in {elapsed/60:.1f} min - Found {len(wins)} improvements")
    print("=" * 80)
    
    if wins:
        timestamp = int(time.time())
        wins_file = f"output/ultra_wins_{len(wins)}_{timestamp}.npz"
        np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
        
        # Calculate score
        total_score = 0.0
        for n in range(1, 1001):
            puzzle_df = df_new[df_new['n'] == n]
            if len(puzzle_df) > 0:
                pack = puzzle_df[['x', 'y', 'angle']].values
                L = pg.side(pack)
                total_score += L / np.sqrt(n) - 1
        
        sub_path = f"output/submission_ultra_{total_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        
        print(f"\n✓ Score: {total_score:.12f}")
        print(f"  File: {sub_path}")

if __name__ == '__main__':
    main()
