#!/usr/bin/env python3
"""Coordinated Attack - Focus on puzzles most likely to improve"""
import sys, os
sys.path.insert(0, '.')
os.chdir('/Users/fabrianivan/kaggle-squares-in-squares')

import numpy as np
import pandas as pd
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

def coordinated_optimize(n, baseline, intensity=50):
    """Coordinated multi-method attack"""
    best = baseline.copy()
    best_side = pg.side(best)
    
    # Strategy 1: Tight polish
    for i in range(intensity):
        seed = np.random.randint(1e9)
        try:
            cand = polish(best, seed=seed, rounds=5, max_seconds=15,
                         trust_start=0.18, regularization=1e-13)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    n={n}: tight polish → {s:.12f}")
        except: pass
    
    # Strategy 2: Medium reclose
    for i in range(intensity):
        seed = np.random.randint(1e9)
        try:
            cand = reclose(best, seed=seed, trust=0.28, tie=0.25,
                         rounds=5, seconds=15)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    n={n}: medium reclose → {s:.12f}")
        except: pass
    
    # Strategy 3: Adaptive mix
    for i in range(intensity):
        seed = np.random.randint(1e9)
        if i % 3 == 0:
            trust, reg = 0.35, 5e-13
        elif i % 3 == 1:
            trust, reg = 0.22, 1e-12
        else:
            trust, reg = 0.45, 1e-11
        
        try:
            cand = polish(best, seed=seed, rounds=4, max_seconds=12,
                         trust_start=trust, regularization=reg)
            s = pg.side(cand)
            if s < best_side:
                best, best_side = cand, s
                print(f"    n={n}: adaptive → {s:.12f}")
        except: pass
    
    return best, best_side

# Main execution
df = pd.read_csv("output/submission_final.csv")

# Focus on small-medium where improvements are most likely
targets = list(range(2, 251)) + list(range(300, 501, 2))
print(f"Coordinated Attack: {len(targets)} high-value targets")

wins = {}
for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    baseline = rows[['x', 'y', 'angle']].values
    baseline_side = pg.side(baseline)
    print(f"\n[{idx}/{len(targets)}] n={n}")
    
    intensity = 80 if n < 100 else 50
    best, best_side = coordinated_optimize(n, baseline, intensity)
    
    if best_side < baseline_side - 1e-12:
        wins[n] = best
        print(f"  ★★ WIN: {baseline_side:.12f} → {best_side:.12f}")

if wins:
    np.savez_compressed(f"output/coordinated_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ SCORE: {s:.12f}, {len(wins)} improvements")
