#!/usr/bin/env python3
"""Final Push - Extreme optimization on remaining opportunities"""
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
print("FINAL PUSH - Extreme Optimization")
print("=" * 80)

# Load the BEST current submission
submission_files = sorted(Path('output').glob('submission_22.*.csv'))
if not submission_files:
    print("No submission files found!")
    sys.exit(1)

best_file = submission_files[0]  # Already sorted, lowest score first
print(f"Starting from: {best_file.name}")

df = pd.read_csv(best_file)

# Target puzzles that are most likely to have room for improvement
# Focus on prime numbers and numbers with special properties
targets = []

# Prime numbers often have irregular packings
primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
          101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199,
          211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281, 283, 293,
          307, 311, 313, 317, 331, 337, 347, 349, 353, 359, 367, 373, 379, 383, 389, 397,
          401, 409, 419, 421, 431, 433, 439, 443, 449, 457, 461, 463, 467, 479, 487, 491, 499,
          503, 509, 521, 523, 541, 547, 557, 563, 569, 571, 577, 587, 593, 599,
          601, 607, 613, 617, 619, 631, 641, 643, 647, 653, 659, 661, 673, 677, 683, 691,
          701, 709, 719, 727, 733, 739, 743, 751, 757, 761, 769, 773, 787, 797,
          809, 811, 821, 823, 827, 829, 839, 853, 857, 859, 863, 877, 881, 883, 887,
          907, 911, 919, 929, 937, 941, 947, 953, 967, 971, 977, 983, 991, 997]

# Numbers just below perfect squares
near_squares = []
for k in range(2, 32):
    sq = k * k
    if sq <= 1000:
        for offset in range(1, min(10, sq)):
            n = sq - offset
            if 5 <= n <= 1000:
                near_squares.append(n)

# Large impact numbers (high weight due to sqrt scaling)
large_impact = list(range(700, 1001))

# Combine all targets (remove duplicates)
all_targets = set(primes + near_squares + large_impact)
targets = sorted(list(all_targets))

print(f"Targeting {len(targets)} strategic puzzles")
print(f"  - {len([p for p in targets if p in primes])} primes")
print(f"  - {len([p for p in targets if p in near_squares])} near-squares")
print(f"  - {len([p for p in targets if p >= 700])} large impact (n>=700)")
print("=" * 80 + "\n")

wins = {}
start_time = time.time()
total_puzzles = len(targets)

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(best_p)
    
    # Progress indicator
    if idx % 50 == 1 or idx == 1:
        elapsed = time.time() - start_time
        if idx > 1:
            rate = elapsed / (idx - 1)
            eta = rate * (total_puzzles - idx + 1) / 60
            print(f"\n[{idx:4d}/{total_puzzles}] {elapsed/60:.1f}min elapsed, ETA: {eta:.1f}min")
    
    print(f"  n={n:4d} L={best_L:.12f}", end="", flush=True)
    
    improvements_found = 0
    
    # EXTREME optimization: 300 attempts with aggressive parameters
    for attempt in range(300):
        seed = np.random.randint(1000000)
        
        # Cycle through 4 strategies
        strategy = attempt % 4
        
        try:
            if strategy == 0:
                # Ultra-tight polish
                trust_start = 0.003 + 0.02 * np.random.random()
                reg = 10 ** (-15 + 2 * np.random.random())
                q, _, _ = polish.polish(best_p, seed=seed, rounds=10, max_seconds=25,
                                       trust_start=trust_start, regularization=reg)
            
            elif strategy == 1:
                # Aggressive reclosure
                trust = 0.1 + 0.45 * np.random.random()
                tie = 0.1 + 0.4 * np.random.random()
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie,
                                           rounds=10, seconds=25)
            
            elif strategy == 2:
                # Medium-tight combination
                # First polish
                trust_start = 0.015 + 0.03 * np.random.random()
                reg = 10 ** (-13 + 1.5 * np.random.random())
                q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=12,
                                       trust_start=trust_start, regularization=reg)
                # Then reclose
                trust = 0.2 + 0.15 * np.random.random()
                tie = 0.2 + 0.15 * np.random.random()
                q, _, _ = reclosure.reclose(q, seed=seed+1, trust=trust, tie=tie,
                                           rounds=4, seconds=12)
            
            else:
                # Wide exploration
                trust = 0.08 + 0.5 * np.random.random()
                tie = 0.08 + 0.45 * np.random.random()
                q, _, _ = reclosure.reclose(best_p, seed=seed, trust=trust, tie=tie,
                                           rounds=8, seconds=20)
            
            new_L = pg.side(q)
            if new_L < best_L - 1e-14:
                best_p = q
                best_L = new_L
                improvements_found += 1
                print(f" →{best_L:.12f}", end="", flush=True)
        
        except:
            pass
    
    # Check for overall win
    if best_L < pg.side(p_base) - 1e-12:
        improvement = pg.side(p_base) - best_L
        wins[n] = best_p
        print(f" ★WIN! Δ={improvement:.2e} ({improvements_found} steps)")
    else:
        print()

elapsed = time.time() - start_time

print("\n" + "=" * 80)
print(f"OPTIMIZATION COMPLETE in {elapsed/60:.1f} minutes")
print(f"Found {len(wins)} improvements")
print("=" * 80)

if wins:
    # Save wins
    timestamp = int(time.time())
    wins_file = f"output/final_push_wins_{len(wins)}_{timestamp}.npz"
    np.savez_compressed(wins_file, **{str(k): v for k, v in wins.items()})
    print(f"\nSaved: {wins_file}")
    
    # Create new submission
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    
    # Score it
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_final_push_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    
    print(f"\n✓ NEW SUBMISSION CREATED")
    print(f"  Score: {new_score:.12f}")
    print(f"  File: {sub_path}")
    print(f"  Wins: {len(wins)} strategic puzzles")
    
    # Compare to starting point
    from src.tools.reference_sources.official_metric import score
    old_score = score(df, 'id', 'n')
    
    print(f"\n📊 IMPROVEMENT BREAKDOWN")
    print(f"   Starting score: {old_score:.12f}")
    print(f"   Final score:    {new_score:.12f}")
    print(f"   Improvement:    {(old_score - new_score):.2e}")
    print(f"   Puzzles won:    {len(wins)}")
    
    if new_score < old_score:
        print(f"\n🎉 SUCCESS! New best score achieved!")
    
    # Save summary
    summary = {
        'start_file': str(best_file.name),
        'start_score': float(old_score),
        'final_score': float(new_score),
        'improvement': float(old_score - new_score),
        'puzzles_improved': len(wins),
        'time_minutes': elapsed / 60,
        'timestamp': timestamp,
        'strategies': ['ultra_tight_polish', 'aggressive_reclosure', 'combination', 'wide_exploration'],
        'attempts_per_puzzle': 300
    }
    
    import json
    summary_file = f"output/final_push_summary_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📄 Summary saved: {summary_file}")
else:
    print("\nNo improvements found - baseline is exceptionally strong!")

print("\n" + "=" * 80)
print("DONE!")
print("=" * 80)
