#!/usr/bin/env python3
"""Ultra Intensive NOW - Maximum effort on most promising puzzles"""
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
print("ULTRA INTENSIVE OPTIMIZATION - MAXIMUM EFFORT MODE")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Target n=2-150 with INTENSIVE optimization
targets = list(range(2, 151))
print(f"Targeting {len(targets)} puzzles (n=2-150)")
print("Running 60 intensive attempts per puzzle with varied strategies\n")

wins = {}
start_time = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    
    print(f"[{idx}/{len(targets)}] n={n} baseline={best_L:.12f}")
    
    # ULTRA INTENSIVE: 60 attempts with maximum diversity
    for attempt in range(60):
        seed = np.random.randint(10000000)
        
        # Rotate through 6 different strategies
        strategy = attempt % 6
        
        if strategy == 0:
            # Ultra tight polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=8, max_seconds=15,
                                       trust_start=0.015, regularization=5e-14)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Ultra-tight → {best_L:.12f}")
            except: pass
        
        elif strategy == 1:
            # Tight reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.18, tie=0.18,
                                           rounds=8, seconds=15)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Tight-reclose → {best_L:.12f}")
            except: pass
        
        elif strategy == 2:
            # Medium polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=7, max_seconds=15,
                                       trust_start=0.03, regularization=1e-12)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Medium-polish → {best_L:.12f}")
            except: pass
        
        elif strategy == 3:
            # Medium reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.3, tie=0.26,
                                           rounds=7, seconds=15)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Medium-reclose → {best_L:.12f}")
            except: pass
        
        elif strategy == 4:
            # Loose polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=0.05, regularization=5e-12)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Loose-polish → {best_L:.12f}")
            except: pass
        
        else:  # strategy == 5
            # Random combo
            trust_p = 0.01 + 0.06 * np.random.random()
            reg = 10 ** (-14 + 2 * np.random.random())
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=trust_p, regularization=reg)
                if pg.side(q) < best_L - 1e-13:
                    best_p, best_L = q, pg.side(q)
                    print(f"  Attempt {attempt}: Random → {best_L:.12f}")
            except: pass
    
    # Check for win
    baseline_L = pg.side(p_base)
    if best_L < baseline_L - 1e-12:
        improvement = baseline_L - best_L
        wins[n] = best_p
        print(f"  ★★★ WIN n={n}: {baseline_L:.12f} → {best_L:.12f} (Δ={improvement:.2e})")
    
    # Progress update every 25 puzzles
    if idx % 25 == 0:
        elapsed = (time.time() - start_time) / 60
        rate = idx / elapsed
        remaining = (len(targets) - idx) / rate
        print(f"\n>>> Progress: {len(wins)} wins, {elapsed:.1f}min elapsed, ~{remaining:.1f}min remaining\n")

elapsed = (time.time() - start_time) / 60
print("\n" + "=" * 80)
print(f"ULTRA INTENSIVE COMPLETE - {elapsed:.1f} minutes")
print("=" * 80)

if wins:
    print(f"\n✓ Found {len(wins)} improvements!")
    
    # Save wins
    np.savez_compressed(f"output/ultra_intensive_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    print(f"✓ Saved to output/ultra_intensive_wins_{len(wins)}.npz")
    
    # Create new submission
    df_new = df.copy()
    for n, packing in wins.items():
        mask = df_new['n'] == n
        df_new.loc[mask, ['x', 'y', 'angle']] = packing
    
    # Calculate score
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    df_new.to_csv("output/submission_ultra_intensive.csv", index=False)
    
    print(f"\n✓ NEW SUBMISSION:")
    print(f"  File: {sub_path}")
    print(f"  Score: {new_score:.12f}")
    
    # Compare
    prev_best = 22.250977
    if new_score < prev_best:
        improvement = prev_best - new_score
        print(f"\n🎉 IMPROVED FROM {prev_best:.12f}")
        print(f"   New best: {new_score:.12f}")
        print(f"   Improvement: {improvement:.2e}")
    else:
        print(f"\n  (Previous best: {prev_best:.12f})")
else:
    print("\nNo improvements found (baseline excellent)")

print("\n" + "=" * 80)
