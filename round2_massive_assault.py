#!/usr/bin/env python3
"""ROUND 2: Massive assault from new baseline 22.250971"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

print("=" * 80)
print("ROUND 2 MASSIVE ASSAULT - Starting from 22.250971")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# ALL puzzles with massive intensity
targets = list(range(2, 1001))
print(f"Targeting ALL {len(targets)} puzzles with 80 attempts each\n")

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best, best_L = p_base.copy(), pg.side(p_base)
    
    if idx % 50 == 1:
        print(f"[{idx}/{len(targets)}] n={n}")
    
    for attempt in range(80):
        seed = np.random.randint(1e9)
        method = attempt % 8
        
        try:
            if method == 0:
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=12,
                                       trust_start=0.015, regularization=1e-13)
            elif method == 1:
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=12,
                                       trust_start=0.028, regularization=5e-13)
            elif method == 2:
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=12,
                                       trust_start=0.042, regularization=1e-12)
            elif method == 3:
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.18, tie=0.18,
                                           rounds=6, seconds=12)
            elif method == 4:
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.28, tie=0.25,
                                           rounds=6, seconds=12)
            elif method == 5:
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.38, tie=0.32,
                                           rounds=5, seconds=12)
            elif method == 6:
                trust = 0.01 + 0.05 * np.random.random()
                reg = 10 ** (-14 + 2 * np.random.random())
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=10,
                                       trust_start=trust, regularization=reg)
            else:
                trust = 0.15 + 0.35 * np.random.random()
                tie = 0.15 + 0.25 * np.random.random()
                q, _, _ = reclosure.reclose(best, seed=seed, trust=trust, tie=tie,
                                           rounds=5, seconds=10)
            
            if pg.side(q) < best_L:
                best, best_L = q, pg.side(q)
        except:
            pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best
        print(f"  n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/round2_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\nROUND 2 RESULT: {s:.12f}, {len(wins)} wins")
