#!/usr/bin/env python3
"""Deep Dive - Intense focus on hardest puzzles"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 51)) + list(range(100, 151))
print(f"Deep Dive: {len(targets)} puzzles, 5 min each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n} - 5min deep dive")
    
    import time
    start = time.time()
    iteration = 0
    while time.time() - start < 300:  # 5 minutes
        iteration += 1
        seed = np.random.randint(1e9)
        
        if iteration % 2 == 0:
            trust = 0.15 + 0.4*np.random.random()
            reg = 10**(-13 + 1.5*np.random.random())
            try:
                cand = polish(best, seed=seed, rounds=5, max_seconds=20,
                            trust_start=trust, regularization=reg)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"  Iter {iteration}: {s:.12f}")
            except: pass
        else:
            trust, tie = 0.15 + 0.4*np.random.random(), 0.15 + 0.3*np.random.random()
            try:
                cand = reclose(best, seed=seed, trust=trust, tie=tie, rounds=5, seconds=20)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"  Iter {iteration}: {s:.12f}")
            except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best
        print(f"  ★★ WIN!")

if wins:
    np.savez_compressed(f"output/deep_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
