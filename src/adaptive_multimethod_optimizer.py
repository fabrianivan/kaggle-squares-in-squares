#!/usr/bin/env python3
"""
Adaptive Multi-Method Optimizer
Intelligently switches between optimization methods based on puzzle characteristics
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from pathlib import Path
import time
from src.tools import packing_geometry as pg

def adaptive_optimize_puzzle(n, baseline_packing, max_time=120):
    """
    Adaptively choose optimization strategy based on puzzle size and characteristics
    """
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    
    # Puzzle characteristics
    density = n / (best_side ** 2)
    
    # Small puzzles (n < 100): intensive random restarts
    if n < 100:
        strategies = [
            ('polish', lambda: polish(best, seed=np.random.randint(1e9), rounds=8, 
                                     max_seconds=max_time//3, trust_start=0.4, regularization=1e-11)),
            ('reclose_tight', lambda: reclose(best, seed=np.random.randint(1e9), 
                                             trust=0.15, tie=0.25, rounds=6, seconds=max_time//3)),
            ('reclose_loose', lambda: reclose(best, seed=np.random.randint(1e9),
                                             trust=0.5, tie=0.35, rounds=6, seconds=max_time//3)),
        ]
    # Medium puzzles (100-300): balanced approach
    elif n < 300:
        strategies = [
            ('polish_medium', lambda: polish(best, seed=np.random.randint(1e9), rounds=6,
                                           max_seconds=max_time//2, trust_start=0.35, regularization=5e-12)),
            ('reclose_balanced', lambda: reclose(best, seed=np.random.randint(1e9),
                                                trust=0.3, tie=0.28, rounds=5, seconds=max_time//2)),
        ]
    # Large puzzles (300+): focus on global structure
    else:
        strategies = [
            ('polish_large', lambda: polish(best, seed=np.random.randint(1e9), rounds=4,
                                          max_seconds=max_time, trust_start=0.25, regularization=1e-12)),
            ('reclose_global', lambda: reclose(best, seed=np.random.randint(1e9),
                                              trust=0.25, tie=0.22, rounds=4, seconds=max_time)),
        ]
    
    # Try each strategy
    for name, strategy_fn in strategies:
        try:
            candidate = strategy_fn()
            candidate_side = pg.side(candidate)
            if candidate_side < best_side:
                best = candidate
                best_side = candidate_side
                print(f"  n={n}: {name} improved to {best_side:.12f}")
        except Exception as e:
            print(f"  n={n}: {name} failed: {e}")
            continue
    
    return best, best_side

def main():
    baseline_path = "output/submission_final.csv"
    df = pd.read_csv(baseline_path)
    
    print("=" * 80)
    print("ADAPTIVE MULTI-METHOD OPTIMIZER")
    print("=" * 80)
    print(f"Baseline: {baseline_path}")
    
    # Target high-value puzzles across all sizes
    # Mix of small (high variance), medium (balance), large (big impact)
    small_targets = list(range(2, 51, 3))  # Every 3rd from 2-50
    medium_targets = list(range(101, 301, 10))  # Every 10th from 101-300
    large_targets = list(range(500, 1001, 25))  # Every 25th from 500-1000
    
    targets = small_targets + medium_targets + large_targets
    print(f"Targeting {len(targets)} puzzles adaptively")
    print(f"Small: {len(small_targets)}, Medium: {len(medium_targets)}, Large: {len(large_targets)}")
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] n={n}")
        
        baseline_row = df[df['n'] == n].iloc[0]
        baseline_packing = np.array(eval(baseline_row['packing']))
        baseline_side = pg.side(baseline_packing)
        
        # Adaptive time allocation
        if n < 100:
            max_time = 180  # 3 min for small
        elif n < 300:
            max_time = 240  # 4 min for medium
        else:
            max_time = 300  # 5 min for large
        
        best, best_side = adaptive_optimize_puzzle(n, baseline_packing, max_time)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.12e})")
        else:
            print(f"  No improvement for n={n}")
        
        # Progress report every 10 puzzles
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed
            remaining = (len(targets) - idx) / rate
            print(f"\n>>> Progress: {idx}/{len(targets)}, {len(wins)} wins, "
                  f"{elapsed/60:.1f}m elapsed, ~{remaining/60:.1f}m remaining")
    
    # Save results
    if wins:
        out_path = f"output/adaptive_wins_{len(wins)}.npz"
        np.savez_compressed(out_path, **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} wins to {out_path}")
        
        # Create submission
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
    
    total_time = time.time() - start_time
    print(f"\nTotal time: {total_time/60:.1f} minutes")

if __name__ == "__main__":
    main()
