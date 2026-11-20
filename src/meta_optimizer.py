#!/usr/bin/env python3
"""
Meta-Optimizer: Learns which optimization methods work best for which puzzles
Then applies the best method to each puzzle
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from pathlib import Path
import time
from src.tools import packing_geometry as pg
from collections import defaultdict

def quick_test_methods(n, baseline_packing, time_limit=30):
    """
    Quickly test multiple methods and return which works best for this puzzle
    """
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    methods = [
        ('polish_tight', lambda: polish(baseline_packing, seed=42, rounds=3, 
                                       max_seconds=time_limit//4, trust_start=0.2, regularization=1e-12)),
        ('polish_loose', lambda: polish(baseline_packing, seed=43, rounds=3,
                                       max_seconds=time_limit//4, trust_start=0.5, regularization=1e-10)),
        ('reclose_tight', lambda: reclose(baseline_packing, seed=44, trust=0.15, 
                                         tie=0.2, rounds=3, seconds=time_limit//4)),
        ('reclose_loose', lambda: reclose(baseline_packing, seed=45, trust=0.45,
                                         tie=0.35, rounds=3, seconds=time_limit//4)),
    ]
    
    baseline_side = pg.side(baseline_packing)
    results = []
    
    for name, method_fn in methods:
        try:
            start = time.time()
            result = method_fn()
            elapsed = time.time() - start
            result_side = pg.side(result)
            improvement = baseline_side - result_side
            
            results.append({
                'method': name,
                'side': result_side,
                'improvement': improvement,
                'time': elapsed,
                'packing': result
            })
        except Exception as e:
            continue
    
    if not results:
        return None, baseline_packing
    
    # Find best method
    best = max(results, key=lambda x: x['improvement'])
    return best['method'], best['packing']

def deep_optimize_with_method(n, baseline_packing, method_name, time_limit=180):
    """
    Apply the identified best method intensively
    """
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    
    # Parse method type
    if 'polish' in method_name:
        is_polish = True
        is_tight = 'tight' in method_name
    else:
        is_polish = False
        is_tight = 'tight' in method_name
    
    # Run multiple seeds with the winning method
    num_seeds = 15
    
    for seed_idx in range(num_seeds):
        seed = np.random.randint(1e9)
        
        try:
            if is_polish:
                trust = 0.2 if is_tight else 0.5
                reg = 1e-12 if is_tight else 1e-10
                candidate = polish(best, seed=seed, rounds=5, 
                                 max_seconds=time_limit//num_seeds,
                                 trust_start=trust, regularization=reg)
            else:
                trust = 0.15 if is_tight else 0.45
                tie = 0.2 if is_tight else 0.35
                candidate = reclose(best, seed=seed, trust=trust, tie=tie,
                                  rounds=4, seconds=time_limit//num_seeds)
            
            candidate_side = pg.side(candidate)
            if candidate_side < best_side:
                best = candidate
                best_side = candidate_side
                
        except Exception as e:
            continue
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("META-OPTIMIZER: Learn then Apply")
    print("=" * 80)
    print(f"Baseline: {baseline_path}")
    
    # Target diverse set
    targets = list(range(2, 201)) + list(range(300, 601, 5)) + list(range(700, 1001, 10))
    print(f"Targeting {len(targets)} puzzles")
    print("Phase 1: Quick learning (which method works best)")
    print("Phase 2: Deep optimization with best method")
    
    wins = {}
    method_stats = defaultdict(int)
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['packing']))
        baseline_side = pg.side(baseline_packing)
        
        # Phase 1: Quick test (30s)
        print(f"  Phase 1: Testing methods...")
        best_method, quick_result = quick_test_methods(n, baseline_packing, time_limit=30)
        
        if best_method is None:
            print(f"  All methods failed")
            continue
        
        print(f"  Best method: {best_method}")
        method_stats[best_method] += 1
        
        # Phase 2: Deep optimization (3 min)
        print(f"  Phase 2: Deep optimization with {best_method}...")
        best, best_side = deep_optimize_with_method(n, quick_result, best_method, time_limit=180)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        else:
            print(f"  No improvement")
        
        if idx % 20 == 0:
            elapsed = time.time() - start_time
            print(f"\n>>> Progress: {len(wins)} wins, {elapsed/60:.1f}m elapsed")
            print(f">>> Method stats: {dict(method_stats)}")
    
    # Save results
    if wins:
        out_path = f"output/meta_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        df_new = df.copy()
        for n, packing in wins.items():
            df_new.loc[df_new['n'] == n, 'packing'] = str(packing.tolist())
        
        from src.metric.metric import score as compute_score
        new_score = compute_score(df_new, 'n')
        sub_path = f"output/submission_{new_score:.6f}.csv"
        df_new.to_csv(sub_path, index=False)
        print(f"✓ New submission: {sub_path} (score={new_score:.12f})")
    else:
        print("\nNo improvements found")
    
    print(f"\nFinal method statistics:")
    for method, count in sorted(method_stats.items(), key=lambda x: -x[1]):
        print(f"  {method}: {count} times")
    
    print(f"\nTotal time: {(time.time() - start_time)/60:.1f} minutes")

if __name__ == "__main__":
    main()
