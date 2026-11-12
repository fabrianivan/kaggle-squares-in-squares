#!/usr/bin/env python3
"""Instant Improve - Fast wins on high-potential puzzles"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
import time
from src.tools import packing_geometry as pg
from src.tools.cpu_contact_polish import polish
from src.tools.cpu_axis_reclosure import reclose

print("=" * 80)
print("INSTANT IMPROVE - Getting wins NOW")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Target small puzzles where wins are most likely (highest variance)
targets = list(range(2, 81))
print(f"Targeting {len(targets)} small puzzles (n=2-80)")
print("Running 25 quick attempts per puzzle")
print("")

wins = {}
start_time = time.time()

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0:
        continue
    
    baseline = rows[['x', 'y', 'angle']].values
    best = baseline.copy()
    best_side = pg.side(best)
    
    print(f"[{idx}/{len(targets)}] n={n} baseline={best_side:.12f}")
    
    # 25 rapid attempts
    for attempt in range(25):
        seed = np.random.randint(1e9)
        
        # Try polish
        if attempt % 2 == 0:
            trust = 0.2 + 0.3 * np.random.random()
            reg = 10 ** (-13 + np.random.random())
            try:
                cand = polish(best, seed=seed, rounds=4, max_seconds=8,
                            trust_start=trust, regularization=reg)
                s = pg.side(cand)
                if s < best_side:
                    improvement = best_side - s
                    best = cand
                    best_side = s
                    print(f"  → Attempt {attempt}: IMPROVED to {s:.12f} (Δ={improvement:.2e})")
            except Exception as e:
                pass
        
        # Try reclose
        else:
            trust = 0.2 + 0.3 * np.random.random()
            tie = 0.2 + 0.2 * np.random.random()
            try:
                cand = reclose(best, seed=seed, trust=trust, tie=tie,
                             rounds=4, seconds=8)
                s = pg.side(cand)
                if s < best_side:
                    improvement = best_side - s
                    best = cand
                    best_side = s
                    print(f"  → Attempt {attempt}: IMPROVED to {s:.12f} (Δ={improvement:.2e})")
            except Exception as e:
                pass
    
    # Check if we got a win
    baseline_side = pg.side(baseline)
    if best_side < baseline_side - 1e-12:
        improvement = baseline_side - best_side
        wins[n] = best
        print(f"  ★★★ WIN for n={n}: {baseline_side:.12f} → {best_side:.12f} (Δ={improvement:.2e})")
    else:
        print(f"  No improvement for n={n}")
    
    # Quick progress update
    if idx % 10 == 0:
        elapsed = time.time() - start_time
        print(f"\n>>> Progress: {len(wins)} wins found in {elapsed:.1f}s\n")

# Create improved submission
elapsed = time.time() - start_time
print("\n" + "=" * 80)
print(f"INSTANT IMPROVE COMPLETE - {elapsed:.1f} seconds")
print("=" * 80)

if wins:
    print(f"\n✓ Found {len(wins)} improvements!")
    
    # Save wins
    np.savez_compressed(f"output/instant_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    print(f"✓ Saved to output/instant_wins_{len(wins)}.npz")
    
    # Create new submission
    df_new = df.copy()
    for n, packing in wins.items():
        mask = df_new['n'] == n
        df_new.loc[mask, ['x', 'y', 'angle']] = packing
    
    # Calculate new score
    from src.tools.reference_sources.official_metric import score
    new_score = score(df_new, 'id', 'n')
    
    sub_path = f"output/submission_{new_score:.6f}.csv"
    df_new.to_csv(sub_path, index=False)
    df_new.to_csv("output/submission_instant.csv", index=False)
    
    print(f"\n✓ NEW SUBMISSION CREATED:")
    print(f"  File: {sub_path}")
    print(f"  Score: {new_score:.12f}")
    
    # Compare to previous best
    prev_best = 22.250979
    if new_score < prev_best:
        improvement = prev_best - new_score
        print(f"\n🎉 IMPROVED FROM {prev_best:.12f}")
        print(f"   New best: {new_score:.12f}")
        print(f"   Improvement: {improvement:.12f} ({improvement:.2e})")
    else:
        print(f"\n  (Previous best was {prev_best:.12f})")
else:
    print("\nNo improvements found (baseline already excellent)")

print("\n" + "=" * 80)
