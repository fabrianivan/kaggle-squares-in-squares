#!/usr/bin/env python3
"""Turbo Sweep - Fast parameter sweep across many puzzles"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 401)) + list(range(500, 801, 3))
print(f"Turbo Sweep: {len(targets)} puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n}")
    
    # Fast sweep: 30 quick attempts
    for i in range(30):
        seed = np.random.randint(1e9)
        try:
            trust = [0.2, 0.3, 0.4][i % 3]
            cand = polish(best, seed=seed, rounds=3, max_seconds=8,
                         trust_start=trust, regularization=1e-12)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"  Improved: {s:.12f}")
        except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best
        print(f"  ★ WIN!")

if wins:
    np.savez_compressed(f"output/turbo_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}")
