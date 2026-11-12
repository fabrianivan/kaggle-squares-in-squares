#!/usr/bin/env python3
"""ROUND 2 Blitz - Fast coverage of all puzzles"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))
import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 1001))
print(f"Round 2 Blitz: ALL {len(targets)} puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    p = rows[['x', 'y', 'angle']].values
    best, best_L = p.copy(), pg.side(p)
    if idx % 100 == 1: print(f"[{idx}/{len(targets)}] n={n}")
    
    for i in range(40):
        seed = np.random.randint(1e9)
        trust = 0.2 + 0.3 * np.random.random()
        tie = 0.2 + 0.2 * np.random.random()
        try:
            q, _, _ = reclosure.reclose(best, seed=seed, trust=trust, tie=tie,
                                       rounds=4, seconds=8)
            if pg.side(q) < best_L: best, best_L = q, pg.side(q)
        except: pass
    
    if best_L < pg.side(p) - 1e-12:
        wins[n] = best

if wins:
    np.savez_compressed(f"output/r2_blitz_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Blitz: {s:.12f}, {len(wins)} wins")
