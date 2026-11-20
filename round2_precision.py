#!/usr/bin/env python3
"""ROUND 2 Precision - High precision on small puzzles"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))
import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151))
print(f"Round 2 Precision: {len(targets)} puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    p = rows[['x', 'y', 'angle']].values
    best, best_L = p.copy(), pg.side(p)
    if idx % 20 == 1: print(f"[{idx}/{len(targets)}] n={n}")
    
    for i in range(100):
        seed = np.random.randint(1e9)
        trust = 0.01 + 0.05 * np.random.random()
        reg = 10 ** (-14 + 1.5 * np.random.random())
        try:
            q, _, _ = polish.polish(best, seed=seed, rounds=7, max_seconds=15,
                                   trust_start=trust, regularization=reg)
            if pg.side(q) < best_L: best, best_L = q, pg.side(q)
        except: pass
    
    if best_L < pg.side(p) - 1e-12:
        wins[n] = best
        print(f"  n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/r2_precision_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Precision: {s:.12f}, {len(wins)} wins")
