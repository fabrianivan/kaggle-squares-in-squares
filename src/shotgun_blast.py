#!/usr/bin/env python3
"""Shotgun Blast - Maximum diversity in approaches"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 301)) + list(range(400, 601, 3))
print(f"Shotgun Blast: {len(targets)} puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n}")
    
    # Blast 1: Ultra tight
    for i in range(15):
        seed = np.random.randint(1e9)
        try:
            cand = polish(best, seed=seed, rounds=5, max_seconds=10,
                         trust_start=0.12, regularization=1e-14)
            s = pg.side(cand)
            if s < best_side: best, best_side = cand, s
        except: pass
    
    # Blast 2: Ultra loose
    for i in range(15):
        seed = np.random.randint(1e9)
        try:
            cand = reclose(best, seed=seed, trust=0.55, tie=0.4, rounds=4, seconds=10)
            s = pg.side(cand)
            if s < best_side: best, best_side = cand, s
        except: pass
    
    # Blast 3: Random mix
    for i in range(20):
        seed = np.random.randint(1e9)
        if np.random.random() < 0.5:
            trust = np.random.uniform(0.1, 0.6)
            reg = 10 ** np.random.uniform(-14, -10)
            try:
                cand = polish(best, seed=seed, rounds=4, max_seconds=8,
                            trust_start=trust, regularization=reg)
                s = pg.side(cand)
                if s < best_side: best, best_side = cand, s
            except: pass
        else:
            trust = np.random.uniform(0.1, 0.6)
            tie = np.random.uniform(0.1, 0.45)
            try:
                cand = reclose(best, seed=seed, trust=trust, tie=tie, rounds=4, seconds=8)
                s = pg.side(cand)
                if s < best_side: best, best_side = cand, s
            except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best
        print(f"  ★ WIN!")

if wins:
    np.savez_compressed(f"output/shotgun_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
