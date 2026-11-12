#!/usr/bin/env python3
"""
BREAKTHROUGH 1: Adaptive Learning Optimizer
Learns which parameters work best for each puzzle size and adapts strategy
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure
from collections import defaultdict

print("=" * 80)
print("BREAKTHROUGH ALGORITHM 1: ADAPTIVE LEARNING")
print("Learns optimal parameters per puzzle size, then exploits that knowledge")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")

# Phase 1: Learning phase - discover what works for different puzzle sizes
print("\nPHASE 1: LEARNING (sample 20 puzzles to learn patterns)")
learning_samples = [5, 10, 15, 25, 35, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 600, 700, 800, 900, 1000]

# Store what works for each size range
success_params = defaultdict(list)

for n in learning_samples:
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_L = pg.side(p_base)
    
    print(f"Learning from n={n}...")
    
    # Try diverse strategies
    test_params = [
        ('ultra_tight', {'method': 'polish', 'trust': 0.015, 'reg': 1e-13}),
        ('tight', {'method': 'polish', 'trust': 0.025, 'reg': 5e-13}),
        ('medium', {'method': 'polish', 'trust': 0.035, 'reg': 1e-12}),
        ('tight_reclose', {'method': 'reclose', 'trust': 0.18, 'tie': 0.18}),
        ('medium_reclose', {'method': 'reclose', 'trust': 0.28, 'tie': 0.25}),
        ('loose_reclose', {'method': 'reclose', 'trust': 0.38, 'tie': 0.32}),
    ]
    
    for name, params in test_params:
        seed = np.random.randint(1e8)
        try:
            if params['method'] == 'polish':
                q, _, _ = polish.polish(p_base, seed=seed, rounds=5, max_seconds=10,
                                       trust_start=params['trust'], 
                                       regularization=params['reg'])
            else:
                q, _, _ = reclosure.reclose(p_base, seed=seed, 
                                           trust=params['trust'], 
                                           tie=params['tie'],
                                           rounds=5, seconds=10)
            
            if pg.side(q) < best_L - 1e-13:
                # This worked! Remember it for this size range
                size_bucket = (n // 50) * 50  # Bucket by 50s
                success_params[size_bucket].append((name, params))
                print(f"  → {name} worked for n={n}")
        except:
            pass

print("\n" + "=" * 80)
print("PHASE 2: EXPLOITATION (use learned patterns on all puzzles)")
print("=" * 80)

# Phase 2: Apply learned strategies
targets = list(range(2, 1001))
wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_p = p_base.copy()
    best_L = pg.side(p_base)
    
    if idx % 50 == 1:
        print(f"[{idx}/{len(targets)}] n={n}")
    
    # Find what worked for similar-sized puzzles
    size_bucket = (n // 50) * 50
    learned_strategies = success_params.get(size_bucket, [])
    
    # If we learned something, prioritize those strategies
    if learned_strategies:
        for name, params in learned_strategies * 3:  # Try each successful strategy 3x
            seed = np.random.randint(1e8)
            try:
                if params['method'] == 'polish':
                    q, _, _ = polish.polish(best_p, seed=seed, rounds=6, max_seconds=12,
                                           trust_start=params['trust'],
                                           regularization=params['reg'])
                else:
                    q, _, _ = reclosure.reclose(best_p, seed=seed,
                                               trust=params['trust'],
                                               tie=params['tie'],
                                               rounds=6, seconds=12)
                
                if pg.side(q) < best_L:
                    best_p, best_L = q, pg.side(q)
            except:
                pass
    
    # Also try some random exploration
    for _ in range(10):
        seed = np.random.randint(1e8)
        trust = 0.015 + 0.05 * np.random.random()
        reg = 10 ** (-13 + np.random.random())
        try:
            q, _, _ = polish.polish(best_p, seed=seed, rounds=5, max_seconds=10,
                                   trust_start=trust, regularization=reg)
            if pg.side(q) < best_L:
                best_p, best_L = q, pg.side(q)
        except:
            pass
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best_p
        print(f"  ★ n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/adaptive_learning_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 1: Score {s:.12f}, {len(wins)} wins")
