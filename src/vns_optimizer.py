#!/usr/bin/env python3
"""
Variable Neighborhood Search (VNS) Optimizer
Systematically changes neighborhood structures to escape local optima
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def vns_optimize_puzzle(n, baseline_packing, max_time=180):
    """VNS with multiple neighborhood structures"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    
    # Define neighborhood structures (different optimization strategies)
    neighborhoods = [
        # (name, method, params)
        ('polish_ultra_tight', polish, {'rounds': 4, 'trust_start': 0.15, 'regularization': 1e-13}),
        ('polish_tight', polish, {'rounds': 5, 'trust_start': 0.25, 'regularization': 1e-12}),
        ('polish_medium', polish, {'rounds': 5, 'trust_start': 0.35, 'regularization': 5e-12}),
        ('polish_loose', polish, {'rounds': 5, 'trust_start': 0.5, 'regularization': 1e-11}),
        ('reclose_tight', reclose, {'trust': 0.15, 'tie': 0.18, 'rounds': 4}),
        ('reclose_medium', reclose, {'trust': 0.28, 'tie': 0.26, 'rounds': 4}),
        ('reclose_loose', reclose, {'trust': 0.42, 'tie': 0.34, 'rounds': 4}),
    ]
    
    start_time = time.time()
    k = 0  # Current neighborhood index
    
    while time.time() - start_time < max_time and k < len(neighborhoods):
        name, method, params = neighborhoods[k]
        
        # Search in neighborhood k
        improved = False
        for attempt in range(3):  # 3 attempts per neighborhood
            try:
                seed = np.random.randint(1e9)
                
                if method == polish:
                    candidate = polish(best, seed=seed, 
                                     max_seconds=max_time//len(neighborhoods)//3,
                                     **params)
                else:  # reclose
                    candidate = reclose(best, seed=seed, 
                                      seconds=max_time//len(neighborhoods)//3,
                                      **params)
                
                candidate_side = pg.side(candidate)
                
                if candidate_side < best_side - 1e-12:
                    best = candidate
                    best_side = candidate_side
                    improved = True
                    print(f"  n={n}: VNS {name} improved to {best_side:.12f}")
                    k = 0  # Reset to first neighborhood
                    break
            except:
                continue
        
        if not improved:
            k += 1  # Move to next neighborhood
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("VARIABLE NEIGHBORHOOD SEARCH OPTIMIZER")
    print("=" * 80)
    
    # Target 300 diverse puzzles
    targets = (list(range(2, 151)) + 
               list(range(200, 401, 2)) + 
               list(range(500, 801, 3)) +
               list(range(850, 1001, 5)))
    
    print(f"Targeting {len(targets)} puzzles with VNS")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['squares']))
        baseline_side = pg.side(baseline_packing)
        
        # More time for small puzzles
        max_time = 240 if n < 100 else 180
        
        best, best_side = vns_optimize_puzzle(n, baseline_packing, max_time)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        
        if idx % 15 == 0:
            print(f">>> {len(wins)} wins, {(time.time()-start_time)/60:.1f}m elapsed")
    
    if wins:
        out_path = f"output/vns_wins_{len(wins)}.npz"
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
