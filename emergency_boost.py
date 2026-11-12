#!/usr/bin/env python3
"""Emergency Boost - Get wins RIGHT NOW with extreme intensity"""
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
print("EMERGENCY BOOST - EXTREME INTENSITY FOR IMMEDIATE WINS")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Target n=2-100 where wins are most likely + high-variance medium puzzles
targets = (list(range(2, 101)) + 
           [101, 103, 105, 107, 110, 113, 117, 121, 125, 130, 135, 140, 145, 150])

print(f"Targeting {len(targets)} HIGH-VALUE puzzles")
print("Running 100 EXTREME attempts per puzzle\n")

wins = {}
start_time = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    
    print(f"\n{'='*70}")
    print(f"[{idx}/{len(targets)}] n={n} - EMERGENCY INTENSITY MODE")
    print(f"Baseline: {best_L:.12f}")
    print(f"{'='*70}")
    
    improvements_this_puzzle = 0
    
    # 100 extreme attempts with maximum parameter diversity
    for attempt in range(100):
        seed = np.random.randint(100000000)
        
        # Cycle through 10 different strategies
        strategy = attempt % 10
        
        if strategy == 0:
            # Ultra-ultra tight polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=10, max_seconds=20,
                                       trust_start=0.01, regularization=1e-14)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] ULTRA-TIGHT → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 1:
            # Super tight polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=9, max_seconds=18,
                                       trust_start=0.018, regularization=5e-14)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] SUPER-TIGHT → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 2:
            # Tight-medium polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=8, max_seconds=18,
                                       trust_start=0.025, regularization=1e-13)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] TIGHT-MED → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 3:
            # Ultra tight reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.15, tie=0.15,
                                           rounds=10, seconds=20)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] ULTRA-RECLOSE → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 4:
            # Super tight reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.2, tie=0.2,
                                           rounds=9, seconds=18)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] SUPER-RECLOSE → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 5:
            # Medium polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=7, max_seconds=18,
                                       trust_start=0.03, regularization=5e-13)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] MEDIUM → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 6:
            # Medium reclose
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=0.28, tie=0.25,
                                           rounds=7, seconds=18)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] MED-RECLOSE → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 7:
            # Loose polish
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=18,
                                       trust_start=0.045, regularization=1e-12)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] LOOSE → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        elif strategy == 8:
            # Random polish
            trust_rand = 0.01 + 0.06 * np.random.random()
            reg_rand = 10 ** (-14 + 2 * np.random.random())
            try:
                q, _, _ = polish.polish(best_p, seed=seed, rounds=7, max_seconds=18,
                                       trust_start=trust_rand, regularization=reg_rand)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] RANDOM → {s:.12f} (Δ={improvement:.2e})")
            except: pass
        
        else:  # strategy == 9
            # Random reclose
            trust_rand = 0.15 + 0.35 * np.random.random()
            tie_rand = 0.15 + 0.25 * np.random.random()
            try:
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust_rand, tie=tie_rand,
                                           rounds=7, seconds=18)
                s = pg.side(q)
                if s < best_L - 1e-14:
                    improvements_this_puzzle += 1
                    improvement = best_L - s
                    best_p, best_L = q, s
                    print(f"  [{attempt:3d}] RAND-RECLOSE → {s:.12f} (Δ={improvement:.2e})")
            except: pass
    
    # Check for overall win
    baseline_L = pg.side(p_base)
    if best_L < baseline_L - 1e-12:
        total_improvement = baseline_L - best_L
        wins[n] = best_p
        print(f"\n★★★ BIG WIN n={n}: {baseline_L:.12f} → {best_L:.12f}")
        print(f"    Total improvement: {total_improvement:.2e}")
        print(f"    Steps improved: {improvements_this_puzzle}")
    else:
        print(f"\nNo net improvement for n={n} (tried {improvements_this_puzzle} sub-improvements)")
    
    # Progress update
    if idx % 10 == 0:
        elapsed = (time.time() - start_time) / 60
        rate = idx / elapsed if elapsed > 0 else 0
        remaining = (len(targets) - idx) / rate if rate > 0 else 0
        print(f"\n{'*'*70}")
        print(f"PROGRESS: {len(wins)} WINS in {elapsed:.1f}min, ~{remaining:.1f}min remaining")
        print(f"{'*'*70}\n")

elapsed = (time.time() - start_time) / 60

print("\n" + "=" * 80)
print(f"EMERGENCY BOOST COMPLETE - {elapsed:.1f} minutes")
print("=" * 80)

if wins:
    print(f"\n✓ FOUND {len(wins)} IMPROVEMENTS!")
    
    # Save
    np.savez_compressed(f"output/emergency_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    print(f"✓ Saved to output/emergency_wins_{len(wins)}.npz")
    
    # Create submission
    df_new = df.copy()
    for n, packing in wins.items():
        mask = df_new['n'] == n
        df_new.loc[mask, ['x', 'y', 'angle']] = packing
    
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    df_new.to_csv("output/submission_emergency.csv", index=False)
    
    print(f"\n🎉 NEW BEST SUBMISSION:")
    print(f"   File: {sub_path}")
    print(f"   Score: {new_score:.12f}")
    
    prev = 22.250977
    if new_score < prev:
        improvement = prev - new_score
        print(f"\n🔥 IMPROVED FROM {prev:.12f}!")
        print(f"   New best: {new_score:.12f}")
        print(f"   Improvement: {improvement:.2e}")
        print(f"   Wins: {len(wins)} puzzles")
    else:
        print(f"\n   (Previous: {prev:.12f})")
        
    print(f"\n✓ Improved puzzles: {sorted(wins.keys())}")
else:
    print("\nNo improvements found (baseline already extremely optimized)")

print("\n" + "=" * 80)
