#!/usr/bin/env python3
"""
GRASP (Greedy Randomized Adaptive Search Procedure) Optimizer
Constructs solutions greedily with randomization, then improves with local search
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def grasp_iteration(n, baseline_packing, alpha=0.3):
    """One GRASP iteration: construct + local search"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    # Phase 1: Greedy randomized construction
    # Start from baseline but add randomization
    constructed = baseline_packing.copy()
    
    # Random perturbation with greedy bias
    perturbation_strength = alpha * 0.05
    constructed[:, :2] += np.random.randn(n, 2) * perturbation_strength
    constructed[:, 2] += np.random.randn(n) * alpha * 10  # rotation
    constructed = pg.normalize(pg.repair(constructed))
    
    # Phase 2: Local search - alternate between two methods
    best = constructed
    best_side = pg.side(best)
    
    for local_iter in range(3):
        seed = np.random.randint(1e9)
        
        # Try polish
        try:
            candidate = polish(best, seed=seed, rounds=3, max_seconds=20,
                             trust_start=0.25 + 0.2*np.random.random(),
                             regularization=1e-12 * (0.1 + np.random.random()))
            cand_side = pg.side(candidate)
            if cand_side < best_side:
                best = candidate
                best_side = cand_side
        except:
            pass
        
        # Try reclose
        try:
            candidate = reclose(best, seed=seed+1,
                              trust=0.15 + 0.3*np.random.random(),
                              tie=0.18 + 0.2*np.random.random(),
                              rounds=3, seconds=20)
            cand_side = pg.side(candidate)
            if cand_side < best_side:
                best = candidate
                best_side = cand_side
        except:
            pass
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("GRASP OPTIMIZER")
    print("=" * 80)
    
    # Target 200 puzzles with multiple GRASP iterations each
    targets = list(range(2, 101)) + list(range(150, 401, 2)) + list(range(500, 701, 5))
    print(f"Targeting {len(targets)} puzzles with GRASP")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['squares']))
        baseline_side = pg.side(baseline_packing)
        
        best = baseline_packing
        best_side = baseline_side
        
        # Multiple GRASP iterations
        num_iterations = 25 if n < 100 else 20
        
        for grasp_iter in range(num_iterations):
            # Vary alpha for diversity
            alpha = 0.2 + 0.4 * (grasp_iter / num_iterations)
            
            candidate, cand_side = grasp_iteration(n, baseline_packing, alpha)
            
            if cand_side < best_side:
                best = candidate
                best_side = cand_side
                print(f"  n={n}: GRASP iter {grasp_iter} → {best_side:.12f}")
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        
        if idx % 20 == 0:
            print(f">>> {len(wins)} wins, {(time.time()-start_time)/60:.1f}m elapsed")
    
    if wins:
        out_path = f"output/grasp_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'squares'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path}")
    
    print(f"\nTotal: {(time.time()-start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
