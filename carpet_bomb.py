#!/usr/bin/env python3
"""Carpet Bomb - Cover everything with massive seeds"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 301))
print(f"Carpet Bomb: {len(targets)} puzzles, 80 seeds each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p, best_L = p_base.copy(), pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n}")
    
    # Carpet bomb with 80 random seeds
    for i in range(80):
        seed = np.random.randint(1e8)
        trust = [0.02, 0.03, 0.05][i % 3]
        reg = 10 ** ([-13, -12.5, -12][i % 3])
        try:
            q, _, _ = polish.polish(best_p, seed=seed, rounds=5, max_seconds=10,
                                   trust_start=trust, regularization=reg)
            if pg.side(q) < best_L:
                best_p, best_L = q, pg.side(q)
        except: pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best_p
        print(f"  ★ n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/carpet_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
