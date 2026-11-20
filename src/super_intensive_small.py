#!/usr/bin/env python3
"""
Super Intensive Small Puzzle Optimizer
Extreme focus on n=2-100 where variance is highest
"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg

def ultra_optimize_small(n, baseline, max_time=600):
    """10 minutes per small puzzle with everything we have"""
    from src.tools.cpu_axis_reclosure import reclose
    from src.tools.cpu_contact_polish import polish
    
    best = baseline.copy()
    best_side = pg.side(best)
    start = time.time()
    
    iteration = 0
    while time.time() - start < max_time:
        iteration += 1
        seed = np.random.randint(1e9)
        
        # Ultra-fine parameter sweep
        trust_values = np.linspace(0.15, 0.55, 9)
        tie_values = np.linspace(0.15, 0.38, 8)
        reg_values = [1e-13, 5e-13, 1e-12, 5e-12, 1e-11]
        
        # Try polish with random params
        trust = np.random.choice(trust_values)
        reg = np.random.choice(reg_values)
        
        try:
            result = polish(best, seed=seed, rounds=6, max_seconds=20,
                          trust_start=trust, regularization=reg)
            side = pg.side(result)
            if side < best_side:
                best = result
                best_side = side
                print(f"  n={n} iter{iteration}: polish improved → {side:.12f}")
        except:
            pass
        
        # Try reclose with random params
        trust = np.random.choice(trust_values[:7])  # 0.15-0.48
        tie = np.random.choice(tie_values)
        
        try:
            result = reclose(best, seed=seed+1, trust=trust, tie=tie,
                           rounds=5, seconds=20)
            side = pg.side(result)
            if side < best_side:
                best = result
                best_side = side
                print(f"  n={n} iter{iteration}: reclose improved → {side:.12f}")
        except:
            pass
    
    return best, best_side

def main():
    df = pd.read_csv("output/submission_final.csv")
    
    print("=" * 80)
    print("SUPER INTENSIVE SMALL PUZZLE OPTIMIZER")
    print("=" * 80)
    print("Strategy: 10 minutes per puzzle for n=2-100")
    
    targets = list(range(2, 101))
    print(f"Targeting {len(targets)} small puzzles")
    print(f"Expected runtime: ~16 hours")
    
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
        
        print(f"\n[{idx}/{len(targets)}] n={n} - Allocating 10 minutes...")
        baseline = packings[n]
        baseline_side = pg.side(baseline)
        
        best, best_side = ultra_optimize_small(n, baseline, max_time=600)
        
        if best_side < baseline_side - 1e-12:
            improvement = baseline_side - best_side
            wins[n] = best
            print(f"  ★★★ MAJOR WIN: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.2e})")
        else:
            print(f"  No improvement for n={n}")
        
        if idx % 10 == 0:
            elapsed = (time.time() - start_time) / 3600
            rate = idx / elapsed
            remaining = (len(targets) - idx) / rate
            print(f"\n>>> {len(wins)} wins, {elapsed:.1f}h elapsed, ~{remaining:.1f}h remaining")
    
    if wins:
        np.savez_compressed(f"output/small_intensive_wins_{len(wins)}.npz",
                           **{str(k): v for k, v in wins.items()})
        
        df_new = df.copy()
        for n, packing in wins.items():
            mask = df_new['n'] == n
            df_new.loc[mask, ['x', 'y', 'angle']] = packing
        
        from src.metric.metric import score
        new_score = score(df_new, 'n')
        df_new.to_csv(f"output/submission_{new_score:.6f}.csv", index=False)
        print(f"\n✓ Final score: {new_score:.12f}")

if __name__ == "__main__":
    main()
