#!/usr/bin/env python3
"""Hammer Time - Pound on small puzzles repeatedly"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 81))
print(f"Hammer Time: {len(targets)} small puzzles, 150 hammer strikes each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n} - HAMMER TIME!")
    
    for strike in range(150):
        seed = np.random.randint(1e9)
        
        # Vary the hammer: sometimes light, sometimes heavy
        if strike % 3 == 0:  # Light hammer
            trust, reg = 0.15, 1e-13
        elif strike % 3 == 1:  # Medium hammer
            trust, reg = 0.28, 5e-13
        else:  # Heavy hammer
            trust, reg = 0.42, 1e-12
        
        try:
            cand = polish(best, seed=seed, rounds=5, max_seconds=12,
                         trust_start=trust, regularization=reg)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"  Strike {strike}: BOOM! {s:.12f}")
        except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best
        print(f"  ★★★ HAMMERED IT!")

if wins:
    np.savez_compressed(f"output/hammer_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"FINAL SCORE: {s:.12f}, {len(wins)} wins!")
