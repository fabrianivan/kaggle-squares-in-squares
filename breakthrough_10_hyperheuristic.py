#!/usr/bin/env python3
"""
BREAKTHROUGH 10: Hyper-Heuristic Optimizer
Meta-algorithm that selects and sequences low-level heuristics
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
print("BREAKTHROUGH 10: HYPER-HEURISTIC OPTIMIZER")
print("Intelligently sequences low-level heuristics")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 151))

# Define low-level heuristics
heuristics = {
    'h1': lambda p, s: polish.polish(p, seed=s, rounds=4, max_seconds=8, trust_start=0.015, regularization=1e-13),
    'h2': lambda p, s: polish.polish(p, seed=s, rounds=4, max_seconds=8, trust_start=0.03, regularization=5e-13),
    'h3': lambda p, s: polish.polish(p, seed=s, rounds=4, max_seconds=8, trust_start=0.05, regularization=1e-12),
    'h4': lambda p, s: reclosure.reclose(p, seed=s, trust=0.18, tie=0.18, rounds=4, seconds=8),
    'h5': lambda p, s: reclosure.reclose(p, seed=s, trust=0.28, tie=0.25, rounds=4, seconds=8),
    'h6': lambda p, s: reclosure.reclose(p, seed=s, trust=0.38, tie=0.32, rounds=4, seconds=8),
}

# Performance tracking
heuristic_performance = {h: [] for h in heuristics.keys()}

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    current = p_base.copy()
    current_L = pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n} - Hyper-Heuristic")
    
    # Sequence of 20 heuristic applications
    for step in range(20):
        # Select next heuristic based on performance history
        heuristic_scores = {}
        
        for h_name in heuristics.keys():
            if len(heuristic_performance[h_name]) > 0:
                # Average improvement from this heuristic
                avg_improvement = np.mean(heuristic_performance[h_name][-10:])  # Last 10
                # Add exploration bonus
                exploration = 1.0 / (len(heuristic_performance[h_name]) + 1)
                heuristic_scores[h_name] = avg_improvement + 0.3 * exploration
            else:
                heuristic_scores[h_name] = 1.0  # Give untried heuristics high priority
        
        # Select best heuristic (epsilon-greedy)
        if np.random.random() < 0.2:  # 20% exploration
            selected = np.random.choice(list(heuristics.keys()))
        else:
            selected = max(heuristic_scores, key=heuristic_scores.get)
        
        # Apply selected heuristic
        seed = np.random.randint(1e8)
        try:
            next_packing, _, _ = heuristics[selected](current, seed)
            next_L = pg.side(next_packing)
            
            improvement = current_L - next_L
            heuristic_performance[selected].append(improvement)
            
            if next_L < current_L:
                current = next_packing
                current_L = next_L
                print(f"  Step {step}: {selected} improved → {current_L:.12f}")
        except:
            heuristic_performance[selected].append(0)  # Failed
    
    if current_L < pg.side(p_base) - 1e-12:
        wins[n] = current
        print(f"  ★★ Hyper-Heuristic WIN for n={n}!")

if wins:
    np.savez_compressed(f"output/hyperheuristic_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 10 (Hyper-Heuristic): Score {s:.12f}, {len(wins)} wins")
