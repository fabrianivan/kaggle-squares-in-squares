#!/usr/bin/env python3
"""Instant Win - Get improvements RIGHT NOW"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import time
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish

print("=" * 80)
print("INSTANT WIN - Fast improvements on small puzzles")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Focus on n=2-60 where wins are easiest
targets = list(range(2, 61))
print(f"Targeting {len(targets)} puzzles with 30 quick attempts each\n")

wins = {}
start = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    
    print(f"[{idx}/{len(targets)}] n={n} baseline={best_L:.12f}", end="")
    
    # 30 rapid attempts with varying strategies
    for attempt in range(30):
        seed = np.random.randint(1000000)
        
        # Alternate between methods
        if attempt % 3 == 0:
            # Tight polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=5, max_seconds=8,
                                       trust_start=0.02, regularization=1e-12)
                if pg.side(q) < best_L:
                    best_p, best_L = q, pg.side(q)
                    print(f" →{best_L:.12f}", end="", flush=True)
            except: pass
        
        elif attempt % 3 == 1:
            # Medium reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.3, tie=0.25,
                                           rounds=5, seconds=8)
                if pg.side(q) < best_L:
                    best_p, best_L = q, pg.side(q)
                    print(f" →{best_L:.12f}", end="", flush=True)
            except: pass
        
        else:
            # Loose polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=4, max_seconds=8,
                                       trust_start=0.05, regularization=5e-12)
                if pg.side(q) < best_L:
                    best_p, best_L = q, pg.side(q)
                    print(f" →{best_L:.12f}", end="", flush=True)
            except: pass
    
    # Check for win
    if best_L < pg.side(p_base) - 1e-12:
        improvement = pg.side(p_base) - best_L
        wins[n] = best_p
        print(f" ★WIN! Δ={improvement:.2e}")
    else:
        print(" (no improvement)")

elapsed = time.time() - start

print("\n" + "=" * 80)
print(f"COMPLETE in {elapsed:.1f}s - Found {len(wins)} improvements")
print("=" * 80)

if wins:
    # Save wins
    np.savez_compressed(f"output/instant_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    
    # Create new submission
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    # Score it
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    
    print(f"\n✓ NEW BEST: {new_score:.12f}")
    print(f"  File: {sub_path}")
    print(f"  Wins: {len(wins)} puzzles improved")
    
    prev = 22.250979
    if new_score < prev:
        print(f"\n🎉 BETTER THAN {prev:.12f}!")
        print(f"   Improvement: {(prev - new_score):.2e}")
else:
    print("\nNo improvements (baseline already good)")
