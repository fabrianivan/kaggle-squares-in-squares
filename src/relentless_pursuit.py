#!/usr/bin/env python3
"""Relentless Pursuit - Never give up on any puzzle"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 501))
print(f"Relentless Pursuit: {len(targets)} puzzles, 60 attempts each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n}")
    
    attempts = 0
    while attempts < 60:
        seed = np.random.randint(1e9)
        attempts += 1
        
        # Alternate between polish and reclose
        if attempts % 2 == 0:
            trust = 0.2 + 0.3 * (attempts / 60)
            reg = 10 ** (-13 + 0.5 * (attempts / 60))
            try:
                cand = polish(best, seed=seed, rounds=4, max_seconds=12,
                            trust_start=trust, regularization=reg)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"  Attempt {attempts}: {s:.12f}")
            except: pass
        else:
            trust = 0.2 + 0.25 * (attempts / 60)
            tie = 0.2 + 0.15 * (attempts / 60)
            try:
                cand = reclose(best, seed=seed, trust=trust, tie=tie, rounds=4, seconds=12)
                s = pg.side(cand)
                if s < best_side:
                    best, best_side = cand, s
                    print(f"  Attempt {attempts}: {s:.12f}")
            except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best

if wins:
    np.savez_compressed(f"output/relentless_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
