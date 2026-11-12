#!/usr/bin/env python3
"""Blitz Attack - Fast but thorough coverage of all puzzles"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 501))
print(f"Blitz Attack: {len(targets)} puzzles, 40 attempts each")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p, best_L = p_base.copy(), pg.side(p_base)
    
    if idx % 50 == 1:
        print(f"[{idx}/{len(targets)}] n={n}")
    
    for i in range(40):
        seed = np.random.randint(1e7)
        trust = 0.015 + 0.05 * np.random.random()
        reg = 10 ** (-14 + 2 * np.random.random())
        try:
            q, _, _ = polish.polish(best_p, seed=seed, rounds=5, max_seconds=12,
                                   trust_start=trust, regularization=reg)
            if pg.side(q) < best_L:
                best_p, best_L = q, pg.side(q)
        except: pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best_p
        print(f"  n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/blitz_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
