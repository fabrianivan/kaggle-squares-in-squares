#!/usr/bin/env python3
"""Surgical Strike - Precise optimization on medium puzzles"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure

df = pd.read_csv("output/submission_final.csv")
targets = list(range(100, 401))
print(f"Surgical Strike: {len(targets)} medium puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p, best_L = p_base.copy(), pg.side(p_base)
    
    if idx % 30 == 1:
        print(f"[{idx}/{len(targets)}] n={n}")
    
    # Surgical: systematic parameter sweep
    for trust in [0.22, 0.28, 0.35, 0.42]:
        for tie in [0.2, 0.27, 0.34]:
            for s in range(5):
                seed = np.random.randint(1e7)
                try:
                    q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie,
                                               rounds=6, seconds=12)
                    if pg.side(q) < best_L:
                        best_p, best_L = q, pg.side(q)
                except: pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best_p
        print(f"  n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/surgical_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
