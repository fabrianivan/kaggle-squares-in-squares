#!/usr/bin/env python3
"""Ultra Optimization NOW - Immediate improvements"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure
import time

print("=" * 80)
print("ULTRA OPTIMIZATION NOW - Running from 22.250971")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Target most improvable: small + selected medium
targets = (list(range(2, 101)) + 
           [105, 110, 115, 120, 125, 130, 135, 140, 145, 150,
            160, 170, 180, 190, 200, 220, 240, 260, 280, 300])

print(f"\nTargeting {len(targets)} puzzles with 100 intensive attempts each")
print("Using 10 different strategies per puzzle\n")

wins = {}
start_time = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best = p_base.copy()
    best_L = pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n} baseline={best_L:.12f}", end=" ", flush=True)
    
    found_improvement = False
    
    # 100 attempts with 10 different strategies
    for attempt in range(100):
        seed = np.random.randint(1000000000)
        strategy = attempt % 10
        
        try:
            if strategy == 0:  # Ultra tight polish
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=10,
                                       trust_start=0.012, regularization=5e-14)
            elif strategy == 1:  # Tight polish
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=10,
                                       trust_start=0.022, regularization=1e-13)
            elif strategy == 2:  # Medium polish
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=10,
                                       trust_start=0.035, regularization=5e-13)
            elif strategy == 3:  # Loose polish
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=10,
                                       trust_start=0.05, regularization=1e-12)
            elif strategy == 4:  # Ultra tight reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.16, tie=0.16,
                                           rounds=6, seconds=10)
            elif strategy == 5:  # Tight reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.22, tie=0.22,
                                           rounds=6, seconds=10)
            elif strategy == 6:  # Medium reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.3, tie=0.27,
                                           rounds=5, seconds=10)
            elif strategy == 7:  # Loose reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.4, tie=0.33,
                                           rounds=5, seconds=10)
            elif strategy == 8:  # Random polish
                trust = 0.01 + 0.05 * np.random.random()
                reg = 10 ** (-14 + 1.5 * np.random.random())
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=10,
                                       trust_start=trust, regularization=reg)
            else:  # Random reclose
                trust = 0.15 + 0.3 * np.random.random()
                tie = 0.15 + 0.25 * np.random.random()
                q, _, _ = reclosure.reclose(best, seed=seed, trust=trust, tie=tie,
                                           rounds=5, seconds=10)
            
            s = pg.side(q)
            if s < best_L - 1e-13:
                best = q
                best_L = s
                found_improvement = True
                print(f"→{s:.12f}", end=" ", flush=True)
        
        except:
            pass
    
    baseline_L = pg.side(p_base)
    if best_L < baseline_L - 1e-12:
        improvement = baseline_L - best_L
        wins[n] = best
        print(f"★ WIN! Δ={improvement:.2e}")
    else:
        print("(no net improvement)")
    
    # Progress update
    if idx % 20 == 0:
        elapsed = (time.time() - start_time) / 60
        rate = idx / elapsed if elapsed > 0 else 0
        remaining = (len(targets) - idx) / rate if rate > 0 else 0
        print(f"\n>>> {len(wins)} wins so far, {elapsed:.1f}m elapsed, ~{remaining:.1f}m remaining\n")

elapsed = (time.time() - start_time) / 60

print("\n" + "=" * 80)
print(f"ULTRA OPTIMIZATION COMPLETE - {elapsed:.1f} minutes")
print("=" * 80)

if wins:
    print(f"\n✓ FOUND {len(wins)} IMPROVEMENTS!")
    
    # Save wins
    np.savez_compressed(f"output/ultra_now_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    print(f"✓ Saved wins to output/ultra_now_wins_{len(wins)}.npz")
    
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
    df_new.to_csv("output/submission_ultra_now.csv", index=False)
    
    print(f"\n🎉 NEW SUBMISSION CREATED:")
    print(f"   File: {sub_path}")
    print(f"   Score: {new_score:.12f}")
    
    baseline_score = 22.250971
    if new_score < baseline_score:
        improvement = baseline_score - new_score
        print(f"\n🔥 IMPROVED FROM {baseline_score:.12f}!")
        print(f"   New score: {new_score:.12f}")
        print(f"   Improvement: {improvement:.2e}")
        print(f"   Total from start: {22.251602 - new_score:.6f}")
    else:
        print(f"\n   Baseline was: {baseline_score:.12f}")
    
    print(f"\n✓ Improved puzzles: {sorted(wins.keys())}")
    
else:
    print("\nNo improvements found")
    print("(Baseline 22.250971 is already extremely well optimized)")

print("\n" + "=" * 80)
