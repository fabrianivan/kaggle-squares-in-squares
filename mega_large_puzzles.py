#!/usr/bin/env python3
"""Mega Large Puzzles - Focus on n >= 500 where score impact is highest"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_axis_reclosure as reclosure
import cpu_contact_polish as polish
import time

print("=" * 80)
print("MEGA LARGE PUZZLES OPTIMIZER")
print("=" * 80)
print("Targeting n >= 500 - Maximum score impact!")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Focus on large puzzles where impact is highest
targets = list(range(500, 1001))
print(f"\nTargeting {len(targets)} large puzzles (n=500-1000)")
print(f"Using 100 seeds per puzzle with multiple strategies\n")

wins = {}
start_time = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    
    print(f"[{idx:3d}/{len(targets)}] n={n:4d} L={best_L:.12f}", end="", flush=True)
    
    improvements = 0
    
    # Strategy 1: Axis reclosure with parameter sweep (60 attempts)
    for attempt in range(60):
        seed = np.random.randint(1000000)
        trust = 0.15 + 0.35 * np.random.random()  # 0.15-0.50
        tie = 0.15 + 0.25 * np.random.random()     # 0.15-0.40
        
        try:
            q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie,
                                       rounds=7, seconds=15)
            if pg.side(q) < best_L - 1e-14:
                best_p, best_L = q, pg.side(q)
                improvements += 1
                print(f" →{best_L:.12f}", end="", flush=True)
        except:
            pass
    
    # Strategy 2: Contact polish with varying parameters (40 attempts)
    for attempt in range(40):
        seed = np.random.randint(1000000)
        trust_start = 0.01 + 0.05 * np.random.random()  # 0.01-0.06
        reg = 10 ** (-13 + 2 * np.random.random())       # 1e-13 to 1e-11
        
        try:
            q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=15,
                                   trust_start=trust_start, regularization=reg)
            if pg.side(q) < best_L - 1e-14:
                best_p, best_L = q, pg.side(q)
                improvements += 1
                print(f" →{best_L:.12f}", end="", flush=True)
        except:
            pass
    
    # Check for overall win
    if best_L < pg.side(p_base) - 1e-12:
        improvement = pg.side(p_base) - best_L
        wins[n] = best_p
        print(f" ★WIN! Δ={improvement:.2e} ({improvements} steps)")
    else:
        print(f" (no improvement)")

elapsed = time.time() - start_time

print("\n" + "=" * 80)
print(f"OPTIMIZATION COMPLETE in {elapsed/60:.1f} minutes")
print(f"Found {len(wins)} improvements on large puzzles")
print("=" * 80)

if wins:
    # Save wins
    timestamp = int(time.time())
    wins_file = f"output/mega_large_wins_{len(wins)}_{timestamp}.npz"
    np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
    print(f"\nSaved wins: {wins_file}")
    
    # Create new submission
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    # Score it
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    
    print(f"\n✓ NEW SUBMISSION CREATED")
    print(f"  Score: {new_score:.12f}")
    print(f"  File: {sub_path}")
    print(f"  Wins: {len(wins)} large puzzles improved")
    
    # Compare to best known
    best_known = 22.250971
    if new_score < best_known:
        print(f"\n🎉 NEW BEST SCORE!")
        print(f"   Previous: {best_known:.12f}")
        print(f"   New:      {new_score:.12f}")
        print(f"   Gain:     {(best_known - new_score):.2e}")
    else:
        print(f"\n   Current best: {best_known:.12f}")
        print(f"   This run:     {new_score:.12f}")
        print(f"   Difference:   {(new_score - best_known):.2e}")
else:
    print("\nNo improvements found - baseline is excellent!")
    print("Large puzzles are already highly optimized.")

print("\n" + "=" * 80)
print("DONE!")
print("=" * 80)
