#!/usr/bin/env python3
"""IMMEDIATE ULTRA BOOST - Maximum intensity RIGHT NOW"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

print("=" * 80)
print("IMMEDIATE ULTRA BOOST - EXTREME INTENSITY")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Target highest-potential puzzles
targets = (list(range(2, 51)) +  # Small: highest variance
           [55, 60, 65, 70, 75, 80, 85, 90, 95, 100] +  # Mid-small
           [105, 111, 117, 123, 129, 135, 141, 147, 153, 159])  # Selected medium

print(f"Targeting {len(targets)} HIGH-POTENTIAL puzzles")
print(f"Running 150 ULTRA-INTENSIVE attempts per puzzle\n")

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best, best_L = p_base.copy(), pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n} baseline={best_L:.12f}")
    
    improvements = 0
    
    # 150 ultra-intensive attempts
    for attempt in range(150):
        seed = np.random.randint(1e9)
        
        # Cycle through 12 ultra-diverse strategies
        strat = attempt % 12
        
        try:
            if strat == 0:  # Ultra-ultra tight
                q, _, _ = polish.polish(best, seed=seed, rounds=8, max_seconds=15,
                                       trust_start=0.01, regularization=5e-14)
            elif strat == 1:  # Super tight
                q, _, _ = polish.polish(best, seed=seed, rounds=7, max_seconds=15,
                                       trust_start=0.018, regularization=1e-13)
            elif strat == 2:  # Tight
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=0.025, regularization=5e-13)
            elif strat == 3:  # Medium-tight
                q, _, _ = polish.polish(best, seed=seed, rounds=6, max_seconds=15,
                                       trust_start=0.032, regularization=1e-12)
            elif strat == 4:  # Medium
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=15,
                                       trust_start=0.04, regularization=5e-12)
            elif strat == 5:  # Loose
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=15,
                                       trust_start=0.055, regularization=1e-11)
            elif strat == 6:  # Ultra tight reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.15, tie=0.15,
                                           rounds=8, seconds=15)
            elif strat == 7:  # Super tight reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.2, tie=0.2,
                                           rounds=7, seconds=15)
            elif strat == 8:  # Tight reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.25, tie=0.23,
                                           rounds=6, seconds=15)
            elif strat == 9:  # Medium reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.3, tie=0.27,
                                           rounds=6, seconds=15)
            elif strat == 10:  # Loose reclose
                q, _, _ = reclosure.reclose(best, seed=seed, trust=0.38, tie=0.32,
                                           rounds=5, seconds=15)
            else:  # Random exploration
                trust = 0.01 + 0.06 * np.random.random()
                reg = 10 ** (-14 + 2.5 * np.random.random())
                q, _, _ = polish.polish(best, seed=seed, rounds=5, max_seconds=12,
                                       trust_start=trust, regularization=reg)
            
            s = pg.side(q)
            if s < best_L - 1e-14:
                improvements += 1
                best, best_L = q, s
                print(f"  [{attempt:3d}] Improved → {s:.12f}")
        
        except:
            pass
    
    if best_L < pg.side(p_base) - 1e-12:
        total_imp = pg.side(p_base) - best_L
        wins[n] = best
        print(f"★★★ WIN n={n}: {pg.side(p_base):.12f} → {best_L:.12f} (Δ={total_imp:.2e}, {improvements} steps)\n")
    else:
        print(f"  No net improvement ({improvements} sub-improvements)\n")

print("\n" + "=" * 80)
print(f"IMMEDIATE ULTRA BOOST COMPLETE")
print("=" * 80)

if wins:
    print(f"\n✓ FOUND {len(wins)} IMPROVEMENTS!")
    
    np.savez_compressed(f"output/immediate_ultra_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    
    print(f"\n🎉 NEW SUBMISSION:")
    print(f"   File: {sub_path}")
    print(f"   Score: {new_score:.12f}")
    
    prev = 22.250977
    if new_score < prev:
        print(f"\n🔥 IMPROVED FROM {prev:.12f}!")
        print(f"   Improvement: {(prev - new_score):.2e}")
    
    print(f"\n✓ Wins: {sorted(wins.keys())}")
else:
    print("\nNo improvements (baseline extremely optimized)")

print("\n" + "=" * 80)
