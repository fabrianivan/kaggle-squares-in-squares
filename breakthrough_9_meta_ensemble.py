#!/usr/bin/env python3
"""
BREAKTHROUGH 9: Meta-Ensemble Optimizer
Combines predictions from multiple optimization strategies
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish
import cpu_axis_reclosure as reclosure

print("=" * 80)
print("BREAKTHROUGH 9: META-ENSEMBLE OPTIMIZER")
print("Ensemble of strategies with weighted voting")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 201))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    
    print(f"[{idx}/{len(targets)}] n={n} - Meta-Ensemble")
    
    # Define ensemble strategies with weights (learned from past performance)
    strategies = [
        ('ultra_tight', 1.2, lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.015, regularization=1e-13)),
        ('tight', 1.0, lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.025, regularization=5e-13)),
        ('medium_polish', 0.8, lambda p, s: polish.polish(p, seed=s, rounds=5, max_seconds=10, trust_start=0.035, regularization=1e-12)),
        ('tight_reclose', 1.1, lambda p, s: reclosure.reclose(p, seed=s, trust=0.18, tie=0.18, rounds=5, seconds=10)),
        ('medium_reclose', 0.9, lambda p, s: reclosure.reclose(p, seed=s, trust=0.28, tie=0.25, rounds=5, seconds=10)),
        ('loose_reclose', 0.7, lambda p, s: reclosure.reclose(p, seed=s, trust=0.38, tie=0.32, rounds=5, seconds=10)),
    ]
    
    # Run all strategies multiple times
    all_candidates = []
    
    for name, weight, strategy_func in strategies:
        for trial in range(5):  # 5 trials per strategy
            seed = np.random.randint(1e8)
            try:
                candidate, _, _ = strategy_func(p_base, seed)
                quality = pg.side(candidate)
                # Weight by strategy confidence and quality
                score = weight / quality  # Higher weight and lower size = better
                all_candidates.append((score, candidate, quality, name))
            except:
                pass
    
    if not all_candidates:
        continue
    
    # Sort by ensemble score
    all_candidates.sort(reverse=True, key=lambda x: x[0])
    
    # Take best candidates and refine them further
    top_k = min(3, len(all_candidates))
    refined = []
    
    for i in range(top_k):
        _, candidate, quality, origin = all_candidates[i]
        
        # Refine this candidate further
        best_refined = candidate
        best_refined_L = quality
        
        for refine_step in range(5):
            seed = np.random.randint(1e8)
            trust = 0.02 + 0.03 * np.random.random()
            reg = 10 ** (-13 + 0.5 * np.random.random())
            
            try:
                refined_cand, _, _ = polish.polish(best_refined, seed=seed, rounds=4,
                                                   max_seconds=8, trust_start=trust,
                                                   regularization=reg)
                if pg.side(refined_cand) < best_refined_L:
                    best_refined = refined_cand
                    best_refined_L = pg.side(refined_cand)
            except:
                pass
        
        refined.append((best_refined_L, best_refined))
    
    # Final best
    refined.sort(key=lambda x: x[0])
    best_L, best = refined[0]
    
    if best_L < pg.side(p_base) - 1e-12:
        wins[n] = best
        print(f"  ★★ Ensemble WIN for n={n}: {pg.side(p_base):.12f} → {best_L:.12f}")

if wins:
    np.savez_compressed(f"output/ensemble_meta_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 9 (Meta-Ensemble): Score {s:.12f}, {len(wins)} wins")
