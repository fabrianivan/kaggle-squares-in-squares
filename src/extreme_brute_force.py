#!/usr/bin/env python3
"""
Extreme Brute Force - Maximum intensity on most promising puzzles
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def extreme_optimize_puzzle(n, baseline_packing, max_seeds=100):
    """Brute force with massive seed count"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline_packing.copy()
    best_side = pg.side(best)
    
    print(f"  n={n}: Running {max_seeds} seeds with both methods...")
    
    for seed_idx in range(max_seeds):
        seed = np.random.randint(1e9)
        
        # Method 1: Polish
        for trust in [0.18, 0.25, 0.35, 0.48]:
            for reg_exp in [-13, -12, -11]:
                try:
                    reg = 10 ** reg_exp
                    result = polish(best, seed=seed, rounds=5, max_seconds=15,
                                  trust_start=trust, regularization=reg)
                    side = pg.side(result)
                    if side < best_side:
                        improvement = best_side - side
                        best = result
                        best_side = side
                        print(f"    Seed {seed_idx}: polish(t={trust:.2f},r={reg:.1e}) → {side:.12f} (Δ={improvement:.2e})")
                except:
                    pass
        
        # Method 2: Reclose
        for trust in [0.15, 0.25, 0.35, 0.45]:
            for tie in [0.18, 0.25, 0.32]:
                try:
                    result = reclose(best, seed=seed, trust=trust, tie=tie,
                                   rounds=4, seconds=15)
                    side = pg.side(result)
                    if side < best_side:
                        improvement = best_side - side
                        best = result
                        best_side = side
                        print(f"    Seed {seed_idx}: reclose(t={trust:.2f},tie={tie:.2f}) → {side:.12f} (Δ={improvement:.2e})")
                except:
                    pass
    
    return best, best_side

def main():
    df = pd.read_csv("output/submission_final.csv")
    
    print("=" * 80)
    print("EXTREME BRUTE FORCE OPTIMIZER")
    print("=" * 80)
    print("Strategy: 100 seeds × 7 param combos = 700 attempts per puzzle")
    
    # Focus on small/medium puzzles where improvements are most likely
    targets = list(range(2, 201)) + list(range(250, 401, 2))
    print(f"Targeting {len(targets)} puzzles (n=2-400)")
    
    # Group by n to get packings
    packings = {}
    for n in targets:
        rows = df[df['n'] == n]
        if len(rows) > 0:
            packing = rows[['x', 'y', 'angle']].values
            packings[n] = packing
    
    wins = {}
    start_time = time.time()
    
    for idx, n in enumerate(targets, 1):
        if n not in packings:
            continue
        
        print(f"\n[{idx}/{len(targets)}] n={n}")
        baseline = packings[n]
        baseline_side = pg.side(baseline)
        
        max_seeds = 150 if n < 100 else 100
        best, best_side = extreme_optimize_puzzle(n, baseline, max_seeds)
        
        if best_side < baseline_side - 1e-12:
            wins[n] = best
            print(f"  ★★★ WIN: {baseline_side:.12f} → {best_side:.12f}")
        
        if idx % 20 == 0:
            elapsed = (time.time() - start_time) / 60
            print(f"\n>>> {len(wins)} wins found in {elapsed:.1f} minutes")
    
    if wins:
        np.savez_compressed(f"output/brute_wins_{len(wins)}.npz",
                           **{str(k): v for k, v in wins.items()})
        print(f"\n✓ Saved {len(wins)} improvements")
        
        # Create submission
        df_new = df.copy()
        for n, packing in wins.items():
            mask = df_new['n'] == n
            df_new.loc[mask, ['x', 'y', 'angle']] = packing
        
        from src.metric.metric import score
        new_score = score(df_new, 'n')
        df_new.to_csv(f"output/submission_{new_score:.6f}.csv", index=False)
        print(f"✓ New submission: {new_score:.12f}")

if __name__ == "__main__":
    main()
