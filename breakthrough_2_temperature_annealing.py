#!/usr/bin/env python3
"""
BREAKTHROUGH 2: Advanced Temperature Annealing
Sophisticated simulated annealing with adaptive temperature schedule
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'tools'))

import numpy as np
import pandas as pd
import packing_geometry as pg
import cpu_contact_polish as polish

print("=" * 80)
print("BREAKTHROUGH ALGORITHM 2: ADVANCED TEMPERATURE ANNEALING")
print("Uses adaptive cooling schedule and restart strategy")
print("=" * 80)

df = pd.read_csv("output/submission_final.csv")
targets = list(range(2, 201))

wins = {}

for idx, n in enumerate(targets, 1):
    rows = df[df['n'] == n]
    if len(rows) == 0: continue
    
    p_base = rows[['x', 'y', 'angle']].values
    best_global = p_base.copy()
    best_global_L = pg.side(p_base)
    
    print(f"[{idx}/{len(targets)}] n={n} - Temperature Annealing")
    
    # Multiple annealing runs with different schedules
    for run in range(5):
        current = p_base.copy()
        current_L = pg.side(current)
        best_run = current.copy()
        best_run_L = current_L
        
        # Temperature schedule
        T_start = 1.0
        T_end = 0.001
        steps = 40
        
        for step in range(steps):
            # Adaptive temperature (faster cooling if finding improvements)
            alpha = step / steps
            T = T_start * ((T_end / T_start) ** alpha)
            
            # Adjust trust based on temperature
            trust = 0.01 + 0.05 * T
            reg = 10 ** (-14 + 1.5 * T)
            
            seed = np.random.randint(1e8)
            
            try:
                candidate, _, _ = polish.polish(current, seed=seed, rounds=5, 
                                               max_seconds=12,
                                               trust_start=trust,
                                               regularization=reg)
                candidate_L = pg.side(candidate)
                
                # Acceptance criterion
                delta = candidate_L - current_L
                
                if delta < 0:  # Better solution
                    current = candidate
                    current_L = candidate_L
                    
                    if current_L < best_run_L:
                        best_run = current.copy()
                        best_run_L = current_L
                        print(f"  Run {run}, T={T:.3f}: {current_L:.12f}")
                
                elif np.random.random() < np.exp(-abs(delta) / (T * 0.01)):  # Accept worse with probability
                    current = candidate
                    current_L = candidate_L
            
            except:
                pass
        
        # Update global best
        if best_run_L < best_global_L:
            best_global = best_run.copy()
            best_global_L = best_run_L
    
    if best_global_L < pg.side(p_base) - 1e-12:
        wins[n] = best_global
        print(f"  ★★ n={n}: WIN!")

if wins:
    np.savez_compressed(f"output/temperature_wins_{len(wins)}.npz",
                       **{str(k): v for k, v in wins.items()})
    df_new = df.copy()
    for n, packing in wins.items():
        df_new.loc[df_new['n'] == n, ['x', 'y', 'angle']] = packing
    from src.tools.reference_sources.official_metric import score
    s = score(df_new, 'id', 'n')
    df_new.to_csv(f"output/submission_{s:.6f}.csv", index=False)
    print(f"\n✓ BREAKTHROUGH 2: Score {s:.12f}, {len(wins)} wins")
