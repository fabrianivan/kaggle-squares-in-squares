#!/usr/bin/env python3
"""Ultra Random Restart - Pure brute force with massive random trials"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

def ultra_random(n, baseline, num_trials=200):
    """Pure random restart with maximum trials"""
    best = baseline.copy()
    best_side = pg.side(best)
    
    for trial in range(num_trials):
        seed = np.random.randint(1e9)
        
        if trial % 2 == 0:
            # Random polish parameters
            trust = 0.1 + 0.5 * np.random.random()
            reg = 10 ** (-14 + 2 * np.random.random())
            try:
                cand = polish(best, seed=seed, rounds=4, max_seconds=10,
                            trust_start=trust, regularization=reg)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"    n={n} trial{trial}: {s:.12f}")
            except: pass
        else:
            # Random reclose parameters
            trust = 0.1 + 0.5 * np.random.random()
            tie = 0.1 + 0.4 * np.random.random()
            try:
                cand = reclose(best, seed=seed, trust=trust, tie=tie,
                             rounds=4, seconds=10)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"    n={n} trial{trial}: {s:.12f}")
            except: pass
    
    return best, best_side

# Load and process
df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 301)) + list(range(400, 701, 2))
print(f"Ultra Random Restart: {len(targets)} puzzles, 200 trials each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    baseline_side = pg.side(baseline)
    print(f"\n[{idx}/{len(targets)}] n={n}")
    
    best, best_side = ultra_random(n, baseline, 200)
    
    if best_side < baseline_side - 1e-12:
        wins[n] = best
        print(f"  ★ WIN: {baseline_side:.12f} → {best_side:.12f}")

if wins:
    np.savez_compressed(f"output/ultra_random_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ Score: {s:.12f}")
