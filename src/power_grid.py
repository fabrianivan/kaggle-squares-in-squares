#!/usr/bin/env python3
"""Power Grid - Systematic grid search on parameters"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151)) + list(range(200, 301, 2))
print(f"Power Grid: {len(targets)} puzzles")

trust_grid = [0.18, 0.25, 0.32, 0.40, 0.48]
reg_grid = [1e-13, 5e-13, 1e-12, 5e-12, 1e-11]

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n}")
    
    for trust in trust_grid:
        for reg in reg_grid:
            for seed_idx in range(10):
                seed = np.random.randint(1e9)
                try:
                    cand = polish(best, seed=seed, rounds=4, max_seconds=10,
                                trust_start=trust, regularization=reg)
                    s = pg.side(cand)
                    if s < best_side:
                        best, best_side = cand, s
                        print(f"  t={trust:.2f},r={reg:.1e}: {s:.12f}")
                except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best

if wins:
    np.savez_compressed(f"output/power_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
