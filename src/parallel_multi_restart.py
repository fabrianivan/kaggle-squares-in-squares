#!/usr/bin/env python3
"""
Parallel Multi-Restart - Run multiple independent restarts simultaneously
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def single_restart(n, baseline, seed, method='polish'):
    """One restart with one method"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    try:
        if method == 'polish':
            trust = 0.2 + 0.3 * np.random.random()
            reg = 10 ** (-13 + np.random.random())
            result = polish(baseline, seed=seed, rounds=5, max_seconds=30,
                          trust_start=trust, regularization=reg)
        else:  # reclose
            trust = 0.15 + 0.35 * np.random.random()
            tie = 0.15 + 0.25 * np.random.random()
            result = reclose(baseline, seed=seed, trust=trust, tie=tie,
                           rounds=5, seconds=30)
        return result, pg.side(result)
    except:
        return baseline, pg.side(baseline)

def parallel_optimize(n, baseline, num_restarts=50):
    """Run many independent restarts and pick best"""
    baseline_side = pg.side(baseline)
    best = baseline
    best_side = baseline_side
    
    print(f"  n={n}: {num_restarts} parallel restarts...")
    
    for i in range(num_restarts):
        seed = np.random.randint(1e9)
        method = 'polish' if i % 2 == 0 else 'reclose'
        
        result, side = single_restart(n, best, seed, method)
        
        if side < best_side:
            best = result
            best_side = side
            improvement = baseline_side - best_side
            print(f"    Restart {i}: {method} → {side:.12f} (Δ={improvement:.2e})")
    
    return best, best_side

def main():
    df = pd.read_csv("output/submission_final.csv")
    
    print("=" * 80)
    print("PARALLEL MULTI-RESTART OPTIMIZER")
    print("=" * 80)
    print("Strategy: 50-100 independent restarts per puzzle")
    
    # Target 400 diverse puzzles
    targets = (list(range(2, 151)) + 
               list(range(200, 501, 2)) + 
               list(range(600, 901, 3)))
    print(f"Targeting {len(targets)} puzzles")
    
    packings = {}
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            packings[n] = rows[['x', 'y', 'angle']].values
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        if n not in packings:
            continue
        
        print(f"\n[{idx}/{len(targets)}] n={n}")
        baseline = packings[n]
        baseline_side = pg.side(baseline)
        
        num_restarts = 100 if n < 100 else 50
        best, best_side = parallel_optimize(n, baseline, num_restarts)
        
        if best_side < baseline_side - 1e-12:
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f}")
        
        if idx % 25 == 0:
            print(f">>> {len(wins)} wins, {(time.time()-start_time)/60:.1f}m elapsed")
    
    if wins:
        np.savez_compressed(f"output/parallel_wins_{len(wins)}.npz",
                           **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, packing in wins.items():
            mask = df_new['n'] == n
            df_new.loc[mask, ['x', 'y', 'angle']] = packing
        
        from src.metric.metric import score
        new_score = score(df_new, 'n')
        df_new.to_csv(f"output/submission_{new_score:.6f}.csv", index=False)
        print(f"\n✓ Score: {new_score:.12f}")

if __name__ == "__main__":
    main()
