#!/usr/bin/env python3
"""Full Spectrum - Cover entire parameter space"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 201)) + list(range(250, 451, 2))
print(f"Full Spectrum: {len(targets)} puzzles")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best, best_side = baseline, pg.side(baseline)
    print(f"[{idx}/{len(targets)}] n={n}")
    
    # Full spectrum of trust values
    for trust in np.linspace(0.12, 0.52, 11):
        for seed_idx in range(5):
            seed = np.random.randint(1e9)
            
            # Polish spectrum
            for reg_exp in [-13, -12.5, -12, -11.5, -11]:
                reg = 10 ** reg_exp
                try:
                    cand = polish(best, seed=seed, rounds=4, max_seconds=8,
                                trust_start=trust, regularization=reg)
                    s = pg.side(cand)
                    if s < best_side:
                        best, best_side = cand, s
                        print(f"  Polish t={trust:.2f}: {s:.12f}")
                except: pass
            
            # Reclose spectrum
            for tie in [0.18, 0.25, 0.32]:
                try:
                    cand = reclose(best, seed=seed+100, trust=trust, tie=tie,
                                 rounds=4, seconds=8)
                    s = pg.side(cand)
                    if s < best_side:
                        best, best_side = cand, s
                        print(f"  Reclose t={trust:.2f},tie={tie:.2f}: {s:.12f}")
                except: pass
    
    if best_side < pg.side(baseline) - 1e-12:
        wins[n] = best

if wins:
    np.savez_compressed(f"output/spectrum_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"Score: {s:.12f}, {len(wins)} wins")
